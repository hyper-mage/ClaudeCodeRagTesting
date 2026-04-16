# Phase 5: Explorer Sub-Agent - Research

**Researched:** 2026-04-15
**Domain:** Multi-turn agentic sub-agent pattern over OpenAI function-calling, nested SSE protocol, context budget enforcement, Supabase-scoped KB traversal
**Confidence:** HIGH

## Summary

Phase 5 adds an Explorer sub-agent that runs a nested tool-use loop over the existing Phase 3 KB tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob). The parent chat agent invokes it via a new `explore_kb` tool (following the existing `analyze_document` sub-agent pattern in `subagent_service.py`). The explorer has its own tiny system prompt, its own message history (isolated from parent), its own budget, and reuses the exact same KB tool functions the parent uses. On completion, it returns a compact Pydantic-validated `ExplorerResult` summary — not the raw transcript — so the parent's context stays lean.

Key architectural insight: this is not a new endpoint, not a new SSE channel, and not a fork of the tool implementations. It's a new service (`explorer_service.py`) that exposes one function (`run_exploration`), called from `execute_tool()` in `chat.py` exactly like `run_document_analysis`. Progress streaming is piggybacked on the parent's SSE stream by making `run_exploration` a generator (or using a callback) that emits `tool_event` events with a `subagent: true, phase: "explorer"` marker — the same marker the frontend already understands for `analyze_document`. The ToolCallCard component already renders subagent events with indigo styling.

Budget enforcement is three-dimensional: max iterations (hard stop on tool-use loop count), max tool calls (distinct from iterations since one iteration can have multiple parallel tool calls), and token-accounted context size (measured via LLM response usage field). Exhaustion produces a graceful summary from whatever has been gathered so far with a `budget_exhausted: true` flag.

**Primary recommendation:** Build `explorer_service.py` modeled on `subagent_service.py` but with a tool-use loop (not single-shot). Expose one new tool `explore_kb` with three modes encoded by the parent in the query text (search, summarize_folder, find_similar). Stream progress through the parent's existing SSE channel using `tool_event` events tagged `subagent: true` with a nested `sub_event` field (`sub_tool_start`, `sub_tool_result`, `sub_iteration`). Return a Pydantic `ExplorerResult` with a bounded `findings` list. Use LangSmith `@traceable(name="subagent_explorer")` to get nested tracing for free.

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 5 at research time. This phase was spawned directly into research; discussion/context gathering has not yet been performed. The research below documents Claude's recommendations for all design decisions. The planner or the user during `/gsd:discuss-phase` will need to lock these choices.

### Locked Decisions
*(none — pending discussion)*

### Claude's Discretion
*(full discretion — pending discussion)*

### Deferred Ideas (OUT OF SCOPE)
From REQUIREMENTS.md, explicitly in v2 (not this phase):
- **EXPL-07:** Side-by-side comparison of rules/mechanics across games
- **EXPL-08:** Game profiles built from ingested content for quick reference

The planner MUST reject any task that expands scope beyond EXPL-01 through EXPL-06.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXPL-01 | Explorer can perform multi-step KB traversal using all navigation tools (ls, tree, read, grep, glob) | Sub-agent tool-use loop reuses Phase 3 `kb_tools_service` functions unchanged. OpenAI function-calling protocol is the same shape; only the system prompt and loop host differ. |
| EXPL-02 | Explorer can generate summaries of folder contents on request | Dedicated operation mode. Explorer's planner prompts it to call kb_tree + kb_ls + selective kb_read, then produce a structured synthesis bounded by `max_summary_chars`. |
| EXPL-03 | Explorer can discover cross-references between games (e.g., similar mechanics) | Combined embedding + keyword lookup. First: `search_documents` on the source game's description to get seed. Then: kb_grep on mechanic keywords pulled from the seed. Finally: rank by co-occurrence. No new infrastructure — reuses existing retrieval_service. |
| EXPL-04 | Explorer can recommend related games based on the current conversation context | Parent passes the last N turns of conversation as the exploration seed query. Explorer does broad retrieval then narrows. Pattern: same as EXPL-03 but seed comes from chat history, not a named document. |
| EXPL-05 | Explorer has output budget limits so parent context isn't overwhelmed | Three knobs enforced: `explorer_max_iterations` (tool-loop count), `explorer_max_tool_calls` (cumulative), `explorer_max_summary_chars` (final return size). Enforced in Python loop before each LLM call. |
| EXPL-06 | Explorer progress is streamed to frontend via SSE | Piggyback the parent's `event_generator`. Explorer runs as an async generator yielding `sub_event` dicts; parent router converts each into an SSE `tool_event` with `subagent: true, phase: "explorer"` and existing ToolCallCard renders nested card updates. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Raw OpenAI SDK only** — no LangChain, no LangGraph. The explorer loop is a hand-written while-loop around `client.chat.completions.create(...)`, mirroring `stream_chat_completion` in `llm_service.py` and the while-loop in `chat.py:484`.
- **Python venv required** — all new deps (none expected) go in `backend/venv/`.
- **Pydantic for structured outputs** — the explorer's final `ExplorerResult` must be a Pydantic model. Use `response_format={"type": "json_schema", ...}` on the final summarization call, OR validate a JSON-mode response with `ExplorerResult.model_validate_json()`.
- **RLS respected** — explorer runs under the user's `user_id` (passed through from the parent chat call). Every KB tool call already scopes to `user_id` OR `visibility='public'` (see `kb_tools_service.py:199`). No new RLS work required.
- **Stateless** — explorer does NOT persist its own conversation. Only the final Pydantic summary goes back to the parent as a tool result. The sub-agent's internal message list is ephemeral, living only for the duration of the tool call.
- **Stream via SSE** — all explorer progress uses the parent's existing `sse-starlette` stream. No WebSocket, no separate endpoint, no client-to-server streaming.
- **snake_case** — service file named `explorer_service.py`, functions like `run_exploration()`, `_build_explorer_tools()`, `_summarize_findings()`.
- **Supabase-only** — all KB reads go through existing `kb_tools_service.py` functions which query Supabase. No local filesystem, no caching layer.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | 1.74.0 | Raw SDK for sub-agent tool-use loop | Already installed; the sub-agent uses `client.chat.completions.create(...)` with `tools=[...]` in a while-loop, just like the parent chat. No streaming needed inside the sub-agent — non-streaming is simpler and cheaper, since sub-agent completions are short. |
| pydantic | 2.11.1 | `ExplorerResult` schema for compact return payload | Already installed. Enforces output shape; also usable as `response_format` for structured-output calls. |
| supabase | 2.13.0 | Used transitively via existing `kb_tools_service.py` | Already installed. |
| sse-starlette | 2.2.1 | Sub-agent progress flows through parent's existing EventSourceResponse | Already installed. No new SSE infrastructure. |
| langsmith | 0.3.42 | Nested tracing via `@traceable(name="subagent_explorer")` | Already installed. LangSmith auto-nests traces when a `@traceable` function is called from within another `@traceable` context — this is free with the existing setup. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tiktoken | not installed | Token counting for context budget | **Optional.** OpenRouter responses include a `usage` object; prefer reading `response.usage.prompt_tokens` + `completion_tokens` from each sub-call and accumulating. Only install tiktoken if you need pre-call budget estimation, which is a later optimization. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New `explore_kb` tool on parent (recommended) | New `/api/threads/{id}/explore` endpoint | Separate endpoint breaks the unified tool-use UX, requires new frontend hook, violates "the agent decides when to use the explorer" principle. Tool-call approach keeps agent in the driver's seat. |
| Sub-agent calls same `kb_tools_service` functions directly (recommended) | Copy tool implementations to isolated `explorer_kb_tools.py` | Duplication; if Phase 3 tools are fixed/extended, explorer diverges. Reuse is safe because the functions are already `(user_id, ...)` pure functions with no global state. |
| Non-streaming sub-agent LLM calls (recommended) | Streaming sub-agent LLM calls | Added complexity; sub-agent output is not shown to user directly — only the final summary is. Progress is already streamed via `sub_event` emissions around each tool call. |
| JSON-mode with Pydantic validation for final summary (recommended) | Free-text summary + post-hoc parsing | Unreliable. Structured output via `response_format={"type": "json_schema", "json_schema": ExplorerResult.model_json_schema()}` has been supported by OpenRouter's OpenAI-compatible API for major models since 2024. Gracefully falls back to plain JSON mode if model refuses schema. |
| Three tool modes behind one `explore_kb` tool (recommended) | Three separate tools: `explore_search`, `summarize_folder`, `find_similar` | Parent agent's tool surface area already has 9 tools. Adding 3 more muddies tool selection. One tool with a `mode` enum ("deep_search", "summarize", "find_similar") is cleaner and the parent can learn it from one prompt example. |

