---
phase: 05-explorer-sub-agent
plan: 02
type: execute
wave: 2
depends_on:
  - "05-01"
files_modified:
  - backend/services/explorer_service.py
  - backend/tests/test_explorer_service.py
  - backend/tests/test_explorer_tools.py
autonomous: true
requirements:
  - EXPL-01
  - EXPL-05
  - EXPL-06
must_haves:
  truths:
    - "Explorer can run a multi-step KB tool-use loop using the existing kb_tools_service functions"
    - "Explorer enforces three budget axes (iterations, tool calls, summary chars) and never exceeds them"
    - "Explorer returns a Pydantic-validated ExplorerResult, never raw transcript"
    - "Explorer yields sub_event dicts during execution so the parent router can stream progress"
  artifacts:
    - path: backend/services/explorer_service.py
      provides: "run_exploration() generator + tool dispatcher + structured-output helper"
      min_lines: 200
      contains: "def run_exploration("
    - path: backend/tests/test_explorer_service.py
      provides: "Activated unit tests (no longer skipped) for tool loop, budget, summary"
      contains: "def test_multi_step_loop"
  key_links:
    - from: backend/services/explorer_service.py
      to: backend/services/kb_tools_service.py
      via: "direct function imports — kb_ls, kb_tree, kb_read, kb_grep, kb_glob"
      pattern: "from services.kb_tools_service import"
    - from: backend/services/explorer_service.py
      to: backend/models/schemas.py
      via: "ExplorerResult Pydantic model for structured output"
      pattern: "from models.schemas import ExplorerResult"
    - from: backend/services/explorer_service.py
      to: backend/config.py
      via: "Settings.explorer_max_iterations / max_tool_calls / max_summary_chars / timeout"
      pattern: "settings.explorer_max_iterations"
---

<objective>
Implement the explorer sub-agent service: a generator function that runs a tool-use loop over the existing Phase 3 KB tools, enforces three budget axes, and yields progress events for SSE streaming. This is the heart of Phase 5.

Purpose: The explorer is the only new behavior in this phase — Plans 03-04 are wiring. Without this service, there is nothing to wire.

Output:
- `backend/services/explorer_service.py` with `run_exploration(user_id, query, mode)` generator yielding `sub_iteration`, `sub_tool_start`, `sub_tool_result`, `result` events
- `_execute_explorer_tool()` dispatcher reusing kb_tools_service functions unchanged
- `_summarize_findings()` helper using `response_format={"type":"json_schema",...}` with json_object + regex fallbacks (Pitfall 4)
- EXPLORER_TOOL_SCHEMAS list (not duplicated — imports KB_*_TOOL constants from chat router)
- Activated tests in `test_explorer_service.py` and `test_explorer_tools.py` (skip markers removed where Plan 02 covers)
</objective>

<execution_context>
@.claude/get-shit-done/workflows/execute-plan.md
@.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/05-explorer-sub-agent/05-RESEARCH.md
@.planning/phases/05-explorer-sub-agent/05-VALIDATION.md
@.planning/phases/05-explorer-sub-agent/05-01-SUMMARY.md
@backend/services/subagent_service.py
@backend/services/kb_tools_service.py
@backend/services/llm_service.py
@backend/routers/chat.py
@backend/config.py
@backend/models/schemas.py

<interfaces>
<!-- Contracts the executor builds against -->

ExplorerResult (from Plan 01, in models.schemas):
```python
class ExplorerFinding(BaseModel):
    title: str = Field(max_length=120)
    path: str | None = None
    excerpt: str = Field(max_length=500)
    relevance: str = Field(max_length=200)

class ExplorerResult(BaseModel):
    mode: str = Field(pattern="^(deep_search|summarize|find_similar)$")
    query: str
    findings: list[ExplorerFinding] = Field(default_factory=list, max_length=8)
    synthesis: str = Field(max_length=2000)
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0
    budget_exhausted: bool = False
```

