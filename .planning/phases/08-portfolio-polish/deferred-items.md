# Phase 08 — Deferred Items

Items discovered during execution that are out of scope for the current plan.

## Plan 08-04 — Frontend Lint Pre-existing Errors

Discovered: 2026-05-18 during Plan 08-04 execution.

`npm run lint` against the frontend reports **4 pre-existing errors** that are NOT caused by this plan's changes:

1. `frontend/src/components/FileUpload.tsx:5:56` — `@typescript-eslint/no-explicit-any` (Unexpected any. Specify a different type).
2. `frontend/src/contexts/AuthContext.tsx:48:17` — `react-refresh/only-export-components` (`useAuth` non-component named export coexisting with `AuthProvider` component). Pre-existing; my Plan 08-04 edits did not touch the `useAuth` export, only the `AuthContextType` interface + provider value object. Line number shifted from 45 → 48 because of the new `isAnon` lines.
3. `frontend/src/contexts/ToastContext.tsx:96:17` — `react-refresh/only-export-components` (same pattern as AuthContext — `useToast` named export coexisting with `ToastProvider` component).
4. `frontend/src/pages/ChatPage.tsx:37:5` — `react-hooks/set-state-in-effect` (`loadThreads()` in a useEffect body calls setState synchronously). Pre-existing; my edit only added `retryLastUserMessage` to the destructure on line 24 and threaded it to `<ChatContainer onRetry={...}>`. Line number shifted from 36 → 37 because the destructure spans 2 lines now.

All four errors exist on `master` HEAD prior to this plan's work (verified via `git diff HEAD --stat -- <file>` returning empty for the offending files in the case of FileUpload, ToastContext, and ChatPage on the offending line). The lint contract for this plan was the **build green** mandate from PLAN.md §verify, which passes (zero TS errors, 2321 modules transformed successfully).

**Recommendation:** Address in a follow-up cleanup plan that extracts `useAuth`/`useToast` to dedicated `hooks/` files (resolves errors 2+3), types FileUpload prop (error 1), and refactors ChatPage's useEffect pattern (error 4). Out of scope for Phase 8.
