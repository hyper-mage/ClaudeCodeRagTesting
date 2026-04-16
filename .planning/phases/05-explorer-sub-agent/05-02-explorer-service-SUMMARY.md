---
phase: 05-explorer-sub-agent
plan: 02
subsystem: backend-services
tags: [explorer, sub-agent, tool-loop, openai, structured-output, pydantic, langsmith, kb-tools]

# Dependency graph
requires:
  - phase: 05-explorer-sub-agent (Plan 01)
    provides: ExplorerResult/ExplorerFinding Pydantic contracts, explorer_* Settings knobs, EXPLORER_SCENARIOS fixtures, mock_llm_client/make_response/make_tool_call helpers
  - phase: 03-kb-tools
    provides: kb_ls / kb_tree / kb_read / kb_grep / kb_glob functions in services/kb_tools_service.py + KB_*_TOOL OpenAI schemas in routers/chat.py (reused unchanged)
provides:
  - run_exploration() generator producing sub_iteration / sub_tool_start / sub_tool_result / result events
  - _execute_explorer_tool() dispatcher that always returns JSON (never raises)
  - _summarize_findings() with 3-tier structured-output fallback (json_schema -> json_object -> regex)
  - _explorer_tool_schemas() lazy-import helper that resolves the chat <-> explorer circular dependency
  - _make_fake_settings() test helper for budget/explorer-config patching (in test_explorer_service.py)
  - Activated unit tests: 17 passing (multi-step loop, dispatch, summarize, iteration budget, tool-call budget, RLS isolation, 6 dispatcher tests, contract tests)
affects: [05-03-parent-tool-and-modes, 05-04-frontend-streaming-ui]

# Tech tracking
tech-stack:
  added: []  # No new deps -- reuses Phase 3 KB tools, Phase 5/01 contracts, existing OpenAI SDK
  patterns:
    - "Sync generator yielding sub_event dicts for SSE bridging (parent router converts each yield to a tool_event row)"
    - "Lazy imports inside helper functions to break circular deps between routers and services"
    - "3-tier structured-output fallback (json_schema -> json_object -> regex extract -> hardcoded ExplorerResult)"
    - "Server-authoritative metadata: tools_used / iterations / budget_exhausted overwrite whatever the LLM put in the JSON"
    - "Dual clipping: 4000 chars to LLM context (preserves token budget); 1000 chars to SSE (preserves UI snappiness)"
    - "MagicMock-based Settings patching (not env-var round-tripping) to avoid silent default fallback when Settings has no explicit env_aliases"

key-files:
  created:
    - backend/services/explorer_service.py
    - .planning/phases/05-explorer-sub-agent/deferred-items.md
    - .planning/phases/05-explorer-sub-agent/05-02-explorer-service-SUMMARY.md
  modified:
    - backend/tests/test_explorer_service.py
    - backend/tests/test_explorer_tools.py

key-decisions:
  - "Lazy import of KB_*_TOOL schemas inside _explorer_tool_schemas() so Plan 03 can register explore_kb in chat.py without import-cycle deadlock"
  - "Server overwrites tools_used / iterations / budget_exhausted in ExplorerResult after the LLM returns the JSON -- model can't lie about budgets it consumed"
  - "Three-tier structured-output fallback (Pitfall 4): preferred path is json_schema strict mode; degrades through json_object then regex; final tier returns a hardcoded refusal ExplorerResult so the parent never sees an exception"
  - "Dispatcher (_execute_explorer_tool) catches every exception and returns a JSON error string so tool failures become LLM-readable text, never propagate up"
  - "Budget tests patch services.explorer_service.get_settings directly -- the Settings class has no explicit env_aliases, so monkeypatch.setenv + cache_clear would silently fall back to defaults and produce false-positive passes"
  - "Iteration cap check is at TOP of loop body, voluntary stop check happens before tool execution -- model can stop short of cap without triggering budget_exhausted=True"

patterns-established:
  - "Sub-agent generator contract: yield sub_iteration / sub_tool_start / sub_tool_result during work; final yield is type='result' with full Pydantic-validated payload"
  - "Lazy import for circular-dependency breakage: import schemas/constants from routers inside the function that needs them, not at module top"
  - "Test helper _make_fake_settings(**overrides) pattern for any service that reads Settings -- mirrors production defaults, override only what the test cares about"

requirements-completed:
  - EXPL-01
  - EXPL-05
  - EXPL-06

# Metrics
duration: ~7 min
completed: 2026-04-16
---

# Phase 05 Plan 02: Explorer Service Summary

**Explorer sub-agent generator (run_exploration) wired to the Phase 3 KB tools, enforcing 3-axis budget caps and producing Pydantic-validated ExplorerResult via 3-tier structured-output fallback. 17 unit tests green.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-16T20:09Z (resume from Plan 01 completion)
- **Completed:** 2026-04-16T20:16Z
- **Tasks:** 2
- **Files created/modified:** 4 (1 service, 2 test files updated, 1 deferred-items log)

