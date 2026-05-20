# Phase 08 — Deferred Items

Out-of-scope issues discovered during execution but not fixed (per executor scope-boundary rule).

## Pre-existing backend test failures (not caused by Phase 08)

### `backend/tests/test_record_manager.py::test_check_duplicate_integration`

- **Discovered during:** Plan 08-02 full-suite verification.
- **Symptom:** `ERROR at setup of test_check_duplicate_integration — fixture 'user_id' not found`.
- **Root cause:** The integration test function signature requests a `user_id: str` fixture that has never been defined in `conftest.py`. The test was authored in Module 3 (commit `c46981a`) and appears to have been runnable only via `python -m tests.test_record_manager` per the module docstring — `pytest` collection picks it up but the fixture is missing.
- **Why not fixed here:** Out of scope for Plan 08-02 (demo-bootstrap router/service). Fixing it requires either (a) adding a `user_id` fixture to `conftest.py` that mints a real or stub Supabase user, or (b) marking the test `integration` + filtering it out by default.
- **Suggested follow-up:** Address in a dedicated maintenance plan or skip-mark the test if it cannot be made to run cleanly. Existing `mock_user_id` fixture is the obvious rename target.

## Plan 08-04 — Frontend Lint Pre-existing Errors

Discovered: 2026-05-18 during Plan 08-04 execution.

`npm run lint` against the frontend reports **4 pre-existing errors** that are NOT caused by Plan 08-04's changes:

1. `frontend/src/components/FileUpload.tsx:5:56` — `@typescript-eslint/no-explicit-any` (Unexpected any. Specify a different type).
2. `frontend/src/contexts/AuthContext.tsx:48:17` — `react-refresh/only-export-components` (`useAuth` non-component named export coexisting with `AuthProvider` component). Pre-existing; Plan 08-04 edits did not touch the `useAuth` export, only the `AuthContextType` interface + provider value object. Line number shifted from 45 → 48 because of the new `isAnon` lines.
3. `frontend/src/contexts/ToastContext.tsx:96:17` — `react-refresh/only-export-components` (same pattern as AuthContext — `useToast` named export coexisting with `ToastProvider` component).
4. `frontend/src/pages/ChatPage.tsx:37:5` — `react-hooks/set-state-in-effect` (`loadThreads()` in a useEffect body calls setState synchronously). Pre-existing; Plan 08-04 edit only added `retryLastUserMessage` to the destructure on line 24 and threaded it to `<ChatContainer onRetry={...}>`. Line number shifted from 36 → 37 because the destructure spans 2 lines now.

All four errors exist on `master` HEAD prior to Plan 08-04's work. The lint contract for this plan was the **build green** mandate from PLAN.md §verify, which passes (zero TS errors, 2321 modules transformed successfully).

**Recommendation:** Address in a follow-up cleanup plan that extracts `useAuth`/`useToast` to dedicated `hooks/` files (resolves errors 2+3), types FileUpload prop (error 1), and refactors ChatPage's useEffect pattern (error 4). Out of scope for Phase 8.
