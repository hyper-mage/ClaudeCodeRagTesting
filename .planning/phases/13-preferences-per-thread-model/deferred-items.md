# Phase 13 — Deferred Items

## D-13-03-A — test_deprecated_model_fallback.py (2 RED scaffolds) belong to Plan 13-04

- **Found during:** Plan 13-03 Task 3 (full-suite wave-merge gate).
- **Tests:** `test_deprecated_model_fallback.py::test_inserts_notice_and_falls_back`,
  `test_notice_excluded_from_history`.
- **Status:** RED by design. Authored in Plan 13-01 (commit df052d4) as Wave 0 scaffolds for
  the `notice`-role insertion + LLM-history-exclusion logic in `chat.py`.
- **Why out of scope for 13-03:** Plan 13-03 ships the preference WRITE endpoints only
  (GET/PUT /api/preferences, PATCH /api/threads/{id}); `chat.py` resolution/notice logic is
  UNCHANGED. The 13-03 plan explicitly states "Plans 03/04 turn them green" — these two are
  Plan 13-04's surface.
- **Verification of non-regression:** `git diff 1a24f71~1 HEAD` touches neither
  `tests/test_deprecated_model_fallback.py` nor `routers/chat.py`; both tests were already RED
  before 13-03 began.
- **Resolution:** Plan 13-04 (notice-role / deprecated-model fallback). No new plan needed.

## D-13-03-B — test_record_manager.py integration cases (pre-existing debt, carried from STATE.md)

- **Tests:** `test_record_manager.py::test_check_duplicate_integration`,
  `test_find_previous_version_integration`.
- **Status:** ERROR — reference a missing `user_id` fixture (conftest provides only
  `test_user_id` / `mock_user_id`). Pre-dates v1.1.
- **Out of scope:** Documented in STATE.md Pending Todos and in the 13-03 plan's Task 3
  acceptance criteria ("may remain skipped/failing as documented"). Fix in a future
  plan-checker pass.
