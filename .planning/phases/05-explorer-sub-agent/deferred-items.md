# Phase 05 Deferred Items

Out-of-scope discoveries logged during plan execution. Not to be fixed by this phase.

## From Plan 02 (explorer-service)

- **`tests/test_record_manager.py`** — 2 ERROR results during full-suite run
  (test_check_duplicate_integration, test_find_previous_version_integration). These
  are pre-existing integration tests requiring a real Supabase DB / fixtures that
  aren't loading. Last touched in commit c46981a ("module 3 completed"). Unrelated
  to Phase 5 work; predates this phase.
