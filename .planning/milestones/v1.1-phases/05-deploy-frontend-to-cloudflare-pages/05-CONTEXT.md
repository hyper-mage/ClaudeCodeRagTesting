# Phase 5: Deploy Frontend to Cloudflare Pages - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the Vite SPA to a public Cloudflare Pages URL (`boardgame-rag-prod.pages.dev`) with API calls pointing at the Fly backend (`boardgame-rag-prod.fly.dev`) and SPA deep-link refresh working. Concretely:

1. CF Pages project connected to GitHub repo, auto-deploying on push to `main`. Root directory = `frontend/`, build command `npm run build`, output `dist`.
2. CF Pages env vars set: `VITE_API_BASE_URL=https://boardgame-rag-prod.fly.dev`, `VITE_SUPABASE_URL` (prod), `VITE_SUPABASE_ANON_KEY` (prod anon).
3. `frontend/public/_redirects` (`/* /index.html 200`) committed so deep-link refresh (e.g. `/documents`) returns SPA instead of CF 404.
4. Fly `CORS_ALLOWED_ORIGINS` overwritten from the Phase 4 placeholder (`http://localhost:5173`) to the CF Pages prod origin so the browser can actually reach the backend.
5. Manual browser verification: login renders, refresh of deep route returns SPA, network tab shows requests going to absolute Fly URL.

**Out of scope (other phases):**
- Supabase Auth redirect URLs for CF Pages origin (Phase 6 / SEC-01)
- CORS rejection-path hardening, preview-URL regex, max-iter cap, rate limit (Phase 6)
- LangSmith prod, Sentry, UptimeRobot (Phase 7)
- "Try demo" button, README live URL, deploy badge (Phase 8)
- Custom domain (use default `*.pages.dev` for portfolio; revisit later)

</domain>

<decisions>
## Implementation Decisions

### Deploy mechanism
- **D-01:** Git auto-deploy via Cloudflare Pages GitHub integration. CF Pages project connects to the repo and auto-builds on push to `main`. Build command + env vars configured once in the CF dashboard. No `wrangler` CLI auth on the developer laptop. Matches the "push to deploy" portfolio narrative.
- **D-02:** Production branch = `main`. Preview/PR deploys disabled (see D-07). Only `main` produces a public deployment.

### Project identity + URL
- **D-03:** CF Pages project slug = `boardgame-rag-prod`. Public URL = `https://boardgame-rag-prod.pages.dev`. Mirrors Fly app name (Phase 4 D-01), Supabase project name (Phase 3 D-15), and LangSmith project name. Naming consistent across all four surfaces.
- **D-04:** No custom domain in this phase. Default `*.pages.dev` is sufficient for portfolio; custom domain is a v1.2+ idea.

### Build configuration
- **D-05:** CF Pages build config: root directory = `frontend/`, build command = `npm run build`, output directory = `dist`. Cleaner than building from repo root. `vite.config.ts` has `envDir: '..'` for local-dev `.env` loading; this is irrelevant on CF Pages because env vars come from the CF dashboard, not a `.env` file. Local dev workflow unchanged.
- **D-06:** Node version pinned for CF Pages build via env var `NODE_VERSION=20` (or whichever LTS version `package-lock.json` was generated with). Avoids "works locally, breaks on CF" drift. Planner verifies the lockfile-compatible Node version before pinning.

### Preview deploys
- **D-07:** Preview deploys (PR + non-`main` branch) disabled in CF Pages settings. Reasons: backend CORS allowlist would reject the per-deploy `<hash>.<slug>.pages.dev` subdomains anyway, and a solo-portfolio project doesn't need them. Eliminates the need for `allow_origin_regex` complexity in the backend CORS config.

### CF Pages env vars
- **D-08:** Three env vars set in CF Pages dashboard, scoped to "Production" environment (not Preview):
  - `VITE_API_BASE_URL = https://boardgame-rag-prod.fly.dev` (no trailing slash, full origin per Phase 1 D-08)
  - `VITE_SUPABASE_URL = <prod Supabase URL>` (from Phase 3 `.env.prod`)
  - `VITE_SUPABASE_ANON_KEY = <prod Supabase anon key>` (from Phase 3 `.env.prod`)