**Installation:** None — all dependencies already present.

**Version verification:** Not performed (no new packages added). Existing versions already validated through prior phases.

## Architecture Patterns

### Recommended Project Structure
```
backend/
  services/
    explorer_service.py        # NEW: run_exploration(), _build_explorer_tools(), _summarize_findings()
    subagent_service.py        # EXISTING: unchanged (analyze_document still works)
    kb_tools_service.py        # EXISTING: unchanged (explorer reuses its functions)
  routers/
    chat.py                    # MODIFIED: add EXPLORE_KB_TOOL constant, dispatch in execute_tool, stream sub_events
  models/
    schemas.py                 # MODIFIED: add ExplorerResult, ExplorerFinding Pydantic models
  tests/
    test_explorer.py           # NEW: unit tests for explorer_service
    test_explorer_sse.py       # NEW: integration tests for sub_event emission
frontend/
  src/
    components/
      ToolCallCard.tsx         # MODIFIED: extend to render nested sub_event list when tool === "explore_kb"
    hooks/
      useChat.ts               # MODIFIED: parse sub_event types (sub_tool_start, sub_tool_result, sub_iteration)
```

### Pattern 1: Sub-Agent Tool-Use Loop (Recommended Core Pattern)
**What:** A while-loop inside `run_exploration()` that repeatedly calls the LLM with the same tool definitions as the parent's KB tools, executes chosen tools via `execute_tool()`-style dispatch, appends results to an isolated message list, and breaks when either (a) the model produces no tool calls, or (b) a budget is exhausted.

**When to use:** EXPL-01 (all modes converge to this loop).

