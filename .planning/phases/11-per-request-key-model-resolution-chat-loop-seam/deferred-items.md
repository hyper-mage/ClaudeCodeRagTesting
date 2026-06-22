# Deferred Items — Phase 11

Out-of-scope discoveries logged during execution (NOT fixed — pre-existing, unrelated to the current task's changes).

## From 11-01 execution

- **Pre-existing collection errors in `backend/tests/test_record_manager.py`** (lines 83, 120): `test_check_duplicate_integration` and `test_find_previous_version_integration` fail at setup with `fixture 'user_id' not found`. These are pre-existing failures present on the plan base commit, in a file NOT part of plan 11-01's `files_modified`. They predate this work and are out of scope. The rest of the suite (150 tests) passes. Fix belongs to whoever owns `test_record_manager.py` (likely a renamed/removed `user_id` fixture).

## From 11-03 execution

- **Pre-existing collection error in `backend/tests/test_e2e_subagent.py`** (line 11): `KeyError: 'VITE_SUPABASE_URL'`. This is a live E2E test that reads `os.environ["VITE_SUPABASE_URL"]` at import and hits `localhost:8000` + a real Supabase project. It errors at collection when `.env` is absent (e.g. an isolated worktree). Not part of plan 11-03's `files_modified`; environmental, not a code defect — out of scope. The `test_record_manager.py` integration errors (above) also recurred for the same reason. The rest of the unit suite is green (165 passed, 9 Wave-0 stubs skipped).
