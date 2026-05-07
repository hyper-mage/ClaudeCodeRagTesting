---
phase: 05-deploy-frontend-to-cloudflare-pages
verified: 2026-05-07T13:03:30Z
status: passed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: unknown
  gaps_closed:
    - "Public CF Pages URL reachable serving SPA"
    - "VITE_API_BASE_URL baked to absolute Fly URL"
    - "Deep-link refresh returns SPA via _redirects"
    - "Fly CORS_ALLOWED_ORIGINS overwritten to CF origin"
    - "Bundle leak grep clean (SEC-07 re-pass)"
  gaps_remaining: []
  regressions: []
---

# Phase 5: Deploy Frontend to Cloudflare Pages — Verification Report

**Phase Goal:** The Vite SPA is live at a public Cloudflare Pages URL, pointing its API calls at the Fly backend, with correct SPA deep-link refresh behavior.
**Verified:** 2026-05-07T13:03:30Z
**Status:** passed
**Re-verification:** Yes — verifying after a prior phase iteration that had outstanding deploy work; this run confirms the live deployed state matches the plan contract.

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                              | Status     | Evidence                                                                                                                                            |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Public URL `https://boardgame-rag-prod.pages.dev` returns SPA login page with no console errors                                    | ✓ VERIFIED | Live `curl -fsSI /` → HTTP/1.1 200 + `content-type: text/html`; SUMMARY notes title "Agentic RAG", bundle `assets/index-CvZieiJm.js`, D-13 step 1 PASS |
| 2   | Frontend Network requests target absolute `https://boardgame-rag-prod.fly.dev/...` (not same-origin)                               | ✓ VERIFIED | `frontend/src/lib/api.ts:3` reads `import.meta.env.VITE_API_BASE_URL`; CF Pages Production env var sets it to Fly URL at build time; D-13 step 5 SSE chat streamed from Fly origin (PASS) |
| 3   | Hard-refresh of deep route `/documents` returns SPA (200 text/html), not CF 404                                                    | ✓ VERIFIED | Live `curl -fsSI /documents` → HTTP/1.1 200 + `content-type: text/html`; D-13 step 4 hard-refresh PASS                                              |
| 4   | After `flyctl secrets set`, cross-origin SSE chat from CF origin to Fly succeeds without CORS rejection                            | ✓ VERIFIED | Fly CORS digest delta `95c5bee9e20ee3ba` → `a3f4b150250b90ce`; live `curl /api/health` → `{"status":"ok"}`; D-13 step 5 SSE chat PASS               |
| 5   | Production bundle on the deployed CF URL contains zero matches for `service_role / sk-proj- / sk-or- / sb_secret_` (SEC-07 re-run) | ✓ VERIFIED | SUMMARY: 689 KB bundle grep returned 0 matches; embedded JWT decoded `role:anon` (Pitfall 6 defense)                                                |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                         | Expected                                                          | Status     | Details                                                                                              |
| -------------------------------- | ----------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------- |
| `frontend/public/_redirects`     | SPA catch-all rewrite rule: `/* /index.html 200`                  | ✓ VERIFIED | Read confirms exactly `/* /index.html 200`; committed in `e132d4f`                                   |
| `frontend/.nvmrc`                | Node 20 pin matching CF `NODE_VERSION` env var                    | ✓ VERIFIED | Read confirms exactly `20`; committed in `e132d4f`                                                   |
| `frontend/dist/_redirects`       | Built artifact proving Vite copies `public/_redirects` verbatim   | ✓ VERIFIED | Live deploy serves SPA on `/documents` — `_redirects` would not fire if Vite hadn't copied it; SUMMARY confirms local `npm run build` produced `dist/_redirects` |

### Key Link Verification

| From                                          | To                                              | Via                                                                              | Status   | Details                                                                                                                                                       |
| --------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| frontend (CF Pages bundle)                    | `https://boardgame-rag-prod.fly.dev`            | `VITE_API_BASE_URL` baked at build time, consumed by `apiFetch`/`apiStream`      | ✓ WIRED  | `frontend/src/lib/api.ts:3` reads env var; Phase 1 prefix wiring intact; D-13 step 5 SSE confirms requests hit Fly origin                                     |
| `https://boardgame-rag-prod.pages.dev/<deep>` | `/index.html` (200)                             | `frontend/public/_redirects` → `dist/_redirects` → CF Pages serves `index.html`  | ✓ WIRED  | Live curl `/documents` → 200 text/html; hard-refresh PASS in D-13 step 4                                                                                      |
| Fly secret `CORS_ALLOWED_ORIGINS`             | Browser cross-origin policy                     | `flyctl secrets set ... -a boardgame-rag-prod` (overwrites Phase 4 placeholder)  | ✓ WIRED  | Digest changed `95c5bee9e20ee3ba` → `a3f4b150250b90ce`; rolling restart on both machines; SSE chat from CF origin succeeded without CORS rejection             |

