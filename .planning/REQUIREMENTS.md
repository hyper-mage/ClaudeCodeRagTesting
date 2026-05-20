# Requirements — Milestone v1.1 Portfolio Deployment

**Milestone:** v1.1 Portfolio Deployment
**Goal:** Ship Board Game KB RAG as publicly accessible portfolio piece on free-tier hosts (Fly.io backend, Cloudflare Pages frontend, prod Supabase project).
**Last updated:** 2026-05-20 (traceability refreshed at milestone close — all 23 requirements satisfied)

## v1.1 Requirements

### Deployment Infrastructure (DEPLOY)

- [x] **DEPLOY-01**: Developer can build a backend container image locally that boots FastAPI + Docling, passes `/api/health`, and handles PDF/DOCX ingest without missing native deps
- [x] **DEPLOY-02**: Developer has a `.dockerignore` that excludes `.env*`, `venv/`, `__pycache__/`, `.git/`, `frontend/node_modules/`, `backend/tests/` so secrets and bloat never enter the image
- [x] **DEPLOY-03**: Developer has a dedicated prod Supabase project with all migrations applied in order, pgvector enabled, Storage bucket policies applied, and default board game KB seeded
- [x] **DEPLOY-04**: Developer can run `fly deploy` and reach the backend at a public `*.fly.dev` URL serving `/api/health` and SSE chat end-to-end
- [x] **DEPLOY-05**: Developer can push the frontend build to Cloudflare Pages and reach a public URL that loads the SPA with correct deep-link refresh behavior (`_redirects`)
- [x] **DEPLOY-06**: Frontend built for prod reads an absolute `VITE_API_BASE_URL` pointing at Fly; dev build still uses Vite proxy (empty default preserves local workflow)
- [x] **DEPLOY-07**: `fly.toml` defaults to free-tier (`auto_stop_machines="suspend"`, no `min_machines_running` set) with a documented one-line toggle to enable keep-warm later
- [x] **DEPLOY-08**: `backend/requirements.txt` pins `docling` to a specific version so image builds are reproducible

### Security & Cost (SEC)

- [x] **SEC-01**: User can log in from the prod frontend with Supabase Auth redirect URLs correctly configured for the Cloudflare Pages domain (no redirect loops, email verification links land on prod)
- [x] **SEC-02**: Backend CORS allowlist reads from env (`CORS_ALLOWED_ORIGINS`), blocks non-prod origins, and preserves credentialed SSE (no `*` + `credentials=true` combo)
- [x] **SEC-03**: All secrets (Supabase service role key, OpenRouter key, LangSmith key, Tavily key) live in Fly `flyctl secrets` and Cloudflare Pages env vars — never committed, never baked into image
- [x] **SEC-04**: `/api/chat` enforces a per-authenticated-user rate limit (configurable via env) that caps requests per minute to prevent LLM cost blowout
- [x] **SEC-05**: Main chat tool-use loop has a max-iterations cap (mirror explorer sub-agent's pattern) so runaway agent behavior can't drain budget
- [x] **SEC-06**: OpenRouter account has a monthly spend cap or alert configured so provider-level cost is bounded independent of app-level limits — *mechanism in place (OpenRouter Guardrail); live spend-trip test deferred to backlog 999.2-cost-guardrail-burn-script*
- [x] **SEC-07**: Frontend bundle contains no `SUPABASE_SERVICE_ROLE_KEY` or other backend-only secrets (verified by grep of production bundle)

### Observability (OBS)

- [x] **OBS-01**: Frontend reports uncaught errors and unhandled promise rejections to a dedicated Sentry project, with source maps uploaded at build time so stack traces are un-minified
- [x] **OBS-02**: Backend traces land in a dedicated LangSmith project (`boardgame-rag-prod`) that is separate from the dev/local project, configured via env vars only
- [x] **OBS-03**: UptimeRobot monitors ping the Fly backend `/api/health` and the Cloudflare Pages frontend on a ≤5 minute interval; owner gets email on downtime
- [x] **OBS-04**: `/api/health` endpoint verifies Supabase DB reachability (not just process liveness) so monitor failures catch real outages and keep Supabase project active (prevents 7-day pause)

### Portfolio Polish (PORT)

- [x] **PORT-01**: Anonymous visitor can log in as a seeded demo user with one click on the login page ("Try demo" button), skipping signup — credentials are shared and documented
- [x] **PORT-02**: When the LLM provider errors or rate-limits, chat UI shows a graceful error message instead of a 500/crash; individual tool failures (rerank, web search, sub-agent) are caught so the agent continues without them
- [x] **PORT-03**: README in repo root includes the live URL, demo credentials, an architecture diagram, the deploy command sequence, screenshots of the app, and a short project pitch suitable for portfolio reviewers
- [x] **PORT-04**: README includes a deploy-status badge (or equivalent) reflecting the current deployment state — *satisfied via UptimeRobot uptime-ratio badge + GitHub last-commit badge*

## Future Requirements (Deferred to v1.2+)

- Nightly demo-user data reset cron (pg_cron or Fly scheduled machine) — add when abuse/clutter observed
- CAPTCHA (Cloudflare Turnstile) + email verification for signups — add when abuse observed
- Per-IP rate limiting for anonymous routes — add if anon flows return
- Landing / marketing page — portfolio README covers it for now
- Staging environment between dev-local and prod — only 2 envs for solo portfolio
- Multi-region deploy
- Redis/Upstash caching layer
- Custom admin UI
- Feature flag system
- Docling model cache on Fly volume (persist across suspend/resume) — evaluate after Phase 4 smoke test shows real cold-start cost

## Out of Scope

- **Admin UI for managing default KB** — seed script already handles it
- **Social features (sharing collections, public reviews)** — not part of portfolio pitch
- **Mobile app** — web-only
- **Automated ingestion pipelines** — manual upload only (project constraint)
- **LangChain/LangGraph** — raw SDK only (project constraint)

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| DEPLOY-01 | Phase 2 | Complete |
| DEPLOY-02 | Phase 1 | Complete |
| DEPLOY-03 | Phase 3 | Complete |
| DEPLOY-04 | Phase 4 | Complete |
| DEPLOY-05 | Phase 5 | Complete |
| DEPLOY-06 | Phase 1 | Complete |
| DEPLOY-07 | Phase 4 | Complete |
| DEPLOY-08 | Phase 1 | Complete |
| SEC-01 | Phase 6 | Complete |
| SEC-02 | Phase 1 | Complete |
| SEC-03 | Phase 4 | Complete |
| SEC-04 | Phase 6 | Complete |
| SEC-05 | Phase 6 | Complete |
| SEC-06 | Phase 6 | Complete (trip-test deferred to backlog 999.2) |
| SEC-07 | Phase 1 | Complete |
| OBS-01 | Phase 7 | Complete |
| OBS-02 | Phase 7 | Complete |
| OBS-03 | Phase 7 | Complete |
| OBS-04 | Phase 7 | Complete |
| PORT-01 | Phase 8 | Complete |
| PORT-02 | Phase 8 | Complete |
| PORT-03 | Phase 8 | Complete |
| PORT-04 | Phase 8 | Complete |

*Phase column filled by roadmapper; status refreshed 2026-05-20 at milestone close via 3-source cross-reference (VERIFICATION/UAT + SUMMARY frontmatter + verification this session). All 23 v1.1 requirements satisfied. See `.planning/v1.1-MILESTONE-AUDIT.md`.*
