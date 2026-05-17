# Phase 7: Observability Baseline — Research

**Researched:** 2026-05-15
**Domain:** Frontend error tracking (Sentry) + backend trace routing (LangSmith) + uptime monitoring (UptimeRobot) + DB-reachability health probe (supabase-py)
**Confidence:** HIGH (every load-bearing claim verified against installed SDK source, official docs, or prior phase artifacts)

## Summary

Phase 7 wires three free-tier observability surfaces around the already-deployed Fly + CF Pages prod stack so failures surface to the developer before the URL is shared. The work is mostly **dashboard + secret configuration** with three small code touches: (1) a `@sentry/vite-plugin` invocation in `frontend/vite.config.ts` plus a `frontend/src/lib/sentry.ts` init module wired from `frontend/src/main.tsx`; (2) the `/api/health` endpoint upgraded from `{"status":"ok"}` to a `supabase.table("documents").select("id", count="exact", head=True).limit(1).execute()` probe with 503-on-failure; (3) a Python verification script under `backend/scripts/` that asserts `LangSmith.list_runs(project_name="boardgame-rag-prod")` returns a freshly-emitted run while `project_name="boardgame-rag-dev"` does not.

The four open questions from CONTEXT.md are resolved with HIGH confidence: vite-plugin auto-detection does NOT cover CF Pages so `release.name` must be set explicitly to `process.env.CF_PAGES_COMMIT_SHA`; Fly suspend-resume on the existing `boardgame-rag-prod` machine completes in 2-5s (Phase 4 SUMMARY measured 2s suspend-resume + 7s cold deploy) — well inside UptimeRobot's configurable 30s default request timeout, so no keep-warm needed; supabase-py 2.13.0 has no inline-SQL escape hatch (verified by inspecting installed `Client.rpc` signature) so the lightest reachability probe is a head-only count against an existing read-mostly table (`documents`) which avoids new migrations; LangSmith 0.3.42 `Client.list_runs` accepts `start_time: Optional[datetime.datetime]` (verified by `inspect.signature` against installed SDK) and the canonical "completed successfully" filter is `error=False` combined with a non-null `end_time`.

**Primary recommendation:** Slice into 3 waves — Wave 1 (Sentry frontend + source maps, in parallel with backend `/api/health` upgrade), Wave 2 (LangSmith env-var routing + Fly secret confirm + verification script), Wave 3 (UptimeRobot monitor creation + simulated-downtime drill). Total estimated effort: ~3-4 hours active execution, mostly dashboard work.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Uncaught error capture (OBS-01) | Browser / Client | CDN / Static (source-map upload at CF Pages build) | Errors happen in user browsers; source maps must be generated at build time and uploaded to Sentry from the CF Pages build environment |
| LLM trace routing (OBS-02) | API / Backend | — | LangSmith SDK runs inside the FastAPI process on Fly; env-var-driven project name is a pure backend concern |
| Uptime monitoring (OBS-03) | External (UptimeRobot) | API / Backend (health endpoint), CDN / Static (CF Pages root) | External pinger; the targets it pings live in two different tiers |
| DB-reachability probe (OBS-04) | API / Backend | Database / Storage (Supabase Postgres) | Backend endpoint that does a trivial DB query; Postgres reachability is the dependency being verified |

**Sanity check:** All four capabilities map to their conventional tiers. No tier confusion. The only cross-tier work is the Sentry source-map upload, which is intentional — source maps are a build-time artifact and must be uploaded from the build environment (CF Pages) to the error-tracking SaaS (Sentry).

## Project Constraints (from CLAUDE.md)

- **Python backend uses `venv`** (`backend/venv/`) — verified present, all probes in this research executed against `backend/venv/Scripts/python.exe`.
- **No LangChain/LangGraph** — using `langsmith` SDK directly is consistent with this rule (langsmith is the observability package, not the framework).
- **All tables need RLS** — `/api/health` MUST NOT touch user-scoped tables in a way that depends on auth. Service-role client bypasses RLS, so a head-only count against `documents` returns a count over the whole table (not RLS-filtered) which is fine for liveness purposes.
- **Free-tier first** — Sentry Developer, UptimeRobot Free, LangSmith free continue.
- **No new backend deps** beyond what's already in `requirements.txt` — confirmed: `langsmith==0.3.42` already there; `supabase==2.13.0` already there; no new Python deps needed.
- **Save plans to `.agent/plans/`** — Note: project also uses `.planning/phases/` (GSD workflow). This research targets the GSD path per the CONTEXT.md directive.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sentry (OBS-01)**
- **Scope:** Frontend only. Backend errors stay in Fly logs + LangSmith traces; no `sentry-sdk[fastapi]` on backend.
- **Tier:** Free Developer (5k errors/mo, 1 user, 30d retention) — sufficient for portfolio traffic.
- **Project:** Single project, name TBD by user during plan execution (`boardgame-rag-frontend` recommended).
- **Source maps:** Uploaded at build time via `@sentry/vite-plugin` configured in `frontend/vite.config.ts`. Plugin reads `SENTRY_AUTH_TOKEN` (CF Pages Build env, NOT runtime).
- **Release tagging:** Git SHA. CF Pages provides `CF_PAGES_COMMIT_SHA` at build; vite-plugin injects it as the release identifier so each deploy is a distinct release in Sentry. No semantic versioning.
- **PII scrub (beforeSend / beforeBreadcrumb):**
  - **MUST scrub:** Auth JWTs (Authorization header, `sb-*-auth-token` localStorage), user email, Supabase user UUID. No `Sentry.setUser({...})` calls — events stay anonymous.
  - **ALLOWED to send:** Chat message content (prompts + assistant responses), document file names + folder paths, error stacks, navigation breadcrumbs. Debug value outweighs privacy concern for a portfolio app handling non-sensitive board-game KB data.
- **Env vars (frontend):** `VITE_SENTRY_DSN` (Production scope only, Preview disabled per Phase 5 convention).

**`/api/health` (OBS-04)**
- **Probe:** `select 1` issued via the existing `supabase-py` service-role client at module level. No new tables, no RLS dependency, no RPC indirection. Lightest possible verification that Postgres is reachable + auth credentials valid.
- **Success response:** HTTP 200 + JSON `{"status": "ok"}` (preserves existing contract).
- **Failure response:** HTTP 503 + JSON `{"status": "degraded", "db": "unreachable"}`. Non-2xx triggers UptimeRobot alert.
- **Auth:** Public, unauthenticated.
- **Rate limit:** EXCLUDED from slowapi rate limiter added in Phase 6. UptimeRobot pings from rotating IPs without auth headers; rate-limit 429s would corrupt uptime ratio and mask real outages.
- **OBS-04 side effect:** Every 5-min ping issues a DB query → keeps Supabase free-tier project active (7-day idle pause prevented).

**LangSmith (OBS-02)**
- **Routing:** Single LangSmith API key in account. Project name routed via `LANGSMITH_PROJECT` env var per environment.
  - Local dev (`.env`): `LANGSMITH_PROJECT=boardgame-rag-dev`
  - Fly prod secret: `LANGSMITH_PROJECT=boardgame-rag-prod`
- **Existing wiring untouched:** `backend/services/tracing.py` already reads project from env; **see research finding below — this needs a small adjustment because the current code path hardcodes `LANGCHAIN_PROJECT`.**
- **Verification:** Automated. Plan must include a verification step that (1) sends a chat request against the deployed Fly URL, (2) calls `langsmith.Client().list_runs(project_name="boardgame-rag-prod", start_time=now-5min)` and asserts at least one run exists, (3) calls `list_runs(project_name="boardgame-rag-dev", start_time=now-5min)` and asserts zero matching runs.

**UptimeRobot (OBS-03)**
- **Tier:** Free. 50-monitor cap, 5-min minimum interval, email alerts.
- **Monitor count:** 2.
  - Monitor 1: `GET https://boardgame-rag-prod.fly.dev/api/health` — HTTP-status check (200 = up, 503 = down).
  - Monitor 2: `GET https://boardgame-rag-prod.pages.dev/` — HTTP-status check on CF Pages root.
- **Interval:** 5 minutes.
- **Alert contact:** Single email `<your-email>`. No SMS. No webhook.
- **Public status page:** NOT created.
- **Verification (simulated downtime):** `flyctl machine stop` on the prod machine briefly (or set CORS to a bogus value to force `/api/health` 5xx without taking down the machine — cleaner since it leaves the process running). Wait ≤10 min, confirm alert email arrives. Revert.

