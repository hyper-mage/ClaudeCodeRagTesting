# Deferred Items — Phase 11

Out-of-scope discoveries logged during execution (NOT fixed — pre-existing, unrelated to the current task's changes).

## From 11-01 execution

- **Pre-existing collection errors in `backend/tests/test_record_manager.py`** (lines 83, 120): `test_check_duplicate_integration` and `test_find_previous_version_integration` fail at setup with `fixture 'user_id' not found`. These are pre-existing failures present on the plan base commit, in a file NOT part of plan 11-01's `files_modified`. They predate this work and are out of scope. The rest of the suite (150 tests) passes. Fix belongs to whoever owns `test_record_manager.py` (likely a renamed/removed `user_id` fixture).
