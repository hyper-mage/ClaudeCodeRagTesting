# Phase 08 — Deferred Items

Out-of-scope issues discovered during execution but not fixed (per executor scope-boundary rule).

## Pre-existing test failures (not caused by Phase 08)

### `backend/tests/test_record_manager.py::test_check_duplicate_integration`

- **Discovered during:** Plan 08-02 full-suite verification.
- **Symptom:** `ERROR at setup of test_check_duplicate_integration — fixture 'user_id' not found`.
- **Root cause:** The integration test function signature requests a `user_id: str` fixture that has never been defined in `conftest.py`. The test was authored in Module 3 (commit `c46981a`) and appears to have been runnable only via `python -m tests.test_record_manager` per the module docstring — `pytest` collection picks it up but the fixture is missing.
- **Why not fixed here:** Out of scope for Plan 08-02 (demo-bootstrap router/service). Fixing it requires either (a) adding a `user_id` fixture to `conftest.py` that mints a real or stub Supabase user, or (b) marking the test `integration` + filtering it out by default.
- **Suggested follow-up:** Address in a dedicated maintenance plan or skip-mark the test if it cannot be made to run cleanly. Existing `mock_user_id` fixture is the obvious rename target.
