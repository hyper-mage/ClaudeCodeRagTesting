---
phase: 05-explorer-sub-agent
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, pydantic, fixtures, contracts]

# Dependency graph
requires:
  - phase: 04-file-manager-ui
    provides: Folder hierarchy + KB tools tests baseline (test_folders_api.py patterns)
provides:
  - ExplorerResult / ExplorerFinding Pydantic contracts with hard caps
  - explorer_* Settings knobs (max_iterations, max_tool_calls, max_summary_chars, timeout, system_prompt)
  - Three test files (test_explorer_service.py, test_explorer_tools.py, test_explorer_integration.py) with skipif markers + contract assertions
  - Shared explorer_fixtures (mock_llm_client, make_tool_call, EXPLORER_SCENARIOS, stub_db_chain)
  - backend/pytest.ini with asyncio_mode=auto + strict-markers
  - pytest-asyncio==0.23.8 added to requirements
affects: [05-02-explorer-service, 05-03-parent-tool-and-modes, 05-04-frontend-streaming-ui]

# Tech tracking
tech-stack:
  added:
    - pytest-asyncio==0.23.8
  patterns:
    - "Pydantic Field(max_length=N, pattern='...') for structured-output hard caps"
    - "Centralized fixtures in tests/fixtures/ re-exported via conftest.py"
    - "Skip-marked tests with explicit downstream-plan reason strings (test scaffold pattern)"
    - "stub_db_chain helper: chainable Supabase mock independent of call ordering"

key-files:
  created:
    - backend/pytest.ini
    - backend/tests/conftest.py
    - backend/tests/fixtures/__init__.py
    - backend/tests/fixtures/explorer_fixtures.py
    - backend/tests/test_explorer_service.py
    - backend/tests/test_explorer_tools.py
    - backend/tests/test_explorer_integration.py
    - .planning/phases/05-explorer-sub-agent/05-01-test-scaffold-and-contracts-SUMMARY.md
  modified:
    - backend/models/schemas.py
    - backend/config.py
    - backend/requirements.txt

key-decisions:
  - "Used Pydantic Field(max_length=...) for caps so oversized output fails at validation, not silently downstream"
  - "Used Pydantic Field(pattern='^(deep_search|summarize|find_similar)$') for mode whitelisting instead of Literal so error messages are clearer at parse time"
  - "Test scaffolds use pytest.mark.skip with reason='... in Plan 0X' so collection succeeds and downstream plans see clear ownership"
  - "stub_db_chain returns the same MagicMock for every chain attribute so tests don't bind to call ordering -- prevents fragile mocks in Plan 03 integration tests"

patterns-established:
  - "Phase scaffold pattern: write failing/skipped tests + Pydantic contracts FIRST, then implement against them in subsequent plans"
  - "Shared fixtures pattern: centralize per-feature fixtures in tests/fixtures/{feature}_fixtures.py, re-export via conftest.py"

requirements-completed:
  - EXPL-01
  - EXPL-02
  - EXPL-05
  - EXPL-06

# Metrics
duration: 4 min
completed: 2026-04-16
---

# Phase 05 Plan 01: Test Scaffold and Contracts Summary

**Wave 0 explorer scaffolding: ExplorerResult/ExplorerFinding Pydantic contracts with hard caps, explorer_* Settings knobs, 23 test nodes across three files (5 contract tests passing, 18 skip-marked with downstream-plan ownership), and a reusable stub_db_chain fixture for Plan 03 integration tests.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-16T20:03:29Z
- **Completed:** 2026-04-16T20:07:31Z
- **Tasks:** 2
- **Files created/modified:** 10 (7 created, 3 modified)

## Accomplishments

