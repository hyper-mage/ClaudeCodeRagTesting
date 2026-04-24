# Deferred Items — Phase 01-secrets-repo-hygiene

## Plan 01-02 — Out-of-scope ESLint errors (pre-existing from 04-04)

`npm run lint` fails with 4 errors in files NOT modified by 01-02:

- `frontend/src/components/FileUpload.tsx:5` — `@typescript-eslint/no-explicit-any`
- `frontend/src/contexts/AuthContext.tsx:45` — `react-refresh/only-export-components`
- `frontend/src/contexts/ToastContext.tsx:96` — `react-refresh/only-export-components`
- `frontend/src/pages/ChatPage.tsx:29` — `react-hooks/set-state-in-effect`

All predate this plan (last touched by commit 5991075 in phase 04-04). Fixing is out of scope for secrets/repo-hygiene plan. The three files modified by 01-02 (api.ts, useChat.ts, useDocuments.ts, useFolderTree.ts) pass lint cleanly.
