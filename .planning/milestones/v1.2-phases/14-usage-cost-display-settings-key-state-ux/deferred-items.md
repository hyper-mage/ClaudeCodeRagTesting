# Deferred Items — Phase 14

Out-of-scope discoveries logged during execution. NOT fixed (do not belong to the executing plan).

## Pre-existing `npm run lint` errors (discovered during 14-02 verification)

These 5 ESLint errors exist on base `caf3dec` in files NOT touched by Plan 14-02. The two hook
files modified by 14-02 (`useChat.ts`, `useKeyStatus.ts`) lint clean. `npm run build` (strict tsc)
passes. Listed here so a future cleanup plan can address them; out of scope for 14-02.

- `frontend/src/components/FileUpload.tsx:5:56` — `@typescript-eslint/no-explicit-any` (Unexpected any)
- `frontend/src/contexts/AuthContext.tsx:48:17` — `react-refresh/only-export-components`
- `frontend/src/contexts/ToastContext.tsx:96:17` — `react-refresh/only-export-components`
- `frontend/src/pages/ChatPage.tsx:52:5` — `react-hooks/set-state-in-effect` (note: ChatPage is edited in Wave 3 Plan 03 — may be resolved there)
- `frontend/src/test/themeBootstrap.test.ts:24:17` — `@typescript-eslint/no-unused-vars` (`_query`)