- ExplorerResult / ExplorerFinding Pydantic models in `backend/models/schemas.py` with hard caps (synthesis ≤ 2000 chars, findings ≤ 8 items, excerpt ≤ 500 chars, mode whitelist of three values)
- Five explorer_* Settings fields added to backend/config.py with documented defaults from research (`explorer_max_iterations=6`, `explorer_max_tool_calls=10`, `explorer_max_summary_chars=3000`, `explorer_timeout=120`, plus the system prompt)
- Three test files created with import-clean collection (23 tests collected, 0 errors): test_explorer_service.py, test_explorer_tools.py, test_explorer_integration.py
- 5 contract tests for ExplorerResult/ExplorerFinding caps PASS NOW (Pydantic enforcement validated)
- Shared fixtures module backend/tests/fixtures/explorer_fixtures.py with `mock_llm_client`, `make_tool_call`, `make_response`, `EXPLORER_SCENARIOS` (3 scripted multi-turn sequences), and `stub_db_chain` helper for Plan 03
- backend/tests/conftest.py re-exports fixtures and provides `test_user_id` + `explorer_scenarios` pytest fixtures
- backend/pytest.ini added with `testpaths=tests`, `--strict-markers`, `asyncio_mode=auto` (no warnings about unrecognized `integration` marker)
- pytest-asyncio==0.23.8 installed (downgraded pytest 9.0.3 → 8.4.2 — compatible with all existing tests; full 68-test collection clean)

## Task Commits

Each task committed atomically (with --no-verify per parallel-executor protocol):

1. **Task 1: Add ExplorerResult/ExplorerFinding + explorer_* Settings + pytest config** — `7fe851e` (feat)
2. **Task 2: Test scaffolds + fixtures (3 test files, conftest.py, fixtures module)** — `8c45922` (test)

**Plan metadata:** _(filled by metadata commit)_

## Files Created/Modified

### Created
- `backend/pytest.ini` — pytest config: testpaths, strict markers, asyncio_mode
- `backend/tests/conftest.py` — sys.path bootstrap + re-exports of explorer fixtures
- `backend/tests/fixtures/__init__.py` — empty package marker
- `backend/tests/fixtures/explorer_fixtures.py` — shared explorer test helpers (132 lines)
- `backend/tests/test_explorer_service.py` — 4 contract tests + 9 skip-marked behavior tests
- `backend/tests/test_explorer_tools.py` — 6 skip-marked dispatcher tests for Plan 02
- `backend/tests/test_explorer_integration.py` — 4 skip-marked SSE sub_event tests for Plan 03

### Modified
- `backend/models/schemas.py` — added ExplorerFinding + ExplorerResult classes (extended import to include `Field`)
- `backend/config.py` — added 5 explorer_* fields to Settings between subagent block and Timeouts comment
- `backend/requirements.txt` — added `pytest-asyncio==0.23.8`

## Contract Shape

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

## Settings Added

| Field | Default | Purpose |
|-------|---------|---------|
| `explorer_system_prompt` | (KB Explorer prompt) | System prompt for explorer LLM |
| `explorer_max_iterations` | 6 | Max LLM turns in explorer loop |
| `explorer_max_tool_calls` | 10 | Max total tool invocations |
| `explorer_max_summary_chars` | 3000 | Soft synthesis budget guidance |
| `explorer_timeout` | 120 | Per-explorer-call timeout (seconds) |

## Skip-Marked Tests by Downstream Plan

### Owned by Plan 02 (explorer-service)
- `test_explorer_service.py::test_multi_step_loop` — multi-step traversal
- `test_explorer_service.py::test_tool_dispatch` — kb_* tool dispatch correctness
- `test_explorer_service.py::test_summarize_mode` — mode='summarize' behavior
- `test_explorer_service.py::test_iteration_budget` — max_iterations cap
- `test_explorer_service.py::test_tool_call_budget` — max_tool_calls cap
- `test_explorer_service.py::test_rls_isolation` — user-scoped private docs
- `test_explorer_tools.py::test_dispatch_kb_ls/tree/read/grep/glob` — 5 dispatcher tests
- `test_explorer_tools.py::test_tool_dispatch_unknown_returns_error_json` — graceful unknown tool

### Owned by Plan 03 (parent-tool-and-modes + integration)
- `test_explorer_service.py::test_find_similar_mode` — mode='find_similar' wiring
- `test_explorer_service.py::test_recommendation_seed` — conversation-derived seed query
- `test_explorer_integration.py::test_explore_kb_tool_registered` — parent advertises EXPLORE_KB_TOOL
- `test_explorer_integration.py::test_sub_events_emitted` — SSE 'tool_event' rows
- `test_explorer_integration.py::test_final_tool_result` — terminating tool_result event
- `test_explorer_integration.py::test_parent_call_id_links_subevents` — parent_call_id linkage

