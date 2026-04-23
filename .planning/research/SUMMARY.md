# Project Research Summary

**Project:** Board Game KB RAG — v1.1 Portfolio Deployment
**Domain:** Deployment of existing feature-complete agentic RAG app to public hosts
**Researched:** 2026-04-22
**Confidence:** HIGH

## Executive Summary

v1.1 ships the already-built Board Game KB RAG app as a publicly reachable portfolio piece on free/near-free tier hosts. Target stack: **Fly.io** for the FastAPI+Docling backend (warm machines, real free tier for portfolio traffic), **Cloudflare Pages** for the Vite React SPA (unlimited bandwidth beats Vercel's 100GB cap), and a **separate prod Supabase project** mirroring dev schema + default KB seed. LangSmith gets a `boardgame-rag-prod` project; Sentry + UptimeRobot round out observability.

The deployment path is dependency-chained, not parallelizable: secrets/repo hygiene → env-split code changes → Dockerize → Supabase prod → backend deploy → frontend deploy → CORS/auth harden → observability + rate limiting → portfolio polish. Shortcuts create rework — e.g., deploying before the prod Supabase project exists breaks auth redirects; hardening CORS before Vercel/CF Pages URL is known means a second pass.

Biggest risks are **LLM cost blowout** on a public unauthenticated surface (agentic tool loop multiplies per-request spend — needs per-user + provider-level caps) and **cold starts from the Docling-fat image** (5–30s first-request latency kills demo first-impression — mitigate with `min_machines_running=1` or keep-warm ping). Three pitfalls are code-level and must land before Docker build: (1) existing `allow_origins=["*"]` + `allow_credentials=True` is spec-invalid — blocks credentialed SSE under real auth; (2) no `.dockerignore` means `COPY . .` will bake `.env` into image; (3) `docling` pin missing in `requirements.txt`.

## Key Findings

### Recommended Stack

Container backend on Fly.io, static frontend on Cloudflare Pages, separate prod Supabase project, Sentry + UptimeRobot + LangSmith prod project for observability. No serverless backend (Docling native deps rule it out). No custom orchestration (k8s overkill for portfolio).

**Core technologies:**
- **Fly.io `shared-cpu-1x@1gb`** — backend host; `suspend` auto-stop keeps resume <250ms; 512MB OOMs on first Docling PDF (confirmed) so 1GB required (~$3–5/mo)
- **Docker `python:3.11-slim-bookworm`** — matches Docling's own reference image; Alpine breaks torch/lxml wheels (musl); CPU-only torch via `--extra-index-url https://download.pytorch.org/whl/cpu` keeps image ~10× smaller
- **Cloudflare Pages** — static frontend; unlimited bandwidth vs Vercel 100GB cap; SPA routing via one-line `public/_redirects` (`/* /index.html 200`)
- **Supabase prod project** (separate from dev) — `supabase db push` applies all 25 migrations in order; pgvector extension must be enabled manually before migration run
- **`@sentry/react@^10.49.0` + `@sentry/vite-plugin@^5.2.0`** — React 19 integration via `Sentry.reactErrorHandler()` into `createRoot` options
- **UptimeRobot** free tier — 50 monitors, 5-min interval; pings `/api/health` (already exists in `backend/main.py`)
- **LangSmith prod project** `boardgame-rag-prod` — zero code change, env-var split only

### Expected Features

**Must have (table stakes):**
- Containerized backend + container deploy to public URL
- Static frontend build + deploy to public URL
- Prod Supabase project with full migrations + default KB seed
- Secrets in host secret stores (no `.env` in repo or image)
- Env-driven CORS allowlist (not wildcard) for prod origin
- Auth redirect URLs configured for prod frontend
- `/api/health` endpoint for Fly checks + uptime monitor
- Per-user rate limit on `/api/chat` (cost cap)
- OpenRouter spend alert configured
- Error boundary + graceful degradation when LLM provider fails
- README with live URL, demo credentials, architecture diagram

**Should have (competitive):**
- Demo user seed + "Try demo" login button (keeps RLS intact vs anonymous guest)
- Sentry frontend error tracking with source maps
- LangSmith prod project (separate from dev)
- Keep-warm strategy (`min_machines_running=1` or scheduled ping)
- Graceful degradation of rerank/web-search/sub-agent when individual tools fail
- Deploy badge on README
- Nightly demo-user cleanup cron (when traffic justifies)

**Defer (v1.2+):**
- CAPTCHA / email verification (add if abuse observed)
- Per-IP rate limiting (add if anon flows return)
- Landing page / marketing site (portfolio README covers it)
- Staging environment (2 envs is enough — dev local + prod)
- Multi-region deploy
- Redis/Upstash cache
- Feature flags
- Custom admin UI

### Architecture Approach

Deployment is **additive** — no refactor of existing services. Changes concentrate in: `backend/main.py` (CORS allowlist), `backend/config.py` (add `cors_allowed_origins`, `environment`, `sentry_dsn`, `rate_limit_*` fields), `frontend/src/lib/api.ts` (prefix fetch with `${VITE_API_BASE_URL ?? ''}`), plus new files (`Dockerfile`, `.dockerignore`, `fly.toml`, `public/_redirects`, `vercel.json`-alt, `README.md` updates). Frontend API base URL is baked at build time — prod uses absolute URL to Fly, dev keeps Vite proxy (empty string default).

**Major components:**
1. **Dockerfile (multi-stage)** — builder installs Docling + CPU torch + pre-downloads models; runtime layer `python:3.11-slim-bookworm` with `poppler-utils`, `tesseract-ocr`, `libglib2.0-0`, `fonts-dejavu-core`. Uses `opencv-python-headless` to skip `libgl1` (~200MB save).
2. **`fly.toml`** — `auto_stop_machines="suspend"`, `min_machines_running=1`, `internal_port=8000`, health check `/api/health`, 1GB VM
3. **Prod Supabase project** — dedicated, schema + RLS + seed applied via `supabase db push`; Auth redirect URLs = CF Pages domain; Storage bucket policies reapplied
4. **Cloudflare Pages site** — Vite build, env vars for `VITE_API_BASE_URL` + `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`; `_redirects` for SPA
5. **Rate limiter middleware** — FastAPI `slowapi` or in-memory token bucket keyed on `user_id`; cap `/api/chat` per-user per-minute
6. **Sentry init** — frontend via `@sentry/react` + `@sentry/vite-plugin` for source maps upload on build
7. **UptimeRobot monitors** — one per domain (Fly + CF Pages), 5-min, HTTPS check on `/` and `/api/health`
8. **README deploy doc** — live URL, demo creds, `docker build` + `fly deploy` commands, architecture diagram

### Critical Pitfalls

1. **Existing CORS bug** (`backend/main.py`) — `allow_origins=["*"]` with `allow_credentials=True` is spec-invalid; browsers silently drop credentialed SSE. **Fix:** env-driven allowlist before any deploy.
2. **`.env` leak into Docker image** — no `.dockerignore` in repo, `backend/config.py` calls `load_dotenv()` unconditionally. `COPY . .` will bake secrets in. **Fix:** `.dockerignore` excludes `.env*`, `venv/`, `__pycache__/`, `.git/`; use Fly secrets.
3. **Docling unpinned** in `requirements.txt` + needs `libgl1|libglib2.0-0`, `libmagic1`, `poppler-utils`, `tesseract-ocr` system packages. Missing packages → runtime 500 on PDF/image ingest (health check still passes). **Fix:** pin Docling version; install apt packages in Dockerfile runtime layer.
4. **LLM cost blowout** — `/api/chat` has no rate limit; agentic tool loop multiplies per-request cost; demo creds will be public. **Fix:** per-user rate limit (slowapi), OpenRouter spend cap, max-iterations on main tool loop (mirror explorer's 6-cap).
5. **Migration order sensitivity** — migration 019 adds `visibility` column; 020 writes RLS referencing it. Copy-pasting into Supabase Studio risks wrong order. **Fix:** `supabase db push` against prod project, verify 25/25 applied.
6. **SSE + Vercel rewrites buffer streams** — if frontend proxies `/api/*` through Vercel rewrites, SSE silently buffers. **Fix:** frontend calls Fly URL directly via `VITE_API_BASE_URL`; skips rewrite layer.
7. **Supabase free-tier 7-day pause** — prod project pauses if idle 7 days. **Fix:** UptimeRobot hit on `/api/health` (which touches DB) keeps active.
8. **Cold start UX killer** — Docling image + Fly auto-stop = 5–30s first-request latency. **Fix:** `min_machines_running=1` (~$3–5/mo) or scheduled warmup ping.

## Implications for Roadmap

Based on research, suggested phase structure (reset numbering — starting Phase 1):

### Phase 1: Secrets & Repo Hygiene
**Rationale:** Must land before any Docker build to prevent `.env` leak and CORS failures in prod. Code-only changes, no infra.
**Delivers:** `.dockerignore`, CORS env-driven allowlist in `backend/main.py`, `backend/config.py` new fields (`cors_allowed_origins`, `environment`, `sentry_dsn`), `frontend/src/lib/api.ts` prefixed with `VITE_API_BASE_URL`, Docling version pin, `docs/DEPLOY.md` stub.
**Avoids:** CORS spec-invalid combo, `.env` image leak, unpinned dep drift.

### Phase 2: Dockerize Backend
**Rationale:** Containerize with Docling native deps locally before attempting cloud deploy — fail fast on `apt` list and image size.
**Delivers:** Multi-stage `Dockerfile` (python:3.11-slim-bookworm, CPU torch, pre-downloaded Docling models, apt: poppler-utils, tesseract-ocr, libglib2.0-0, fonts-dejavu-core), local `docker build` + `docker run --env-file .env` validation, `/api/health` verified under container.
**Uses:** Docker, Docling installation reference.
**Avoids:** Missing system libs (silent PDF 500s), image bloat past free-tier, Alpine/musl wheel breakage.

### Phase 3: Supabase Prod Project
**Rationale:** Prod DB must exist and be seeded before backend can deploy — auth + default KB + RLS all depend on it.
**Delivers:** New Supabase project (prod region), `supabase db push` applied (25 migrations in order, pgvector enabled), Storage buckets + policies reapplied, default KB seed script rerun, Auth redirect URLs prepped (placeholder until frontend URL known), service role + anon keys captured as secrets.
**Avoids:** Migration order skew, missing pgvector, Storage policy gap, free-tier 7-day pause mitigation plan.

### Phase 4: Deploy Backend to Fly.io
**Rationale:** Backend URL needed before frontend can bake `VITE_API_BASE_URL`.
**Delivers:** `fly.toml` (shared-cpu-1x@1gb, suspend auto-stop, min_machines_running=1, /api/health check), `flyctl secrets` set (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENROUTER_API_KEY, LANGSMITH_*, TAVILY_API_KEY, CORS placeholder), first `fly deploy`, smoke test SSE streaming end-to-end via curl.
**Uses:** Fly.io CLI, Dockerfile from Phase 2.
**Avoids:** Cold-start demo failure, secret leaks, SSE buffer.

### Phase 5: Deploy Frontend to Cloudflare Pages
**Rationale:** Needs Fly URL from Phase 4 baked into `VITE_API_BASE_URL`; produces the domain needed for Phase 6 CORS + Auth URLs.
**Delivers:** CF Pages project, build command (`npm run build`), env vars set (`VITE_API_BASE_URL` pointing to Fly, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` = prod anon key), `public/_redirects` for SPA, first deploy, live URL captured.
**Avoids:** SSE proxy buffer, wrong anon key, SPA 404 on route refresh.

### Phase 6: Prod Wiring — CORS, Auth, Rate Limiting
**Rationale:** Once both URLs are known, close the loop — CORS allowlist, Auth redirect URLs, rate limiting before traffic.
**Delivers:** Fly CORS secret updated with CF Pages origin, Supabase Auth redirect URLs updated with CF Pages origin, `slowapi` per-user rate limit on `/api/chat`, max-iterations cap on main chat tool loop (mirror explorer's 6-cap), OpenRouter spend-alert configured, end-to-end login + chat + upload verified from prod URL.
**Avoids:** Auth failure, cost blowout, unbounded agentic loops.

### Phase 7: Observability Baseline
**Rationale:** Close the loop on visibility before sharing URL — errors, uptime, traces, costs.
**Delivers:** `@sentry/react` + `@sentry/vite-plugin` wired with source maps upload, `boardgame-rag-prod` LangSmith project active, UptimeRobot monitors (Fly + CF Pages), Sentry test error triggered + verified non-minified stack, LangSmith prod trace verified.
**Avoids:** Silent prod failures, dev-trace pollution, Supabase pause.

### Phase 8: Portfolio Polish
**Rationale:** Final presentation layer — demo UX, README, graceful degradation.
**Delivers:** Demo user seed + "Try demo" login button, graceful degradation wrappers on rerank/web/sub-agent (skip-not-500), README with live URL + demo creds + architecture diagram + deploy commands + badges, screenshot/GIF of working app.
**Avoids:** Demo-breaking edge cases, portfolio presentation gaps.

### Phase Ordering Rationale

- **Phase 1 must be first** — CORS bug and `.env` leak are blocking prerequisites for any container build; pure code, no infra dependency
- **Phase 2 before 3/4** — Dockerize locally to fail fast on Docling deps without burning Fly deploy cycles
- **Phase 3 before 4** — backend can't boot without prod Supabase URL + service role key
- **Phase 4 before 5** — frontend bakes absolute Fly URL at build time
- **Phase 5 before 6** — CORS allowlist and Auth redirects need CF Pages origin
- **Phase 6 before 7** — rate limiting + auth must work before adding observability so traces capture real usage shape
- **Phase 7 before 8** — observability must be live before portfolio URL is shared; phase 8 is the "share it" phase

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2:** exact Docling version pin + verify `apt` package list against that version's release notes; empirical image size check vs Fly rootfs limit
- **Phase 4:** Fly.io body-size limit for doc uploads — community threads ambiguous, verify with real staging request; Docling model cache volume mount decision (persistent across suspend/resume)
- **Phase 6:** slowapi vs custom token-bucket for rate limiting; OpenRouter spend-alert granularity; max-iterations placement in chat tool loop

Phases with standard patterns (skip research-phase):
- **Phase 1:** pure code hygiene, no research needed
- **Phase 3:** Supabase prod setup is well-documented
- **Phase 5:** Cloudflare Pages + Vite is a standard path
- **Phase 7:** Sentry + UptimeRobot + LangSmith are well-documented
- **Phase 8:** presentation + docs

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified (Sentry 10.49.0, vite-plugin 5.2.0); Fly pricing + Docling reference Dockerfile from official sources |
| Features | MEDIUM-HIGH | Table stakes / differentiators pattern well-established; some host-specific flags need docs-verification at plan time |
| Architecture | HIGH | Integration points verified against actual source files (`main.py`, `config.py`, `api.ts`, `supabase.ts`, `vite.config.ts`) |
| Pitfalls | HIGH | Repo-specific pitfalls (CORS bug, missing `.dockerignore`, unpinned Docling, migration order) verified in code/repo |

**Overall confidence:** HIGH — HIGH on repo-specific and code-level findings; MEDIUM on evolving platform free-tier specifics (Fly rootfs limits, LangSmith quotas).

### Gaps to Address

- **Fly body-size limit for uploads** — verify empirically during Phase 4 smoke test; set app-side cap (25MB recommended) as safety net
- **Docling model cache persistence** — decide during Phase 4 whether to mount Fly volume for `~/.cache/docling` to skip re-download on suspend/resume
- **Main chat tool loop iteration cap** — confirm during Phase 6 planning whether `routers/chat.py` already has a max; explorer has 6, main loop may not
- **Storage bucket policies in migration SQL vs dashboard** — inspect before Phase 3 to avoid policy gap; capture as SQL if dashboard-only
- **Supabase free tier `pg_cron` availability** — affects Phase 8 nightly demo-reset approach (pg_cron vs Fly scheduled machine)

## Sources

### Primary (HIGH confidence)
- Fly.io FastAPI docs — container hosting pattern, `fly.toml` reference
- Fly.io app configuration reference — `auto_stop_machines`, `min_machines_running`
- Vercel Vite framework guide — (excluded in favor of CF Pages)
- Cloudflare Pages + Vite SPA routing via `_redirects` — official
- Docling installation docs + FAQ — apt package list
- docling-serve container images reference — multi-stage pattern
- npm registry — `@sentry/react@10.49.0`, `@sentry/vite-plugin@5.2.0`
- LangChain LangSmith env-var support article — prod project config
- Repo source: `backend/main.py`, `backend/config.py`, `frontend/vite.config.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/supabase.ts`, `backend/requirements.txt`, `supabase/migrations/`

### Secondary (MEDIUM confidence)
- Fly.io community threads — HTTP request size limits (ambiguous, flagged for verification)
- UptimeRobot free-tier specs — 50 monitors / 5-min interval
- BetterStack alternative — overkill for 2 URLs

### Tertiary (LOW confidence)
- LangSmith free-tier exact quotas — evolve over time; pattern solid, numbers not

---
*Research completed: 2026-04-22*
*Ready for roadmap: yes*
