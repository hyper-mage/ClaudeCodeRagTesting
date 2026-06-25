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

## D-13-06-A — pre-existing `react-hooks/set-state-in-effect` lint error in ChatPage.tsx

- **Found during:** Plan 13-06 Task 2 (eslint on touched files).
- **Location:** `frontend/src/pages/ChatPage.tsx` — the mount effect `useEffect(() => { loadThreads() }, [loadThreads])`.
- **Status:** ERROR — the new `react-hooks/set-state-in-effect` rule flags `loadThreads()` because
  it transitively calls `setThreads`. It is a false positive (the `setThreads` happens in a
  microtask after `await apiFetch(...)`, not synchronously in the effect body), and it PRE-EXISTS
  Plan 13-06 (confirmed via `git stash` → lint on HEAD: identical error at the same effect).
- **Out of scope (scope boundary):** Plan 13-06 did not author this effect; my NEW effects
  (catalog fetch, prefs/theme reconcile) use `.then().catch()` async patterns and are NOT flagged.
  Touching the pre-existing effect to silence the rule is unrelated churn.
- **Resolution:** address in a future ChatPage lint-cleanup pass (or a project-wide
  `react-hooks/set-state-in-effect` triage). No new plan needed.