**Example (structure only, not production-complete):**
```python
# Source: Pattern derived from backend/services/subagent_service.py + backend/routers/chat.py:484-566
import json
import logging
from pydantic import BaseModel, Field
from services.llm_service import get_llm_client
from services.kb_tools_service import kb_ls, kb_tree, kb_read, kb_grep, kb_glob
from config import get_settings

try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

logger = logging.getLogger(__name__)

EXPLORER_SYSTEM_PROMPT = """You are the KB Explorer — a specialist sub-agent for deep, multi-step knowledge-base traversal.

You have the KB navigation tools: kb_tree, kb_ls, kb_glob, kb_grep, kb_read.
Start with kb_tree to orient yourself. Then narrow down with kb_ls/kb_glob. Finally read only what you need.

Your goal: gather focused, well-cited evidence and return a structured summary. Do NOT return raw tool output. Do NOT exceed 5 tool calls unless essential. Stop exploring the moment you have enough to answer."""


class ExplorerFinding(BaseModel):
    title: str = Field(max_length=120)
    path: str | None = None  # KB path e.g. "Board Games/Catan/rules.md"
    excerpt: str = Field(max_length=500)
    relevance: str = Field(max_length=200)  # why this matters to the query


class ExplorerResult(BaseModel):
    mode: str  # "deep_search" | "summarize" | "find_similar"
    query: str
    findings: list[ExplorerFinding] = Field(max_length=8)  # hard cap
    synthesis: str = Field(max_length=2000)  # final prose answer
    tools_used: list[str] = []
    iterations: int = 0
    budget_exhausted: bool = False


EXPLORER_TOOL_SCHEMAS = [
    # Reuse the exact KB_*_TOOL schemas from chat.py; import or duplicate
]


def _execute_explorer_tool(fn_name: str, fn_args: dict, user_id: str) -> str:
    """Dispatch for explorer's tool calls. Parallel to execute_tool() in chat.py but KB-only."""
    try:
        if fn_name == "kb_ls":
            return json.dumps({"tool": "kb_ls", "output": kb_ls(user_id, fn_args["path"])})
        elif fn_name == "kb_tree":
            return json.dumps({"tool": "kb_tree", "output": kb_tree(
                user_id, fn_args.get("path", ""), fn_args.get("depth", 2))})
        elif fn_name == "kb_read":
            return json.dumps({"tool": "kb_read", "output": kb_read(
                user_id, fn_args["path"], fn_args.get("lines"))})
        elif fn_name == "kb_grep":
            return json.dumps({"tool": "kb_grep", "output": kb_grep(
                user_id, fn_args["pattern"], fn_args.get("mode", "keyword"), fn_args.get("path"))})
        elif fn_name == "kb_glob":
            return json.dumps({"tool": "kb_glob", "output": kb_glob(user_id, fn_args["pattern"])})
        else:
            return json.dumps({"error": f"Unknown tool: {fn_name}"})
    except Exception as e:
        logger.error(f"Explorer tool {fn_name} failed: {e}", exc_info=True)
        return json.dumps({"tool": fn_name, "error": str(e)})


@traceable(name="subagent_explorer")
def run_exploration(
    user_id: str,
    query: str,
    mode: str = "deep_search",
):
    """Run the explorer sub-agent. Yields sub_event dicts for streaming;
    the last yield is {"type": "result", "result": ExplorerResult}.
    """
    settings = get_settings()
    client = get_llm_client()

    messages = [
        {"role": "system", "content": EXPLORER_SYSTEM_PROMPT},
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
                tools=EXPLORER_TOOL_SCHEMAS,
                timeout=settings.explorer_timeout,
            )
        except Exception as e:
            logger.error(f"Explorer LLM call failed: {e}", exc_info=True)
            break

        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        # No tool calls → model wants to stop. Final synthesis call happens next.
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            break

        messages.append({
            "role": "assistant",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            if tool_call_count >= settings.explorer_max_tool_calls:
                budget_exhausted = True
                break
            tool_call_count += 1
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            tools_used.append(fn_name)

            yield {
                "type": "sub_tool_start",
                "call_id": tc.id,
                "tool": fn_name,
                "args_preview": _build_args_preview(fn_args),
            }

            result = _execute_explorer_tool(fn_name, fn_args, user_id)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

            yield {
                "type": "sub_tool_result",
                "call_id": tc.id,
                "tool": fn_name,
                "output": result[:1000],  # clipped for SSE; full goes back to LLM
            }

        if budget_exhausted:
            break

    # Final structured summary call
    try:
        result = _summarize_findings(client, settings, messages, query, mode, tools_used, iteration, budget_exhausted)
    except Exception as e:
        logger.error(f"Explorer summary failed: {e}", exc_info=True)
        result = ExplorerResult(
            mode=mode, query=query, findings=[], synthesis=f"Exploration failed: {e}",
            tools_used=tools_used, iterations=iteration, budget_exhausted=True,
        )

    yield {"type": "result", "result": result.model_dump()}


def _summarize_findings(client, settings, messages, query, mode, tools_used, iterations, budget_exhausted):
    """Final non-streaming call that returns structured ExplorerResult via JSON schema."""
    summary_messages = messages + [{
        "role": "user",
        "content": (
            "Now produce your final structured result. Fill in findings[] with the most "
            "relevant excerpts (max 8). Write synthesis as a direct, concise answer to the "
            "original task. Stay under the character caps in the schema."
        ),
    }]
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=summary_messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ExplorerResult",
                "strict": True,
                "schema": ExplorerResult.model_json_schema(),
            },
        },
        timeout=settings.explorer_timeout,
    )
    parsed = ExplorerResult.model_validate_json(response.choices[0].message.content)
    # Fill metadata the LLM can't know
    parsed.tools_used = tools_used
    parsed.iterations = iterations
    parsed.budget_exhausted = budget_exhausted
    return parsed
```

**Key insight:** `run_exploration` is a **generator**, not a coroutine that returns a value. The parent router drives it with `for event in run_exploration(...)`, emits SSE events from each yield, and treats the final `{"type": "result", ...}` yield as the tool result.

### Pattern 2: SSE Nesting via Existing `tool_event` Channel
**What:** Do NOT invent a new SSE event name. The existing `tool_event` channel already carries a `subagent` flag (see `chat.py:530-531`, rendered in `ToolCallCard.tsx:45` as indigo styling). Extend the payload shape with a nested `sub_event` field.

**When to use:** EXPL-06.

**Payload shape:**
```jsonc
// parent tool_start
{ "tool_event": true, "type": "tool_start", "tool": "explore_kb", "subagent": true, "call_id": "call_abc", "args_preview": "mode=\"deep_search\" query=\"...\"" }

// each sub-iteration / sub-tool
{ "tool_event": true, "type": "sub_event", "subagent": true, "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_tool_start", "call_id": "call_xyz", "tool": "kb_tree", "args_preview": "depth=2" } }

{ "tool_event": true, "type": "sub_event", "subagent": true, "parent_call_id": "call_abc",
  "sub_event": { "type": "sub_tool_result", "call_id": "call_xyz", "tool": "kb_tree", "output": "..." } }

// parent tool_result (final summary)
{ "tool_event": true, "type": "tool_result", "tool": "explore_kb", "subagent": true, "call_id": "call_abc",
  "output": "<ExplorerResult JSON, possibly clipped for display>" }
```

**Frontend (useChat.ts) adapts by:** On a `type === "sub_event"` event, find the parent ToolCallCard by `parent_call_id` and append the sub-event to a nested list. `ToolCallCard.tsx` conditionally renders a nested block when `tool === "explore_kb"`.