## Accomplishments

- `backend/services/explorer_service.py` (329 lines): `run_exploration()` generator + `_execute_explorer_tool()` dispatcher + `_summarize_findings()` with 3-tier structured-output fallback + `_explorer_tool_schemas()` lazy-import helper
- All 5 KB tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob) reused from Phase 3's `kb_tools_service.py` with no duplication
- 3 budget axes wired to Settings: `explorer_max_iterations` (top-of-loop check), `explorer_max_tool_calls` (per-call check), `explorer_max_summary_chars` (passed to summary prompt)
- Dual clipping: 4000 chars to LLM context messages, 1000 chars to SSE sub_tool_result events
- @traceable decorator hooks into LangSmith when configured (graceful fallback to no-op decorator otherwise)
- All exceptions in tool dispatch and LLM calls caught -- explorer never raises; on failure returns ExplorerResult with `budget_exhausted=True` and a fallback synthesis
- 17 unit tests passing in `test_explorer_service.py` + `test_explorer_tools.py` (covers EXPL-01, EXPL-05; partial EXPL-06)
- Pydantic contract tests verify hard caps: synthesis ≤2000, findings ≤8, excerpt ≤500, mode ∈ {deep_search, summarize, find_similar}

## Task Commits

Each task committed atomically (with `--no-verify` per parallel-executor protocol):

1. **Task 1: Implement explorer_service.py** -- `10d45a7` (feat)
2. **Task 2: Activate explorer unit tests** -- `79e8a23` (test)

**Plan metadata:** _(filled by metadata commit)_

## Files Created/Modified

### Created
- `backend/services/explorer_service.py` -- Explorer generator + dispatcher + summary helper (329 lines)
- `.planning/phases/05-explorer-sub-agent/deferred-items.md` -- Logs pre-existing test_record_manager.py errors (out of scope)

### Modified
- `backend/tests/test_explorer_service.py` -- 7 tests un-skipped + implemented; `_make_fake_settings()` helper added; 2 Plan 03 tests still skipped
- `backend/tests/test_explorer_tools.py` -- All 6 dispatcher tests un-skipped + implemented

## Sub-Event Payload Shapes (for Plan 03 SSE wiring)

The generator yields these dict shapes; Plan 03's chat router translates each to an SSE `tool_event` row with `type=sub_event`:

```python
{"type": "sub_iteration", "iteration": int}
{"type": "sub_tool_start", "call_id": str, "tool": str, "args_preview": str}  # args_preview <= 200 chars
{"type": "sub_tool_result", "call_id": str, "tool": str, "output": str}       # output <= 1000 chars
{"type": "result", "result": <ExplorerResult.model_dump() dict>}              # FINAL yield only
```

The `result` event always fires last. On any failure path the explorer returns an ExplorerResult with `budget_exhausted=True` rather than crashing.

## Pitfall Mitigations (line ranges in explorer_service.py)

- **Pitfall 1 (context bleed):** Tool result clipping -- lines 27 (constants), 297-302 (clipping before message append), 312-316 (separate clipping for SSE)
- **Pitfall 4 (structured output unreliable):** 3-tier fallback in `_summarize_findings` -- lines 138-160 (Tier 1 json_schema), 162-172 (Tier 2 json_object), 174-184 (Tier 3 regex), 186-195 (Tier 4 hardcoded refusal)
- **Pitfall 5 (budget enforcement):** Top-of-loop iteration cap -- line 232 (while clause), 233-234 (increment + sub_iteration yield); tool-call cap -- lines 271-273 (per-call check); voluntary-stop break -- lines 256-258
- **Pitfall 7 (refusal/empty handling):** Falls through all 3 summary tiers to a hardcoded ExplorerResult -- lines 186-195

## Test Coverage Matrix

| Requirement | Test | File |
|-------------|------|------|
| EXPL-01 (multi-step traversal) | test_multi_step_loop | test_explorer_service.py |
| EXPL-01 (5-tool dispatch) | test_tool_dispatch + test_dispatch_kb_{ls,tree,read,grep,glob} | both |
| EXPL-01 (graceful unknown tool) | test_tool_dispatch_unknown_returns_error_json | test_explorer_tools.py |
| EXPL-02 (summarize mode) | test_summarize_mode | test_explorer_service.py |
| EXPL-05 (output size cap) | test_explorer_result_rejects_oversized_synthesis, test_explorer_finding_rejects_oversized_excerpt, test_explorer_result_rejects_too_many_findings, test_output_size_cap | test_explorer_service.py |
| EXPL-05 (iteration budget) | test_iteration_budget | test_explorer_service.py |
| EXPL-05 (tool-call budget) | test_tool_call_budget | test_explorer_service.py |
| EXPL-05 (mode whitelist) | test_explorer_result_mode_pattern | test_explorer_service.py |
| EXPL-06 (sub_event shapes) | test_multi_step_loop (asserts sub_tool_start / sub_tool_result / result events) | test_explorer_service.py |
| RLS scoping | test_rls_isolation | test_explorer_service.py |

