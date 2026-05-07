---
phase: 06-agent-intelligence-and-polish
plan: 02
subsystem: backend-api
tags: [token-budget, source-routing, scope-parsing, sse, subagent-alignment, chat-loop, tool-card]

requires:
  - phase: 06-agent-intelligence-and-polish
    provides: "TokenBudget, infer_source_scope, parse_scope_hint, fetch_model_context_length (Plan 01)"
provides:
  - "Budget-tracked chat event_generator with dynamic OpenRouter context-length lookup and FIFO oldest-pair truncation"
  - "Source routing and scope hints wired from user message through stream_chat_completion into the LLM system prompt"
  - "analyze_document emits SSE sub_event rows (sub_iteration / sub_tool_start / sub_tool_result / result) matching the explore_kb contract"
  - "ToolCallCard renders a scope:<scope> prefix as a colored badge so routing is visible in the UI"
affects: [phase-07, chat-streaming, subagent-ui]

tech-stack:
  added: []
  patterns:
    - "Yield-first system_content event from stream_chat_completion so callers can budget-track the exact system prompt sent to the model"
    - "Sub-agent SSE bridge via asyncio.to_thread + queue.Queue, identical for explore_kb and analyze_document"
    - "Scope prefix convention in args_preview (scope:<scope>) so frontend can decorate without extra event fields"

key-files:
  created:
    - "backend/tests/test_subagent_alignment.py"
    - ".planning/phases/06-agent-intelligence-and-polish/deferred-items.md"
  modified:
    - "backend/routers/chat.py"
    - "backend/services/llm_service.py"
    - "backend/services/subagent_service.py"
    - "backend/tests/test_explorer_integration.py"
    - "frontend/src/components/ToolCallCard.tsx"

key-decisions:
  - "stream_chat_completion yields a leading system_content event so token accounting uses the exact post-hint system prompt"
  - "analyze_document reuses the exact asyncio.to_thread + queue bridge that explore_kb uses -- one sub-agent execution pattern across the codebase"
  - "Pair-tracking for budget uses reverse scan of current_messages to find the assistant tool_calls message by id so multi-tool-call batches are handled correctly"
  - "Scope indicator is encoded as an args_preview prefix (scope:<scope>) rather than a new SSE field, keeping the contract backwards-compatible"

patterns-established:
  - "Generator-style sub-agents with a sentinel 'result' event as the final yield (applies to explore_kb and analyze_document)"
  - "Two-phase scope resolution: infer_source_scope as default, parse_scope_hint.source_hint as explicit override"

requirements-completed: [AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05]

duration: 36 min
completed: 2026-04-22
---

# Phase 06 Plan 02: Chat Loop Integration Summary

**Wired TokenBudget, source routing, scope parsing, and sub-agent SSE alignment into the live chat event_generator; analyze_document now emits explore_kb-style sub_events and tool cards surface a colored scope badge.**

## Performance

- **Duration:** 36 min
- **Started:** 2026-04-22T03:31:09Z
- **Completed:** 2026-04-22T04:06:55Z
- **Tasks:** 3
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- Budget tracking is live: every tool round-trip is registered via `budget.add_tool_result_pair`, and when the system_content event fires we set system/history tokens and truncate oldest pairs if over the limit (`TokenBudget.truncate_oldest_tool_results`)
- Dynamic context length: `fetch_model_context_length` is best-effort called against OpenRouter on every request and overrides the static `model_context_length` config when available
- Source routing + scope parsing: `infer_source_scope` + `parse_scope_hint` are invoked once per message; source hints override inferred scope; folder hints flow into the system prompt as search guidance
- `run_document_analysis` became an `Iterator[dict]` generator yielding the same event shapes as `run_exploration`, so the existing frontend sub_event handling just works for analyze_document
- `ToolCallCard.renderArgsPreview` parses a leading `scope:<scope>` and renders a colored badge (blue=default_kb, green=private, yellow=both)

## Task Commits

1. **Task 1: Wire budget tracking and source routing into chat loop** -- `c6d5c73` (feat)
2. **Task 2: Align analyze_document SSE events with explore_kb contract** -- `8e17b87` (feat)
3. **Task 3: Add scope indicator to ToolCallCard and fix explorer test stub** -- `c5359d1` (feat)

## Files Created/Modified

