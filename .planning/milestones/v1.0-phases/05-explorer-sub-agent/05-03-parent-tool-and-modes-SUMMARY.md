---
phase: 05-explorer-sub-agent
plan: 03
subsystem: backend-services
tags: [explorer, sub-agent, tool-registration, sse, asyncio, streaming, integration-testing]

# Dependency graph
requires:
  - phase: 05-explorer-sub-agent (Plan 02)
    provides: run_exploration() generator, _execute_explorer_tool dispatcher, ExplorerResult contracts
  - phase: 05-explorer-sub-agent (Plan 01)
    provides: ExplorerResult/ExplorerFinding Pydantic contracts, explorer_* Settings, stub_db_chain fixture, EXPLORER_SCENARIOS
provides:
  - EXPLORE_KB_TOOL constant registered on parent chat loop with mode enum {deep_search, summarize, find_similar}
  - Streaming dispatcher branch in event_generator() bridging sync explorer generator to async SSE via asyncio.to_thread + queue
  - SSE sub_event rows with parent_call_id linking child events to parent tool_start
  - TOOL_SELECTION_GUIDE with Deep exploration section
  - 4 SSE integration tests (TestClient-based) verifying end-to-end flow
  - 2 activated unit tests for find_similar mode and recommendation_seed pattern (EXPL-03, EXPL-04)