- **D-09:** Anon key is fine to ship in the bundle (it's a public key bound by RLS). Service-role key is NOT set anywhere in CF Pages — already pinned by Phase 1 D-12 / SEC-07. Phase 1's grep guard remains the canonical leak check.

### SPA deep-link routing
- **D-10:** Commit `frontend/public/_redirects` with the single line `/* /index.html 200`. Vite copies `public/` contents to `dist/` at build time, so the file ends up at `dist/_redirects` where CF Pages picks it up. No CF dashboard configuration needed beyond standard CF Pages defaults.

### Backend CORS update
- **D-11:** Phase 5 owns the CORS update from Phase 4's placeholder (`http://localhost:5173`) to the prod CF Pages origin. After the first green CF deploy succeeds and the URL is confirmed, run:
  ```
  flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod
  ```
  This triggers a Fly machine restart with the new allowlist. Required for Phase 5 success criterion #4 (browser actually hits Fly without CORS rejection).
- **D-12:** Single-origin string only — no `localhost:5173` fallback in the prod allowlist. Local dev still works because Phase 1 D-02 falls back to `["http://localhost:5173"]` when `CORS_ALLOWED_ORIGINS` is unset (i.e. only on the dev laptop, not on Fly). Phase 6 owns any future hardening (rejection-path tests, preview-URL regex if previews are ever re-enabled).

### Verification
- **D-13:** Manual browser verification, documented as a PLAN checklist:
  1. Load `https://boardgame-rag-prod.pages.dev` — login page renders without console errors.
  2. Open browser devtools → Network tab → confirm requests target absolute `https://boardgame-rag-prod.fly.dev/api/...` (not same-origin `/api`).
  3. Log in with the seeded test user (`ragtest1@gmail.com` / `testpass123` from CLAUDE.md).
  4. Navigate to `/documents`, then hard-refresh the page — SPA route renders (proves `_redirects` works), not a CF 404.
  5. Send a chat message — SSE streams from Fly to CF-hosted UI without CORS rejection in the console.
- **D-14:** No scripted CF smoke harness in this phase. SSE end-to-end is already covered by Phase 4's `fly_smoke.sh`; static-asset checks would be redundant. Phase 7 / Phase 8 may revisit if uptime monitoring or the README needs an automated link-check.

### Claude's Discretion
- Exact Node version pin in D-06 — planner reads `frontend/package-lock.json` lockfile version + `engines` field (if any) and picks the matching LTS major (likely `20` or `22`).
- Whether to add a `frontend/.nvmrc` alongside the CF Pages env var — nice-to-have for local-dev consistency, not required by phase success criteria.
- Order of operations: connect repo first vs set env vars first. CF Pages typically prompts for env vars during initial connection; planner can pick whichever flow the dashboard surfaces.
- Whether to pre-create the CF Pages project via Wrangler API or do it entirely in the dashboard — dashboard is fine for a one-time setup; no automation needed.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 5 — 5 success criteria (CF project + green deploy, CF env vars set, `_redirects` present, browser network tab proves absolute Fly URL, UI hint = frontend)
- `.planning/REQUIREMENTS.md` — DEPLOY-05 definition

### Research
- `.planning/research/SUMMARY.md` — Frontend hosting rationale (CF Pages free tier vs Vercel)
- `.planning/research/STACK.md` §"Cloudflare Pages" — Build config conventions, `_redirects` syntax, Node version pinning
- `.planning/research/ARCHITECTURE.md` — Frontend↔Fly integration map, CORS allowlist pattern
- `.planning/research/PITFALLS.md` — SPA 404 on deep-link refresh, CORS prod-origin missing, anon vs service-role key confusion in bundle

### Prior-phase context (carry forward, do not re-plan)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §Frontend API Base URL (D-05/D-06/D-07/D-08) — `apiFetch`/`apiStream` already prefix `${VITE_API_BASE_URL ?? ''}`; empty default keeps Vite proxy in dev; absolute Fly URL with no trailing slash in prod. No code changes needed in this phase — only env var values.
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §CORS Allowlist (D-01/D-02/D-03) — `CORS_ALLOWED_ORIGINS` is a comma-separated env var consumed by `Settings`; dev fallback `["http://localhost:5173"]` when unset; `allow_credentials=True` preserved. D-11 above writes the prod value via `flyctl secrets set`.
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §SEC-07 grep guard (D-12) — Phase 1's prod-bundle secret-leak grep stays the canonical SEC-07 check; nothing here re-implements it.
- `.planning/phases/03-prod-supabase-project/03-CONTEXT.md` §Project metadata (D-15/D-16) — Prod Supabase URL + anon key live in `.env.prod`; D-08 above pulls those values into CF Pages dashboard.
- `.planning/phases/04-deploy-backend-to-fly-io/04-CONTEXT.md` §App identity (D-01) — Fly app `boardgame-rag-prod`, public URL `https://boardgame-rag-prod.fly.dev`. Baked into `VITE_API_BASE_URL` per D-08 above.
- `.planning/phases/04-deploy-backend-to-fly-io/04-CONTEXT.md` §CORS placeholder (D-07/D-08) — Hand-off: Phase 4 set `CORS_ALLOWED_ORIGINS=http://localhost:5173` placeholder; Phase 5 D-11 overwrites it.

### Source files this phase TOUCHES (small surface)
- `frontend/public/_redirects` — CREATE (D-10)
- `frontend/.nvmrc` — CREATE if planner picks D-06 nice-to-have
- No code changes in `frontend/src/**` — Phase 1 already prepared the URL prefix
- No backend code changes — only a Fly secret update via `flyctl` CLI

### Out-of-repo configuration (manual, document in PLAN)
- Cloudflare Pages dashboard: project creation, GitHub integration, build settings (D-05), env vars (D-08), preview-deploy disabled (D-07)
- Fly secret update via `flyctl secrets set` (D-11)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/lib/api.ts` (`apiFetch`, `apiStream` from Phase 1) — already prefix `VITE_API_BASE_URL`, no changes needed.
- `frontend/vite.config.ts` `envDir: '..'` — only affects local dev; CF Pages env vars come from dashboard, so this is a no-op in prod build.
- `backend/scripts/fly_smoke.sh` (Phase 4) — already exercises end-to-end SSE chat against Fly. Phase 5 verification is browser-side only; no scripted smoke duplicated here (D-14).

### Established Patterns
- Naming: `boardgame-rag-prod` across Fly + Supabase + LangSmith + (now) CF Pages.
- Env var convention: `VITE_*` for frontend public, no service-role key ever in bundle (Phase 1 D-12 / SEC-07).
- Phase hand-off via `flyctl secrets set` for backend config changes (Phase 4 D-04 used `flyctl secrets import`; D-11 here uses single `set` for one-key update).

### Integration Points
- Browser ↔ CF Pages edge: serves `frontend/dist/*` + `_redirects` for SPA routing.
- Browser ↔ Fly: cross-origin XHR/SSE with credentials; backend CORS must list `https://boardgame-rag-prod.pages.dev` (D-11).
- Browser ↔ Supabase: anon key + auth flow direct to Supabase; no proxy through Fly. Auth redirect URLs (SEC-01) deferred to Phase 6.

</code_context>

<specifics>
## Specific Ideas

- "Push to deploy" portfolio narrative: Git auto-deploy reinforces the story that the whole stack is reproducible from a single repo + commit (D-01).
- Mirror Fly + Supabase + LangSmith naming on CF Pages so the README architecture diagram has one consistent identifier across surfaces (D-03).

</specifics>

<deferred>
## Deferred Ideas

- Custom domain on CF Pages — defer to v1.2+. Default `*.pages.dev` is fine for portfolio.
- Preview deploys with backend `allow_origin_regex` for CORS — deferred indefinitely (no demand for solo portfolio); revisit only if PR-preview workflow becomes valuable.
- Scripted CF Pages smoke (`cf_smoke.sh`) — deferred. Phase 4 `fly_smoke.sh` covers the SSE path; Phase 7 may add UptimeRobot pings against the CF URL instead.
- CORS rejection-path test (proves non-allowlisted origins are blocked) — Phase 6 SEC-02.
- Wildcard / regex CORS for preview deploys — Phase 6 if previews ever re-enabled.
- `frontend/.nvmrc` for local-dev Node consistency — Claude's discretion at plan time.

</deferred>

---

*Phase: 05-deploy-frontend-to-cloudflare-pages*
*Context gathered: 2026-05-05*
