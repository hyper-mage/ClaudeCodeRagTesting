# Phase 5: Deploy Frontend to Cloudflare Pages - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 05-deploy-frontend-to-cloudflare-pages
**Areas discussed:** Deploy mechanism, CORS update scope, Project name + Preview deploys, Build config + Verification

---

## Deploy mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Git auto-deploy | Connect GitHub repo → CF builds on push to `main`. Build cmd + env vars set in dashboard once. Zero-touch after setup. | ✓ |
| wrangler CLI | Build locally, push via `wrangler pages deploy frontend/dist`. Requires `CLOUDFLARE_API_TOKEN` on laptop. | |
| Dashboard upload | Manual drag-drop dist to dashboard each time. | |

**User's choice:** Git auto-deploy (recommended).
**Notes:** User asked "what is CF Pages" before answering — clarified Cloudflare Pages = static SPA host on CF edge (free tier, unlimited bandwidth, 500 builds/month) and the three deploy mechanisms before re-asking.

---

## CORS update scope

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 5 | Set `CORS_ALLOWED_ORIGINS` to CF URL here, after CF deploy lands. Required for Phase 5 success criterion #4. | ✓ |
| Defer to Phase 6 | Phase 6 owns SEC-02 (CORS hardening). Bundle there. Trade-off: Phase 5 verification can't fully prove frontend↔backend until Phase 6. | |
| Split | Phase 5 sets prod origin so app works. Phase 6 hardens (rejection tests, preview-URL regex if needed). | |

**User's choice:** Phase 5 (recommended).
**Notes:** User asked "what does any of this mean" before answering — clarified what CORS is, what `CORS_ALLOWED_ORIGINS` does, the specific phase hand-off (Phase 4 D-08 → Phase 5), and which Phase 6 SEC items are adjacent. Re-asked and user picked Phase 5. Phase 6 retains hardening / rejection-path / preview-regex work as deferred ideas.

---

## Project name + Preview deploys

### Project slug

| Option | Description | Selected |
|--------|-------------|----------|
| boardgame-rag-prod | Mirrors Fly + Supabase + LangSmith. URL: `boardgame-rag-prod.pages.dev`. | ✓ |
| boardgame-rag | Shorter; drop `-prod` since CF only has one env. | |
| bgkb-rag | Even shorter; matches Phase 4 fallback. | |

**User's choice:** boardgame-rag-prod (recommended).

### Previews

| Option | Description | Selected |
|--------|-------------|----------|
| Disable, main only | Only `main` deploys. No preview subdomains → no CORS regex needed. | ✓ |
| Enable + add CORS regex | PR previews at `<hash>.<slug>.pages.dev`. Requires `allow_origin_regex` in backend. | |
| Enable but ignore | Preview deploys exist but won't reach backend (CORS blocks). | |

**User's choice:** Disable, main only (recommended).

---

## Build config + Verification

### Build config

| Option | Description | Selected |
|--------|-------------|----------|
| Root dir = `frontend/` | CF Pages: root `frontend`, build cmd `npm run build`, output `dist`. Cleaner. `envDir: '..'` irrelevant on CF (env vars come from dashboard). | ✓ |
| Root dir = `.` repo root | Build cmd `cd frontend && npm install && npm run build`, output `frontend/dist`. Slightly uglier. | |

**User's choice:** Root dir = `frontend/` (recommended).

### Verification

| Option | Description | Selected |
|--------|-------------|----------|
| Manual browser check | Load CF URL: login renders, Network tab shows Fly URL, deep-link refresh returns SPA. Documented as PLAN checklist. | ✓ |
| Scripted smoke | `frontend/scripts/cf_smoke.sh` headless checks (200 HTML, deep route SPA, secrets grep). | |
| Both | Scripted + manual. | |

**User's choice:** Manual browser check (recommended).
**Notes:** SSE end-to-end already covered by Phase 4 `fly_smoke.sh`; no need to duplicate.

---

## Claude's Discretion

- Exact Node version pin (planner reads `package-lock.json`)
- Whether to add `frontend/.nvmrc`
- Order of CF Pages dashboard steps (connect repo first vs env vars first)
- Whether to pre-create CF Pages project via Wrangler API or all-dashboard

## Deferred Ideas

- Custom domain on CF Pages — v1.2+
- Preview deploys with backend CORS regex — deferred indefinitely
- Scripted `cf_smoke.sh` — Phase 7 UptimeRobot covers it instead
- CORS rejection-path test — Phase 6 SEC-02
- `frontend/.nvmrc` — Claude's discretion at plan time
