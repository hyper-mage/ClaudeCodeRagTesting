# Architecture Research — v1.1 Portfolio Deployment

**Domain:** Public deployment of existing FastAPI + Vite + Supabase RAG app
**Researched:** 2026-04-22
**Confidence:** HIGH (integration shape), MEDIUM (exact Docling system package list, Fly.io body-size behavior — verify at build time)

---

## Standard Architecture (Target State)

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Browser (any machine)                         │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                    Frontend SPA (Vite build)                 │    │
│   │  - AuthContext (Supabase JS, anon key)                       │    │
│   │  - useChat / useDocuments hooks                              │    │
│   │  - apiFetch(`${API_BASE}/api/...`)  ← NEW: absolute URL      │    │
│   │  - Sentry browser SDK              ← NEW                     │    │
│   └─────────────────────────────────────────────────────────────┘    │
└──────────────────┬────────────────────────┬──────────────────────────┘
                   │                        │
              HTTPS│ REST + SSE             │ HTTPS (auth, realtime)
                   ▼                        ▼
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│  Vercel (frontend static)    │   │  Supabase PROD project           │
│  - SPA rewrite → index.html  │   │  - Postgres + pgvector           │
│  - Env: VITE_API_BASE_URL    │   │  - Auth (JWT, redirect allowlist)│
│  - Env: VITE_SUPABASE_URL    │   │  - Storage (documents bucket)    │
│  - Env: VITE_SUPABASE_ANON   │   │  - Realtime (ingestion status)   │
│  - Env: VITE_SENTRY_DSN      │   │  - RLS policies                  │
└──────────────────────────────┘   └──────────────┬───────────────────┘
                                                  │ service-role key
                                                  │ (server-side only)
┌──────────────────────────────────────────────────┼───────────────────┐
│  Fly.io machine (backend)                        │                   │
│  ┌─────────────────────────────────────────────┐ │                   │
│  │  Docker image (multi-stage)                 │ │                   │
│  │  Stage 1: builder — pip install deps        │ │                   │
│  │  Stage 2: runtime — slim python + OS pkgs   │ │                   │
│  │    - poppler-utils, tesseract-ocr,          │ │                   │
│  │      libgl1 (or opencv-headless only),      │ │                   │
│  │      libglib2.0-0, fonts                    │ │                   │
│  │  uvicorn main:app --host 0.0.0.0 --port 8080│─┘                   │
│  │  - CORSMiddleware: allow Vercel origin ONLY │                     │
│  │  - /api/health                              │                     │
│  │  - Sentry python SDK  ← NEW                 │                     │
│  └─────────────────────────────────────────────┘                     │
│  Secrets: flyctl secrets set (no .env in image)                      │
│  fly.toml: http_service, concurrency, health_check                   │
└──────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Observability                                                        │
│  - LangSmith prod project (LANGCHAIN_PROJECT=rag-prod)                │
│  - Sentry (frontend + backend DSNs, separate projects)                │
│  - UptimeRobot / BetterStack → GET /api/health every 5 min            │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| Vercel | Static host for SPA, SPA rewrite, env var injection at build | `vercel.json` + dashboard env vars |
| Fly.io machine | FastAPI + Docling runtime, persistent process | Dockerfile + `fly.toml` |
| Supabase prod | DB, auth, storage, realtime for production data | Separate project from dev |
| LangSmith prod project | LLM trace isolation per env | `LANGCHAIN_PROJECT` env var |
| Sentry | Error aggregation, source-mapped stack traces | `@sentry/react` + `sentry-sdk` |
| Uptime monitor | External liveness ping, alerting | UptimeRobot free tier → `/api/health` |

---

## Integration Points (How Deploy Layer Connects to Existing App)

### 1. Env Config — dev vs prod separation

**Current state:** Single `.env` at repo root, loaded by both `backend/config.py` (via `python-dotenv`) and Vite (via `envDir: '..'`). Single Supabase project for everything.

**Target state:** Two-axis split.

| Axis | Dev | Prod |
|------|-----|------|
| **Source of secrets** | `.env` file at repo root (gitignored) | Host secret stores: `flyctl secrets` for backend, Vercel dashboard for frontend |
| **Supabase project** | `rag-dev` (current) | `rag-prod` (new — fresh migrations + seed) |
| **LangSmith project** | `rag-masterclass` (current default) | `rag-prod` (env-switched via `LANGCHAIN_PROJECT`) |
| **CORS origin** | `*` (current) | `https://<portfolio>.vercel.app` only |
| **API base URL (frontend)** | relative `/api/...` via Vite proxy | absolute `https://<app>.fly.dev/api/...` via `VITE_API_BASE_URL` |