affects: [05-04-frontend-streaming-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread + queue.Queue bridging: sync generator on worker thread, async consumer on event loop"
    - "SSE sub_event nesting: parent tool_event wraps child sub_events with parent_call_id linkage"
    - "sse_starlette AppStatus.should_exit_event reset between TestClient tests to avoid event-loop binding errors"

key-files:
  created:
    - .planning/phases/05-explorer-sub-agent/05-03-parent-tool-and-modes-SUMMARY.md
  modified:
    - backend/routers/chat.py
    - backend/tests/test_explorer_service.py
    - backend/tests/test_explorer_integration.py

key-decisions:
  - "asyncio.to_thread + queue pattern for bridging sync generator to async event_generator -- avoids blocking the event loop while allowing incremental SSE emission"
  - "is_subagent flag unifies analyze_document and explore_kb tagging logic -- single check instead of per-tool conditionals"
  - "Extended find_similar_azul scenario with explicit summary response to avoid relying on 3-tier fallback (which produces empty findings)"
  - "Reset sse_starlette AppStatus.should_exit_event in test fixture to prevent cross-test event-loop binding errors"

patterns-established:
  - "Sub-agent SSE nesting: parent tool_start (subagent=true) -> N sub_event rows (parent_call_id) -> parent tool_result (subagent=true)"
  - "Integration test DB mocking: route db.table() calls to operation-specific stub_db_chain instances by table name"

requirements-completed:
  - EXPL-01
  - EXPL-02
  - EXPL-03
  - EXPL-04
  - EXPL-06

# Metrics
duration: ~14 min
completed: 2026-04-17
---

# Phase 05 Plan 03: Parent Tool and Modes Summary

**EXPLORE_KB_TOOL wired into parent chat loop with async-bridged streaming dispatcher emitting nested SSE sub_event rows; find_similar and recommendation_seed modes verified by unit tests; 4 integration tests proving end-to-end SSE flow.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-17T14:17:53Z
- **Completed:** 2026-04-17T14:32:01Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- EXPLORE_KB_TOOL constant with mode enum {deep_search, summarize, find_similar} registered on parent chat loop -- always available (KB always exists)
- Streaming dispatcher branch in event_generator() uses asyncio.to_thread + queue.Queue to bridge the sync run_exploration() generator to the async SSE stream without blocking the event loop
- SSE sub_event rows emitted with parent_call_id linking child explorer events to parent tool_start
- TOOL_SELECTION_GUIDE updated with "Deep exploration" section documenting when to use explore_kb vs simpler tools
- find_similar mode and recommendation_seed pattern verified by unit tests (EXPL-03, EXPL-04)
- 4 SSE integration tests using FastAPI TestClient prove the full request path: tool registration, sub_event emission, ExplorerResult in tool_result, parent_call_id linkage
- All 23 explorer tests passing (13 unit + 6 dispatcher + 4 integration), 66 total tests passing

## Task Commits

Each task committed atomically (with --no-verify per parallel-executor protocol):

1. **Task 1: Register EXPLORE_KB_TOOL + streaming dispatcher** -- `39d662c` (feat)
2. **Task 2: Activate find_similar + recommendation_seed unit tests** -- `36d3fd6` (test)
3. **Task 3: Activate SSE integration tests** -- `e8761ed` (test)

## Files Created/Modified

### Modified
- `backend/routers/chat.py` -- EXPLORE_KB_TOOL constant, TOOL_SELECTION_GUIDE Deep exploration section, explore_kb streaming dispatcher branch with asyncio.to_thread + queue bridging
- `backend/tests/test_explorer_service.py` -- Un-skipped test_find_similar_mode and test_recommendation_seed with full assertions (0 skips remaining)
- `backend/tests/test_explorer_integration.py` -- Replaced 4 skip-marked stubs with full TestClient-based SSE integration tests

## EXPLORE_KB_TOOL Schema

```python
EXPLORE_KB_TOOL = {
    "type": "function",
    "function": {
        "name": "explore_kb",
        "parameters": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["deep_search", "summarize", "find_similar"]},
                "query": {"type": "string"},
            },
            "required": ["mode", "query"],
        },
    },
}
```

## SSE Row Shapes (for Plan 04 Frontend)

```jsonc
// 1. Parent tool_start (existing shape + subagent flag)
{"tool_event": true, "type": "tool_start", "tool": "explore_kb",
 "subagent": true, "call_id": "call_abc", "args_preview": "mode=\"summarize\" query=\"...\""}

// 2. Sub-events (NEW -- one per explorer sub-tool invocation)
{"tool_event": true, "type": "sub_event", "subagent": true,
 "parent_call_id": "call_abc",
 "sub_event": {"type": "sub_tool_start", "call_id": "sub_1", "tool": "kb_tree", "args_preview": "..."}}

// 3. Parent tool_result (existing shape -- output is ExplorerResult JSON)
{"tool_event": true, "type": "tool_result", "tool": "explore_kb", "subagent": true,
 "call_id": "call_abc", "output": "{\"tool\": \"explore_kb\", \"mode\": \"summarize\", ...}"}
```

## asyncio.to_thread + Queue Pattern

The sync `run_exploration()` generator cannot be driven directly from the async `event_generator()`. The solution uses a `queue.Queue` as a cross-thread channel:

1. `asyncio.create_task(asyncio.to_thread(_drive))` runs the sync generator on a worker thread
2. Each yield from the generator is put into the queue
3. The async event_generator awaits `asyncio.to_thread(q.get)` to consume events without blocking the event loop
4. A SENTINEL object signals generator completion

This avoids Pitfall 3 (blocking the event loop with sync I/O) while preserving incremental SSE emission.

## Test Coverage Matrix

| Requirement | Test | File |
|-------------|------|------|
| EXPL-01 (multi-step traversal) | test_multi_step_loop | test_explorer_service.py |
| EXPL-01 (5-tool dispatch) | test_tool_dispatch + test_dispatch_kb_* | both |
| EXPL-02 (summarize mode) | test_summarize_mode | test_explorer_service.py |
| EXPL-03 (find_similar mode) | test_find_similar_mode | test_explorer_service.py |
| EXPL-04 (recommendation seed) | test_recommendation_seed | test_explorer_service.py |
| EXPL-05 (output size caps) | test_explorer_result_* | test_explorer_service.py |
| EXPL-05 (budget enforcement) | test_iteration_budget, test_tool_call_budget | test_explorer_service.py |
| EXPL-06 (SSE sub_events) | test_sub_events_emitted | test_explorer_integration.py |
| EXPL-06 (tool_result) | test_final_tool_result | test_explorer_integration.py |
| EXPL-06 (parent_call_id) | test_parent_call_id_links_subevents | test_explorer_integration.py |
| EXPL-06 (tool registered) | test_explore_kb_tool_registered | test_explorer_integration.py |
| RLS scoping | test_rls_isolation | test_explorer_service.py |

## stub_db_chain Usage in Integration Tests

Integration tests use `stub_db_chain` from `tests/fixtures/explorer_fixtures.py` for Supabase mocking. The test routes `db.table()` calls by table name to operation-specific stubs:

- `threads` table: returns thread_row dict for maybe_single()
- `messages` table: routes select/insert/update to separate chains with appropriate return shapes
- `documents` table: returns empty list (no completed docs)

Future test authors should reuse `stub_db_chain` and the table-routing pattern rather than hand-rolling chain mocks, which are fragile to chat.py's internal query-builder ordering.

## Decisions Made

- **asyncio.to_thread + queue for sync-async bridging** -- Avoids blocking the event loop; the queue allows incremental SSE emission as the explorer progresses rather than waiting for the full result
- **is_subagent unification** -- Single `fn_name in ("analyze_document", "explore_kb")` check replaces per-tool conditionals for cleaner code
- **Extended find_similar scenario for unit test** -- The EXPLORER_SCENARIOS["find_similar_azul"] fixture has 3 responses, but `_summarize_findings` makes an additional LLM call. Added a 4th response with the expected ExplorerResult JSON to avoid relying on the 3-tier fallback (which produces empty findings)
- **AppStatus.should_exit_event reset** -- sse_starlette binds an asyncio.Event to the first event loop; subsequent TestClient instances create new loops, causing RuntimeError. Reset in autouse fixture.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended find_similar_azul scenario with summary response**
- **Found during:** Task 2 (test_find_similar_mode)
- **Issue:** The EXPLORER_SCENARIOS["find_similar_azul"] has 3 scripted responses (2 tool calls + 1 voluntary stop), but _summarize_findings makes an additional LLM call. With side_effect exhausted, StopIteration was caught by the 3-tier fallback, producing an ExplorerResult with empty findings -- failing the assert len(findings) >= 2 check.
- **Fix:** Added a 4th make_response with the expected ExplorerResult JSON to the scenario in the test.
- **Files modified:** backend/tests/test_explorer_service.py
- **Committed in:** 36d3fd6

**2. [Rule 3 - Blocking] Fixed sse_starlette AppStatus event-loop binding in integration tests**
- **Found during:** Task 3 (test_final_tool_result, test_parent_call_id_links_subevents)
- **Issue:** sse_starlette's AppStatus.should_exit_event binds to the first event loop; subsequent TestClient instances create new loops, causing RuntimeError("bound to a different event loop").
- **Fix:** Added autouse fixture that resets AppStatus.should_exit_event after each test.
- **Files modified:** backend/tests/test_explorer_integration.py
- **Committed in:** e8761ed

**3. [Rule 3 - Blocking] Fixed DB mock routing for integration tests**
- **Found during:** Task 3 (test_sub_events_emitted)
- **Issue:** Plan's single stub_db_chain returning thread_row dict caused TypeError when chat.py iterated history.data as list of message dicts.
- **Fix:** Routed db.table() calls by table name to operation-specific stub_db_chain instances with correct return shapes.
- **Files modified:** backend/tests/test_explorer_integration.py
- **Committed in:** e8761ed

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking)
**Impact on plan:** All auto-fixes necessary for test correctness. No scope creep.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

Plan 04 (frontend-streaming-ui) can now:
- Subscribe to SSE `tool_event` rows where `tool=explore_kb` AND `type=sub_event` to render nested sub-tool indicators
- Use the documented SSE row shapes (tool_start with subagent=true, sub_event with parent_call_id, tool_result with ExplorerResult JSON)
- The backend contract is stable: 23 tests verify the exact SSE shapes Plan 04 will consume

No blockers. No concerns.

## Self-Check: PASSED

All modified files exist on disk. All 3 task commits verified in git history.

---
*Phase: 05-explorer-sub-agent*
*Completed: 2026-04-17*