### Pattern 3: Parent-Side Integration (One New Tool, Thin Dispatcher)
**What:** Add `EXPLORE_KB_TOOL` constant in `chat.py` and a new branch in `execute_tool()`. Because `run_exploration` is a generator, the dispatcher needs to consume it and emit SSE along the way. This means **dispatch logic for explore_kb lives inside `event_generator()`**, not in `execute_tool()`.

**When to use:** Wiring the tool into the parent chat loop.

**Refactor:** Introduce a dispatcher layer — most tools still go through `execute_tool()` synchronously; `explore_kb` uses a streaming dispatch path.

**Example:**
```python
# In backend/routers/chat.py event_generator(), when a tool_call for "explore_kb" is seen:
if fn_name == "explore_kb":
    from services.explorer_service import run_exploration
    tool_result_str = None
    for sub_ev in run_exploration(
        user_id=user_id,
        query=fn_args["query"],
        mode=fn_args.get("mode", "deep_search"),
    ):
        if sub_ev["type"] == "result":
            tool_result_str = json.dumps({"tool": "explore_kb", **sub_ev["result"]})
        else:
            yield {
                "event": "tool_event",
                "data": json.dumps({
                    "tool_event": True,
                    "type": "sub_event",
                    "subagent": True,
                    "parent_call_id": tc["id"],
                    "sub_event": sub_ev,
                }),
            }
    tool_result = tool_result_str or json.dumps({"tool": "explore_kb", "error": "No result produced"})
else:
    tool_result = execute_tool(fn_name, fn_args, user_id)
```

### Pattern 4: Pydantic Structured Output for Compact Return
**What:** Use the final `ExplorerResult` model both for internal validation AND as the JSON blob returned to the parent agent. The parent LLM sees a compact, schema-conformant object — not a full exploration transcript.

**When to use:** All EXPL requirements (this is how outputs come back).

**Key detail:** `ExplorerResult` has explicit character/item caps (`max_length=8` on findings, `max_length=2000` on synthesis, `max_length=500` on excerpt). Pydantic rejects oversized output — the explorer gets one retry to shrink, then falls back to truncation.