**Change to `backend/config.py`:** None required — `pydantic-settings` already reads from the process env, which is how Fly.io injects secrets. The `load_dotenv()` call at top of file is harmless on Fly (no `.env` in image → no-op). **Keep it** for dev parity.

**Change to frontend:** `apiFetch` in `frontend/src/lib/api.ts` must prefix paths with `import.meta.env.VITE_API_BASE_URL ?? ''`. Empty string in dev preserves the Vite proxy path; absolute URL in prod hits Fly directly.

### 2. CORS for SSE

**Current (`backend/main.py`):**
```python
allow_origins=["*"],
allow_credentials=True,   # ← INVALID with "*" per CORS spec
```

Browsers reject this combo silently for credentialed requests; SSE `EventSource` with `withCredentials: true` will break. Even without credentials, `*` is unsafe for a public backend with service-role secrets.

**Target:**
```python
allowed = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,            # e.g. ["https://bgkb.vercel.app", "http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Type"],
)
```

Add `cors_allowed_origins: str = "http://localhost:5173"` to `Settings`. On Fly: `flyctl secrets set CORS_ALLOWED_ORIGINS="https://bgkb.vercel.app"`. Preview deploys (Vercel PR URLs) require either wildcard pattern support (not in stdlib CORSMiddleware — would need `allow_origin_regex`) or omitting preview from backend reach.

**SSE-specific:** No special CORS knobs needed beyond the above. SSE is just a long-lived GET; `sse-starlette` streams as `text/event-stream` and CORSMiddleware handles the preflight correctly when `Authorization` is in `allow_headers`.

### 3. Frontend API Base URL

**Pattern — "empty-string default" preserves both modes:**

```ts
// frontend/src/lib/api.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function apiFetch(path: string, options: RequestInit = {}) {
  // path is always "/api/..."; API_BASE is "" in dev, absolute in prod
  const url = `${API_BASE}${path}`
  // ... rest unchanged
}
```

Same pattern must be applied to the SSE `EventSource` construction in `useChat` (wherever `/api/chat/stream` or similar is opened). `EventSource` does not send `Authorization` headers — if the current flow relies on cookies or query-param tokens, that behavior is unchanged; just prefix the URL.

**Dev:** `VITE_API_BASE_URL` unset → empty string → `/api/...` → Vite proxy → localhost:8000.
**Prod:** Vercel env `VITE_API_BASE_URL=https://bgkb-api.fly.dev` → absolute URL → Fly.io → CORS check passes.

### 4. Supabase Auth Redirect URLs

Supabase Auth rejects OAuth / magic-link / email-confirmation redirects not in the project allowlist. For v1.1 (email+password), this matters for **email confirmation** and **password reset** flows.

- Dev Supabase project: `http://localhost:5173/**` allowlisted (already working).
- Prod Supabase project (new): allowlist `https://<portfolio>.vercel.app/**` AND `http://localhost:5173/**` if the same prod project is ever hit from dev (not recommended — keep projects isolated).
- Set `Site URL` on prod project to the Vercel production URL.
- Vercel preview deploys get unique URLs; either add `https://*.vercel.app` (wildcard allowed) or accept that confirmations only work from the stable prod URL.

### 5. Docker Image for Docling

**Strategy:** Multi-stage build; `python:3.12-slim` runtime; pre-download Docling models in builder to avoid cold-start downloads.

**System packages (runtime stage):**
- `poppler-utils` — PDF rendering for page images
- `tesseract-ocr` + `tesseract-ocr-eng` — OCR engine (EasyOCR also works but downloads ~100MB models)
- `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1` — image libs
- `libgl1` — **only if** using `opencv-python`; prefer `opencv-python-headless` and skip `libgl1` (reduces image ~200MB)
- `fonts-dejavu-core` — font fallback for rendered PDFs

