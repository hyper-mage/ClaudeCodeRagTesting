"""Explorer sub-agent: multi-step KB traversal via a tool-use loop.

Spawned by the parent chat agent via the `explore_kb` tool (registered in
backend/routers/chat.py in Plan 03). Reuses the Phase 3 KB tool functions
unchanged. Returns an ExplorerResult Pydantic model -- never the raw transcript.

`run_exploration` is a SYNC generator that yields progress events; the parent
router converts each yield to an SSE `tool_event` with `type=sub_event`.
"""
import json
import logging
from typing import Iterator

from config import get_settings
from models.schemas import ExplorerResult
from services.llm_service import get_llm_client
from services.kb_tools_service import kb_ls, kb_tree, kb_read, kb_grep, kb_glob

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

logger = logging.getLogger(__name__)

SUBAGENT_TOOL_RESULT_CLIP_CHARS = 4000   # what we append to LLM messages
SUBAGENT_SSE_OUTPUT_CLIP_CHARS = 1000    # what we send over SSE

# Mode-specific guidance appended to the system prompt for steering.
MODE_HINTS = {
    "deep_search": "Cast a wide net first (kb_tree -> kb_grep), then narrow by reading the most relevant files.",
    "summarize":   "Use kb_tree on the target folder, then kb_read each direct child. Synthesize a coherent overview.",
    "find_similar": "kb_grep on mechanic keywords from the seed game, then kb_ls candidate folders, then kb_read sparingly.",
}


def _build_args_preview(fn_args: dict) -> str:
    """Same convention as chat.py:_build_args_preview."""
    parts = []
    for k, v in fn_args.items():
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        else:
            parts.append(f"{k}={v}")
    return " ".join(parts)[:200]


def _explorer_tool_schemas() -> list[dict]:
    """Import the parent's KB tool schemas. Imported lazily to avoid circular import
    with backend/routers/chat.py (which will import from this module in Plan 03)."""
    from routers.chat import (
        KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL,
    )
    return [KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL]


def _execute_explorer_tool(fn_name: str, fn_args: dict, user_id: str) -> str:
    """Dispatch a KB tool call. Always returns a JSON string; never raises."""
    try:
        if fn_name == "kb_ls":
            out = kb_ls(user_id, fn_args["path"])
            return json.dumps({"tool": "kb_ls", "output": out})
        if fn_name == "kb_tree":
            out = kb_tree(user_id, fn_args.get("path", ""), fn_args.get("depth", 2))
            return json.dumps({"tool": "kb_tree", "output": out})
        if fn_name == "kb_read":
            out = kb_read(user_id, fn_args["path"], fn_args.get("lines"))
            return json.dumps({"tool": "kb_read", "output": out})
        if fn_name == "kb_grep":
            out = kb_grep(
                user_id,
                fn_args["pattern"],
                fn_args.get("mode", "keyword"),
                fn_args.get("path"),
            )
            return json.dumps({"tool": "kb_grep", "output": out})
        if fn_name == "kb_glob":
            out = kb_glob(user_id, fn_args["pattern"])
            return json.dumps({"tool": "kb_glob", "output": out})
        return json.dumps({"tool": fn_name, "error": f"Unknown tool: {fn_name}"})
    except KeyError as e:
        return json.dumps({"tool": fn_name, "error": f"Missing required argument: {e}"})
    except Exception as e:
        logger.error(f"Explorer tool {fn_name} failed: {e}", exc_info=True)
        return json.dumps({"tool": fn_name, "error": str(e)})


def _extract_json_blob(text: str) -> str | None:
    """Best-effort: pull the first balanced {...} block from text."""
    if not text:
        return None
    # Greedy first-{ to last-} works for well-formed single-object responses.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1]


def _summarize_findings(
    client,
    settings,
    messages: list[dict],
    query: str,
    mode: str,
    tools_used: list[str],
    iterations: int,
    budget_exhausted: bool,
) -> ExplorerResult:
    """Final structured-output call with three-tier fallback.

    1) response_format=json_schema   (preferred -- strict)
    2) response_format=json_object   (loose -- schema in prompt)
    3) regex extract {...} block from plain text
    """
    schema = ExplorerResult.model_json_schema()
    summary_user = {
        "role": "user",
        "content": (
            "Now produce your final structured result as JSON matching this schema:\n"
            f"{json.dumps(schema)}\n\n"
            f"- mode: {mode}\n"
            f"- query: {query!r}\n"
            "- Fill `findings` with the most relevant excerpts (max 8).\n"
            "- Write `synthesis` as a direct, concise answer to the original task. "
            f"Stay under {settings.explorer_max_summary_chars} chars."
        ),
    }
    summary_messages = messages + [summary_user]

    def _try(model_kwargs):
        return client.chat.completions.create(
            model=settings.llm_model,
            messages=summary_messages,
            timeout=settings.explorer_timeout,
            **model_kwargs,
        )

    # Tier 1: json_schema
    try:
        response = _try({
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ExplorerResult",
                    "strict": True,
                    "schema": schema,
                },
            },
        })
        content = (response.choices[0].message.content or "").strip()
        if content:
            parsed = ExplorerResult.model_validate_json(content)
            parsed.tools_used = tools_used
            parsed.iterations = iterations
            parsed.budget_exhausted = budget_exhausted
            return parsed
    except Exception as e:
        logger.warning(f"json_schema summary failed, falling back to json_object: {e}")

    # Tier 2: json_object
    try:
        response = _try({"response_format": {"type": "json_object"}})
        content = (response.choices[0].message.content or "").strip()
        if content:
            parsed = ExplorerResult.model_validate_json(content)
            parsed.tools_used = tools_used
            parsed.iterations = iterations
            parsed.budget_exhausted = budget_exhausted
            return parsed
    except Exception as e:
        logger.warning(f"json_object summary failed, falling back to regex extract: {e}")

    # Tier 3: regex extract
    try:
        response = _try({})
        content = (response.choices[0].message.content or "").strip()
        blob = _extract_json_blob(content)
        if blob:
            parsed = ExplorerResult.model_validate_json(blob)
            parsed.tools_used = tools_used
            parsed.iterations = iterations
            parsed.budget_exhausted = budget_exhausted
            return parsed
    except Exception as e:
        logger.error(f"Regex-extract summary failed: {e}", exc_info=True)

    # Final fallback: refusal/empty handling (Pitfall 7)
    return ExplorerResult(
        mode=mode,
        query=query,
        findings=[],
        synthesis=f"The explorer could not produce a structured summary. Tools used: {tools_used}",
        tools_used=tools_used,
        iterations=iterations,
        budget_exhausted=True,
    )