### Claude's Discretion

- Wave slicing within the plan (researcher recommends 3 waves; planner may collapse to 2 if dashboard work parallelizes).
- Exact filename of verification script under `backend/scripts/`.
- Exact wording of `beforeSend` filter regex for JWT scrubbing (must match `/^eyJ/` shape plus the `Authorization` header pattern; full implementation per Code Examples below).
- Whether to add a `LANGSMITH_PROJECT` field to `Settings` or rely on the langsmith SDK's native env-var resolution (RESEARCH recommends the latter — zero-touch).

### Deferred Ideas (OUT OF SCOPE)

- **Backend Sentry integration** — captured as future optional enhancement.
- **LangSmith automated daily digest / cost report** — out of scope.
- **UptimeRobot public status page** — explicitly rejected for now.
- **Backend log shipping (e.g., to Logtail, Axiom)** — Fly logs sufficient.
- **SLO / error budget tracking** — premature for solo portfolio.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-01 | Frontend reports uncaught errors and unhandled promise rejections to a dedicated Sentry project, with source maps uploaded at build time so stack traces are un-minified | Standard Stack §1 (Sentry SDK + vite-plugin); Code Example §1 (init); Code Example §2 (vite.config.ts); Pitfalls §1, §2, §3 |
| OBS-02 | Backend traces land in a dedicated LangSmith project (`boardgame-rag-prod`) separate from dev/local, configured via env vars only | Open Question 4 resolution; Standard Stack §3; Code Example §4 (verification script); Pitfalls §5 |
| OBS-03 | UptimeRobot monitors ping Fly `/api/health` and CF Pages frontend on ≤5-min interval; owner gets email on downtime | Open Question 2 resolution; Standard Stack §4; Pitfalls §6 |
| OBS-04 | `/api/health` performs a lightweight Supabase query so monitor failures catch real outages and keep Supabase prod project from pausing after 7-day idle | Open Question 3 resolution; Code Example §3 (FastAPI endpoint); Pitfalls §4, §7 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@sentry/react` | 10.53.1 (latest, verified via `npm view`) | Frontend SDK — `init`, `reactErrorHandler`, `ErrorBoundary` | React 19's createRoot exposes `onUncaughtError`/`onRecoverableError`/`onCaughtError` hooks; `@sentry/react` ≥9 ships `reactErrorHandler` designed for these hooks `[VERIFIED: npm view @sentry/react version → 10.53.1]` `[CITED: docs.sentry.io/platforms/javascript/guides/react/]` |
| `@sentry/vite-plugin` | 5.3.0 (latest, verified via `npm view`) | Build-time source-map upload + release tagging; auto-deletes `.map` files after upload | Official Sentry-maintained Vite plugin; only sanctioned path for source-map upload + release create. Engines: `node >= 18` (verified). Vite 6.4.1 is supported `[VERIFIED: npm view @sentry/vite-plugin version → 5.3.0]` `[VERIFIED: npm view @sentry/vite-plugin engines → {node: ">= 18"}]` |
| `langsmith` (Python) | 0.3.42 (already in `requirements.txt`) | LLM observability + run query API for verification script | Already wired in `backend/services/tracing.py`; SDK natively reads `LANGSMITH_PROJECT` env var (verified by inspecting installed SDK source — see Open Question 4) `[VERIFIED: backend/venv inspection of langsmith.utils.get_env_var]` |
| `supabase` (Python) | 2.13.0 (already in `requirements.txt`) | DB client for `/api/health` reachability probe | Already used everywhere; service-role client bypasses RLS so head-only count works without auth context `[VERIFIED: installed package version]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `slowapi` | 0.1.9 (already pinned) | Rate limiter; need to exempt `/api/health` from its scope | Use `@limiter.exempt` decorator OR (cleaner) keep `/api/health` undecorated since slowapi is opt-in per-route via `@limiter.limit` decorator (verified: current code only decorates `send_message`, so `/api/health` is already exempt) `[VERIFIED: grep of backend/routers/ for @limiter usage]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@sentry/vite-plugin` source-map upload | `sentry-cli releases files <release> upload-sourcemaps` shell step in CF Pages build command | CLI works but adds a separate npm install step + custom build script. Vite plugin is one config edit, runs as part of `npm run build`, and Sentry docs treat it as the canonical path. |
| `supabase.table("documents").select(count="exact", head=True)` | Create a `select_one()` Postgres RPC + `supabase.rpc("select_one")` | RPC is cleaner conceptually but adds a migration (24 → 25 files in `supabase/migrations/`) AND must be applied to prod via `supabase db push`. The table-coupled approach uses an existing public table (default KB seed has ≥10 rows after Phase 3) and adds zero migrations. **RECOMMENDED: table approach.** |
| `Sentry.captureException` manual wiring | Use `Sentry.ErrorBoundary` component AND `reactErrorHandler` in createRoot | Both. React 19's three error hooks catch most cases; `ErrorBoundary` catches render-tree errors per-route. Belt-and-suspenders is the documented best practice. `[CITED: docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/]` |
| Per-route `@limiter.exempt` on `/api/health` | Leave it undecorated (current state) | The CONTEXT decision says "EXCLUDED from rate limiter" — but in fact `/api/health` is in `main.py`, not `routers/chat.py`, and slowapi only enforces on routes decorated with `@limiter.limit`. **CONFIRMATION: no code change needed to satisfy "excluded from rate limit"** — the endpoint is already exempt by construction. `[VERIFIED: backend/main.py:65-67 has no @limiter decorator]` |

**Installation:**

```bash
# Frontend (Phase 7 adds these):
cd frontend
npm install --save @sentry/react@10
npm install --save-dev @sentry/vite-plugin@5

# Backend: zero new deps. langsmith and supabase already in requirements.txt.
```

**Version verification (run before plan execution):**

```bash
npm view @sentry/react version       # confirms ≥10.x stable
npm view @sentry/vite-plugin version # confirms ≥5.x stable
```

Verified 2026-05-15: latest stable versions are `@sentry/react@10.53.1` and `@sentry/vite-plugin@5.3.0`.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────┐
                          │       Developer (developer)       │
                          │  Receives: Sentry digest, UR email  │
                          └────────────▲────────────────────────┘
                                       │ email alerts
        ┌──────────────────────────────┼─────────────────────────────────┐
        │                              │                                 │
   ┌────▼────┐                ┌────────▼─────────┐               ┌──────▼────────┐
   │ Sentry  │                │   UptimeRobot    │               │   LangSmith   │
   │  Org    │                │  (2 monitors,    │               │  (2 projects: │
   │ project │                │   5-min interval)│               │   prod / dev) │
   │frontend │                └────────┬─────────┘               └──────▲────────┘
   └────▲────┘                         │                                │
        │ POST events                  │ GET /api/health                │ traces (HTTPS)
        │ + source-maps (build)        │ GET /                          │ when
        │                              │                                │ LANGSMITH_API_KEY set
        │                              │                                │
   ┌────┴──────────────┐    ┌──────────▼──────────────┐         ┌───────┴───────────┐
   │   Browser (CF)    │    │     Fly.io (prod)       │         │  Local dev laptop │
   │ React app +       │◄───┤  FastAPI /api/health    │         │  .env →           │
   │ @sentry/react init│SSE │   → supabase.table()    │         │  LANGSMITH_PROJECT│
   │ (DSN baked in)    ├───►│     .select(head=True)  │         │   =boardgame-rag- │
   └───────────────────┘    │   → Postgres ping       │         │     dev           │
        ▲                   │  Fly secret             │         └───────────────────┘
        │ build-time        │  LANGSMITH_PROJECT=     │
        │ source-map        │    boardgame-rag-prod   │
        │ upload            └─────────────┬───────────┘
        │                                 │
   ┌────┴────────────────────┐            │
   │  Cloudflare Pages       │            ▼
   │  build environment      │     ┌──────────────┐
   │  CF_PAGES_COMMIT_SHA    │     │   Supabase   │
   │  SENTRY_AUTH_TOKEN      │     │   Postgres   │
   │  (Build scope only)     │     │  (prod proj) │
   └─────────────────────────┘     └──────────────┘
