# Stack Research — v1.1 Portfolio Deployment

**Domain:** Public deployment of existing FastAPI + Vite + Supabase RAG app (free/low-tier hosting)
**Researched:** 2026-04-22
**Confidence:** HIGH (official docs + current 2026 pricing pages verified)

**Scope note:** Existing stack (React 19, Vite 6, FastAPI 0.115, Supabase, OpenAI SDK, Docling, LangSmith) is frozen. This doc ONLY covers what's added for deployment.

---

## Recommended Stack

### Core Deployment Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Docker** | 26+ (any recent) | Containerize backend w/ Docling native deps | Docling requires `libgl1` + `libglib2.0-0` system libs for PDF/OCR; container is the only portable way to ship those reliably. Fly.io deploys directly from a Dockerfile. |
| **`python:3.11-slim-bookworm`** | 3.11 | Docker base image for backend | Official Docling Docker reference uses this exact base. Docling supports 3.9–3.13; 3.11 matches local dev and avoids 3.12+ wheel gaps in some transitive deps. Bookworm has needed `libgl1`/`libglib2.0-0` packages. |
| **Fly.io** | `flyctl` latest | Backend host (Docker) | Native Dockerfile deploy, volumes for Docling model cache, generous RAM options ($3–5/mo for 512MB–1GB shared-cpu-1x), SSE streaming works out of the box (no 10s edge timeouts like Vercel functions), persistent machine model fits a long-lived FastAPI process with warm Docling converter singleton. |
| **Cloudflare Pages** | current | Frontend SPA host | Unlimited bandwidth on free tier (vs Vercel's 100GB/mo), 500 builds/mo is plenty for a portfolio, `_redirects` file gives clean SPA routing. Frontend has zero Vercel-specific features to justify paying attention to their Hobby tier limits. |
| **Supabase (prod project)** | hosted | Separate prod DB/Auth/Storage | New Supabase project (second free-tier project under same org) isolates prod data from dev. Free tier: 500MB DB, 1GB storage, 50k MAU — ample for portfolio. |
| **Sentry** | `@sentry/react@^10.49.0` | Frontend error tracking | Free Developer tier: 5k errors/mo, 10k perf events, 1 user. Native React 19 error-hook integration via `Sentry.reactErrorHandler` on `createRoot`. Integrates with Vite via `@sentry/vite-plugin` for source maps. |
| **`@sentry/vite-plugin`** | `^5.2.0` | Upload source maps on build | Auto-injects release IDs and uploads sourcemaps so stack traces un-minify. Plug into `vite.config.ts` `plugins` array. |
| **UptimeRobot** | free | HTTP uptime monitor | 50 monitors, 5-min interval, free. Portfolio only needs 2 (frontend URL + `/api/health`). Simpler than BetterStack (10 monitors, requires email setup) and doesn't need commercial-use dance of Cronitor. |
| **LangSmith (prod project)** | existing SDK `0.3.42` | Observability (already wired) | Just set `LANGSMITH_PROJECT=boardgame-rag-prod` + API key as Fly secrets. No code changes. |

### Supporting Libraries / Tooling

| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `flyctl` | latest | Fly deploy CLI | Local + CI deploy (`fly deploy`), secret mgmt (`fly secrets set`) |
| `wrangler` (optional) | `^4` | Cloudflare Pages CLI | Only if deploying via CLI vs Git integration; Git push is simpler |
| `supabase` CLI | `^1.200+` | Apply migrations to prod project | `supabase db push --db-url $PROD_DB_URL` before going live |
| `.dockerignore` | n/a | Keep build context small | Exclude `venv/`, `.planning/`, `frontend/`, tests |
| Health endpoint | n/a | `GET /health` in `main.py` | UptimeRobot + Fly machine health checks |

### What's NOT Added (explicit)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Kubernetes / ECS / custom orchestration | Overkill for single-container portfolio | Fly Machines (single `fly.toml`) |
| Vercel for frontend | 100GB bandwidth cap; SSE-proxy complications if proxying backend through Vercel functions | Cloudflare Pages (unlimited bandwidth, static only — backend is on Fly) |
| Render / Railway backend | Render spins down free tier (cold start kills first SSE request); Railway removed free tier | Fly.io (machines stay warm on paid $3–5/mo tier, or use `auto_stop_machines=suspend` for fast wake) |
| Netlify | Similar bandwidth caps to Vercel, no edge advantage for a pure static SPA | Cloudflare Pages |
| Datadog / New Relic | Paid-only for what we need | Sentry (frontend) + LangSmith (LLM) + UptimeRobot (HTTP) — all free |
| Docker Compose in prod | Only one service (backend); frontend is static | Raw `Dockerfile` + `fly.toml` |
| GPU instance for Docling | CPU torch install (`--extra-index-url .../cpu`) is ~10x smaller image | Default CPU-only torch in Dockerfile |
| BetterStack / Pingdom | Overkill free tier for one URL pair | UptimeRobot |
| Alpine base image | Docling has native torch + lxml deps that break on musl | `python:3.11-slim-bookworm` (glibc) |

---

## Integration Points (existing code touch-map)

### Backend (`backend/`)
- **New files:** `Dockerfile`, `.dockerignore`, `fly.toml` (repo root or `backend/`)
- **Modify `backend/main.py`:** Add `GET /health` returning `{"status":"ok"}`; tighten `CORSMiddleware` to read `ALLOWED_ORIGINS` from settings (comma-split) instead of `*`
- **Modify `backend/config.py`:** Add `allowed_origins: str = ""` field; keep `.env` local but expect Fly secrets in prod
- **No changes to services, routers, auth** — stateless backend already deploys as-is

### Frontend (`frontend/`)
- **New files:** `public/_redirects` (contents: `/* /index.html 200`), `.env.production` (with `VITE_API_BASE_URL`, `VITE_SENTRY_DSN`)
- **Modify `frontend/src/lib/api.ts`:** Read `import.meta.env.VITE_API_BASE_URL` (fallback to `/api` for dev via Vite proxy)
- **Modify `frontend/src/main.tsx`:** Add `Sentry.init({ dsn, integrations: [browserTracingIntegration(), replayIntegration()], tracesSampleRate: 0.1 })` + pass `Sentry.reactErrorHandler` to `createRoot(... , { onUncaughtError, onCaughtError })`
- **Modify `frontend/vite.config.ts`:** Add `sentryVitePlugin({ org, project, authToken: process.env.SENTRY_AUTH_TOKEN })` (guarded to prod build)

### Supabase
- **New project** in same org (free tier). Apply all `supabase/migrations/*.sql` via `supabase db push`
- **Re-run seed** script for default KB (10 board games)
- **Auth → URL Configuration:** Add prod frontend URL to Site URL + Redirect URLs allowlist
- **Storage bucket:** Recreate `documents` bucket + policies

### Secrets (set via `fly secrets set KEY=value`)
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET` (or JWKS URL), `OPENAI_API_KEY` / `OPENROUTER_API_KEY`, `EMBEDDING_API_KEY`, `TAVILY_API_KEY` (if used), `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=boardgame-rag-prod`, `LANGSMITH_TRACING=true`, `ALLOWED_ORIGINS=https://<app>.pages.dev`

---

## Reference Dockerfile Pattern

```dockerfile
FROM python:3.11-slim-bookworm

# Docling native deps (PDF rendering, image ops, OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

COPY backend/ ./backend/

ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    PORT=8000

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Reference `fly.toml` Essentials

```toml
app = "boardgame-rag"
primary_region = "iad"   # or nearest

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "suspend"   # fast wake, keeps warm state
  auto_start_machines = true
  min_machines_running = 0          # cost = 0 when idle

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/health"

[[vm]]
  size = "shared-cpu-1x"
  memory = "1gb"   # Docling model load needs headroom; 512mb OOMs on first PDF
```

## Reference `public/_redirects` (Cloudflare Pages SPA)

```
/*  /index.html  200
```

## Reference Sentry init (`frontend/src/main.tsx`)

```ts
import * as Sentry from "@sentry/react";

if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    tracesSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    replaysSessionSampleRate: 0.0,
  });
}

createRoot(document.getElementById("root")!, {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
}).render(<App />);
```

---

## Installation

```bash
# Frontend (run in frontend/)
npm install @sentry/react@^10.49.0
npm install -D @sentry/vite-plugin@^5.2.0

# Deploy CLIs (local machine)
# Fly: https://fly.io/docs/hands-on/install-flyctl/
# Cloudflare (optional): npm i -g wrangler@^4
# Supabase CLI: https://supabase.com/docs/guides/cli
```

No backend `requirements.txt` additions needed — Docker handles infra, LangSmith SDK already installed.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Fly.io | Render | If you want Git-push deploy over CLI and don't mind free-tier cold starts (~30s spin-up breaks first SSE stream — bad for chat UX) |
| Fly.io | Railway | If you need a built-in Postgres alongside (we don't — Supabase is our DB); Railway has no real free tier anymore |
| Fly.io | Hetzner/DigitalOcean droplet + Caddy | If you already run a VPS and want one monthly bill; loses auto-scale but costs ~$4/mo flat |
| Cloudflare Pages | Vercel | If you need Next.js ISR/serverless functions colocated with frontend (we don't — pure SPA) |
| Cloudflare Pages | Netlify | If you need Netlify Forms or specific plugin ecosystem (portfolio doesn't) |
| UptimeRobot | BetterStack | If you want a public status page + incident management for free (BetterStack's free tier includes that; UptimeRobot status page is paid) |
| Sentry | LogRocket / Highlight.io | If session replay is the primary need (Sentry has replay but LogRocket's UX is richer) |
| `python:3.11-slim-bookworm` | `python:3.12-slim` | Once Docling officially publishes Python 3.12 wheels for all transitive deps (verify before bumping) |

---

## Stack Patterns by Variant

**If budget = strict $0/mo:**
- Fly.io machines sized `shared-cpu-1x@512mb` with `auto_stop=suspend` + `min_machines_running=0` → often $0–2/mo if traffic is sporadic (portfolio demo clicks)
- BUT: 512MB will OOM on first Docling PDF parse. Accept ~$3–5/mo for 1GB, OR add a Fly volume for model cache + keep `min_machines_running=1` only during demos

**If demo traffic spikes (portfolio review day):**
- Bump `min_machines_running = 1` temporarily; Fly auto-scales up to `max_machines_running` you set. Revert after.

**If you want zero cold-start on backend:**
- `auto_stop_machines = "off"` → always-on single machine ~$5/mo for 1GB RAM

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `@sentry/react@^10.49` | React 19.2.4 | React 19 error-hook support added in Sentry v9+; v10 is current recommended |
| `@sentry/vite-plugin@^5.2` | Vite 6.4.1 | Vite 5 and 6 both supported |
| `python:3.11-slim-bookworm` | `docling` (latest) | Docling's own Dockerfile uses this exact base — lowest risk |
| Fly Machines `shared-cpu-1x@1gb` | Docling + torch CPU | 512MB is insufficient for first model load; 1GB tested minimum |
| Cloudflare Pages build | Vite 6 | Node 20+ default build image supports Vite 6 natively |
| Supabase CLI `^1.200` | Postgres 15+ pgvector migrations in repo | All existing migrations compatible; no rewrites |

---

## Free-Tier Constraints to Watch

| Service | Free Limit | Portfolio Impact |
|---------|------------|------------------|
| Fly.io | No true free tier anymore; pay-as-you-go from $0.0000022/s | Realistic $3–5/mo for 1GB machine with suspend |
| Cloudflare Pages | Unlimited bandwidth, 500 builds/mo | Nowhere near limit |
| Supabase Free | 500MB DB, 1GB storage, 50k MAU, pauses after 7d inactivity | Log in weekly OR upgrade to $25/mo Pro if reviewers hit a paused instance |
| Sentry Developer | 5k errors, 10k perf, 50 replays/mo | Fine for portfolio; add `tracesSampleRate: 0.1` to avoid burning quota |
| UptimeRobot | 50 monitors, 5-min interval, non-commercial | Portfolio = non-commercial, OK |
| LangSmith | 5k traces/mo free (Developer) | Portfolio demos won't exceed |

**Critical gotcha:** Supabase free projects pause after 7 days of no API activity. Mitigations: (a) UptimeRobot hitting `/health` which touches Supabase, (b) upgrade prod project to Pro ($25/mo) if this is a hiring-review piece.

---

## Sources

- [Fly.io Run a FastAPI app docs](https://fly.io/docs/python/frameworks/fastapi/) — fly.toml + Dockerfile patterns (HIGH)
- [Fly.io Pricing](https://fly.io/pricing/) — 2026 pricing model, machine costs (HIGH)
- [Fly.io Resource Pricing](https://fly.io/docs/about/pricing/) — per-second billing math (HIGH)
- [Docling Docker Deployment (DeepWiki)](https://deepwiki.com/docling-project/docling/10.1-docker-deployment) — base image, `libgl1`/`libglib2.0-0`, CPU torch flag, `OMP_NUM_THREADS=4` (HIGH)
- [Docling Installation docs](https://docling-project.github.io/docling/getting_started/installation/) — Python 3.9–3.13 support matrix (HIGH)
- [Sentry React docs](https://docs.sentry.io/platforms/javascript/guides/react/) — React 19 `reactErrorHandler` pattern (HIGH)
- [Sentry Vite sourcemaps](https://docs.sentry.io/platforms/javascript/guides/react/sourcemaps/uploading/vite/) — `@sentry/vite-plugin` usage (HIGH)
- [`@sentry/react` on npm](https://www.npmjs.com/package/@sentry/react) — current 10.49.0 verified (HIGH)
- [`@sentry/vite-plugin` on npm](https://www.npmjs.com/package/@sentry/vite-plugin) — current 5.2.0 verified (HIGH)
- [Cloudflare Pages vs Vercel vs Netlify 2026](https://www.codebrand.us/blog/vercel-vs-netlify-vs-cloudflare-2026/) — bandwidth + SPA routing specifics (MEDIUM — secondary source, matches CF docs)
- [BetterStack — Best Website Uptime Monitoring Tools 2026](https://betterstack.com/community/comparisons/website-uptime-monitoring-tools/) — free-tier monitor counts (MEDIUM)
- [UptimeRobot — 11 Best Uptime Monitoring Tools 2026](https://uptimerobot.com/knowledge-hub/monitoring/11-best-uptime-monitoring-tools-compared/) — free-tier limits (MEDIUM)
- [LangSmith env vars — LangChain support](https://support.langchain.com/articles/3567245886-how-do-i-set-up-langsmith-api-key-environment-variables) — `LANGSMITH_PROJECT`, `LANGSMITH_TRACING` (HIGH)

---
*Stack research for: v1.1 Portfolio Deployment of Board Game KB RAG*
*Researched: 2026-04-22*