**Dockerfile skeleton:**
```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt
# Pre-download Docling models (optional — trades image size for cold-start speed)
RUN python -c "from docling.document_converter import DocumentConverter; DocumentConverter()"

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-eng \
    libglib2.0-0 libsm6 libxext6 libxrender1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
COPY --from=builder /root/.cache/docling /root/.cache/docling
ENV PATH=/root/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/ ./
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Size target:** ~1.2–1.8 GB with pre-downloaded Docling models. Without model pre-download: ~700–900 MB but first ingestion is slow. **Recommendation:** pre-download; Fly.io scratch pull is fast, user-facing latency matters more.

### 6. File Upload Size Limits

Fly.io proxy itself does not impose a strict request-body cap in current docs (community reports historic ~3MB issues were usually uvicorn/stdlib defaults, not the proxy). Real constraints:

- **uvicorn**: no default body cap; accepts what ASGI receives.
- **FastAPI `UploadFile`**: streams to disk via `SpooledTemporaryFile` (default 1MB spool → then disk). No hard cap.
- **Supabase Storage**: 50MB per file on free tier (enforced server-side).
- **Recommendation:** enforce `MAX_UPLOAD_MB = 25` in the documents router (read `content-length` header, 413 early). Matches a reasonable board-game rulebook ceiling and leaves headroom under Supabase's 50MB.

**SSE timeouts:** Fly.io's default request timeout is generous (hours for long-running connections), but chat streams should complete in < 2 min. The existing `llm_timeout: int = 120` in `Settings` is the binding constraint. No Fly-specific tweak needed.

### 7. Health Check

`backend/main.py` **already has** `GET /api/health` returning `{"status": "ok"}` — sufficient for:
- Fly.io `[[http_service.checks]]` in `fly.toml` (liveness for zero-downtime deploys)
- UptimeRobot external monitor (5-min interval, free tier)

**Enhancement (optional):** a `/api/health/deep` that checks Supabase reachability and LLM API key presence, returning 503 on failure. Keep the simple `/api/health` for Fly (fast, no external deps) to avoid flapping during Supabase blips.

### 8. Deploy Flow

**Recommended: manual first, automated second.**

Phase A (first deploy — manual, catch surprises):
1. `flyctl launch` → edits `fly.toml`, `flyctl deploy`
2. `vercel deploy --prod`
3. Verify end-to-end, then snapshot working state.

Phase B (automation — only after Phase A is green):
- GitHub Actions on push to `main`:
  - Backend job: `flyctl deploy --remote-only` (uses `FLY_API_TOKEN` secret)
  - Frontend job: Vercel's native GitHub integration (no workflow needed — Vercel auto-builds on push)
- Preview deploys: Vercel preview for every PR; backend stays pinned to prod Fly machine (no ephemeral backends).

**Why manual first:** Docling native deps, CORS origin, Supabase redirect URLs, and Fly secrets all have silent-failure modes that are faster to debug interactively than through CI logs.

---

## New Components (Files/Artifacts Introduced by v1.1)

| File / Artifact | Purpose | Location |
|---|---|---|
| `backend/Dockerfile` | Multi-stage image with Docling system deps | repo root of backend context |
| `backend/.dockerignore` | Exclude `venv/`, `tests/`, `__pycache__`, `.env` | backend dir |
| `fly.toml` | App name, region, http_service, health_check, concurrency | repo root (or `backend/`) |
| `frontend/vercel.json` | SPA rewrite (`/(.*)` → `/index.html`), optional headers | `frontend/` |
| `backend/services/sentry_init.py` (or inline in `main.py`) | `sentry_sdk.init(dsn=..., traces_sample_rate=0.1)` | backend services |
| `frontend/src/lib/sentry.ts` | `Sentry.init({ dsn: VITE_SENTRY_DSN, integrations: [browserTracingIntegration()] })` | frontend lib |
| `.github/workflows/deploy-backend.yml` (Phase B) | CI deploy to Fly.io | repo |
| Supabase prod project | Separate project; run all migrations in `supabase/migrations/` + seed | hosted |
| `scripts/seed-prod-kb.py` (if not already idempotent) | Seed 10 default board games into prod project | repo |
| `DEPLOY.md` or README section | Demo creds, deployed URL, env var checklist | repo |

## Modified Components

| File | Change |
|---|---|
| `backend/main.py` | Replace `allow_origins=["*"]` with env-driven allowlist; optional Sentry init |
| `backend/config.py` | Add `cors_allowed_origins`, `sentry_dsn`, `environment` ("dev"/"prod") fields |
| `frontend/src/lib/api.ts` | Prefix paths with `VITE_API_BASE_URL` (empty-string default) |
| `frontend/src/lib/supabase.ts` | No change (already env-driven via `VITE_*`) |
| `frontend/vite.config.ts` | No change — dev proxy stays; prod build uses env var |
| `useChat` hook (SSE `EventSource` construction) | Same API-base prefix pattern |
| `.env.example` | Add `CORS_ALLOWED_ORIGINS`, `VITE_API_BASE_URL`, `VITE_SENTRY_DSN`, `SENTRY_DSN` |

---

## Data Flow Changes (Dev vs Prod)

### Dev (unchanged)
```
Browser → http://localhost:5173/api/chat  (Vite proxy)
       → http://localhost:8000/api/chat   (FastAPI)
       → Supabase rag-dev
       → LangSmith "rag-masterclass"