```

Data flow for the four observability streams:
1. **Browser error** → `@sentry/react` `init` → POST to Sentry DSN → source map dereferences stack → human-readable trace in dashboard
2. **UptimeRobot** → polls 2 endpoints every 5 min → 503/non-200/timeout → SMTP email to owner
3. **/api/health** → triggers `supabase.table("documents").select(...).limit(1).execute()` → Postgres reads index → returns 200 (also: this query touches Postgres so the project's 7-day idle clock resets)
4. **Chat request to Fly** → `wrap_openai`-decorated client → langsmith SDK reads `LANGSMITH_PROJECT` env → trace routed to `boardgame-rag-prod`

### Recommended Project Structure

Phase 7 adds/modifies the following files (mapped 1:1 from `07-PATTERNS.md`):

```
frontend/
├── src/
│   ├── lib/
│   │   └── sentry.ts          # NEW: Sentry init singleton (mirrors lib/supabase.ts)
│   └── main.tsx               # MODIFY: side-effect import './lib/sentry' BEFORE createRoot
├── vite.config.ts             # MODIFY: append sentryVitePlugin() AFTER react() + tailwindcss()
└── package.json               # MODIFY: +@sentry/react, +@sentry/vite-plugin

backend/
├── main.py                    # MODIFY: /api/health body becomes DB probe with try/except → 503
├── services/
│   └── tracing.py             # MODIFY: read LANGSMITH_PROJECT first, fall back to current (or document zero-touch path — see Open Question 4)
└── scripts/
    └── verify_langsmith_routing.py  # NEW: posts test chat to prod, polls list_runs, asserts routing
```

### Pattern 1: Sentry browser init with React 19 + Vite

**What:** Single init module imported for side-effects at the top of `main.tsx` so it runs before any React rendering and registers global error/promise handlers; React 19's three `createRoot` error hooks are wired to `Sentry.reactErrorHandler()` for in-tree errors.

**When to use:** Every Vite + React 19 SPA that ships to a public URL with frontend error tracking.

**Example:** See Code Examples §1 + §2.

### Pattern 2: Vite plugin position matters

**What:** `sentryVitePlugin` must come AFTER all other plugins in the `plugins:` array, AND `build.sourcemap: true` must be set, otherwise the plugin can't find maps to upload.

**When to use:** Every time the plugin is added.

**Source:** `[CITED: docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/]` — "Place this plugin after all other plugins to ensure correct source map generation."

### Pattern 3: FastAPI health check with DB probe + 503 envelope

**What:** Wrap the DB call in a narrow try/except, return `{"status": "ok"}` on success or `JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})` on any exception. Don't expose error details (security).

**When to use:** Public health endpoints behind a load balancer or uptime monitor.

**Example:** See Code Examples §3.

### Pattern 4: Verification script structure (Python)

**What:** Stand-alone Python script under `backend/scripts/` that bootstraps `sys.path` like `seed_default_kb.py`, imports `Settings`, POSTs a real chat request to the prod Fly URL with the test JWT, polls `LangSmith.Client.list_runs` for up to 60s, asserts prod has ≥1 run AND dev has 0 runs.

**Reference analog:** `backend/scripts/seed_default_kb.py` (sys.path bootstrap) + `backend/scripts/fly_smoke.sh` (wait-and-assert idiom with `FIRST_CHUNK_MAX` timeout pattern).

**When to use:** Anytime you need to verify out-of-band SaaS state (LangSmith, Sentry) reflects an in-band action (chat request).

**Example:** See Code Examples §4.

### Anti-Patterns to Avoid

- **Initializing Sentry inside a React component** — must be at module-top side effect, before any code that could throw. If inside `useEffect`, you miss errors during initial render.
- **Forgetting `build.sourcemap: true`** — without it, `sentryVitePlugin` has nothing to upload, but doesn't error loudly; you just get minified stacks in Sentry forever.
- **Hardcoding the Sentry DSN in source** — must come from `import.meta.env.VITE_SENTRY_DSN` so dev builds don't pollute the prod project.
- **Calling `Sentry.setUser({email, id})`** — CONTEXT decision: events stay anonymous. Don't do it.
- **Using IP-based UptimeRobot keyword matching for "down"** — HTTP-status check (200 = up, anything else = down) is sufficient and simpler.
- **Probing `/api/health` with an authenticated query** — UptimeRobot doesn't carry auth headers. The probe must be unauthenticated and the service-role client (which is already used everywhere in `backend/`) is the right choice.
- **Touching user-scoped tables in `/api/health`** — would mask DB outages behind RLS issues. Stick to `documents` (default KB is global by design).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Frontend error capture + de-minification | A custom `window.onerror` handler + manual source-map lookup | `@sentry/react` + `@sentry/vite-plugin` | Source-map upload, release tagging, stack re-symbolication, fingerprinting, sampling, breadcrumbs, replay — all solved problems. |
| LLM trace routing per env | A custom log shipper that POSTs OpenAI responses to a server | `langsmith` SDK reading `LANGSMITH_PROJECT` env var | Already integrated; the project is just an env-var change. |
| Uptime monitoring | A cron job + `curl` + email script | UptimeRobot free tier | 50 monitors, 5-min interval, email/SMS/webhook alerts, status page — all for free. Building this badly is a classic rite of passage; don't. |
| DB-reachability probe | Direct psycopg connection | Existing `supabase-py` service-role client (`get_supabase()`) | Same auth context as the rest of the app; one less dep; verifies the actual code path used in production. |

**Key insight:** This entire phase is configuration + 3 small code touches. The temptation to invent custom telemetry/log-shipping/status-page infrastructure must be resisted. Free-tier SaaS solves all four problems.

## Common Pitfalls

### Pitfall 1: Source-map upload silent failure

**What goes wrong:** Build "succeeds", but Sentry never receives source maps and prod stacks remain minified for weeks before someone notices.

**Why it happens:** (a) `SENTRY_AUTH_TOKEN` is set in CF Pages **Runtime** env scope instead of **Build** scope (build can't see runtime-only vars); (b) `build.sourcemap` not set to `true`; (c) plugin placed before `react()` in the array; (d) wrong org/project slug.

**How to avoid:**
- Set `SENTRY_AUTH_TOKEN` in CF Pages dashboard under **Settings → Environment variables → Build environment variables** (NOT runtime variables) `[CITED: CF Pages build configuration]`
- Add `build: { sourcemap: true }` to vite.config.ts
- Put `sentryVitePlugin()` LAST in plugins array
- Enable plugin `debug: process.env.CF_PAGES === "1" ? false : true` for first deploy, then turn off
- After first deploy, manually trigger an error in browser DevTools and confirm un-minified stack in Sentry

**Warning signs:** Stack traces in Sentry show only `index-abc123.js:1:4567` with no source line numbers.

### Pitfall 2: Source maps publicly accessible

**What goes wrong:** Sentry has the maps, BUT `dist/` also still ships them to the CDN. Anyone can curl `https://prod.pages.dev/assets/index-abc123.js.map` and reverse-engineer the bundle.

**Why it happens:** Plugin defaults to KEEPING source-map files in dist after upload — only deletes them when `sourcemaps.filesToDeleteAfterUpload` is set.

**How to avoid:** Set `sourcemaps.filesToDeleteAfterUpload: ["./dist/**/*.map"]` in the plugin options (see Code Example §2).

**Warning signs:** `curl -fsSI https://boardgame-rag-prod.pages.dev/assets/index-<hash>.js.map` returns 200 instead of 404.

### Pitfall 3: PII leaked in Sentry breadcrumbs

**What goes wrong:** Sentry's default breadcrumbs include `fetch` requests with full `Authorization: Bearer <JWT>` headers. JWT contains the user's UUID + email + role.

**Why it happens:** The default breadcrumb integration captures everything. You must scrub via `beforeSend` AND `beforeBreadcrumb`.

**How to avoid:** Implement BOTH hooks per Code Example §1. Test by triggering an error after login and inspecting the Sentry event JSON for `eyJ` patterns (JWT prefix) in `breadcrumbs[].data.request_headers`.

**Warning signs:** Sentry event JSON contains strings matching `/^Bearer eyJ/` or `/sb-.*-auth-token/`.

### Pitfall 4: `/api/health` blocks on slow Postgres → cascading timeouts

**What goes wrong:** Supabase free tier has occasional cold-connection latency. If `/api/health` blocks for 30s+ on a slow query, UptimeRobot times out → false-positive downtime → developer noise.

**Why it happens:** No timeout on the supabase-py call; default httpx timeout is per-connection, not per-query.