### Anti-Patterns to Avoid
- **Do NOT spawn the explorer as a separate HTTP endpoint.** Frontend already has a single-stream SSE model; a second stream would double the state-management surface area.
- **Do NOT forward the parent's full chat history into the explorer.** That defeats the purpose of isolation and blows context budget. Only pass the distilled `query` string.
- **Do NOT give the explorer the `search_documents`, `analyze_document`, `query_database`, or `web_search` tools.** It is KB-only by design (EXPL-01 is explicit about navigation tools). If the agent needs semantic search, the parent does that before calling the explorer.
- **Do NOT stream LLM text tokens from the sub-agent.** The sub-agent's intermediate reasoning is not for user display. Only tool starts/results and the final structured summary go out.
- **Do NOT persist sub-agent messages to the `messages` table.** Only the parent's `tools_used` accumulator is persisted (tagged with `subagent: true`), per the existing `analyze_document` pattern.
- **Do NOT block the main event loop with synchronous `client.chat.completions.create`.** `run_exploration` should be a plain (non-async) generator; when dispatched from `event_generator()` (an async generator), wrap the sync calls appropriately — or run the explorer in a threadpool via `asyncio.to_thread`. Inspect current chat.py: `stream_chat_completion` is a sync generator consumed inside an async `event_generator`, so the same pattern applies.
- **Do NOT hand-roll token counting by string length.** Use the OpenAI response's `usage` field. String length is a wildly inaccurate proxy.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-turn tool loop | Custom state machine | `while`-loop around `client.chat.completions.create(messages=..., tools=...)` | OpenAI SDK already handles tool-call protocol. The existing `chat.py:484-566` is the reference pattern — copy it. |
| Nested tracing | Custom trace IDs, manual span nesting | `@traceable(name="subagent_explorer")` on `run_exploration` + existing `langsmith.wrappers.wrap_openai` on the client | LangSmith auto-nests traces when a `@traceable` function is invoked inside another `@traceable` context. `chat_send_message` is already traced. Free nesting. |
| KB tool implementations | Isolated copies in the explorer | Reuse `kb_tools_service.py` functions directly | They are pure `(user_id, ...) -> str` functions. Duplication would create drift. Visibility is already enforced inside them. |
| Structured output parsing | Custom regex on LLM free-text | `response_format={"type": "json_schema", ...}` + `Pydantic.model_validate_json` | JSON-schema structured output is supported end-to-end by OpenRouter for major models; Pydantic gives validation + the `.model_json_schema()` helper feeds the API directly. |
| SSE progress events | New event name / new SSE endpoint | Reuse `tool_event` with a nested `sub_event` payload field | Frontend already handles `tool_event` + `subagent: true` (indigo styling). Incremental extension; no new plumbing. |
| Token budget tracking | Manual prompt-size estimation via `len(str(messages))` | Sum `response.usage.prompt_tokens + completion_tokens` from each sub-call | OpenRouter returns usage on every completion. String length is a terrible proxy (tokenization varies wildly). |
| Folder summarization prompt | Custom "walk this tree and summarize" scaffolding | Delegate to the LLM via the explorer's loop with `mode="summarize"` in the user message | The LLM decides whether to kb_tree+kb_ls+kb_read or just kb_read a single rules.md. Hard-coding a traversal pattern will lose to a capable model. |
| "Similar games" ranking | Custom embedding-cosine-loop | Existing `search_documents` RPC (hybrid RRF + optional rerank) + kb_grep for mechanic keywords | The retrieval pipeline already does vector+keyword RRF and reranking. Explorer just needs to call it (but it's NOT in the explorer's toolset — the *parent* should call `search_documents` to seed the explorer's query, OR the explorer includes a scoped-retrieval helper as a sixth tool — see Open Questions). |

**Key insight:** Every single explorer capability maps to an existing service or SDK primitive. This phase should be mostly plumbing, not new algorithms.

## Common Pitfalls

### Pitfall 1: Context Accumulation in Sub-Agent Message History
**What goes wrong:** Each tool result gets appended to `messages` as a `role: "tool"` entry. After 5-6 kb_read calls with large outputs, the message list exceeds the model's context window and the next `client.chat.completions.create` call errors with `context_length_exceeded`.
**Why it happens:** kb_read can return up to 200 lines of monospace text; that's easily 1500-3000 tokens per call. Five of them + system prompt + query + tool schemas = 15k+ tokens just in messages.
**How to avoid:** (a) Clip tool results before appending to sub-agent messages (e.g., 4000 chars max), with a continuation hint; (b) enforce `explorer_max_tool_calls` (recommended: 8) BEFORE token exhaustion hits; (c) on `context_length_exceeded` error, catch it, truncate the middle of the message list (keep system + first few + last few), retry once, then bail to summary.
**Warning signs:** Sub-agent silently dies with 400 errors; explorer returns "Exploration failed" with no findings.

### Pitfall 2: Tool Call Schema Drift
**What goes wrong:** The explorer's tool schemas and the parent's tool schemas diverge because they're defined in two places. Agent works in parent but fails in explorer, or vice versa.
**Why it happens:** Copy-pasting the KB_LS_TOOL etc. dicts into `explorer_service.py`.
**How to avoid:** Import them: `from routers.chat import KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL` and build `EXPLORER_TOOL_SCHEMAS = [KB_LS_TOOL, KB_TREE_TOOL, ...]`. If the circular-import risk is a concern (chat.py imports explorer_service.py), move the five KB_*_TOOL constants into `kb_tools_service.py` next to their implementations. That's the cleanest refactor and aligns with the existing "tool constants belong beside their dispatch" assumption — but that assumption already fails (all tools live in chat.py), so just do the explicit import.
**Warning signs:** "unknown tool" errors; tool_call structure differs between parent and sub trace.

### Pitfall 3: Sync-Generator-in-Async-Generator Blocking
**What goes wrong:** `event_generator()` in chat.py is an async generator. Calling `for sub_ev in run_exploration(...)` (a sync generator) inside it blocks the event loop during each LLM call, which can be 10-30 seconds. SSE heartbeats stop; client may disconnect.
**Why it happens:** The sub-agent uses synchronous `client.chat.completions.create(...)` which blocks.
**How to avoid:** Option A (simpler): run each sub-agent LLM call in `asyncio.to_thread(...)` and make `run_exploration` an async generator. Option B (matches existing pattern): the parent already does `for event in stream_chat_completion(...)` synchronously inside an async generator — this works in FastAPI/sse-starlette because the underlying HTTP transport is still chunked, but it DOES block the single worker. For the existing single-user dev setup this is fine; for production it's a known wart. Do what matches the existing code first; document the wart.
**Warning signs:** Other concurrent SSE requests appear stuck; SSE connection drops during long exploration.

### Pitfall 4: JSON-Schema Structured Output Fallback
**What goes wrong:** Not every model on OpenRouter supports `response_format={"type": "json_schema"}` — some only support `{"type": "json_object"}`, and some don't support either.
**Why it happens:** OpenRouter is a routing proxy over many providers; feature support is uneven.
**How to avoid:** Try JSON-schema first. On 400 error mentioning `response_format`, retry with `{"type": "json_object"}` and include "Respond with valid JSON matching this schema: {schema}" in the user message. On second failure, fall back to regex-extract-JSON-from-text. Log which path was used.
**Warning signs:** `ExplorerResult.model_validate_json` raises on malformed input; 400 errors from the LLM.

### Pitfall 5: Budget Enforcement Off-By-One
**What goes wrong:** Explorer loops exactly `max_iterations` times even when the model wanted to stop at iteration 3. OR: the limit is checked AFTER the call that exceeds it, wasting one call's worth of tokens.
**Why it happens:** Loop structure puts the check in the wrong place.
**How to avoid:** Two distinct checks: `if iteration >= settings.explorer_max_iterations: break` at the TOP of the loop body (enforces ceiling), and `if not msg.tool_calls: break` BEFORE appending tool results (lets the model terminate voluntarily). Test with mocked LLM returning no tool calls on iteration 2 — explorer should emit `sub_iteration=1` and `sub_iteration=2`, then stop.
**Warning signs:** Explorer always reports `iterations=max_iterations` even for simple queries.

### Pitfall 6: User-ID Bleed in Reused Tool Functions
**What goes wrong:** The explorer runs under one user's `user_id`, but if the kb_tools_service functions ever cached state at module level or used thread-locals, exploration for user A could leak to user B.
**Why it happens:** Rare but catastrophic if it happens.
**How to avoid:** Verify `kb_tools_service.py` has no module-level caches with user-scoped data. (At time of research: confirmed — only `get_supabase()` is called which returns the service-role singleton, and all queries explicitly filter by `user_id`.) Add a unit test that calls kb_ls concurrently for two user_ids and asserts no cross-visibility.
**Warning signs:** User A sees user B's private documents during exploration.

### Pitfall 7: Model Refusal / Safety-Gated Model Responses
**What goes wrong:** The model refuses to produce the requested summary (e.g., "I cannot help with that") or returns an empty `content` on the final call.
**Why it happens:** Rare with the KB domain (board games), but happens for edge-case queries.
**How to avoid:** Catch empty/refusal content in `_summarize_findings`, return an `ExplorerResult` with a synthesis of `"The explorer could not produce a summary. Tools used: {tools_used}. See raw findings."` and `findings=[]`, and bubble that up. Never let the parent agent see a None content.
**Warning signs:** Parent chat ends mid-sentence; tool result is `{"synthesis": null}`.

### Pitfall 8: ToolCallCard Nesting UI Explosion
**What goes wrong:** Explorer calls kb_read 5 times; nested cards render 5 inline sub-cards; message bubble grows to 80vh; other messages scroll off.
**Why it happens:** No upper bound on nested card rendering.
**How to avoid:** Frontend ToolCallCard (when `tool === "explore_kb"`) collapses sub-events by default into a single "5 sub-tools" summary line. Expand on click. OR render only the LAST 3 sub-events in the preview, with a "+N earlier" chip.
**Warning signs:** User complaints about vertical scroll; long explorations dominate chat view.

## Runtime State Inventory

Not applicable. Phase 5 is additive — it introduces a new service, a new tool, and new Pydantic models. No renames, no migrations, no build-artifact churn. Every category below would be "None":

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no existing `explorer_*` tables, no ChromaDB, no Mem0 | — |
| Live service config | None — no n8n, no Datadog | — |
| OS-registered state | None — no scheduled tasks | — |
| Secrets/env vars | New env vars will be added (explorer_max_iterations etc.), but these are config defaults, not secrets | Add to `config.py` Settings class with defaults |
| Build artifacts | None — no compiled packages change | — |

*Section included for completeness; this is not a rename/refactor phase.*

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| OpenRouter API key | Explorer LLM calls | — (assumed present — parent chat requires it) | — | Falls back to `openai_api_key` via `resolved_llm_api_key` |
| Supabase service role | Explorer KB tool calls | — (assumed present) | — | None — hard requirement |
| LangSmith API key | Explorer tracing | Optional | — | `@traceable` is a no-op decorator if not set (already handled in code) |
| pytest | Explorer unit tests | ✓ (in requirements.txt) | unpinned | None |

**Missing dependencies with no fallback:** None — this phase only uses infrastructure Phase 1-3 already stood up.

**Missing dependencies with fallback:** None relevant.

## Code Examples

Verified patterns from official sources and existing codebase:

### Extending the Tool Dispatcher for a Generator-Based Tool
```python
# Source: Adapted from backend/routers/chat.py:484-566 (existing tool-use loop)
# The existing execute_tool() returns str synchronously. For the explorer we need
# a streaming path. Two options:
#
# OPTION 1: Special-case explore_kb in event_generator() itself (simpler).
#   - Keep execute_tool() as-is for all other tools
#   - Add an `if fn_name == "explore_kb": ... else: ...` branch in the SSE loop
#
# OPTION 2: Refactor execute_tool to return either str or a generator of (sub_event, final_str).
#   - Cleaner abstraction, more work, more places to break
#
# Recommendation: Option 1 for this phase.

# In event_generator(), inside the `for tc in event["tool_calls"]:` loop:
if fn_name == "explore_kb":
    from services.explorer_service import run_exploration
    final_result_str = None
    for sub_ev in run_exploration(
        user_id=user_id,
        query=fn_args["query"],
        mode=fn_args.get("mode", "deep_search"),
    ):
        if sub_ev["type"] == "result":
            final_result_str = json.dumps({"tool": "explore_kb", **sub_ev["result"]})
        else:
            # Emit nested sub_event under the parent call_id
            yield {
                "event": "tool_event",
                "data": json.dumps({
                    "tool_event": True,
                    "type": "sub_event",
                    "subagent": True,
                    "parent_call_id": tc["id"],
                    "sub_event": sub_ev,
                }),
            }
    tool_result = final_result_str or json.dumps({
        "tool": "explore_kb",
        "error": "Exploration produced no result",
    })
else:
    tool_result = execute_tool(fn_name, fn_args, user_id)
```

### Adding the Explorer Tool Schema to Parent
```python
# Source: Pattern matches existing KB_LS_TOOL, ANALYZE_DOCUMENT_TOOL in backend/routers/chat.py:110-265
EXPLORE_KB_TOOL = {
    "type": "function",
    "function": {
        "name": "explore_kb",
        "description": (
            "Spawn a sub-agent to perform complex, multi-step exploration of the knowledge base. "
            "Use this when a single tool call cannot answer the question -- for example: "
            "(1) summarizing an entire folder's contents, "
            "(2) finding cross-references across multiple games, "
            "(3) recommending games similar to one mentioned by the user. "
            "Do NOT use for simple lookups -- kb_ls/kb_read/kb_grep are faster."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["deep_search", "summarize", "find_similar"],
                    "description": (
                        "deep_search: multi-step search across the KB. "
                        "summarize: produce a synthesis of a folder's contents. "
                        "find_similar: find games with mechanics similar to a given game."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "The question or task for the explorer. Be specific; include any folder paths or game names.",
                },
            },
            "required": ["mode", "query"],
        },
    },
}

# In event_generator(), append to tools list:
tools = [KB_LS_TOOL, KB_TREE_TOOL, KB_READ_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL, EXPLORE_KB_TOOL]
```

### LangSmith Nested Tracing
```python
# Source: backend/services/subagent_service.py:51 (existing pattern)
try:
    from langsmith import traceable
except ImportError:
    def traceable(func=None, **kwargs):
        if func:
            return func
        return lambda f: f

@traceable(name="subagent_explorer")
def run_exploration(user_id: str, query: str, mode: str = "deep_search"):
    # Because event_generator() / send_message() is inside @traceable(name="chat_send_message"),
    # this nested @traceable will appear as a child span in LangSmith automatically.
    # No manual trace-context propagation needed.
    ...
```

### Frontend Sub-Event Handling
```typescript
// Source: frontend/src/hooks/useChat.ts:99-148 (existing tool_event parsing)
// Extend the existing parsed.tool_event branch:

if (parsed.tool_event === true) {
  if (parsed.type === 'tool_start') {
    // ... existing code
  } else if (parsed.type === 'tool_result') {
    // ... existing code
  } else if (parsed.type === 'sub_event') {
    // NEW: append to the parent tool's nested sub_events list
    setMessages(prev =>
      prev.map(m => {
        if (m.id !== assistantId) return m
        return {
          ...m,
          toolsUsed: (m.toolsUsed || []).map(t =>
            t.call_id === parsed.parent_call_id
              ? { ...t, subEvents: [...(t.subEvents || []), parsed.sub_event] }
              : t
          ),
        }
      })
    )
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-agent chat with flat tool use | Parent agent + specialist sub-agents (analyze_document, explore_kb) | Phase 5 | Parent reasoning stays lean; specialists burn tokens in isolation. |
| Unstructured sub-agent output | Pydantic-schema-validated return payloads | Phase 5 | Predictable parent-side consumption; fewer "tool returned malformed data" errors. |
| No progress for long sub-agent calls | Nested SSE sub_events | Phase 5 | User sees what the explorer is doing; less perceived latency. |
| Unlimited sub-agent runtime | Three-axis budget (iterations, tool calls, final chars) | Phase 5 | Cost-capped; predictable latency. |

**Deprecated/outdated:** Nothing deprecated — Phase 5 is additive.

## Open Questions

1. **Should the explorer have access to `search_documents` (semantic retrieval) in addition to the 5 KB tools?**
   - What we know: EXPL-01 explicitly lists "all navigation tools (ls, tree, read, grep, glob)". EXPL-03 (cross-reference discovery) and EXPL-04 (recommendations) are much more efficient with embedding search.
   - What's unclear: Whether "navigation tools" was meant strictly (5 tools) or loosely (any retrieval tool).
   - Recommendation: **Give the explorer access to `search_documents` too.** Cross-reference discovery without embeddings is grep-only, which misses semantic similarity. Document the decision in CONTEXT.md. If the user wants strict interpretation, remove it — the risk is low (one less tool).

2. **How should the parent agent seed the explorer for `find_similar` mode?**
   - What we know: Parent has the conversation history and user's current question. Explorer receives only a `query` string.
   - What's unclear: Does the parent pass "find games similar to Catan" (parent already resolved the reference), or does the parent pass the entire last N turns?
   - Recommendation: Parent resolves the reference and passes an explicit seed: `query="Find games similar to Catan. Focus on trading, resource management, tile placement mechanics."`. Keeps explorer context minimal. Let the parent's LLM do the reference resolution in its prompt.

3. **Where do `explorer_max_iterations`, `explorer_max_tool_calls`, `explorer_max_summary_chars`, `explorer_timeout` live?**
   - What we know: Current sub-agent settings (`subagent_max_tokens`, `subagent_max_context_chars`, `subagent_timeout`) live in `config.py` Settings class with defaults.
   - What's unclear: Exact default values.
   - Recommendation: Add with these defaults: `explorer_max_iterations: int = 6`, `explorer_max_tool_calls: int = 10`, `explorer_max_summary_chars: int = 3000`, `explorer_timeout: int = 120` (total budget across all sub-LLM calls; enforced via per-call 30s timeout and iteration count). Tune during UAT.

4. **Should we memoize exploration results?**
   - What we know: Two users asking "summarize Catan rules" redo the same work. The default KB is shared.
   - What's unclear: Whether caching violates any data-freshness constraint.
   - Recommendation: **Defer to v2.** Premature optimization. Record exploration latency in UAT; only add caching if we see repeated duplicate queries in production.

5. **Should the explorer support multi-turn conversations with the user (parent re-invokes with new query)?**
   - What we know: Each `explore_kb` tool call is independent — new message history, new budget.
   - What's unclear: Whether there's value in "continuing" an exploration.
   - Recommendation: **No — stateless per invocation.** The parent agent's own memory serves as continuity. If the user follows up, the parent spawns a fresh explorer with the refined query. Matches existing `analyze_document` semantics.

6. **Frontend UX for deep nested cards — is a pure "collapsed by default" good enough?**
   - What we know: ToolCallCard is already collapsed-by-default; its expansion shows raw output.
   - What's unclear: Whether explorer cards need a special "progress bar" or "X of N tools complete" indicator.
   - Recommendation: Start simple — nested list with the same collapse/expand behavior. If iteration count exceeds 3, show a compact "Exploring... (3/6 steps)" header. Validate in UAT.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (in requirements.txt, unpinned — Wave 0 pins version) |
| Config file | none — create `backend/pytest.ini` in Wave 0 or rely on defaults |
| Quick run command | `cd backend && venv/Scripts/python -m pytest tests/test_explorer.py -x -q` |
| Full suite command | `cd backend && venv/Scripts/python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXPL-01 | Explorer completes a multi-step traversal using KB tools | unit (mocked LLM) | `pytest tests/test_explorer.py::test_multi_step_loop -x` | Wave 0 |
| EXPL-01 | Explorer dispatches kb_tree, kb_ls, kb_read, kb_grep, kb_glob correctly | unit (mocked tools) | `pytest tests/test_explorer.py::test_tool_dispatch -x` | Wave 0 |
| EXPL-02 | `mode="summarize"` produces ExplorerResult with non-empty synthesis | unit (mocked LLM returns schema-valid JSON) | `pytest tests/test_explorer.py::test_summarize_mode -x` | Wave 0 |
| EXPL-03 | `mode="find_similar"` assembles findings across multiple games | unit (scripted LLM turn sequence) | `pytest tests/test_explorer.py::test_find_similar_mode -x` | Wave 0 |
| EXPL-04 | Explorer accepts conversation-derived seed query and returns recommendations | unit | `pytest tests/test_explorer.py::test_recommendation_seed -x` | Wave 0 |
| EXPL-05 | Budget exhaustion on max_iterations sets budget_exhausted=True | unit | `pytest tests/test_explorer.py::test_iteration_budget -x` | Wave 0 |
| EXPL-05 | Budget exhaustion on max_tool_calls sets budget_exhausted=True | unit | `pytest tests/test_explorer.py::test_tool_call_budget -x` | Wave 0 |
| EXPL-05 | ExplorerResult rejects oversized synthesis (Pydantic max_length) | unit | `pytest tests/test_explorer.py::test_output_size_cap -x` | Wave 0 |
| EXPL-06 | `event_generator` emits `sub_event` SSE events during explore_kb call | integration | `pytest tests/test_explorer_sse.py::test_sub_events_emitted -x` | Wave 0 |
| EXPL-06 | Final `tool_result` event contains ExplorerResult JSON | integration | `pytest tests/test_explorer_sse.py::test_final_tool_result -x` | Wave 0 |
| All EXPL | Explorer respects RLS — user A cannot see user B's private docs | integration (two user IDs) | `pytest tests/test_explorer.py::test_rls_isolation -x` | Wave 0 |
| All EXPL | Frontend renders nested sub-event list inside ToolCallCard | manual UAT | Open chat, ask "summarize the Catan folder", verify nested cards appear | n/a |

### Sampling Rate
- **Per task commit:** `cd backend && venv/Scripts/python -m pytest tests/test_explorer.py -x -q` (< 10s with mocked LLM)
- **Per wave merge:** `cd backend && venv/Scripts/python -m pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green + manual UAT of 3 golden queries before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_explorer.py` — unit tests for `explorer_service.run_exploration()` with mocked LLM client (patch `services.llm_service.get_llm_client`)
- [ ] `backend/tests/test_explorer_sse.py` — integration tests for `event_generator` emitting `sub_event` SSE items; use FastAPI TestClient + iterate over StreamingResponse
- [ ] `backend/tests/conftest.py` — shared fixtures: (a) `mock_llm_client` factory that returns scripted tool_call sequences; (b) `test_user_id`, `test_board_games_folder_id`; (c) `mock_supabase_with_kb_fixtures` that seeds a 2-folder, 3-document KB
- [ ] `backend/tests/fixtures/explorer_scenarios.py` — scripted LLM turn sequences for each test case (e.g., "summarize_catan" scenario = [call kb_tree, call kb_read rules.md, return structured JSON])
- [ ] `backend/pytest.ini` — pin test paths, verbosity defaults
- [ ] Framework pin: update `requirements.txt` to `pytest>=8.0,<9.0` if unpinned is causing drift

### Golden UAT Queries (manual, post-implementation)
1. **Multi-step search:** "Find all board games in the KB that have tile placement mechanics." — verify at least 2 games surfaced, progress cards visible.
2. **Folder summarization:** "Summarize the Catan folder." — verify kb_tree + kb_read calls in sub-event list, coherent multi-paragraph synthesis.
3. **Similar games:** "What games are like Azul?" — verify at least 2 candidate games, each with a reasoning sentence.
4. **Budget exhaustion:** Temporarily set `explorer_max_iterations=2`, run query 1 — verify `budget_exhausted: true` flag in result, UI shows it gracefully.
5. **Graceful error:** Break kb_read (inject exception in test double) — verify explorer recovers, other tools still called, summary mentions the failure.

## Sources

### Primary (HIGH confidence — direct code inspection)
- `backend/routers/chat.py` — tool-use loop pattern, SSE event_generator, execute_tool dispatcher (lines 303-401, 444-609)
- `backend/services/subagent_service.py` — reference sub-agent implementation; `@traceable` usage; `get_full_document_text` reassembly pattern
- `backend/services/kb_tools_service.py` — Phase 3 tool functions the explorer will reuse (kb_ls, kb_tree, kb_read, kb_grep, kb_glob)
- `backend/services/llm_service.py` — `get_llm_client()` factory, `stream_chat_completion` streaming tool-use pattern, LangSmith `wrap_openai`
- `backend/services/retrieval_service.py` — existing hybrid search that could feed EXPL-03/04 seed queries
- `backend/config.py` — `Settings` singleton pattern for budget knobs; existing `subagent_*` settings as template for `explorer_*`
- `backend/services/tracing.py` — LangSmith env-var wiring
- `frontend/src/components/ToolCallCard.tsx` — existing `subagent` prop + indigo styling; extension point for nested sub-events
- `frontend/src/hooks/useChat.ts` — existing `tool_event` SSE parsing; extension point for `sub_event` handling
- `frontend/src/components/MessageBubble.tsx` — ToolCallCard rendering within assistant messages
- `backend/tests/test_e2e_subagent.py` — existing E2E test pattern for sub-agent behavior via SSE
- `backend/tests/test_folders_api.py` — FastAPI TestClient + Supabase-mocking pattern for new explorer tests
- `backend/requirements.txt` — confirms openai 1.74.0, pydantic 2.11.1, sse-starlette 2.2.1, langsmith 0.3.42 all already present
- `.planning/phases/03-kb-navigation-tools/03-RESEARCH.md` — Phase 3 research context (visibility filter patterns, tool schema conventions)
- `.planning/phases/03-kb-navigation-tools/03-CONTEXT.md` — locked decisions D-04 (human-readable paths), D-07 (9 existing tools), D-08 (tool complementarity)
- `.planning/REQUIREMENTS.md` — EXPL-01 through EXPL-06 authoritative text
- `.planning/ROADMAP.md` — Phase 5 success criteria

### Secondary (MEDIUM confidence — standard patterns from training knowledge)
- OpenAI function-calling tool-use loop pattern: well-established since mid-2024, documented in OpenAI's "Function calling" guide. The parent chat.py implementation is the authoritative in-repo reference.
- LangSmith nested `@traceable` auto-nesting: documented behavior of `langsmith>=0.1.0`. The existing `chat_send_message` → `subagent_document_analysis` trace proves it works in this repo.
- Pydantic `response_format={"type": "json_schema"}`: OpenAI-native feature since late 2024; supported by OpenRouter for major models. Fallback to `{"type": "json_object"}` is the standard degradation path.

### Tertiary (LOW confidence — not independently verified)
- Exact OpenRouter model support matrix for `response_format=json_schema` — varies over time; flag as a runtime fallback path, not a hard assumption.
- `tiktoken` token counting accuracy for OpenRouter-routed models — deliberately avoided; using `response.usage` is more reliable.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already installed; direct inspection of requirements.txt
- Architecture: HIGH — the "sub-agent as tool" pattern already exists in the codebase (`subagent_service.py`), so this is a proven pattern being extended, not invented
- SSE nesting: HIGH — reuses the existing `tool_event`/`subagent` fields; extension shape is straightforward
- Pitfalls: HIGH — derived from (a) direct inspection of chat.py tool loop, (b) known characteristics of OpenAI function-calling (context growth, tool-call ordering), (c) prior Phase 3 UAT findings on tool error handling
- Validation architecture: HIGH — testing strategy mirrors existing `test_folders_api.py` and `test_e2e_subagent.py` patterns

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable — the only moving piece is OpenRouter model feature support, which is a runtime-fallback concern not a plan-time concern)