- `backend/routers/chat.py` - Budget init, source/scope inference, system_content handler, analyze_document inline dispatch, scope in args_preview, pair tracking
- `backend/services/llm_service.py` - New `source_hint` / `scope_hint` params, system_content event, Source Routing / Search Scope guidance blocks
- `backend/services/subagent_service.py` - Rewrote `run_document_analysis` as `Iterator[dict]` generator yielding sub_iteration / sub_tool_start / sub_tool_result / result events
- `backend/tests/test_subagent_alignment.py` - NEW: 7 tests for sub-agent SSE alignment (happy path, not-found, multiple-match, timeout, event shape)
- `backend/tests/test_explorer_integration.py` - Updated stub to accept `source_hint` / `scope_hint` and yield leading `system_content` event
- `frontend/src/components/ToolCallCard.tsx` - `renderArgsPreview` helper that parses `scope:<scope>` and renders a colored badge
- `.planning/phases/06-agent-intelligence-and-polish/deferred-items.md` - NEW: logs pre-existing unrelated test_record_manager fixture error

## Decisions Made

- **system_content as the first yielded event:** lets the router budget-account for the *actual* system prompt (including routing + scope hints) without re-duplicating the template
- **Reuse explore_kb bridge for analyze_document:** asyncio.to_thread + queue.Queue + sentinel object. Identical contract for the frontend (`type=sub_event`, `parent_call_id`)
- **Scope indicator as args_preview prefix:** avoids a new SSE field; works with existing `tool_start` / `tool_result` plumbing; frontend does a cheap regex parse

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Explorer integration test stub missing new kwargs**
- **Found during:** Task 3 full backend test run
- **Issue:** `test_explorer_integration._make_explore_tool_call_streams._stream()` was stubbed with `(messages, tools=None, tool_guide=None)` and did not yield a leading `system_content` event. After adding `source_hint` / `scope_hint` to `stream_chat_completion`, the mock side_effect raised `TypeError: unexpected keyword argument 'source_hint'`, breaking `test_sub_events_emitted`
- **Fix:** Extended stub signature to accept `source_hint=None, scope_hint=None` and yield a leading `{"type": "system_content", "content": "system"}` event so the new event_generator path exercises the budget bookkeeping branch
- **Files modified:** backend/tests/test_explorer_integration.py
- **Verification:** `pytest tests/test_explorer_integration.py -x` passes (full integration suite green)
- **Committed in:** c5359d1 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to keep the existing explorer integration test green after the llm_service signature change. No scope creep.

## Issues Encountered

- `test_record_manager.py::test_check_duplicate_integration` fails with a fixture error (`user_id` not found). This predates Phase 6 (traces back to commit `c46981a`, module 3) and does not touch any Plan 06-02 surface area. Logged in `deferred-items.md`; full suite with `--ignore=tests/test_record_manager.py` runs **97 passed**

## Deferred Issues

- **test_record_manager fixture mismatch** -- pre-existing, unrelated. A future cleanup plan should rename the local fixture to `test_user_id` or add a `user_id` fixture alias in `tests/conftest.py`

## User Setup Required

None - no external service configuration required. All new behavior is internal to the chat loop.

## Next Phase Readiness

- All five AGNT requirements (AGNT-01..05) are now active in the live chat loop
- Phase 06 is complete: budget (Plan 01) + wiring (Plan 02) both shipped
- Ready for `/gsd:verify-work` pass and milestone completion

## Self-Check: PASSED

- File `backend/tests/test_subagent_alignment.py` exists: FOUND
- File `backend/routers/chat.py` contains `TokenBudget(`: FOUND
- File `backend/routers/chat.py` contains `infer_source_scope(`: FOUND
- File `backend/routers/chat.py` contains `parse_scope_hint(`: FOUND
- File `backend/services/llm_service.py` contains `source_hint`: FOUND
- File `backend/services/llm_service.py` contains `## Source Routing`: FOUND
- File `backend/services/subagent_service.py` contains `yield {"type": "sub_iteration"`: FOUND
- File `frontend/src/components/ToolCallCard.tsx` contains `renderArgsPreview`: FOUND
- Commit `c6d5c73` present: FOUND
- Commit `8e17b87` present: FOUND
- Commit `c5359d1` present: FOUND
- `pytest tests/test_subagent_alignment.py` result: 7 passed
- `pytest tests/ --ignore=tests/test_record_manager.py` result: 97 passed
- `npx tsc --noEmit` (frontend): exit 0

---
*Phase: 06-agent-intelligence-and-polish*
*Completed: 2026-04-22*