**How to avoid:** Wrap the DB call with `asyncio.wait_for(..., timeout=5.0)` OR (simpler) configure the supabase client with a 5s timeout. For Phase 7 specifically, since `supabase.table().select(head=True)` is a pure index-count query, latency should be <100ms in practice; the bigger risk is full Postgres unreachability which the try/except already catches.

**Warning signs:** UptimeRobot logs show "Timeout" outcomes rather than "503" outcomes when something is wrong.

### Pitfall 5: LangSmith project name silently ignored

**What goes wrong:** Fly secret `LANGSMITH_PROJECT=boardgame-rag-prod` is set, but prod traces still land in `rag-masterclass`.

**Why it happens:** `backend/services/tracing.py:15` UNCONDITIONALLY sets `os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project` at startup. Since `Settings.langchain_project` defaults to `"rag-masterclass"` and is not auto-aliased to `LANGSMITH_PROJECT`, the env-var routing decision is silently overridden.

**How to avoid:** EITHER
- **(A)** name the Fly secret `LANGCHAIN_PROJECT` instead of `LANGSMITH_PROJECT` (pydantic-settings will pick it up into `Settings.langchain_project`; no code change). Per `04-02-PLAN.md:94`, the Fly secret was actually staged as `LANGSMITH_PROJECT` — so this option requires a Fly-side rename. CONTEXT.md also says `LANGSMITH_PROJECT`.
- **(B)** modify `tracing.py` to prefer `LANGSMITH_PROJECT` env var, falling back to `LANGCHAIN_PROJECT`, falling back to `settings.langchain_project`. One-line code change.
- **(C)** add a `langsmith_project` field to `Settings` with `validation_alias` for `LANGSMITH_PROJECT`, change `tracing.py` to use it.

**RECOMMENDED: option B.** Minimal change, preserves backward compatibility, matches CONTEXT decision. See Code Example §5.

**Warning signs:** LangSmith dashboard shows traces in `rag-masterclass` project even after Fly secret update + restart.

### Pitfall 6: Fly suspend-resume cold start vs UptimeRobot timeout

**What goes wrong:** Fly auto-stop-machines=suspend → machine suspended → UptimeRobot probe → machine wakes → request 30s+ → UptimeRobot timeout → false alert.

**Why it happens:** Worst-case cold-start when machine is fully stopped, especially with Docling models being lazy-loaded.

**How to avoid (per Open Question 2 resolution):**
- Phase 4 SUMMARY measured: **suspend-resume 2s, cold-deploy 7s**. UptimeRobot's default 30s timeout has 4x headroom even on worst case.
- Fly's HTTP service health check (`grace_period = "10s"`, `interval = "30s"`, configured in `fly.toml`) ensures the Fly proxy doesn't route traffic to the machine until `/api/health` itself returns 200 — so by the time UptimeRobot's request reaches the FastAPI process, the app is fully booted.
- **NO keep-warm needed.** The `min_machines_running = 1` toggle in `fly.toml` stays commented out.
- Documented mitigation if false alerts appear in practice: bump UptimeRobot per-monitor request timeout from default 30s to 45s (max 60s on free tier).

**Warning signs:** UptimeRobot reports "Down" with outcome "Timeout" on first ping after long idle period.

### Pitfall 7: Health endpoint accidentally rate-limited

**What goes wrong:** UptimeRobot pings every 5 minutes (288/day). If `/api/health` is decorated with `@limiter.limit("20/minute")`, the IP-based limit will trip if `key_func` falls back to IP. But it's per-user-id, so this is actually fine for UptimeRobot... except slowapi defaults to IP when `user_id_key` returns `"anonymous"`. The bigger issue: the `slowapi` middleware (`SlowAPIMiddleware`) is registered globally in `main.py` but only enforces decorated routes — verified in `backend/main.py:49` + Phase 6 SUMMARY.

**How to avoid:** `/api/health` is in `main.py` and has no `@limiter.limit` decorator → it's already exempt. **No change needed.** If anyone moves it into a router file and refactors, add `@limiter.exempt` explicitly.

**Warning signs:** UptimeRobot uptime ratio drifts below 99% within hours of going live.

### Pitfall 8: Sentry's `tracesSampleRate: 1.0` consumes free-tier quota fast

**What goes wrong:** Free tier is 5,000 errors/month. Default `tracesSampleRate: 1.0` plus session replay can blow through quota in a busy day if performance tracing is enabled.

**Why it happens:** Sentry beginner docs frequently set `tracesSampleRate: 1.0` and `replaysSessionSampleRate: 0.1` by default in their copy-paste blocks.

**How to avoid:** For portfolio (low traffic) — `tracesSampleRate: 0.1` is plenty; skip session replay entirely (`replaysSessionSampleRate: 0`). Even 100% sampling at portfolio traffic levels won't hit 5k/month, but be conservative.

**Warning signs:** "Quota exceeded" email from Sentry; events stop arriving mid-month.

## Code Examples

### 1. `frontend/src/lib/sentry.ts` (NEW)

Verified pattern from `[CITED: docs.sentry.io/platforms/javascript/guides/react/]` adapted for the codebase conventions (mirrors `frontend/src/lib/supabase.ts` per `07-PATTERNS.md`):

```typescript
// frontend/src/lib/sentry.ts
import * as Sentry from "@sentry/react";

const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

// No-op in dev / when DSN missing so dev builds don't pollute the prod project
if (dsn) {
  Sentry.init({
    dsn,
    // Tag every event with the CF Pages git SHA; vite-plugin injects this at build time
    // via `release.inject: true` (default). The injected value matches the release we
    // create in vite.config.ts.
    integrations: [
      Sentry.browserTracingIntegration(),
      // No session replay — out of scope for portfolio quota envelope.
    ],
    tracesSampleRate: 0.1,

    // PII scrub: strip JWTs from request headers and storage breadcrumbs.
    beforeSend(event) {
      // Strip Authorization headers from request context if present
      if (event.request?.headers) {
        const headers = event.request.headers as Record<string, string>;
        for (const key of Object.keys(headers)) {
          if (key.toLowerCase() === "authorization") {
            headers[key] = "[redacted]";
          }
        }
      }
      // Strip any user identity Sentry may have auto-attached
      if (event.user) {
        event.user = { ip_address: "{{auto}}" };
      }
      return event;
    },

    beforeBreadcrumb(breadcrumb) {
      // Strip JWT from fetch breadcrumbs
      if (breadcrumb.category === "fetch" || breadcrumb.category === "xhr") {
        const data = breadcrumb.data as Record<string, unknown> | undefined;
        if (data && typeof data === "object") {
          // Sentry's default fetch breadcrumb shape stores request headers in data.request_headers
          const reqHeaders = (data as { request_headers?: Record<string, string> }).request_headers;
          if (reqHeaders) {
            for (const key of Object.keys(reqHeaders)) {
              if (key.toLowerCase() === "authorization") {
                reqHeaders[key] = "[redacted]";
              }
            }
          }
        }
      }
      // Strip localStorage breadcrumbs that mention the Supabase auth token
      if (breadcrumb.category === "console" && typeof breadcrumb.message === "string") {
        if (/sb-[^-]+-auth-token/.test(breadcrumb.message)) {
          return null; // drop entirely
        }
      }
      return breadcrumb;
    },
  });
}

export { Sentry };
```

**Source:** Pattern adapted from `[CITED: docs.sentry.io/platforms/javascript/guides/react/]` (Sentry init pattern); `beforeSend` scrub pattern from `[CITED: docs.sentry.io best practices]`; module structure mirrors `frontend/src/lib/supabase.ts` (existing).

### 2. `frontend/vite.config.ts` (MODIFY)