```

### Prod
```
Browser (any) → https://bgkb.vercel.app           (static assets)
             → https://bgkb-api.fly.dev/api/chat  (absolute, CORS-checked)
                 → Supabase rag-prod (service role)
                 → LangSmith "rag-prod"
                 → Sentry on error
```

**Key change:** API base URL is now **read at build time** on the frontend (baked into the JS bundle by Vite) and **read at process-start time** on the backend (from Fly secrets). Neither is runtime-configurable in the browser — a change to `VITE_API_BASE_URL` requires a Vercel rebuild.

---

## Suggested Build Order (dependency-respecting)

1. **Supabase prod project** — create, run migrations, seed default KB, verify auth works via SQL editor. *(Blocks everything downstream — no point deploying backend until it can point at a real DB.)*
2. **Env split in code** — add `cors_allowed_origins`, `environment`, Sentry fields to `backend/config.py`; update `backend/main.py` CORS; update `frontend/src/lib/api.ts` and SSE call sites to use `VITE_API_BASE_URL`. *Validate locally by setting `VITE_API_BASE_URL=http://localhost:8000` and running frontend without Vite proxy.*
3. **Dockerize backend** — write Dockerfile + `.dockerignore`, build locally (`docker build`), run locally (`docker run -p 8080:8080 --env-file .env`), confirm `/api/health` and one ingestion + one chat request work against **dev Supabase**.
4. **Deploy backend to Fly.io** — `flyctl launch`, set secrets (incl. `SUPABASE_URL` pointing at **prod** project now), deploy, verify `/api/health` externally, verify one chat from curl with CORS origin header.
5. **Deploy frontend to Vercel** — `vercel.json` rewrite, env vars (`VITE_API_BASE_URL=https://<fly-url>`, `VITE_SUPABASE_*` for prod), deploy, end-to-end smoke test.
6. **Harden CORS & Supabase redirects** — narrow `CORS_ALLOWED_ORIGINS` to the exact Vercel prod URL; add Vercel URL to Supabase Auth allowlist + Site URL.
7. **Observability** — LangSmith prod project env switch, Sentry frontend + backend init, UptimeRobot monitor on `/api/health`.
8. **CI (optional)** — GitHub Action for backend deploy; Vercel auto-deploys frontend on push.
9. **Docs** — README deployed URL, demo credentials, env var checklist, architecture diagram.

**Rationale:**
- Env split (step 2) must land **before** Dockerize (step 3) because the image will bake in the new config shape.
- Dockerize (step 3) must land **before** Fly deploy (step 4) — Fly needs an image.
- Backend deploy (step 4) must land **before** frontend deploy (step 5) — frontend needs an API URL to bake into its bundle.
- CORS hardening (step 6) comes **after** both are live so you can set the exact Vercel URL, not a guess.

---

## Anti-Patterns to Avoid

### AP1: Shared Supabase project across dev and prod
**What people do:** Save the $0 of a second project, use one DB for both.
**Why it's wrong:** Test data pollutes prod; RLS bugs in dev leak real user data; migrations become irreversible; auth redirect allowlists conflict.
**Instead:** Two projects. Supabase free tier allows two. The only shared asset is the migration SQL files.

### AP2: `CORS allow_origins=["*"]` with `allow_credentials=True`
**What people do:** Keep the dev-convenient wildcard.
**Why it's wrong:** Browsers silently drop credentialed responses; spec-violating; any site can hit your backend API.
**Instead:** Explicit origin list from env var. `*` is only tolerable for non-credentialed public APIs.

### AP3: `.env` file baked into the Docker image
**What people do:** `COPY .env .` in Dockerfile for convenience.
**Why it's wrong:** Secrets in the image registry; every layer push leaks them; rotation requires rebuild.
**Instead:** `.dockerignore` excludes `.env`; secrets injected by `flyctl secrets set` at deploy time; `pydantic-settings` reads from process env — zero code change needed.

