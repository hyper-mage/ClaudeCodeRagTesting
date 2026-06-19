# Phase 10 — Deferred Items

Out-of-scope discoveries logged during execution. NOT fixed in-plan (SCOPE BOUNDARY rule).

## D-10-A: Pre-existing `react-hooks/set-state-in-effect` lint errors in ChatPage.tsx

- **Found during:** Plan 10-03, Task 2 verify (`cd frontend && npm run lint`)
- **Where:** `frontend/src/pages/ChatPage.tsx` (4 errors — `loadThreads()`, `loadMessages()`, and related `useEffect` setState calls; rule `react-hooks/set-state-in-effect`)
- **Pre-existing:** Confirmed present on commit `f30b364` (the committed tree before Task 2), reproduced via `git stash` — predates Plan 10-03 and is in a file this plan does not touch.
- **Why deferred:** Out of scope per the SCOPE BOUNDARY rule (only auto-fix issues directly caused by the current task's changes). The new Plan 10-03 files (`SettingsPage.tsx`, `useKeyStatus.ts`, `pkce.ts`, `sentry.ts`) are lint-clean (`npx eslint <those files>` exits 0). The rule appears to have been promoted to an error by a newer `eslint-plugin-react-hooks` after Phase 8.
- **Suggested owner:** A future frontend lint-cleanup pass (or whichever plan next touches ChatPage's effect wiring). Low risk; not a runtime bug — the effects work, the rule flags a perf/style smell.