Verified pattern from `[CITED: app.unpkg.com/@sentry/vite-plugin@5.x README]`:

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { sentryVitePlugin } from '@sentry/vite-plugin'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // sentryVitePlugin MUST come AFTER react/tailwindcss per Sentry docs.
    // Conditionally enabled: only run during CF Pages production builds
    // (CF_PAGES=1 and SENTRY_AUTH_TOKEN are both present), otherwise no-op.
    sentryVitePlugin({
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      // Release.name auto-detection does NOT cover CF Pages
      // (verified against vite-plugin 5.3.0 README — auto-detects Cordova/Heroku/
      // AWS CodeBuild/CircleCI/Xcode/Gradle only). So we set it explicitly:
      release: {
        name: process.env.CF_PAGES_COMMIT_SHA, // present in CF Pages build env
      },
      sourcemaps: {
        // Delete .map files from dist after upload so they're not publicly served.
        filesToDeleteAfterUpload: ['./dist/**/*.map'],
      },
      // Disable plugin entirely when not in a CF Pages build to avoid local-dev noise.
      disable: !process.env.CF_PAGES,
    }),
  ],
  envDir: '..',
  build: {
    // Required for source-map upload. Vite default is `false`.
    sourcemap: true,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**Required CF Pages env vars (Build scope only):**
- `SENTRY_AUTH_TOKEN` — created in Sentry org settings → Auth Tokens; scopes: `project:releases` + `org:read`
- `SENTRY_ORG` — Sentry org slug (e.g., `mlynn-personal`)
- `SENTRY_PROJECT` — Sentry project slug (e.g., `boardgame-rag-frontend`)
- `VITE_SENTRY_DSN` — Sentry public DSN for the frontend project (this one is Runtime/Bundle scope because it's read by `import.meta.env` at runtime)
- `CF_PAGES_COMMIT_SHA` — auto-injected by CF Pages, no manual setup

**CF Pages env var scope distinction (per Cloudflare docs):**
- **Build environment variables:** visible to `npm run build` process, NOT bundled into output. Use for `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
- **Runtime / build-time bundled variables:** read by Vite as `import.meta.env.VITE_*` and BAKED INTO THE BUNDLE. Use for `VITE_SENTRY_DSN`.

**Source:** `[VERIFIED: @sentry/vite-plugin@5.3.0 README via unpkg]`, `[CITED: developers.cloudflare.com/pages/configuration/build-configuration/]`

### 3. `backend/main.py` `/api/health` upgrade (MODIFY)

```python
# backend/main.py — replace existing /api/health handler

import logging
from fastapi.responses import JSONResponse
from database import get_supabase

logger = logging.getLogger(__name__)

@app.get("/api/health")
async def health():
    """Liveness + DB-reachability probe.

    OBS-04: Issues a trivial Postgres query via supabase-py service-role client so:
      - UptimeRobot 200/503 reflects ACTUAL DB reachability, not just process liveness
      - Each 5-min ping touches the DB → resets Supabase free-tier 7-day idle pause clock

    Returns 200 + {"status": "ok"} on success.
    Returns 503 + {"status": "degraded", "db": "unreachable"} on any DB exception.
    """
    try:
        db = get_supabase()
        # Lightest possible reachability probe: head-only count against a public table.
        # head=True returns no rows (just the Content-Range header), so we transfer
        # zero data over the wire beyond the count integer.
        # `documents` is chosen because:
        #   (1) it always has ≥10 rows after Phase 3 seed (default KB), so the count
        #       is non-zero, distinguishing "DB reachable" from "DB reachable but
        #       all data missing" if you want to look at uptime logs.
        #   (2) it's not user-scoped — service-role bypasses RLS so visibility=public
        #       rows are always counted.
        #   (3) it does not require a new RPC or migration.
        db.table("documents").select("id", count="exact", head=True).limit(1).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Health check DB probe failed: %s", e, exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "unreachable"},
        )
```

**Why `select("id", count="exact", head=True).limit(1)` and not something else?**

| Option | Verdict |
|--------|---------|
| `supabase.rpc("select_one")` | Cleanest but requires new migration `26_select_one_rpc.sql` + `supabase db push` against prod. Adds maintenance surface. REJECTED. |
| `supabase.postgrest.session.get(...)` (raw HTTP) | Bypasses query builder; brittle if PostgREST changes. REJECTED. |
| `supabase.table("documents").select("id").limit(1).execute()` | Returns one row — slightly more bandwidth than head=True, otherwise identical. Acceptable alternative. |
| `supabase.table("documents").select("id", count="exact", head=True).limit(1).execute()` | **RECOMMENDED.** head=True means body is empty; only the `Content-Range` header carries the count. Lowest bandwidth + lightest Postgres work. |

**Source:** `[VERIFIED: backend/venv inspection of supabase-py 2.13.0 — SyncRequestBuilder.select signature accepts head: Optional[bool]]`; pattern from `[CITED: supabase.com/docs/reference/python/select]`.

### 4. `backend/scripts/verify_langsmith_routing.py` (NEW)

Verified parameter types via `inspect.signature(langsmith.Client.list_runs)` against installed langsmith 0.3.42:

```python
#!/usr/bin/env python
"""Verify OBS-02: prod chat requests land in boardgame-rag-prod LangSmith project,
NOT in boardgame-rag-dev.

Usage:
    cd backend && venv/Scripts/python.exe scripts/verify_langsmith_routing.py

Reads from `.env` (or ENV_FILE override per backend/config.py:8):
  - LANGSMITH_API_KEY
  - SUPABASE_URL (to get JWT for test user)
  - test user email/password from CLAUDE.md test credentials

Asserts:
  1. POST /api/threads + POST /api/threads/{id}/messages against prod Fly URL succeeds
  2. langsmith.Client.list_runs(project_name="boardgame-rag-prod", start_time=t0)
     returns ≥1 completed run within 60s of the chat request
  3. langsmith.Client.list_runs(project_name="boardgame-rag-dev", start_time=t0)
     returns 0 runs in the same window (proves no leakage)
"""
import os
import sys
import time
import datetime
from pathlib import Path

# sys.path bootstrap to import config — pattern from backend/scripts/seed_default_kb.py
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from langsmith import Client
from config import get_settings

# --- config ---
FLY_URL = "https://boardgame-rag-prod.fly.dev"
PROD_PROJECT = "boardgame-rag-prod"
DEV_PROJECT = "boardgame-rag-dev"
POLL_TIMEOUT_S = 90
POLL_INTERVAL_S = 5

settings = get_settings()
if not settings.langsmith_api_key:
    sys.exit("FAIL: LANGSMITH_API_KEY not set in env")

client = Client(api_key=settings.langsmith_api_key)


def get_test_jwt() -> str:
    """Mint a Supabase JWT for the test user via password grant.

    Mirrors backend/scripts/_lib/get_test_jwt.sh logic but in Python.
    """
    supabase_url = settings.supabase_url_resolved
    anon_key = settings.vite_supabase_anon_key
    if not anon_key:
        sys.exit("FAIL: VITE_SUPABASE_ANON_KEY not set in env")
    resp = httpx.post(
        f"{supabase_url}/auth/v1/token?grant_type=password",
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        json={"email": "ragtest1@gmail.com", "password": "testpass123"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def send_chat() -> tuple[datetime.datetime, str]:
    """POST a chat request to prod Fly. Returns (start_time_utc, thread_id)."""
    jwt = get_test_jwt()
    headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
    # Create thread
    r1 = httpx.post(f"{FLY_URL}/api/threads", headers=headers, json={"title": "OBS-02 verify"}, timeout=15.0)
    r1.raise_for_status()
    thread_id = r1.json()["id"]
    # Capture timestamp BEFORE sending message — list_runs.start_time is a lower bound
    t0 = datetime.datetime.now(datetime.timezone.utc)
    # Send message (SSE stream — we just need to consume it)
    with httpx.stream(
        "POST",
        f"{FLY_URL}/api/threads/{thread_id}/messages",
        headers=headers,
        json={"content": "What is the simplest board game in the KB?"},
        timeout=60.0,
    ) as r2:
        r2.raise_for_status()
        for _ in r2.iter_lines():
            pass  # drain stream
    return t0, thread_id


def assert_routing(t0: datetime.datetime) -> None:
    """Poll list_runs until prod has ≥1 completed run, or timeout."""
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        # langsmith.Client.list_runs signature (verified against 0.3.42):
        #   project_name: Optional[Union[str, Sequence[str]]]
        #   start_time:   Optional[datetime.datetime]      <-- pass datetime, not ISO string
        #   error:        Optional[bool]                    <-- error=False = completed-successfully
        prod_runs = list(client.list_runs(
            project_name=PROD_PROJECT,
            start_time=t0,
            error=False,   # filter out failed runs
            limit=10,
        ))
        # "Completed" filter: a run has end_time set when finalized.
        # Filtering error=False AND has end_time = "completed successfully".
        completed = [r for r in prod_runs if r.end_time is not None]
        if completed:
            print(f"PASS: {len(completed)} completed run(s) in {PROD_PROJECT}")
            break
        time.sleep(POLL_INTERVAL_S)
    else:
        sys.exit(f"FAIL: no completed runs in {PROD_PROJECT} within {POLL_TIMEOUT_S}s")

    # Assert dev has zero
    dev_runs = list(client.list_runs(
        project_name=DEV_PROJECT,
        start_time=t0,
        limit=10,
    ))
    if dev_runs:
        sys.exit(f"FAIL: {len(dev_runs)} run(s) leaked into {DEV_PROJECT} — routing broken")
    print(f"PASS: 0 runs in {DEV_PROJECT}")


def main():
    print(f"[1/2] Sending test chat to {FLY_URL}...")
    t0, thread_id = send_chat()
    print(f"      Sent at {t0.isoformat()} (thread_id={thread_id})")
    print(f"[2/2] Polling LangSmith for routing assertion...")
    assert_routing(t0)
    print("OBS-02 VERIFY: PASS")


if __name__ == "__main__":
    main()
```

**Source for `list_runs` signature:** `[VERIFIED: inspect.signature(Client.list_runs) against installed langsmith==0.3.42]` — accepts `project_name: Optional[Union[str, Sequence[str]]]`, `start_time: Optional[datetime.datetime]`, `error: Optional[bool]`.

**Source for Run completion detection:** `[VERIFIED: Run.__fields__ inspection — end_time, error, status fields exist]`. A run with `error=False` (no exception captured) AND `end_time is not None` (finalize signal sent) is a successfully completed run.

### 5. `backend/services/tracing.py` patch (MODIFY) — RECOMMENDED Pitfall 5 fix

```python
# backend/services/tracing.py
import os
from config import get_settings


def setup_tracing():
    """Configure LangSmith tracing. No-op if LANGSMITH_API_KEY is not set.

    Project name resolution (highest to lowest precedence):
      1. LANGSMITH_PROJECT env var (canonical name per langsmith SDK 0.3.42+)
      2. LANGCHAIN_PROJECT env var (legacy name, still respected by SDK)
      3. settings.langchain_project (pydantic-settings default)
    """
    settings = get_settings()

    if not settings.langsmith_api_key:
        return

    # Determine project name from highest-precedence source.
    project = (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or settings.langchain_project
    )

    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = project
    # Also set canonical name for SDK's own env-var walker.
    os.environ["LANGSMITH_PROJECT"] = project
```

**Why both env vars are set:** The langsmith 0.3.42 SDK's `get_env_var()` walker checks `LANGSMITH_PROJECT` first then `LANGCHAIN_PROJECT` (verified). Some downstream code paths (the `@traceable` decorator's project lookup, `wrap_openai`'s session naming) may use either name. Setting both is defense in depth at zero cost.

**Source:** `[VERIFIED: backend/venv inspection of langsmith.utils.get_env_var and langsmith.run_trees]`

## Runtime State Inventory

This is a code/config addition phase, not a rename or refactor — no stored state in datastores carries observability identifiers that need migration. But there ARE out-of-repo configurations that must be created/updated:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no datastores key observability identifiers by name | None |
| Live service config | **Sentry org/project** (creation needed); **UptimeRobot account + 2 monitors** (creation needed); **CF Pages env vars** (`SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `VITE_SENTRY_DSN`); **LangSmith dev/prod projects** (creation needed if not already); **Fly secret `LANGSMITH_PROJECT`** (already set per `04-02-PLAN.md:94` — confirm via `flyctl secrets list`) | Manual dashboard work; documented in plan as Wave 3 + USER-SETUP.md |
| OS-registered state | None | None |
| Secrets/env vars | `SENTRY_AUTH_TOKEN` (new, CF Pages Build env); `VITE_SENTRY_DSN` (new, CF Pages Build+bundled env); `SENTRY_ORG`, `SENTRY_PROJECT` (new, CF Pages Build env); `LANGSMITH_PROJECT` (already on Fly — confirm); `LANGSMITH_PROJECT` in local `.env` (new, set to `boardgame-rag-dev`) | Plan must document each secret's destination and scope |
| Build artifacts | `frontend/dist/**/*.map` files — currently NOT generated (build.sourcemap=false by default). After Phase 7 they ARE generated AT BUILD TIME and then DELETED by the plugin's `filesToDeleteAfterUpload` before CF Pages serves dist. Verify by curling a hashed `.js.map` URL post-deploy. | First deploy after Phase 7 should be verified manually with `curl -fsSI <map-url>` returning 404. |

## Common Pitfalls (continued from section above)

### Pitfall 9: `disable: !process.env.CF_PAGES` breaks local prod-style smoke

**What goes wrong:** Developer runs `npm run build && npm run preview` locally to test bundle. Plugin is disabled because `CF_PAGES` isn't set → no source maps uploaded, no release created → "but it works in dev?" debugging spiral.

**How to avoid:** Document explicitly in code comment that local-build is no-op-by-design. Use CF Pages preview deployments (or staging deploy on `main`) for true upload testing.

**Warning signs:** Local `npm run build` log doesn't show "[sentry] Uploading source maps".

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `npm` | Frontend install of @sentry/* | ✓ | per `frontend/.nvmrc` Node 20 | — |
| `node` | Vite build + sentry plugin | ✓ | Node 20 (CF Pages NODE_VERSION=20 confirmed in 05-01-SUMMARY) | — |
| Python venv | Verification script | ✓ | `backend/venv/Scripts/python.exe` | — |
| `langsmith` (Python) | Verification script + tracing | ✓ | 0.3.42 (in requirements.txt) | — |
| `supabase` (Python) | /api/health probe | ✓ | 2.13.0 (in requirements.txt) | — |
| `httpx` (Python) | Verification script HTTP calls | ✓ | transitive, pulled in by supabase/openai | — |
| `flyctl` | Setting Fly secret (if not already correct) | ✓ (per Phase 4) | — | — |
| Sentry account | OBS-01 | ✗ (must be created) | — | None — required |
| UptimeRobot account | OBS-03 | ✗ (must be created) | — | None — required |
| LangSmith account | OBS-02 | ✓ (already used in Phase 4) | — | — |
| Cloudflare Pages dashboard access | Env var setting | ✓ (per Phase 5) | — | — |

**Missing dependencies with no fallback:**
- Sentry account creation — must be done manually before Wave 1 execution.
- UptimeRobot account creation — must be done manually before Wave 3 execution.

**Missing dependencies with fallback:**
- None — all blockers are SaaS sign-ups, no code fallback.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest==8.4.2` + `pytest-asyncio==0.23.8` (already in requirements.txt) |
| Config file | None at repo root (pytest discovers via `backend/tests/conftest.py`) |
| Quick run command | `backend/venv/Scripts/python.exe -m pytest backend/tests/ -x` |
| Full suite command | `backend/venv/Scripts/python.exe -m pytest backend/tests/` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| OBS-01 | Sentry init module imports without error; `beforeSend` redacts JWT-shaped values | unit (frontend) | none — no frontend test infra in project (per STACK.md "No test framework detected in frontend/package.json") | N/A — manual browser smoke test instead (see below) |
| OBS-01 | Source maps uploaded to Sentry at CF Pages build | manual + integration | trigger deliberate error in deployed prod → check Sentry shows un-minified stack | manual — Wave 1 verification step |
| OBS-02 | `/api/health` returns 200 + `{"status":"ok"}` when DB reachable | unit | `pytest backend/tests/test_health.py::test_health_ok -x` | ❌ Wave 0 |
| OBS-02 | `/api/health` returns 503 + `{"status":"degraded"...}` when DB raises | unit | `pytest backend/tests/test_health.py::test_health_degraded -x` | ❌ Wave 0 |
| OBS-02 | LangSmith routing: prod traces in prod project, dev in dev | integration | `backend/venv/Scripts/python.exe backend/scripts/verify_langsmith_routing.py` | ❌ Wave 2 |
| OBS-03 | UptimeRobot reports down when /api/health returns 503 | manual (drill) | flyctl machine stop → wait ≤10min → confirm email arrives → start | manual — Wave 3 |
| OBS-04 | `/api/health` actually queries Supabase | unit + integration | `pytest backend/tests/test_health.py::test_health_calls_supabase -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `backend/venv/Scripts/python.exe -m pytest backend/tests/test_health.py -x` (Wave 0+1 health tests only — fast)
- **Per wave merge:** `backend/venv/Scripts/python.exe -m pytest backend/tests/` (full backend suite)
- **Phase gate:** Full backend suite green + verify_langsmith_routing.py PASS + manual UR downtime drill confirmed + browser-trigger-error smoke confirms Sentry receives event with un-minified stack.

### Wave 0 Gaps

- [ ] `backend/tests/test_health.py` — covers OBS-04 (health endpoint DB probe + 503 path). Likely 3 tests:
  - `test_health_ok` — mocked supabase returns count → 200 + `{"status":"ok"}`
  - `test_health_degraded` — mocked supabase raises → 503 + `{"status":"degraded", "db":"unreachable"}`
  - `test_health_calls_supabase` — asserts `db.table("documents").select(...)` was invoked (proves the DB probe is wired, not a stub)
- [ ] `backend/tests/test_tracing.py` (optional) — covers Pitfall 5 fix: assert `setup_tracing()` reads `LANGSMITH_PROJECT` env var with correct precedence
- [ ] No new conftest fixtures needed — existing `mock_supabase` pattern (if it exists per Phase 6 conftest scaffolding) can be reused; otherwise inline `unittest.mock.patch` is sufficient for these 3 tests.
- [ ] Frontend has no test framework. OBS-01 verification is manual: trigger deliberate error in deployed prod browser → check Sentry dashboard. Not blocking — adding Vitest is a larger scope decision deferred per project rules.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (Sentry beforeSend strips JWT) | Manual scrub in `beforeSend`/`beforeBreadcrumb` |
| V3 Session Management | yes (auth token in localStorage is referenced in breadcrumbs) | Drop console breadcrumbs matching `sb-*-auth-token` |
| V4 Access Control | no (health endpoint is intentionally public) | — |
| V5 Input Validation | partial — `/api/health` ignores all input | FastAPI dependency injection handles types |
| V6 Cryptography | no — no new crypto introduced | — |
| V7 Error Handling | yes — `/api/health` returns 503 without leaking exception details | `logger.error(..., exc_info=True)` server-side; minimal client response |
| V8 Data Protection | yes — Sentry handles PII | beforeSend strips JWT/email/UUID; no setUser call |
| V14 Configuration | yes — source maps must not be public | `sourcemaps.filesToDeleteAfterUpload` removes maps from dist |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Source map leak → reverse-engineered bundle | Information Disclosure | `sourcemaps.filesToDeleteAfterUpload` + `curl -I` smoke verification |
| PII in Sentry events → GDPR/portfolio reputation risk | Information Disclosure | `beforeSend` redaction + `Sentry.setUser` never called |
| Health endpoint DoS via UptimeRobot frequency | Denial of Service | DB probe is O(microseconds) head-only count; supabase free tier has rate budget headroom |
| Sentry quota exhaustion → false sense of "no errors" | Denial of Service (self-inflicted) | `tracesSampleRate: 0.1`; no session replay |
| LangSmith trace cross-contamination dev↔prod | Information Disclosure (between own envs) | Env-var-driven project name + automated verification script |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sentry v7/v8 with separate `BrowserTracing` import + manual error boundary | Sentry v9+/v10 with `Sentry.browserTracingIntegration()` + `Sentry.reactErrorHandler` + React 19 createRoot hooks | Sentry v9 release + React 19 stable (early 2025) | `@sentry/react` 10.x is the current best-practice path. Older docs you may find on the web still show v7 patterns; do not copy those. |
| Manual `sentry-cli` source-map upload in build script | `@sentry/vite-plugin` | Sentry vite-plugin GA late 2023 | One-config-edit replaces a custom build step. |
| `LANGCHAIN_*` env vars only | Both `LANGSMITH_*` and `LANGCHAIN_*` accepted (LANGSMITH_ preferred) | langsmith SDK 0.1.0+ | Set both for backward compatibility (see Pitfall 5). |
| psutil/curl-based uptime checks | SaaS uptime monitor | always — DIY is the anti-pattern | Don't roll your own. |

**Deprecated/outdated:**
- `Sentry.captureException` with manual context-setting → use `ErrorBoundary` + React 19 hooks
- `Sentry.BrowserTracing` class import → use `Sentry.browserTracingIntegration()` factory
- Sentry "release" with `inject: false` + manual `Sentry.init({ release: ... })` → use vite-plugin defaults (`inject: true`) so SDK auto-picks-up plugin-injected release at runtime

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `documents` table has ≥1 row after Phase 3 seed (so the head-count returns >0 if needed for liveness telemetry). | Code Example §3 | LOW — the head=True probe succeeds whether the count is 0 or 10. Used only for prose justification of table choice. |
| A2 | UptimeRobot's "default 30s timeout" applies to free tier. | Pitfall 6 | LOW — web search confirmed configurable 1-60s range. Worst case: bump to 45s in dashboard if false alerts appear. |
| A3 | CF Pages "Build environment variables" scope is the right place for `SENTRY_AUTH_TOKEN` (vs the unified env-var list). | Pitfall 1, Code Example §2 | MEDIUM — confirmed via CF docs that build-time secrets do NOT get bundled, runtime-bundled (VITE_*) DO get bundled. Phase 5 SUMMARY already uses both modes correctly so the dashboard supports both. |
| A4 | Phase 4 staged `LANGSMITH_PROJECT` as a Fly secret with value `boardgame-rag-prod`. | Pitfall 5, Open Question 4 resolution | LOW — `04-02-PLAN.md` lines 93-95 explicitly list this secret. Plan should `flyctl secrets list` first to confirm before depending on it. |

**Note:** All four assumptions are LOW-MEDIUM risk and have explicit verification steps in the recommended plan structure. None block Phase 7 execution.

## Open Question Resolutions

### Open Question 1: `@sentry/vite-plugin` config shape

**Resolved.** Latest version is `@sentry/vite-plugin@5.3.0` (verified via `npm view`). Required configuration:
- `org`, `project`, `authToken` from env
- `release.name: process.env.CF_PAGES_COMMIT_SHA` — required EXPLICITLY because auto-detection does NOT cover CF Pages (only Cordova/Heroku/AWS CodeBuild/CircleCI/Xcode/Gradle per docs)
- `sourcemaps.filesToDeleteAfterUpload: ['./dist/**/*.map']` — deletes from dist after upload
- `authToken` env var name: `SENTRY_AUTH_TOKEN` (canonical; CF Pages **Build** scope, NOT Runtime)
- `build.sourcemap: true` in vite config (separate from the plugin)
- Plugin must come AFTER `react()` and `tailwindcss()` in `plugins:` array
- Compatible with React 19 + Vite 6 (Node ≥18 engine requirement satisfied)

Full code in Code Example §2.

`[VERIFIED: npm view @sentry/vite-plugin version → 5.3.0, engines → {node: ">= 18"}]`
`[CITED: unpkg.com/@sentry/vite-plugin@2.16.1/README.md (auto-detect list)]`
`[CITED: docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/]`

### Open Question 2: Fly auto-stop/suspend interaction with UptimeRobot

**Resolved.** Phase 4 SUMMARY recorded measured latencies:
- Cold start (full deploy): 7s to first `/api/health` 200
- Suspend-resume: 2s to `/api/health` 200

Both are well inside UptimeRobot's default 30s request timeout (configurable to 60s on free tier). Fly's `[[http_service.checks]]` block in `fly.toml` ensures Fly proxy doesn't route traffic to a not-yet-ready machine — the request waits for the health check to pass before being forwarded.

**Recommendation:** Keep `min_machines_running = 0`. Do NOT enable keep-warm. If false alerts occur in production, the documented mitigation path is: bump UR per-monitor request timeout from 30s → 45s in UR dashboard (no Fly change).

`[VERIFIED: 04-02-SUMMARY.md "Cold start (deploy): 7s ... Cold resume (suspend): 2s"]`
`[CITED: fly.io/docs/reference/suspend-resume/ — "Resume from suspend: a few hundred ms; Cold start: ~2+ seconds"]`
`[CITED: help.uptimerobot.com — Free tier timeout default 30s, configurable 1-60s]`

### Open Question 3: supabase-py `select 1` syntax

**Resolved.** supabase-py 2.13.0 does NOT expose inline SQL — `Client.rpc()` requires a pre-registered Postgres function name (verified by `inspect.signature(SyncPostgrestClient.rpc)` against installed package: `rpc(func: str, params: dict, ...)`).

Options evaluated:
- **Create RPC `select_one()` + call via `supabase.rpc("select_one")`:** clean but requires migration #25 + `supabase db push` against prod. Maintenance overhead.
- **`supabase.table("documents").select("id", count="exact", head=True).limit(1).execute()`:** uses existing public table + zero migrations. Head-only count: zero rows in body, count in Content-Range header.
- **Direct postgrest raw query:** supabase-py does not expose a clean raw-SQL path on the postgrest client. REJECTED.

**Recommended:** the head-only count against `documents`. See Code Example §3.

`[VERIFIED: backend/venv inspect.signature of supabase.Client.rpc and SyncRequestBuilder.select]`
`[CITED: supabase.com/docs/reference/python/select — count='exact' pattern]`

### Open Question 4: LangSmith `list_runs` time filter granularity + completion-status field

**Resolved.** Verified against installed `langsmith==0.3.42`:

```
Client.list_runs(
    project_id, project_name, run_type, trace_id, reference_example_id,
    query, filter, trace_filter, tree_filter, is_root, parent_run_id,
    start_time: Optional[datetime.datetime],   # NATIVE datetime, NOT ISO string
    error: Optional[bool],                      # True=failed runs, False=successful, None=both
    run_ids, select, limit, **kwargs
)
```

- `project_name` accepts `str` OR `Sequence[str]`
- `start_time` accepts `datetime.datetime` (use `datetime.now(timezone.utc) - timedelta(minutes=5)`); does NOT accept ISO string or epoch int
- Completion detection: `Run.end_time` field (None while in-progress, datetime once finalized) AND `Run.status` field (verified present in schema). The cleanest "completed successfully" predicate is `error=False` passed to `list_runs` (filter at SaaS side) + post-filter `r.end_time is not None` (client side, defensive).

Run schema fields confirmed via `Run.__fields__`: `['app_path', 'attachments', 'child_run_ids', 'child_runs', 'completion_cost', 'completion_tokens', 'dotted_order', 'end_time', 'error', 'events', 'extra', 'feedback_stats', 'first_token_time', 'id', 'in_dataset', 'inputs', 'manifest_id', 'name', 'outputs', 'parent_run_id', 'parent_run_ids', 'prompt_cost', 'prompt_tokens', 'reference_example_id', 'run_type', 'serialized', 'session_id', 'start_time', 'status', 'tags', 'total_cost', 'total_tokens', 'trace_id']`.

Minimum stable version: 0.3.x (current 0.3.42 in `requirements.txt`); latest released is 0.8.5 on PyPI (no upgrade needed for this phase).

`[VERIFIED: inspect.signature(Client.list_runs) and Run.__fields__ against backend/venv installed langsmith==0.3.42]`

## Recommended Plan Slicing (for Planner)

Three waves, executable in this order:

**Wave 1 — Frontend Sentry + Backend health probe (parallel)**
- Plan 07-01: Sentry frontend init module, vite-plugin in vite.config.ts, package.json deps, frontend/src/main.tsx wiring (OBS-01, no backend touch)
- Plan 07-02: `/api/health` upgrade to DB probe + `backend/tests/test_health.py` (OBS-04, no frontend touch)
- These two can run in parallel — disjoint file sets.
- Closes OBS-01 (frontend code path) + OBS-04 (backend code path). External SaaS dashboard config still pending.

**Wave 2 — LangSmith routing + Fly secret confirm + tracing.py fix**
- Plan 07-03: `backend/services/tracing.py` patch (Pitfall 5 fix); `backend/scripts/verify_langsmith_routing.py` (OBS-02). Fly secret confirmation via `flyctl secrets list` (no-op if `LANGSMITH_PROJECT` already set per Phase 4).
- Closes OBS-02 verification path. Depends on prod chat being functional (already true).

**Wave 3 — External SaaS dashboard config + drills**
- Plan 07-04: Sentry org/project creation, CF Pages env vars, deploy + verify source-map upload + browser-trigger-error verifies un-minified stack in Sentry. (OBS-01 closes here.)
- Plan 07-05: UptimeRobot account + 2 monitors + simulated downtime drill (OBS-03 closes here).
- These two can run in parallel — disjoint external services.

Effort estimate: 1-1.5h Wave 1, ~45min Wave 2, ~1-1.5h Wave 3 (mostly waiting for UR alert email). Total active: ~3-4h.

## Sources

### Primary (HIGH confidence)
- **Installed `langsmith==0.3.42` SDK** — `inspect.signature(Client.list_runs)`, `Run.__fields__`, `langsmith.utils.get_env_var` source inspection (definitive verification of OQ4)
- **Installed `supabase==2.13.0` + `postgrest==0.19.3` SDK** — `inspect.signature` of `Client.rpc`, `SyncPostgrestClient.rpc`, `SyncRequestBuilder.select` (definitive verification of OQ3)
- **`npm view @sentry/vite-plugin version`** → 5.3.0; engines → `{node: ">= 18"}` (OQ1)
- **`npm view @sentry/react version`** → 10.53.1 (Standard Stack)
- **`backend/main.py:65-67`** — current `/api/health` implementation (existing state)
- **`backend/services/tracing.py:5-15`** — current LangSmith wiring (Pitfall 5 trigger)
- **`backend/config.py:18-19`** — current `langchain_project` field default `"rag-masterclass"`
- **`fly.toml`** — confirmed `auto_stop_machines = "suspend"`, `min_machines_running = 0`, health check `grace_period = "10s"`
- **`frontend/vite.config.ts`** — current plugin chain (where vite-plugin will slot in)
- **`.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md`** — measured suspend-resume 2s, cold-deploy 7s (OQ2 ground truth); `LANGSMITH_PROJECT` Fly secret name confirmed at `04-02-PLAN.md:94`
- **`.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md`** — CF Pages env var scope conventions (Production-only, Preview disabled)
- **`.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-01-SUMMARY.md`** — slowapi decorator behavior (per-route opt-in; `/api/health` already exempt)

### Secondary (MEDIUM confidence — verified against multiple sources)
- [Sentry Vite plugin docs (Cloudflare guide)](https://docs.sentry.io/platforms/javascript/guides/cloudflare/sourcemaps/uploading/vite/) — canonical plugin invocation pattern
- [Sentry Vite plugin README on unpkg](https://app.unpkg.com/@sentry/vite-plugin@2.16.1/files/README.md) — option-level docs, release auto-detection list
- [Sentry React SDK docs](https://docs.sentry.io/platforms/javascript/guides/react/) — React 19 createRoot hooks pattern with `reactErrorHandler`
- [Sentry React 19 changelog](https://sentry.io/changelog/react-19-support/) — `reactErrorHandler` introduction
- [Cloudflare Pages build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/) — `CF_PAGES_COMMIT_SHA` auto-injection; build vs runtime env var scopes
- [Fly Machine Suspend and Resume docs](https://fly.io/docs/reference/suspend-resume/) — resume latency claim "a few hundred ms" (we measured 2s in our app — higher because of Docling lazy load — still within 30s envelope)
- [Supabase Python select docs](https://supabase.com/docs/reference/python/select) — `count='exact'` pattern (head=True confirmed via SDK inspection)
- [Supabase Python rpc docs](https://supabase.com/docs/reference/python/rpc) — confirms RPC requires pre-defined function
- [LangSmith list_runs reference](https://reference.langchain.com/python/langsmith/client/Client/list_runs) — `start_time: Optional[datetime.datetime]` confirmed
- [slowapi exempt docs](https://slowapi.readthedocs.io/) — `@limiter.exempt` decorator pattern (not needed since /api/health is undecorated)
- [UptimeRobot advanced settings](https://help.uptimerobot.com/en/articles/11360863-uptimerobot-advanced-settings-customize-your-monitor-configuration) — configurable 1-60s timeout, default 30s

### Tertiary (LOW confidence — single source)
- None. Every load-bearing claim has either SDK inspection or two independent doc sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified via `npm view` and `backend/venv` inspection
- Architecture: HIGH — file layout maps 1:1 to existing patterns documented in 07-PATTERNS.md
- Pitfalls: HIGH — Pitfall 5 (LangSmith project routing) verified by SDK source inspection; others corroborated by multiple sources
- Open question resolutions: HIGH — all four resolved by inspecting installed SDKs and/or measuring real prod state from Phase 4 SUMMARY

**Research date:** 2026-05-15
**Valid until:** 2026-06-15 (30 days for stable SaaS APIs; Sentry/CF Pages/UR are stable; langsmith SDK is the fastest-moving dependency but verification is against an installed pinned version so internal use is stable until that pin changes)