### AP4: Hardcoded prod API URL in frontend source
**What people do:** `const API = 'https://bgkb-api.fly.dev'` in a constants file.
**Why it's wrong:** Breaks dev proxy; forces source edits to change deploy target; hostile to preview environments.
**Instead:** `import.meta.env.VITE_API_BASE_URL` with empty-string fallback. Preserves dev proxy path, parameterizes prod.

### AP5: Running Docling model downloads on first request
**What people do:** Skip pre-download to save image size.
**Why it's wrong:** First user to upload a PDF waits 30–120s for model downloads; Fly.io machine may hit memory/disk limits during concurrent downloads; cold starts look broken.
**Instead:** Pre-download in Dockerfile builder stage and `COPY` the cache into runtime stage. Accept the ~500MB image size cost.

### AP6: Deploying before migrations are applied
**What people do:** Push backend code, then remember to run migrations.
**Why it's wrong:** First requests hit missing tables, 500s flood LangSmith/Sentry, false alerts.
**Instead:** Apply migrations to prod Supabase **first** (Step 1 above), verify schema with a SQL probe, then deploy backend. Add a startup check in `main.py` that queries one known table and logs a fatal error on failure.

---

## Scaling Considerations (portfolio scope)

| Scale | Adjustment |
|-------|-----------|
| 0–10 users (portfolio demo) | Single Fly.io shared-cpu-1x 256MB machine; Supabase free tier; no Redis/queue needed |
| 10–100 users (unexpected traffic) | Scale Fly machine to 1x 512MB; set `auto_stop_machines=false`; enable Fly metrics; watch Supabase connection pool |
| 100+ users | Not in v1.1 scope — would need: Fly machines plural + sticky sessions for SSE, Supabase Pro for connection pooler, rate limiting, background worker for Docling ingestion |

**First bottleneck in portfolio scope:** Docling CPU on concurrent uploads (single-threaded per machine). Mitigation: document limit per user, `MAX_UPLOAD_MB`, surface ingestion queue status via existing Realtime channel.

---

## Open Questions / Flags

- **Docling exact `apt` list** (MEDIUM confidence): verify at first `docker build` — the list above is standard across reference Dockerfiles but Docling's dep tree can shift across releases. Pin `docling==<ver>` in `requirements.txt` before prod deploy.
- **Fly.io body-size cap** (MEDIUM): community reports historic issues, docs are quiet. Test a 25MB upload against a staging Fly machine before committing to the limit. If 413 appears from Fly (not uvicorn), lower the app-side cap.
- **Vercel preview CORS** (LOW urgency): if preview deploys are needed, either switch CORS to `allow_origin_regex=r"https://.*\.vercel\.app$"` or document that previews hit prod backend anyway (RLS keeps it safe but auth redirects won't work from preview URLs unless Supabase allowlist uses `https://*.vercel.app`).
- **SSE reconnection semantics**: `EventSource` auto-reconnects; verify backend tolerates mid-stream CORS preflight on reconnect (stdlib CORSMiddleware handles this fine; just flagging for validation).

---

## Sources

- [Fly.io FastAPI docs](https://fly.io/docs/python/frameworks/fastapi/) — deploy pattern, fly.toml shape
- [Fly.io app configuration reference](https://fly.io/docs/reference/configuration/) — http_service, checks, concurrency
- [Fly.io request body size community thread](https://community.fly.io/t/http-request-size-limits/12698) — known historic upload issues
- [Vercel Vite framework guide](https://vercel.com/docs/frameworks/frontend/vite) — SPA rewrite, env vars
- [Vercel vercel.json reference](https://vercel.com/docs/project-configuration/vercel-json) — rewrites config
- [Docling installation docs](https://docling-project.github.io/docling/getting_started/installation/) — system deps
- [Docling FAQ — libGL issue](https://docling-project.github.io/docling/faq/) — opencv-headless vs opencv-python
- [docling-serve container images](https://deepwiki.com/docling-project/docling-serve/6.1-container-images) — multi-stage reference, model pre-download pattern
- [FastAPI CORSMiddleware docs](https://fastapi.tiangolo.com/tutorial/cors/) — `allow_credentials` + origin list requirement
- [Supabase Auth redirect URL docs](https://supabase.com/docs/guides/auth/concepts/redirect-urls) — Site URL + allowlist pattern
- Existing repo files: `backend/main.py`, `backend/config.py`, `frontend/vite.config.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/supabase.ts`, `.planning/PROJECT.md`

---
*Architecture research for: v1.1 Portfolio Deployment integration*
*Researched: 2026-04-22*
