---
phase: 01-secrets-repo-hygiene
plan: 02
subsystem: frontend
tags: [vite, react, typescript, env-vars, sse, fetch, supabase-auth]

requires:
  - phase: 01-secrets-repo-hygiene
    provides: VITE_API_BASE_URL convention (documented in 01-CONTEXT.md D-05..D-08)
provides:
  - Centralized apiFetch (JSON) and apiStream (raw Response for SSE) helpers in frontend/src/lib/api.ts
  - Every frontend HTTP call routes through VITE_API_BASE_URL prefix (empty default preserves dev proxy)
  - Zero direct fetch('/api/...') call sites remain in frontend/src/hooks/
  - Verified production bundle contains no backend-only secret env names
affects: [02-backend-hosting-fly, 05-frontend-hosting-cloudflare-pages]

tech-stack:
  added: []
  patterns:
    - "All frontend API calls go through apiFetch/apiStream (centralized token attach + base URL prefix)"
    - "Streaming endpoints use apiStream companion helper (returns raw Response for reader.read())"
    - "Content-Type skipped for FormData bodies to preserve multipart boundary"

key-files:
  created: []
  modified:
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useChat.ts
    - frontend/src/hooks/useDocuments.ts
    - frontend/src/hooks/useFolderTree.ts

key-decisions:
  - "Companion function (apiStream) chosen over overload/flag — clearer at call sites (D-06)"
  - "Default API_BASE to empty string when VITE_API_BASE_URL unset — preserves dev Vite proxy (D-07)"
  - "buildHeaders shared between apiFetch and apiStream — single source of truth for token attach"
  - "apiFetch skips Content-Type for FormData bodies so multipart uploads retain boundary"

patterns-established:
  - "VITE_API_BASE_URL prefix convention: const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''"
  - "Streaming-aware companion helper pattern (apiFetch + apiStream)"
  - "Error wrapping pattern: try/catch + rethrow with prefix (preserves existing 'X failed: ...' shape)"

requirements-completed: [DEPLOY-06, SEC-07]

duration: 18min
completed: 2026-04-23
---

# Phase 01 Plan 02: Frontend API Base URL Centralization Summary

**Centralized 16 direct fetch('/api/...') call sites behind apiFetch/apiStream helpers that prefix every path with import.meta.env.VITE_API_BASE_URL, enabling one frontend codebase for both dev (Vite proxy) and prod (absolute Fly URL).**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-23T22:45:22Z
- **Completed:** 2026-04-23T23:03:49Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Rewrote `frontend/src/lib/api.ts` with `apiFetch` (JSON) and `apiStream` (raw Response) helpers, both prefixed with `VITE_API_BASE_URL ?? ''`
- Migrated all 2 fetch sites in `useChat.ts` (loadMessages → apiFetch, SSE streaming → apiStream)
- Migrated all 5 fetch sites in `useDocuments.ts` (loadDocuments, uploadDocument FormData, deleteDocument, bulk delete/move)
- Migrated all 9 fetch sites in `useFolderTree.ts` (folders CRUD, contents, move, rename operations)
- Verified production Vite build (`frontend/dist/`) contains zero occurrences of 6 backend-only secret env names (SEC-07)
- Streaming SSE chat loop preserved byte-for-byte inside the new apiStream caller

## Task Commits

1. **Task 1: Extend api.ts with API_BASE prefix + apiStream helper** — `aef8656` (feat)
2. **Task 2: Migrate useChat.ts, useDocuments.ts, useFolderTree.ts to apiFetch/apiStream** — `765393e` (feat)
3. **Task 3: Production build + SUPABASE_SERVICE_ROLE_KEY grep guard** — `63766ef` (chore, verification-only)

## Files Created/Modified
- `frontend/src/lib/api.ts` — Rewrote with API_BASE prefix + apiStream companion; shared buildHeaders
- `frontend/src/hooks/useChat.ts` — loadMessages via apiFetch; sendMessage SSE via apiStream
- `frontend/src/hooks/useDocuments.ts` — 5 sites migrated to apiFetch (FormData branch handled)
- `frontend/src/hooks/useFolderTree.ts` — 9 sites migrated to apiFetch

