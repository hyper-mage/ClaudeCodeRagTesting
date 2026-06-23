# Phase 12 — Deferred Items

Out-of-scope discoveries logged during execution (SCOPE BOUNDARY). NOT fixed here —
these are pre-existing issues in files unrelated to the current plan's changes.

## Pre-existing test-collection/env failures (discovered during 12-03 full-suite run)

These predate this plan and are unrelated to the 12-03 router/schema/main changes.
The 12-03 changes touch only `backend/models/schemas.py`, `backend/routers/models.py`,
and `backend/main.py`; none of the failing files import or depend on those.

1. **`tests/test_e2e_subagent.py` — collection error: `KeyError: 'VITE_SUPABASE_URL'`**
   - Cause: module-level `os.environ["VITE_SUPABASE_URL"]` at import; the test loads the
     repo-root `.env` and targets a running API at `localhost:8000`. The worktree has no
     root `.env` and no running server — this is an E2E/integration test, not a unit test.
   - Disposition: out of scope. Run only with a live env + server.

2. **`tests/test_record_manager.py::test_check_duplicate_integration` and
   `::test_find_previous_version_integration` — `fixture 'user_id' not found`**
   - Cause: both `*_integration` node IDs request a `user_id` fixture that is not defined
     in the standard (offline) fixture set. They are live-Supabase integration tests.
   - Disposition: out of scope. Pre-existing; unrelated to 12-03.

Offline suite result for 12-03: **189 passed** (incl. all 3 new `test_models_api.py`
route tests + the 10 plan-01 `test_model_catalog.py` tests), excluding the two
integration files above. No regressions attributable to this plan.