KB tool constants in backend/routers/chat.py (import these — do NOT duplicate):
- KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL

KB tool functions in backend/services/kb_tools_service.py:
- kb_ls(user_id, path) -> str
- kb_tree(user_id, path="", depth=2) -> str
- kb_read(user_id, path, lines=None) -> str
- kb_grep(user_id, pattern, mode="keyword", path=None) -> str
- kb_glob(user_id, pattern) -> str

LLM client (backend/services/llm_service.py):
- get_llm_client() -> openai.OpenAI  (already wraps with langsmith if configured)

LangSmith pattern (backend/services/subagent_service.py:7-13):
```python
try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f
```

Sub-event payload shapes (consumed by Plan 03 in chat.py event_generator):
```python
{"type": "sub_iteration", "iteration": int}
{"type": "sub_tool_start", "call_id": str, "tool": str, "args_preview": str}
{"type": "sub_tool_result", "call_id": str, "tool": str, "output": str}  # output clipped to 1000 chars
{"type": "result", "result": <ExplorerResult.model_dump() dict>}  # FINAL yield
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement explorer_service.py — tool loop, dispatcher, structured-output helper</name>
  <read_first>
    - backend/services/subagent_service.py (full — pattern to mirror)
    - backend/services/kb_tools_service.py (lines 1-50, 145-230 — verify function signatures)
    - backend/routers/chat.py (lines 138-265 — KB_*_TOOL constants to import)
    - backend/routers/chat.py (lines 484-566 — parent tool-use loop pattern)
    - backend/services/llm_service.py (full — get_llm_client signature)
    - backend/config.py (after Plan 01 — verify explorer_* fields present)
    - backend/models/schemas.py (after Plan 01 — verify ExplorerResult shape)
    - .planning/phases/05-explorer-sub-agent/05-RESEARCH.md (lines 113-318 — Pattern 1 reference implementation; lines 412-462 — pitfalls)
  </read_first>
  <files>
    - backend/services/explorer_service.py
  </files>
  <behavior>
    - `run_exploration(user_id, query, mode)` is a sync generator (matches existing chat.py pattern)
    - First yield is always `{"type": "sub_iteration", "iteration": 1}`
    - For each tool the model wants to call, yields `{"type": "sub_tool_start", ...}` BEFORE executing and `{"type": "sub_tool_result", ...}` AFTER
    - Final yield is always `{"type": "result", "result": <dict>}` — even on failure (with budget_exhausted=True or fallback synthesis)
    - Iteration cap (`explorer_max_iterations`) checked at TOP of loop body — model can stop voluntarily before
    - Tool-call cap (`explorer_max_tool_calls`) checked BEFORE each tool execution; on hit sets budget_exhausted=True and breaks
    - Tool result CLIPPED to 4000 chars before appending to messages list (Pitfall 1)
    - Sub_tool_result event CLIPPED to 1000 chars (sent over SSE; full result still in LLM context)
    - Unknown tool name returns `{"tool": fn_name, "error": "Unknown tool: ..."}` JSON, never raises
    - Tool exceptions caught and returned as `{"tool": fn_name, "error": str(e)}` JSON
    - Final summary tries `response_format={"type":"json_schema", ...}` first; on Exception falls back to `{"type":"json_object"}` with schema in prompt; on second failure regex-extracts first {...} block; on third failure returns ExplorerResult with synthesis="Exploration failed: ..." and budget_exhausted=True
    - `tools_used`, `iterations`, `budget_exhausted` overwrite whatever the LLM put in the JSON (server is authoritative for metadata)
    - `_explorer_tool_schemas()` returns exactly 5 schemas for the KB tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob) — lazy import avoids circular dependency with routers.chat
  </behavior>
  <action>
    Create `backend/services/explorer_service.py`:

    ```python
    """Explorer sub-agent: multi-step KB traversal via a tool-use loop.

    Spawned by the parent chat agent via the `explore_kb` tool (registered in
    backend/routers/chat.py in Plan 03). Reuses the Phase 3 KB tool functions
    unchanged. Returns an ExplorerResult Pydantic model — never the raw transcript.

    `run_exploration` is a SYNC generator that yields progress events; the parent
    router converts each yield to an SSE `tool_event` with `type=sub_event`.
    """
    import json
    import logging
    import re
    from typing import Iterator

    from config import get_settings
    from models.schemas import ExplorerResult, ExplorerFinding
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

        1) response_format=json_schema   (preferred — strict)
        2) response_format=json_object   (loose — schema in prompt)
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

            # Voluntary stop — no more tool calls
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
    ```
  </action>
  <acceptance_criteria>
    - `backend/services/explorer_service.py` exists and is ≥200 lines
    - `grep -n "def run_exploration" backend/services/explorer_service.py` returns a match
    - `grep -n "def _execute_explorer_tool" backend/services/explorer_service.py` returns a match
    - `grep -n "def _summarize_findings" backend/services/explorer_service.py` returns a match
    - `grep -n "@traceable(name=\"subagent_explorer\")" backend/services/explorer_service.py` returns a match
    - `grep -n "from services.kb_tools_service import" backend/services/explorer_service.py` returns a match (reuses Phase 3)
    - `grep -n "from models.schemas import ExplorerResult" backend/services/explorer_service.py` returns a match
    - `grep -n "explorer_max_iterations" backend/services/explorer_service.py` returns a match
    - `grep -n "explorer_max_tool_calls" backend/services/explorer_service.py` returns a match
    - `grep -n "json_schema" backend/services/explorer_service.py` returns a match (structured output tier 1)
    - `grep -n "json_object" backend/services/explorer_service.py` returns a match (structured output tier 2)
    - `grep -n "SUBAGENT_TOOL_RESULT_CLIP_CHARS" backend/services/explorer_service.py` returns a match
    - Structural: generator function typed correctly — `cd backend && venv/Scripts/python -c "from services.explorer_service import run_exploration; import inspect; assert inspect.isgeneratorfunction(run_exploration)"` exits 0
    - Schema-import check (proves lazy circular import resolves): `cd backend && venv/Scripts/python -c "from services.explorer_service import _explorer_tool_schemas; s = _explorer_tool_schemas(); assert len(s) == 5; names = [t['function']['name'] for t in s]; assert set(names) == {'kb_ls','kb_tree','kb_grep','kb_glob','kb_read'}; print('OK')"` exits 0
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -c "from services.explorer_service import run_exploration, _execute_explorer_tool, _summarize_findings, _explorer_tool_schemas; import inspect; assert inspect.isgeneratorfunction(run_exploration); schemas = _explorer_tool_schemas(); assert len(schemas) == 5; names = {t['function']['name'] for t in schemas}; assert names == {'kb_ls','kb_tree','kb_grep','kb_glob','kb_read'}, names; print('OK')"</automated>
  </verify>
  <done>
    explorer_service.py importable, generator function correctly typed, lazy circular import between explorer_service and routers.chat resolves cleanly (all 5 KB tool schemas reachable), three budget axes wired to Settings, structured-output helper has three fallback tiers, KB tool functions reused from kb_tools_service.py without duplication.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Activate explorer unit tests — multi-step loop, tool dispatch, budget enforcement</name>
  <read_first>
    - backend/services/explorer_service.py (after Task 1)
    - backend/tests/test_explorer_service.py (Plan 01 scaffold)
    - backend/tests/test_explorer_tools.py (Plan 01 scaffold)
    - backend/tests/fixtures/explorer_fixtures.py (Plan 01 — EXPLORER_SCENARIOS, mock_llm_client, make_response)
    - backend/config.py (after Plan 01 — so you know every field Settings exposes; the budget tests must construct a fake_settings MagicMock covering all fields the explorer reads)
  </read_first>
  <files>
    - backend/tests/test_explorer_service.py
    - backend/tests/test_explorer_tools.py
  </files>
  <behavior>
    - test_multi_step_loop: drives `run_exploration` with EXPLORER_SCENARIOS["summarize_catan"], asserts ≥2 sub_tool_start events + 1 result event with non-empty synthesis
    - test_tool_dispatch: directly invokes `_execute_explorer_tool` for all 5 KB tools (with mocked kb_* functions returning sentinel strings), asserts each returns parseable JSON with the sentinel
    - test_iteration_budget: patches `services.explorer_service.get_settings` with a fake_settings MagicMock (explorer_max_iterations=2), drives with budget_exhaustion_loop scenario, asserts exactly 2 iterations + budget_exhausted=True
    - test_tool_call_budget: patches `services.explorer_service.get_settings` with a fake_settings MagicMock (explorer_max_tool_calls=1), drives with scenario where iteration 1 returns 3 tool calls, asserts only first executes + budget_exhausted=True
    - test_summarize_mode: drives with `mode="summarize"`, asserts result.mode=="summarize" and synthesis non-empty
    - test_dispatch_kb_ls/tree/read/grep/glob: each patches the corresponding `services.explorer_service.kb_*` symbol with a sentinel, calls `_execute_explorer_tool`, asserts JSON contains sentinel
    - test_tool_dispatch_unknown_returns_error_json: passes "kb_bogus", asserts JSON contains "Unknown tool"
    - test_rls_isolation: calls `_execute_explorer_tool("kb_ls", {"path": "Board Games"}, user_id="user_a")` and `..."user_b")` against patched kb_ls; asserts user_id is forwarded unchanged on each call (kb_ls already enforces RLS — we verify the explorer doesn't strip/replace user_id)
  </behavior>
  <action>
    1) In `backend/tests/test_explorer_service.py`:
       - REMOVE the `@pytest.mark.skip` marker from: test_multi_step_loop, test_tool_dispatch, test_summarize_mode, test_iteration_budget, test_tool_call_budget, test_rls_isolation. Keep skips on test_find_similar_mode and test_recommendation_seed (those land in Plan 03).
       - Replace the `pass` body of each unskipped test with the implementation below. Keep imports + contract tests intact.

       **Critical fixture pattern for budget tests (B1 fix):** Do NOT use `monkeypatch.setenv(...) + get_settings.cache_clear()` — pydantic-settings auto-mapping of field_name -> ENV_VAR is not guaranteed by the current `Settings` class (no explicit env prefix/alias), so env-var round-trips may silently fall back to defaults and give false-positive passes. Instead, patch `services.explorer_service.get_settings` directly with a MagicMock that matches the full Settings surface the explorer reads. Add this helper at the top of the test file (just below imports):

       ```python
       def _make_fake_settings(**overrides):
           """Build a MagicMock matching every Settings field explorer_service reads.

           Override only what the test cares about; defaults mirror production.
           Keep this list in sync with backend/config.py whenever new explorer_* or
           llm_* fields are added.
           """
           from config import get_settings as _real_get_settings
           real = _real_get_settings()
           fake = MagicMock()
           fake.explorer_max_iterations = overrides.get("explorer_max_iterations", 6)
           fake.explorer_max_tool_calls = overrides.get("explorer_max_tool_calls", 10)
           fake.explorer_max_summary_chars = overrides.get("explorer_max_summary_chars", 3000)
           fake.explorer_timeout = overrides.get("explorer_timeout", 120)
           fake.explorer_system_prompt = overrides.get(
               "explorer_system_prompt", real.explorer_system_prompt
           )
           fake.llm_model = overrides.get("llm_model", real.llm_model or "gpt-4o-mini")
           return fake
       ```

       Then implement the tests:

       ```python
       def test_multi_step_loop():
           """EXPL-01: Explorer drives a multi-turn tool loop and emits a final result."""
           from services import explorer_service
           client = mock_llm_client(EXPLORER_SCENARIOS["summarize_catan"])
           with patch.object(explorer_service, "get_llm_client", return_value=client), \
                patch.object(explorer_service, "kb_tree", return_value="Catan/\n  rules.md"), \
                patch.object(explorer_service, "kb_read", return_value="Players collect resources..."):
               from services.explorer_service import run_exploration
               events = list(run_exploration(TEST_USER_ID, "Summarize Catan", "summarize"))
           tool_starts = [e for e in events if e["type"] == "sub_tool_start"]
           tool_results = [e for e in events if e["type"] == "sub_tool_result"]
           result_events = [e for e in events if e["type"] == "result"]
           assert len(tool_starts) >= 2, f"Expected >=2 tool starts, got {len(tool_starts)}"
           assert len(tool_results) >= 2
           assert len(result_events) == 1
           assert result_events[0]["result"]["synthesis"]


       def test_tool_dispatch():
           """EXPL-01: All 5 KB tools dispatched to kb_tools_service.* functions."""
           from services import explorer_service
           with patch.object(explorer_service, "kb_ls", return_value="LS_OUT") as ml, \
                patch.object(explorer_service, "kb_tree", return_value="TREE_OUT") as mt, \
                patch.object(explorer_service, "kb_read", return_value="READ_OUT") as mr, \
                patch.object(explorer_service, "kb_grep", return_value="GREP_OUT") as mg, \
                patch.object(explorer_service, "kb_glob", return_value="GLOB_OUT") as mb:
               for fn_name, fn_args, expected in [
                   ("kb_ls",   {"path": "/x"},                    "LS_OUT"),
                   ("kb_tree", {"path": "/x", "depth": 2},        "TREE_OUT"),
                   ("kb_read", {"path": "/x.md"},                 "READ_OUT"),
                   ("kb_grep", {"pattern": "p", "mode": "keyword"}, "GREP_OUT"),
                   ("kb_glob", {"pattern": "*.md"},               "GLOB_OUT"),
               ]:
                   out_json = explorer_service._execute_explorer_tool(fn_name, fn_args, TEST_USER_ID)
                   parsed = json.loads(out_json) if isinstance(out_json, str) else out_json
                   assert parsed["tool"] == fn_name
                   assert parsed["output"] == expected
           ml.assert_called_with(TEST_USER_ID, "/x")
           mt.assert_called_with(TEST_USER_ID, "/x", 2)


       def test_summarize_mode():
           """EXPL-02: mode='summarize' returns ExplorerResult with non-empty synthesis."""
           from services import explorer_service
           client = mock_llm_client(EXPLORER_SCENARIOS["summarize_catan"])
           with patch.object(explorer_service, "get_llm_client", return_value=client), \
                patch.object(explorer_service, "kb_tree", return_value="x"), \
                patch.object(explorer_service, "kb_read", return_value="y"):
               events = list(explorer_service.run_exploration(TEST_USER_ID, "Summarize Catan", "summarize"))
           result = events[-1]["result"]
           assert result["mode"] == "summarize"
           assert result["synthesis"]


       def test_iteration_budget():
           """EXPL-05: Hitting max_iterations sets budget_exhausted=True.

           NOTE: patches `services.explorer_service.get_settings` directly (not
           os.environ + cache_clear). The Settings class does not declare explicit
           env-var aliases, so relying on pydantic-settings auto-mapping here
           would silently fall back to defaults and produce a false-positive pass.
           """
           from services import explorer_service
           fake = _make_fake_settings(explorer_max_iterations=2)
           client = mock_llm_client(EXPLORER_SCENARIOS["budget_exhaustion_loop"])
           with patch.object(explorer_service, "get_settings", return_value=fake), \
                patch.object(explorer_service, "get_llm_client", return_value=client), \
                patch.object(explorer_service, "kb_ls", return_value="ok"):
               events = list(explorer_service.run_exploration(TEST_USER_ID, "test", "deep_search"))
           result = events[-1]["result"]
           iters = [e for e in events if e["type"] == "sub_iteration"]
           assert len(iters) == 2, f"Expected exactly 2 iterations, got {len(iters)}"
           assert result["budget_exhausted"] is True


       def test_tool_call_budget():
           """EXPL-05: Hitting max_tool_calls sets budget_exhausted=True.

           Same patching rationale as test_iteration_budget — patch
           `services.explorer_service.get_settings` directly.
           """
           from services import explorer_service
           from tests.fixtures.explorer_fixtures import make_tool_call, make_response
           fake = _make_fake_settings(explorer_max_tool_calls=1)
           # Iteration 1 returns 3 tool calls; only first should run
           three_calls = make_response(tool_calls=[
               make_tool_call("kb_ls", {"path": "a"}, "c1"),
               make_tool_call("kb_ls", {"path": "b"}, "c2"),
               make_tool_call("kb_ls", {"path": "c"}, "c3"),
           ])
           summary = make_response(content=json.dumps({
               "mode": "deep_search", "query": "q", "findings": [],
               "synthesis": "done", "tools_used": [], "iterations": 0, "budget_exhausted": False,
           }))
           client = mock_llm_client([three_calls, summary])
           with patch.object(explorer_service, "get_settings", return_value=fake), \
                patch.object(explorer_service, "get_llm_client", return_value=client), \
                patch.object(explorer_service, "kb_ls", return_value="ok"):
               events = list(explorer_service.run_exploration(TEST_USER_ID, "test", "deep_search"))
           tool_starts = [e for e in events if e["type"] == "sub_tool_start"]
           assert len(tool_starts) == 1, f"Expected exactly 1 tool start, got {len(tool_starts)}"
           assert events[-1]["result"]["budget_exhausted"] is True


       def test_rls_isolation():
           """All EXPL: explorer forwards user_id verbatim to kb tools (no swap, no strip)."""
           from services import explorer_service
           seen = []
           def fake_ls(uid, path):
               seen.append(uid)
               return "ok"
           with patch.object(explorer_service, "kb_ls", side_effect=fake_ls):
               explorer_service._execute_explorer_tool("kb_ls", {"path": "/x"}, "user_a")
               explorer_service._execute_explorer_tool("kb_ls", {"path": "/x"}, "user_b")
           assert seen == ["user_a", "user_b"]
       ```

       Add `import json` and `from unittest.mock import patch, MagicMock` at top if not already present.

    2) In `backend/tests/test_explorer_tools.py`:
       - REMOVE skip markers on all 6 tests; replace bodies:
       ```python
       import json
       from unittest.mock import patch
       from tests.fixtures.explorer_fixtures import TEST_USER_ID

       def _dispatch(fn_name, fn_args, **patches):
           from services import explorer_service
           with patch.multiple(explorer_service, **patches):
               return explorer_service._execute_explorer_tool(fn_name, fn_args, TEST_USER_ID)

       def test_dispatch_kb_ls():
           out = _dispatch("kb_ls", {"path": "/p"}, kb_ls=lambda u, p: "LS_SENTINEL")
           assert json.loads(out) == {"tool": "kb_ls", "output": "LS_SENTINEL"}

       def test_dispatch_kb_tree():
           out = _dispatch("kb_tree", {"path": "/p", "depth": 3},
                           kb_tree=lambda u, p, d: f"TREE_{d}")
           assert json.loads(out)["output"] == "TREE_3"

       def test_dispatch_kb_read():
           out = _dispatch("kb_read", {"path": "/p.md", "lines": "1-10"},
                           kb_read=lambda u, p, lines=None: f"READ_{lines}")
           assert json.loads(out)["output"] == "READ_1-10"

       def test_dispatch_kb_grep():
           out = _dispatch("kb_grep", {"pattern": "x", "mode": "regex", "path": "/p"},
                           kb_grep=lambda u, pattern, mode="keyword", path=None: f"GREP_{mode}_{path}")
           assert json.loads(out)["output"] == "GREP_regex_/p"

       def test_dispatch_kb_glob():
           out = _dispatch("kb_glob", {"pattern": "**/*.md"},
                           kb_glob=lambda u, pattern: f"GLOB_{pattern}")
           assert json.loads(out)["output"] == "GLOB_**/*.md"

       def test_tool_dispatch_unknown_returns_error_json():
           from services import explorer_service
           out = explorer_service._execute_explorer_tool("kb_bogus", {}, TEST_USER_ID)
           parsed = json.loads(out)
           assert "error" in parsed
           assert "Unknown tool" in parsed["error"]
       ```
  </action>
  <acceptance_criteria>
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q -k "not find_similar and not recommendation_seed"` exits 0
    - `cd backend && venv/Scripts/python -m pytest tests/test_explorer_tools.py -q` exits 0
    - `grep -c "@pytest.mark.skip" backend/tests/test_explorer_service.py` returns 2 or fewer (only Plan 03 tests still skipped)
    - `grep -c "@pytest.mark.skip" backend/tests/test_explorer_tools.py` returns 0 (all activated)
    - `grep -n "test_multi_step_loop" backend/tests/test_explorer_service.py` returns a match (and it's NOT marked skip — verify with `grep -B 1 "def test_multi_step_loop" backend/tests/test_explorer_service.py | grep -c skip` returning 0)
    - `grep -n "test_iteration_budget" backend/tests/test_explorer_service.py` returns a match
    - `grep -n "test_tool_call_budget" backend/tests/test_explorer_service.py` returns a match
    - Budget tests patch get_settings directly (B1 fix): `grep -n 'patch.object(explorer_service, "get_settings"' backend/tests/test_explorer_service.py` returns at least 2 matches
    - Budget tests do NOT rely on env-var round-tripping: `grep -n "monkeypatch.setenv" backend/tests/test_explorer_service.py` returns 0 matches
  </acceptance_criteria>
  <verify>
    <automated>cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_tools.py -q -k "not find_similar and not recommendation_seed"</automated>
  </verify>
  <done>
    Tool loop, dispatch, and both budget caps verified by passing tests; budget tests patch `services.explorer_service.get_settings` directly (no env-var round-trip); only the two Plan-03-owned tests remain skipped; full explorer-service test file green.
  </done>
</task>

</tasks>

<verification>
- `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_tools.py -q -k "not find_similar and not recommendation_seed"` returns 0 exit code, ≥10 tests passing
- explorer_service.py imports cleanly with no missing dependencies
- run_exploration is a generator function (verified via `inspect.isgeneratorfunction`)
- `_explorer_tool_schemas()` returns all 5 KB schemas (verified at Task 1 — proves the lazy circular import resolves)
- The three Pitfall mitigations are in code: Pitfall 1 (clipping), Pitfall 4 (3-tier structured output), Pitfall 5 (top-of-loop iteration check + voluntary stop)
</verification>

<success_criteria>
- Phase success criteria #5 (output stays within budget) ENFORCED by Pydantic + iteration/tool-call caps
- EXPL-01 (multi-step traversal) and EXPL-05 (budget) PROVABLY met by automated tests (budgets verified via direct get_settings patching, not env-var round-tripping)
- EXPL-06 (SSE streaming) PARTIALLY met — generator yields well-shaped sub_event dicts; Plan 03 wires them to SSE
- Explorer NEVER raises uncaught exceptions; always returns an ExplorerResult (success or fallback)
</success_criteria>

<output>
After completion, create `.planning/phases/05-explorer-sub-agent/05-02-SUMMARY.md` documenting:
- Final shape of the sub_event dicts (so Plan 03 knows what to translate to SSE)
- Where each pitfall mitigation lives (line ranges)
- Test coverage matrix: which EXPL-* requirement each passing test verifies
- `_make_fake_settings` helper signature (so Plan 03 can reuse if needed)
- Any deviations from the research-recommended pattern, with rationale
</output>
</output>