## Decisions Made
- **D-06 resolved → companion function:** Separate `apiStream` for SSE instead of an overload or a `streaming: true` flag; call sites read more naturally
- **D-07 resolved → empty-string default:** `?? ''` for API_BASE keeps `npm run dev` unchanged (Vite proxy kicks in); prod injects the absolute Fly URL
- **D-08 respected:** No trailing slash on prod value; paths keep their `/api/...` prefix

## Deviations from Plan

None — plan executed exactly as written. All three tasks hit their acceptance criteria on the first pass.

## Issues Encountered
- Frontend `node_modules/` absent in fresh worktree — ran `npm install` (22s, 300 packages) before verification. Not a source change; resolved transparently.
- Pre-existing ESLint errors in files not modified by this plan (FileUpload.tsx, AuthContext.tsx, ToastContext.tsx, ChatPage.tsx) — all from phase 04-04 commit 5991075. Logged to `.planning/phases/01-secrets-repo-hygiene/deferred-items.md`. Out of scope per GSD scope boundary rule (only auto-fix issues caused by current task). The four files modified by this plan pass lint cleanly.

## Verification

### Automated (all PASS)
- `grep -Fn 'import.meta.env.VITE_API_BASE_URL' frontend/src/lib/api.ts` → 1 match
- `grep -Fn 'export async function apiFetch' frontend/src/lib/api.ts` → 1 match
- `grep -Fn 'export async function apiStream' frontend/src/lib/api.ts` → 1 match
- `grep -c '${API_BASE}${path}' frontend/src/lib/api.ts` → 2 (one per helper)
- `grep -rn "fetch('/api" frontend/src/hooks/` → 0 matches
- `grep -rn 'fetch(\`/api' frontend/src/hooks/` → 0 matches
- `apiFetch` usage: useDocuments.ts = 6, useFolderTree.ts = 10, useChat.ts = 2 (import+call)
- `apiStream` usage: useChat.ts = 2 (import+call)
- `cd frontend && npx tsc --noEmit -p tsconfig.app.json` → exit 0

### Production bundle grep (SEC-07)
- `SUPABASE_SERVICE_ROLE_KEY` in `frontend/dist/` → 0 matches PASS
- `SUPABASE_JWT_SECRET` in `frontend/dist/` → 0 matches PASS
- `OPENROUTER_API_KEY` in `frontend/dist/` → 0 matches PASS
- `OPENAI_API_KEY` in `frontend/dist/` → 0 matches PASS
- `LANGSMITH_API_KEY` in `frontend/dist/` → 0 matches PASS
- `TAVILY_API_KEY` in `frontend/dist/` → 0 matches PASS
- `/api/threads` in `frontend/dist/` → present (API paths shipped)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- DEPLOY-06 and SEC-07 requirements satisfied for v1.1 portfolio deployment milestone.
- Frontend is now ready to be deployed anywhere: set `VITE_API_BASE_URL=https://<fly-app>.fly.dev` at build time and the same codebase ships.
- Phase 2 (backend hosting on Fly) can now reason about a stable, env-driven origin on the client side.
- Phase 5 (Cloudflare Pages) inherits this convention automatically.

## Self-Check: PASSED

- frontend/src/lib/api.ts: FOUND (commit aef8656)
- frontend/src/hooks/useChat.ts: FOUND (commit 765393e)
- frontend/src/hooks/useDocuments.ts: FOUND (commit 765393e)
- frontend/src/hooks/useFolderTree.ts: FOUND (commit 765393e)
- Commit aef8656: FOUND
- Commit 765393e: FOUND
- Commit 63766ef: FOUND

---
*Phase: 01-secrets-repo-hygiene*
*Completed: 2026-04-23*
