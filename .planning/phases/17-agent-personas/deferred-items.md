# Phase 17 — Deferred Items (out of scope for the current plans)

## Pre-existing frontend lint baseline (discovered during 17-10)

`cd frontend && npm run lint` reports **5 pre-existing errors** on the clean tree (confirmed
via `git stash` — present WITHOUT any 17-10 wiring changes). None are introduced by the persona
wiring. Out of scope for 17-10 (scope boundary: only auto-fix issues directly caused by the
task's changes). Left untouched:

| File | Loc | Rule |
|------|-----|------|
| `frontend/src/components/FileUpload.tsx` | 5:56 | `@typescript-eslint/no-explicit-any` |
| `frontend/src/contexts/AuthContext.tsx` | 48:17 | `react-refresh/only-export-components` |
| `frontend/src/contexts/ToastContext.tsx` | 96:17 | `react-refresh/only-export-components` |
| `frontend/src/pages/ChatPage.tsx` | 66:5 | `react-hooks/set-state-in-effect` (the pre-existing `loadThreads()` effect — NOT the new `/api/personas` effect) |
| `frontend/src/test/themeBootstrap.test.ts` | 24:17 | `@typescript-eslint/no-unused-vars` (`_query`) |

These predate v1.3 (all in v1.2 files or the pre-existing `loadThreads` effect). Tracked for a
future lint-cleanup pass; the production build (`tsc -b && vite build`) is green.
