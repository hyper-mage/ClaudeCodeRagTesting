# Deferred Items — Phase 06.1

Pre-existing issues discovered during execution that are out of scope for
the current plan (per execute-plan SCOPE BOUNDARY rule).

## Pre-existing ESLint Errors (not introduced by Plan 06.1-01)

Surfaced when running `npm run lint` after Task 2 (06.1-01). All four errors
exist on `master` prior to Plan 06.1-01 and live in files this plan does
NOT touch.

| File | Line | Rule | Description |
|------|------|------|-------------|
| `frontend/src/components/FileUpload.tsx` | 5:56 | `@typescript-eslint/no-explicit-any` | Unexpected `any` in props type |
| `frontend/src/contexts/AuthContext.tsx` | 45:17 | `react-refresh/only-export-components` | Mixes `useAuth` hook export with `AuthProvider` component |
| `frontend/src/contexts/ToastContext.tsx` | 96:17 | `react-refresh/only-export-components` | Mixes `useToast` hook export with `ToastProvider` component |
| `frontend/src/pages/ChatPage.tsx` | 29:5 | `react-hooks/set-state-in-effect` | `loadThreads()` called synchronously in `useEffect` |

Status: not fixed. These predate Plan 06.1-01 and are unrelated to mobile
responsiveness. Track for a dedicated lint-cleanup plan in a future phase.