### Data-Flow Trace (Level 4)

| Artifact                       | Data Variable                                  | Source                                                          | Produces Real Data | Status     |
| ------------------------------ | ---------------------------------------------- | --------------------------------------------------------------- | ------------------ | ---------- |
| Deployed SPA bundle            | `import.meta.env.VITE_API_BASE_URL`            | CF Pages Production env var (baked at build time)               | Yes                | ✓ FLOWING  |
| Fly CORS allowlist enforcement | `Settings.cors_origins_list`                   | Fly secret `CORS_ALLOWED_ORIGINS` (env var on running machines) | Yes                | ✓ FLOWING  |
| `/documents` SPA fallback      | CF Pages routing rule (`/* /index.html 200`)   | `frontend/public/_redirects` → `dist/_redirects` (verbatim copy) | Yes                | ✓ FLOWING  |

### Behavioral Spot-Checks

| Behavior                                              | Command                                                          | Result                                       | Status |
| ----------------------------------------------------- | ---------------------------------------------------------------- | -------------------------------------------- | ------ |
| Public CF Pages root serves SPA                       | `curl -fsSI https://boardgame-rag-prod.pages.dev/`               | HTTP/1.1 200 + `content-type: text/html`     | ✓ PASS |
| Deep-link `/documents` returns SPA (not CF 404)       | `curl -fsSI https://boardgame-rag-prod.pages.dev/documents`      | HTTP/1.1 200 + `content-type: text/html`     | ✓ PASS |
| Fly backend health endpoint reachable post-CORS-set   | `curl -fsS https://boardgame-rag-prod.fly.dev/api/health`        | `{"status":"ok"}`                            | ✓ PASS |

All probes ran in <2s wall-clock; no state mutations.

### Requirements Coverage

| Requirement | Source Plan         | Description                                                                                                                                            | Status      | Evidence                                                                                                  |
| ----------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | --------------------------------------------------------------------------------------------------------- |
| DEPLOY-05   | `05-01-PLAN.md`     | Developer can push the frontend build to Cloudflare Pages and reach a public URL that loads the SPA with correct deep-link refresh behavior (`_redirects`) | ✓ SATISFIED | All 5 truths VERIFIED; live URL serves SPA + deep-link works; REQUIREMENTS.md row 15 marked `[x]` and table row marks `Complete` |

No orphaned requirements: REQUIREMENTS.md lists DEPLOY-05 as the sole Phase 5 ID, and PLAN frontmatter declares it.

### Anti-Patterns Found

| File                          | Line | Pattern | Severity | Impact |
| ----------------------------- | ---- | ------- | -------- | ------ |
| (none)                        | —    | —       | —        | —      |

The two repo artifacts (`_redirects`, `.nvmrc`) are single-line config files with no code surface to scan; SUMMARY's deviation note (CF Workers→Pages re-do) was a dashboard-flow correction with no in-repo footprint.

### Human Verification Required

(None outstanding for Phase 5 — D-13 5/5 PASS already user-confirmed. Phase 6 owns SEC-01 Auth-redirect URL config; out of scope here.)

### Gaps Summary

No gaps. All 5 must-have observable truths are verified by a combination of live HTTP probes (CF Pages root, `/documents` deep-link, Fly `/api/health`), source-code wiring inspection (`frontend/src/lib/api.ts` reading `VITE_API_BASE_URL`), in-repo artifact verification (`_redirects` + `.nvmrc` exact contents, committed in `e132d4f`), Fly secret digest delta evidence (`95c5bee9e20ee3ba` → `a3f4b150250b90ce`), bundle leak-grep evidence (0 matches; JWT `role:anon`), and the user-confirmed D-13 5/5 PASS browser checklist (login + cross-origin SSE chat both succeeded). REQUIREMENTS.md correctly reflects `DEPLOY-05` as Complete. Phase 5 goal — "Vite SPA live at public CF Pages URL, pointing at Fly backend, with correct SPA deep-link refresh" — is achieved.

The single SUMMARY-noted deviation (CF dashboard initially created a Worker instead of a Pages project, rejected by `_redirects` validator code 10021) was resolved out-of-repo by recreating as Pages; documented for future phases and does not affect the verified end-state.

---

_Verified: 2026-05-07T13:03:30Z_
_Verifier: Claude (gsd-verifier)_