@traceable(name="subagent_explorer")
def run_exploration(user_id: str, query: str, mode: str = "deep_search") -> Iterator[dict]:
    """Run the explorer sub-agent. Yields progress events; the LAST yield is
    {"type": "result", "result": <ExplorerResult dict>}.

    Yields:
      {"type": "sub_iteration", "iteration": N}
      {"type": "sub_tool_start", "call_id": str, "tool": str, "args_preview": str}
      {"type": "sub_tool_result", "call_id": str, "tool": str, "output": str}  # clipped
      {"type": "result", "result": dict}                                       # final
    """
    if mode not in ("deep_search", "summarize", "find_similar"):
        mode = "deep_search"

    settings = get_settings()
    client = get_llm_client()
    tool_schemas = _explorer_tool_schemas()

    system_prompt = settings.explorer_system_prompt + "\n\n" + MODE_HINTS.get(mode, "")
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Mode: {mode}\nTask: {query}"},
    ]

    tools_used: list[str] = []
    tool_call_count = 0
    iteration = 0
    budget_exhausted = False

    while iteration < settings.explorer_max_iterations:
        iteration += 1
        yield {"type": "sub_iteration", "iteration": iteration}

        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                tools=tool_schemas,
                timeout=settings.explorer_timeout,
            )
        except Exception as e:
            logger.error(f"Explorer LLM call failed at iteration {iteration}: {e}", exc_info=True)
            budget_exhausted = True
            break

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)

        # Voluntary stop -- no more tool calls
        if not tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            break

        # Append assistant turn with tool calls
        messages.append({
            "role": "assistant",
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })

        for tc in tool_calls:
            if tool_call_count >= settings.explorer_max_tool_calls:
                budget_exhausted = True
                break
            tool_call_count += 1

            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                fn_args = {}
            tools_used.append(fn_name)

            yield {
                "type": "sub_tool_start",
                "call_id": tc.id,
                "tool": fn_name,
                "args_preview": _build_args_preview(fn_args),
            }

            tool_result = _execute_explorer_tool(fn_name, fn_args, user_id)

            # Clip what we feed back into messages (Pitfall 1)
            clipped_for_llm = tool_result
            if len(clipped_for_llm) > SUBAGENT_TOOL_RESULT_CLIP_CHARS:
                clipped_for_llm = (
                    clipped_for_llm[:SUBAGENT_TOOL_RESULT_CLIP_CHARS]
                    + f'\n[... clipped at {SUBAGENT_TOOL_RESULT_CLIP_CHARS} chars]'
                )

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": clipped_for_llm,
            })

            yield {
                "type": "sub_tool_result",
                "call_id": tc.id,
                "tool": fn_name,
                "output": tool_result[:SUBAGENT_SSE_OUTPUT_CLIP_CHARS],
            }

        if budget_exhausted:
            break

    # Iteration cap reached without voluntary stop -> mark exhausted
    if iteration >= settings.explorer_max_iterations and not budget_exhausted:
        # If the final iteration produced no voluntary break, treat as exhausted.
        # (If the model DID stop voluntarily we already break-ed out above.)
        last = messages[-1] if messages else {}
        if last.get("role") != "assistant" or last.get("tool_calls"):
            budget_exhausted = True

    try:
        result = _summarize_findings(
            client, settings, messages, query, mode,
            tools_used, iteration, budget_exhausted,
        )
    except Exception as e:
        logger.error(f"Explorer summary phase crashed: {e}", exc_info=True)
        result = ExplorerResult(
            mode=mode, query=query, findings=[],
            synthesis=f"Exploration failed during summary: {e}",
            tools_used=tools_used, iterations=iteration, budget_exhausted=True,
        )

    yield {"type": "result", "result": result.model_dump()}
