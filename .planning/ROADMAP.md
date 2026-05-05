# Roadmap — Milestone v1.1 Portfolio Deployment

**Milestone:** v1.1 Portfolio Deployment
**Goal:** Ship Board Game KB RAG as a publicly reachable portfolio piece on free-tier hosts (Fly.io backend, Cloudflare Pages frontend, prod Supabase project) — with secrets, auth, CORS, rate limiting, and observability hardened for a shared demo URL.
**Granularity:** standard
**Phases:** 8
**Coverage:** 23/23 requirements mapped
**Last updated:** 2026-04-23

## Phases

- [ ] **Phase 1: Secrets & Repo Hygiene** — Land code-level pre-reqs (CORS env allowlist, `.dockerignore`, Docling pin, `VITE_API_BASE_URL`) so nothing unsafe can be containerized or shipped.
- [ ] **Phase 2: Dockerize Backend** — Build a reproducible backend image that boots FastAPI + Docling with all native deps, validated locally before any cloud deploy.
- [ ] **Phase 3: Prod Supabase Project** — Stand up a dedicated prod Supabase project with all migrations, pgvector, Storage policies, and default KB seed applied.
- [ ] **Phase 4: Deploy Backend to Fly.io** — Ship the container to Fly with free-tier config, secrets in `flyctl secrets`, and a public `*.fly.dev` URL serving `/api/health` + SSE chat.
- [ ] **Phase 5: Deploy Frontend to Cloudflare Pages** — Build and deploy the Vite SPA to a public CF Pages URL with `VITE_API_BASE_URL` pointing at Fly and SPA deep-link routing.
- [ ] **Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps** — Close the loop between frontend and backend: Auth redirect URLs, CORS allowlist, per-user chat rate limit, max-iterations cap, and OpenRouter spend alert.
- [ ] **Phase 7: Observability Baseline** — Wire Sentry (with source maps), LangSmith prod project, and UptimeRobot monitors (including DB-touching `/api/health`) so prod failures are visible.
- [ ] **Phase 8: Portfolio Polish** — Demo user + "Try demo" button, graceful degradation, and a portfolio-grade README (live URL, creds, architecture diagram, screenshots, deploy badge).

## Phase Details

### Phase 1: Secrets & Repo Hygiene
**Goal**: Developer has the code-level safety rails (CORS allowlist, secret exclusion, dep pin, frontend base URL) needed before any container build or cloud deploy.
**Depends on**: Nothing (first phase)
**Requirements**: DEPLOY-02, DEPLOY-06, DEPLOY-08, SEC-02, SEC-07
**Success Criteria** (what must be TRUE):
  1. `.dockerignore` exists at repo root and excludes `.env*`, `venv/`, `__pycache__/`, `.git/`, `frontend/node_modules/`, `backend/tests/` — verified by inspecting `docker build --dry-run` context.
  2. `backend/main.py` CORS middleware reads its allowlist from `CORS_ALLOWED_ORIGINS` env (comma-separated) with no `["*"]` + `credentials=True` combination anywhere.
  3. Frontend `api.ts` prefixes every fetch with `${VITE_API_BASE_URL ?? ''}` so dev (empty → Vite proxy) and prod (absolute Fly URL) both work without code changes.
  4. `backend/requirements.txt` pins `docling` to a specific version and `pip install -r requirements.txt` reproduces the same resolved tree twice in a row.
  5. A production Vite build grepped for `SUPABASE_SERVICE_ROLE_KEY` / other backend-only secrets returns zero matches.
**Plans**: 2 plans
  - [ ] 01-01-PLAN.md — Backend hygiene: .dockerignore, env-driven CORS allowlist, docling pin + unpinned-dep audit
  - [ ] 01-02-PLAN.md — Frontend VITE_API_BASE_URL centralization + prod bundle secret-leak grep guard

### Phase 2: Dockerize Backend
**Goal**: Developer can build and run the backend container locally and confirm FastAPI + Docling + PDF/DOCX/image ingest all work inside the image before spending any Fly deploy cycles.
**Depends on**: Phase 1
**Requirements**: DEPLOY-01
**Success Criteria** (what must be TRUE):
  1. `docker build .` produces a backend image based on `python:3.11-slim-bookworm` with apt packages (`poppler-utils`, `tesseract-ocr`, `libglib2.0-0`, `fonts-dejavu-core`) and CPU-only torch installed.
  2. `docker run --env-file .env -p 8000:8000 <image>` boots the container and `curl http://localhost:8000/api/health` returns 200.
  3. Ingesting a real PDF and a real DOCX against the running container completes without missing-native-dep errors (no `libgl`, `libglib`, `poppler`, or `tesseract` runtime failures).
  4. Built image size is within Fly free-tier rootfs limits, verified by `docker image inspect`.