### Passing NOW (contract verification of Task 1 work)
- `test_explorer_result_rejects_oversized_synthesis`
- `test_explorer_result_rejects_too_many_findings`
- `test_explorer_finding_rejects_oversized_excerpt`
- `test_explorer_result_mode_pattern`
- `test_output_size_cap`

## stub_db_chain Helper

**Signature:** `stub_db_chain(execute_return=None) -> MagicMock`

**Behavior:** Returns a Supabase-style chainable MagicMock. Every chain-builder attribute (table/select/insert/update/delete/eq/neq/in_/is_/or_/and_/order/limit/single/maybe_single/range/ilike/like/contains/filter) returns the same mock so tests don't depend on chain ordering. Only `.execute().data` is meaningful — it returns `execute_return`.

**Intended consumer:** Plan 03 integration tests that need to patch `routers.chat.get_supabase` while exercising parent → explorer → SSE flow. Without this helper, Plan 03 tests would hand-roll fragile chain mocks (as Phase 04's `test_folders_api.py::_make_query_chain` does, but only for a fixed method list).

**Verified:** `c.table('t').select('*').eq('id','1').maybe_single().execute().data == {'id':'x'}` round-trips correctly.

## Decisions Made

- **Field(pattern=...) over Literal for mode** — clearer Pydantic ValidationError messages and easier to extend if a new mode is added later
- **Skip-marked tests instead of pytest.mark.xfail** — these aren't "expected failures", they're "not implemented yet by an upstream plan"; skip with `reason="... in Plan 0X"` makes ownership explicit
- **stub_db_chain returns the same mock for every attribute** — eliminates a category of false test failures where production code reorders chain calls
- **pytest-asyncio downgraded pytest 9 → 8.4.2** — accepted because all 68 existing tests still collect cleanly and pytest-asyncio 0.23.8 is the version pinned for SSE integration in Plan 03

## Deviations from Plan

None - plan executed exactly as written.

The plan's two tasks both have `tdd="true"` markers, but they are scaffolding/contract tasks (creating Pydantic models + test files), not RED-GREEN-REFACTOR feature tasks. The natural execution order (model first, then tests that import the model) was followed. The contract tests written in Task 2 act as the "RED equivalent" — they verify Task 1's Pydantic caps work, and they pass on first run because Task 1 implemented the contracts correctly.

## Issues Encountered

None — pytest-asyncio install transparently downgraded pytest from 9.0.3 to 8.4.2 (its supported upper bound), full collection still clean (68 tests, 0 errors).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Wave 0 complete. Plan 02 can:
- `from models.schemas import ExplorerResult, ExplorerFinding` — contracts ready
- `get_settings().explorer_max_iterations` etc. — budget knobs ready
- Implement explorer_service.run_exploration() against the existing skip-marked tests by un-skipping and asserting (no new test files needed)
- Reuse `mock_llm_client(EXPLORER_SCENARIOS["summarize_catan"])` for unit tests

Plan 03 can:
- Import `stub_db_chain` to patch Supabase in SSE integration tests
- Un-skip tests in test_explorer_integration.py and add real assertions
- Use `EXPLORER_SCENARIOS["find_similar_azul"]` for find-similar mode test

No blockers. No concerns.

## Self-Check: PASSED

All 8 expected files exist on disk:
- backend/pytest.ini
- backend/tests/conftest.py
- backend/tests/fixtures/__init__.py
- backend/tests/fixtures/explorer_fixtures.py
- backend/tests/test_explorer_service.py
- backend/tests/test_explorer_tools.py
- backend/tests/test_explorer_integration.py
- .planning/phases/05-explorer-sub-agent/05-01-test-scaffold-and-contracts-SUMMARY.md

Both task commits exist in git history:
- `7fe851e` (Task 1: contracts + Settings + pytest config)
- `8c45922` (Task 2: test scaffolds + fixtures)

---
*Phase: 05-explorer-sub-agent*
*Completed: 2026-04-16*