Plan 03 owns:
- test_find_similar_mode (still skipped)
- test_recommendation_seed (still skipped)
- 4 integration tests in test_explorer_integration.py (still skipped)

## _make_fake_settings Helper Signature

For Plan 03 reuse if needed (currently lives in `test_explorer_service.py`):

```python
def _make_fake_settings(**overrides) -> MagicMock:
    """Build a MagicMock matching every Settings field explorer_service reads.

    Defaults mirror production. Override only what the test cares about.
    Patches services.explorer_service.get_settings directly (not env-vars +
    cache_clear) because the Settings class has no explicit env aliases.
    """
```

Fields covered: `explorer_max_iterations`, `explorer_max_tool_calls`, `explorer_max_summary_chars`, `explorer_timeout`, `explorer_system_prompt`, `llm_model`.

## Decisions Made

- **Lazy import of KB schemas inside _explorer_tool_schemas()** -- Plan 03 will import `run_exploration` from `routers/chat.py`, and Plan 03's EXPLORE_KB_TOOL will live in chat.py. Top-level import would deadlock on first import. Verified by acceptance test (`venv/Scripts/python -c "from services.explorer_service import _explorer_tool_schemas; ..."` exits 0)
- **Server overwrites metadata after summary** -- the LLM is unreliable about reporting its own resource consumption; tools_used/iterations/budget_exhausted are computed by the explorer loop and stamped onto the parsed ExplorerResult before yielding
- **3-tier structured-output fallback** -- OpenRouter routes to many backends; some support response_format=json_schema strictly, some only json_object, some neither. Each tier degrades gracefully to the next. The 4th tier (hardcoded refusal) ensures the explorer NEVER raises an exception to the parent
- **Dual clipping** -- 4000 chars to LLM messages prevents context bloat across many iterations; 1000 chars to SSE keeps the frontend tool-card payload small. Both are conservative defaults; future tuning lives in module constants
- **MagicMock Settings patching for budget tests (B1 fix)** -- the Settings class doesn't declare explicit env aliases, so pydantic-settings' field_name -> ENV_VAR auto-mapping isn't guaranteed for the explorer_* fields. monkeypatch.setenv would silently fall back to defaults, producing a false-positive pass

## Deviations from Plan

None -- plan executed exactly as written.

The plan's two tasks both have `tdd="true"` markers, but they are scaffolding/contract tasks (the tests were written in Plan 01 as skip-marked stubs). Task 1 implemented the service against those skip-marked tests (RED was already in place); Task 2 un-skipped them and tightened to real assertions (GREEN). No new tests were added beyond what Plan 01's scaffold prescribed.

## Issues Encountered

- **Pre-existing test_record_manager.py errors (out of scope)** -- 2 ERROR results during full-suite run for `test_check_duplicate_integration` and `test_find_previous_version_integration`. These are integration tests requiring a real Supabase DB, last touched in commit `c46981a` (module 3 completion). Logged in `.planning/phases/05-explorer-sub-agent/deferred-items.md`. Not Phase 5's concern.

## User Setup Required

None -- no external service configuration required. The explorer reuses existing OpenAI/OpenRouter and LangSmith credentials already in `.env`.

## Next Phase Readiness

Plan 03 (parent-tool-and-modes) can now:
- `from services.explorer_service import run_exploration` -- generator ready
- Define `EXPLORE_KB_TOOL` schema in `backend/routers/chat.py` (next to existing KB_*_TOOL constants)
- Add `explore_kb` branch in `execute_tool()` that calls `run_exploration(user_id, query, mode)` and bridges yields into the SSE `tool_event` stream
- Reuse `EXPLORER_SCENARIOS["find_similar_azul"]` from explorer_fixtures.py for mode='find_similar' integration test
- Reuse `_make_fake_settings()` pattern (or import it directly) for any new tests that need to override explorer Settings

Plan 04 (frontend-streaming-ui) can:
- Subscribe to SSE `tool_event` rows where `tool=explore_kb` AND `type=sub_event` to render nested sub-tool indicators
- Use the documented sub_event payload shapes to type the frontend event handlers

No blockers. No concerns.

## Self-Check: PASSED

All 4 expected files exist on disk:
- `backend/services/explorer_service.py` -- 329 lines, importable, `run_exploration` is a generator function, `_explorer_tool_schemas()` returns 5 KB schemas
- `backend/tests/test_explorer_service.py` -- 17 active tests, 2 skipped (Plan 03)
- `backend/tests/test_explorer_tools.py` -- 6 active tests, 0 skipped
- `.planning/phases/05-explorer-sub-agent/05-02-explorer-service-SUMMARY.md` -- this file

Both task commits exist in git history:
- `10d45a7` (Task 1: explorer_service.py)
- `79e8a23` (Task 2: activated unit tests)

Final test run: `17 passed, 2 deselected, 1 warning in 2.59s`.

---
*Phase: 05-explorer-sub-agent*
*Completed: 2026-04-16*