**Plans**: 1 plan
  - [x] 02-01-PLAN.md — Dockerfile (single-stage, non-root, CPU torch, Docling model preload) + smoke-test script (build, health, PDF/DOCX ingest, size audit) + fixtures

### Phase 3: Prod Supabase Project
**Goal**: A dedicated prod Supabase project exists with the exact schema, RLS policies, Storage bucket config, and default board-game KB that the app expects at runtime.
**Depends on**: Phase 1 (secrets hygiene before handling prod keys)
**Requirements**: DEPLOY-03
**Success Criteria** (what must be TRUE):
  1. A new prod Supabase project exists, separate from dev, with `pgvector` extension enabled before migrations run.
  2. `supabase db push` applied all current migrations in order; `SELECT count(*) FROM supabase_migrations.schema_migrations` matches the repo migration count.
  3. Storage bucket `documents` exists in prod with policies reapplied so RLS behaves identically to dev.
  4. Default board-game KB seed script completes successfully against prod and `SELECT count(*) FROM documents WHERE visibility='public'` returns the expected seed count (≥10 games).
  5. Prod `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and anon key are captured in the developer's password manager (not in the repo).
**Plans**: 2 plans
  - [x] 03-01-PLAN.md — Repo prep (.gitignore .env*, supabase init, migration rename to timestamps, run_all bundle to legacy/, backend/config.py ENV_FILE patch, verify_prod_supabase.sh) + supabase link/db push + schema verify
  - [x] 03-02-PLAN.md — Build .env.prod, run idempotent seed (10 board games), verify seed counts, capture creds in 1Password, supabase unlink

### Phase 4: Deploy Backend to Fly.io
**Goal**: The containerized backend is reachable at a public `*.fly.dev` URL, talking to the prod Supabase project, serving `/api/health` and SSE chat end-to-end.
**Depends on**: Phase 2, Phase 3
**Requirements**: DEPLOY-04, DEPLOY-07, SEC-03
**Success Criteria** (what must be TRUE):
  1. `fly.toml` exists with `shared-cpu-1x@1gb`, `internal_port=8000`, `/api/health` health check, `auto_stop_machines="suspend"`, and no `min_machines_running` — with a one-line commented toggle documented for keep-warm.
  2. All runtime secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENROUTER_API_KEY`, `LANGSMITH_*`, `TAVILY_API_KEY`, placeholder `CORS_ALLOWED_ORIGINS`) are set via `flyctl secrets set` — verified with `flyctl secrets list` and grep of the pushed image showing none of these values baked in.
  3. `fly deploy` succeeds and `curl https://<app>.fly.dev/api/health` returns 200.
  4. End-to-end SSE chat request via `curl` to the Fly URL streams tokens without buffering.
**Plans**: 2 plans
  - [x] 04-01-PLAN.md — Wave 1 artifacts: fly.toml (D-11/D-12), shared JWT helper _lib/get_test_jwt.sh (D-14), fly_smoke.sh (D-13), refactor docker_smoke.sh to consume helper
  - [x] 04-02-PLAN.md — Wave 2 deploy: preflight (auth, .env.prod, prod test user), flyctl apps create (with collision fallback), secrets import --stage, flyctl deploy, fly_smoke.sh end-to-end, SEC-03 image-purity check

### Phase 5: Deploy Frontend to Cloudflare Pages
**Goal**: The Vite SPA is live at a public Cloudflare Pages URL, pointing its API calls at the Fly backend, with correct SPA deep-link refresh behavior.
**Depends on**: Phase 4 (needs Fly URL to bake into `VITE_API_BASE_URL`)
**Requirements**: DEPLOY-05
**Success Criteria** (what must be TRUE):
  1. A Cloudflare Pages project is connected to the repo with build command `npm run build` and output dir `frontend/dist`, producing a green deploy.
  2. CF Pages env vars are set for `VITE_API_BASE_URL` (= Fly URL), `VITE_SUPABASE_URL` (prod), and `VITE_SUPABASE_ANON_KEY` (prod anon key).
  3. `public/_redirects` (`/* /index.html 200`) is present so refreshing a deep route (e.g. `/documents`) returns the SPA, not a 404.
  4. Loading the public CF Pages URL in a browser renders the login page and the Network tab shows requests going to the absolute Fly URL (not same-origin `/api`).
  5. UI hint check: frontend phase involves React/Vite/SPA routing.
**Plans**: TBD
**UI hint**: yes

### Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps
**Goal**: With both URLs known, a real end user can log in and chat on the prod URL, and no agentic or rate-based runaway can drain the LLM budget.
**Depends on**: Phase 4, Phase 5
**Requirements**: SEC-01, SEC-04, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. A user can sign up + log in from the prod CF Pages URL — Supabase Auth redirect URLs include the CF Pages origin, email verification links land on prod, and there are no redirect loops.
  2. `CORS_ALLOWED_ORIGINS` Fly secret contains the CF Pages origin; cross-origin credentialed SSE from the prod frontend to the Fly backend succeeds, while a request from a non-allowlisted origin is rejected.
  3. A single authenticated user exceeding the configured per-minute `/api/chat` cap receives HTTP 429 with a JSON error — verified by a scripted burst.
  4. The main chat tool-use loop has a max-iterations cap (mirroring the explorer's 6-cap); an adversarial prompt cannot drive unbounded tool calls.
  5. An OpenRouter monthly spend alert/cap is configured on the account and a test alert has been confirmed delivered.
**Plans**: TBD

### Phase 7: Observability Baseline
**Goal**: Before the prod URL is shared publicly, uncaught frontend errors, backend traces, and uptime all flow to dedicated prod channels so real failures are visible to the developer.
**Depends on**: Phase 6
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. A deliberately triggered uncaught error in the prod frontend appears in a dedicated Sentry project with a fully un-minified stack trace (source maps uploaded by `@sentry/vite-plugin` at build time).
  2. A real chat request against the prod backend appears as a trace in the `boardgame-rag-prod` LangSmith project and not in the dev project.
  3. UptimeRobot monitors are active against the Fly `/api/health` endpoint and the CF Pages frontend on ≤5-minute intervals, and a simulated downtime produces an email alert to the owner.
  4. `/api/health` performs a lightweight Supabase query (e.g. `select 1` or a `count` on a small table) so monitor success also keeps the Supabase prod project from pausing after 7 days idle.
**Plans**: TBD

### Phase 8: Portfolio Polish
**Goal**: A reviewer visiting the public URL cold can try the app in one click, see a polished error surface if anything upstream fails, and get a full portfolio story from the README.
**Depends on**: Phase 7
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04
**Success Criteria** (what must be TRUE):
  1. The prod login page shows a "Try demo" button that logs the visitor in as a pre-seeded demo user in one click — no signup required — and the credentials are documented in the README.
  2. When the LLM provider errors or rate-limits, the chat UI renders a graceful error message instead of a crash; individual tool failures (rerank, web search, sub-agent) are caught so the main agent continues without them.
  3. The repo root `README.md` contains the live URL, demo credentials, an architecture diagram, the deploy command sequence (`docker build`, `fly deploy`, CF Pages), screenshots/GIF of the app in use, and a short portfolio pitch.
  4. The README displays a deploy-status badge (or equivalent) reflecting current deployment health.
  5. UI hint check: "Try demo" button and graceful chat error surface are UI-visible changes.
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Secrets & Repo Hygiene | 0/2 | Not started | — |
| 2. Dockerize Backend | 0/? | Not started | — |
| 3. Prod Supabase Project | 0/2 | Not started | — |
| 4. Deploy Backend to Fly.io | 0/? | Not started | — |
| 5. Deploy Frontend to Cloudflare Pages | 0/? | Not started | — |
| 6. Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps | 0/? | Not started | — |
| 7. Observability Baseline | 0/? | Not started | — |
| 8. Portfolio Polish | 0/? | Not started | — |

## Coverage Map

| REQ-ID | Phase |
|--------|-------|
| DEPLOY-01 | 2 |
| DEPLOY-02 | 1 |
| DEPLOY-03 | 3 |
| DEPLOY-04 | 4 |
| DEPLOY-05 | 5 |
| DEPLOY-06 | 1 |
| DEPLOY-07 | 4 |
| DEPLOY-08 | 1 |
| SEC-01 | 6 |
| SEC-02 | 1 |
| SEC-03 | 4 |
| SEC-04 | 6 |
| SEC-05 | 6 |
| SEC-06 | 6 |
| SEC-07 | 1 |
| OBS-01 | 7 |
| OBS-02 | 7 |
| OBS-03 | 7 |
| OBS-04 | 7 |
| PORT-01 | 8 |
| PORT-02 | 8 |
| PORT-03 | 8 |
| PORT-04 | 8 |

**Coverage:** 23/23 requirements mapped, no orphans, no duplicates.

## Backlog

### Phase 999.1: Chat empty-state UX (BACKLOG)

**Goal:** When no threads exist, sending a chat message silently does nothing. Either block the input until "+ New Chat" is clicked OR auto-create an initial thread on first message send. Caught during Phase 3 UAT.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
