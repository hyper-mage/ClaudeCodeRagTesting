---
phase: "07"
slug: observability-baseline
created: 2026-05-15
mapper: gsd-pattern-mapper
files_analyzed: 7
analogs_found: 7
---

# Phase 07: Observability Baseline — Pattern Map

Maps each new/modified file in Phase 7 to its closest existing codebase analog. Planner should reference these excerpts directly in plan `<action>` blocks rather than inventing new patterns.

> NOTE: RESEARCH.md does not exist yet for Phase 7 (researcher runs after this mapping per `/gsd:plan-phase` orchestration). All analogs sourced from current codebase + CONTEXT.md + DISCUSSION-LOG.md decisions. The four open questions in `07-CONTEXT.md` will be resolved by gsd-phase-researcher and may add concrete syntax constants (e.g., supabase-py `select 1` shape) that supplement these patterns.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/src/lib/sentry.ts` (new) | utility / module-init singleton | side-effect (init at import) | `frontend/src/lib/supabase.ts` | exact (role + structure) |
| `frontend/src/main.tsx` (modify) | entry point | side-effect bootstrap | itself (existing structure) | self — insert one import-with-side-effects line before `createRoot` |
| `frontend/vite.config.ts` (modify) | config | plugin pipeline | itself + `frontend/package.json` | self — extend `plugins:` array |
| `backend/main.py` `/api/health` (modify) | router endpoint | request-response, DB probe | `backend/services/sql_service.py:execute_sql` (supabase-py + try/except → JSON dict) | role-match (DB probe pattern, NOT auth-scoped) |
| `backend/scripts/verify_langsmith_routing.py` (new) | verification script | HTTP request + API list + assert | `backend/scripts/seed_default_kb.py` (Python sys.path bootstrap + Settings) + `backend/scripts/fly_smoke.sh` (wait-and-assert idiom) | hybrid (no Python verification analog exists) |
| `backend/config.py` (modify) | config | env→Settings field | itself (existing `langchain_project` field at line 19) | self — wire `langsmith_project` alias or reuse `langchain_project` |
| **No-code dashboard work** (UptimeRobot + Sentry project + CF Pages env vars + Fly secret) | runbook | n/a | `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md` (CF Pages dashboard checklist) + `.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md` (Fly secrets pattern) | role-match (dashboard runbook idiom) |

---

## Pattern Assignments

### 1. `frontend/src/lib/sentry.ts` (new — Sentry init singleton)

**Closest analog:** `frontend/src/lib/supabase.ts` (lines 1-6)

**What to mirror — exact:**
- File location: `frontend/src/lib/{lowercase}.ts`
- Naming: `camelCase.ts` (single noun, no `-init` or `Service` suffix)
- Single named export of the configured client/SDK
- Env vars read once at module top via `import.meta.env.VITE_*`
- No JSX, no React, no default export

**Reference excerpt (`frontend/src/lib/supabase.ts:1-6`):**
```typescript
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
```

**Adapted shape for `sentry.ts` (sketch — planner refines from RESEARCH):**
```typescript
import * as Sentry from '@sentry/react'

const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
const release = import.meta.env.VITE_GIT_SHA as string | undefined  // CF_PAGES_COMMIT_SHA, exposed as VITE_GIT_SHA at build

export function initSentry(): void {
  if (!dsn) return  // mirror tracing.py "no-op if env var unset" pattern (backend/services/tracing.py:9-10)
  Sentry.init({
    dsn,
    release,
    beforeSend(event) { /* PII scrub: JWT, email, UUID */ return event },
    beforeBreadcrumb(crumb) { /* scrub auth headers from xhr/fetch breadcrumbs */ return crumb },
  })
}
```

**Deviations from `supabase.ts` analog (deliberate):**
- Wrap in `initSentry()` function rather than executing at module import — main.tsx calls it explicitly before `createRoot` so init order is auditable. `supabase.ts` runs eagerly because `createClient` is cheap and pure; `Sentry.init` has global side effects (window error handlers) that must run before React mounts.
- Named export is a function, not a configured instance. Sentry hooks (`captureException`, `withScope`) are imported directly from `@sentry/react` everywhere else.
- Add no-op guard for missing DSN (matches `backend/services/tracing.py:9-10` `if not langsmith_api_key: return` pattern).

**Reference for no-op guard pattern (`backend/services/tracing.py:5-15`):**
```python
def setup_tracing():
    """Configure LangSmith tracing. No-op if LANGSMITH_API_KEY is not set."""
    settings = get_settings()

    if not settings.langsmith_api_key:
        return

    # Set env vars that LangSmith SDK reads
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
```

This is the precedent for "external observability SDK init module": (1) read settings, (2) early-return if disabled, (3) configure SDK. `initSentry()` should follow the same skeleton.

---

### 2. `frontend/src/main.tsx` (modify — call `initSentry()` before React mount)

**Closest analog:** itself (lines 1-10) — no other file mounts React.

**Current shape (`frontend/src/main.tsx:1-10`):**
```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

**Pattern to apply:** Insert exactly two lines — an import and a call — before `createRoot`. Sentry must wrap React error boundaries, so init runs before mount.

**Target shape (planner spec):**
```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { initSentry } from './lib/sentry'   // NEW
import './index.css'
import App from './App'

initSentry()                                  // NEW — must run before createRoot

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

**What NOT to do:**
- Do NOT wrap `<App />` with `<Sentry.ErrorBoundary>` in main.tsx — that decision is React-tree-shape work and was not in CONTEXT.md. If RESEARCH recommends it, it lands in `App.tsx`, not here.
- Do NOT call `Sentry.setUser(...)` anywhere. CONTEXT.md decision 1 explicitly forbids identity attachment.

---

### 3. `frontend/vite.config.ts` (modify — add `@sentry/vite-plugin`)

**Closest analog:** itself (lines 1-16). Existing pattern is a flat `plugins: [react(), tailwindcss()]` array.

**Current shape (`frontend/vite.config.ts:1-16`):**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: '..',
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

**Pattern to apply:**
- Add `sentryVitePlugin` import alongside existing plugin imports
- Append to `plugins:` array **last** so it runs against the final emitted bundle (source-map upload requires post-build artifacts)
- Pass `authToken: process.env.SENTRY_AUTH_TOKEN` (Node-side env var, NOT `import.meta.env` — vite.config.ts runs in Node at build time, where `process.env` is the correct surface)
- Pass `release: process.env.CF_PAGES_COMMIT_SHA` for SHA-tagged releases (CONTEXT.md decision 1, Sentry section)

**Build-time vs runtime env-var split:**
- `VITE_SENTRY_DSN` — runtime (baked into bundle at build, available via `import.meta.env`) → set in CF Pages dashboard with **Production scope, no Preview** per Phase 5 SUMMARY pattern (line 47: "VITE_* env vars set in CF dashboard (Production scope); never include service-role keys").
- `SENTRY_AUTH_TOKEN` — build-only (used by vite-plugin at build time, NEVER shipped to browser) → set in CF Pages dashboard as **Build environment variable** only. Verify post-deploy with the SEC-07 leak grep idiom from Phase 5 (re-run against the deployed bundle, not just local build).

**Reference for CF Pages env-var conventions (`.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md:46-47`):**
```
- "VITE_* env vars set in CF dashboard (Production scope); never include service-role keys (SEC-07)"
- "Bundle leak-grep re-run against live URL after every deploy that touches dashboard env vars (defense against paste errors)"
```

**Deviation:** vite-plugin gets `SENTRY_AUTH_TOKEN` from `process.env` (Node build context), NOT `import.meta.env` (browser runtime). This is the one Vite config file that legitimately reaches into `process.env`.

---

### 4. `backend/main.py` `/api/health` upgrade (modify — DB probe + 503 + limiter exclusion)

**Closest analogs (composite — no single file matches both DB-probe and limiter-exempt patterns):**

#### Analog A — supabase-py call with try/except → JSON dict (`backend/services/sql_service.py:48-67`)

```python
def execute_sql(user_id: str, query: str) -> dict:
    """Execute a read-only SQL query via the safe RPC function."""
    settings = get_settings()
    db = get_supabase()
    try:
        result = db.rpc("execute_readonly_query", {
            "query_text": query,
            "max_rows": settings.sql_max_rows,
            "calling_user_id": user_id,
        }).execute()
        rows = result.data if result.data else []
        return {
            "success": True,
            "rows": rows,
            ...
        }
    except Exception as e:
        logger.error(f"SQL execution failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "rows": [], "row_count": 0}
```

**What to mirror:**
- `db = get_supabase()` to obtain the service-role client (`backend/database.py:5-7`)
- Wrap the `.execute()` call in `try/except Exception` — `supabase-py` raises broad exceptions on connection failure
- `logger.error(..., exc_info=True)` on failure (project convention: errors get stack traces; warnings/info don't — confirmed across `services/`)
- Return a structured dict, never re-raise the supabase exception out of the handler

**What to deviate:**
- `/api/health` returns a FastAPI Response with a non-200 status (503) on failure, not a 200 with a `success: false` field. CONTEXT.md decision 2 specifies HTTP 503 + JSON `{"status": "degraded", "db": "unreachable"}` so UptimeRobot triggers on non-2xx.
- Use `JSONResponse(status_code=503, content={...})` — same pattern already used in `main.py:20-46` for the rate-limit 429 handler.
- The exact supabase-py invocation for `select 1` is CONTEXT open question #3; planner waits for RESEARCH.md. Two candidate shapes:
  - `db.rpc("execute_readonly_query", {"query_text": "select 1", ...}).execute()` — reuses existing RPC; downside: adds auth dependency (`calling_user_id` is required arg → would need a system UUID).
  - `db.table("<any_existing_table>").select("id").limit(1).execute()` — uses postgrest path; lightweight; only verifies reachability, not raw SQL.
  - The DECISION says "lightest possible, no schema coupling, no RLS dependency" → candidate 2 is wrong (couples to schema), candidate 1 has RLS via `calling_user_id`. RESEARCH must resolve, but the **pattern** (try/except + structured response) is set regardless.

#### Analog B — `JSONResponse` with non-200 status (`backend/main.py:20-46`)

```python
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    ...
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "detail": "Too many chat requests — slow down.",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
```

**What to mirror:** the 503 path uses `JSONResponse(status_code=503, content={...})` — no need for a separate `Response` import; `JSONResponse` is already imported at `main.py:3`.

#### Analog C — slowapi limiter scope (`backend/routers/chat.py:467-475`)

```python
@router.post("/{thread_id}/messages")
@traceable(name="chat_send_message")
@limiter.limit(get_settings().chat_rate_limit)  # SEC-04: per-user 20/minute on /api/chat
async def send_message(
    request: Request,                            # SEC-04: REQUIRED by slowapi (RESEARCH Pitfall 1)
    thread_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_user_id),
):
```

**Key observation:** Phase 6 added rate limiting **per-route via decorator only**. There is NO global `app.add_middleware(SlowAPIMiddleware)`-side filter that lists routes — `main.py:49` adds the middleware so decorators *can* fire, but it never auto-applies to all routes. Conclusion: `/api/health` is **already** rate-limit-free in the current codebase because it has no `@limiter.limit` decorator.

**What this means for Phase 7:** "Exclude `/api/health` from rate limiter" requires NO new code — the absence of `@limiter.limit` IS the exclusion. The planner's verification task must just assert "no `@limiter.limit` decorator on `/api/health`" rather than apply a `@limiter.exempt` decorator. The DISCUSSION-LOG and CONTEXT phrasing ("EXCLUDED from slowapi limiter") describes current-state truth that needs documenting, not new wiring.

**Deviation note for planner:** if RESEARCH later finds Phase 6 introduced an `app.add_middleware` global filter (e.g., a `limit_all_routes` config), update this assumption. Greppable invariant: `@limiter.limit` appears only at `backend/routers/chat.py:469` today.

#### Adapted shape for new `/api/health` (composite):

```python
from fastapi.responses import JSONResponse
# get_supabase, logger already needed

@app.get("/api/health")
async def health():
    """DB-reachability probe. Excluded from slowapi (no @limiter.limit decorator).
    Returns 200 when Postgres reachable, 503 when degraded.
    Also serves OBS-04 side-effect: 5-min UptimeRobot ping keeps Supabase free-tier active.
    """
    try:
        db = get_supabase()
        # Exact probe TBD by RESEARCH (CONTEXT open question 3) — placeholder:
        db.rpc("execute_readonly_query", {"query_text": "select 1", ...}).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"/api/health DB probe failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "unreachable"},
        )
```

---

### 5. `backend/scripts/verify_langsmith_routing.py` (new — automated OBS-02 verification)

**Closest analogs (hybrid — no Python verification script exists):**

#### Analog A — Python script bootstrap (`backend/scripts/seed_default_kb.py:1-21`)

```python
"""Seed the default knowledge base with 10 popular board game markdown files.
...
"""

import sys
import os
...

# Add backend directory to sys.path so imports work when run as a module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_supabase
from services.record_manager import hash_content, check_duplicate
from services.ingestion_service import process_document

logger = logging.getLogger(__name__)
```

**What to mirror:**
- Module docstring explaining purpose + usage at top (matches convention from CLAUDE.md: "Module-level docstrings for test files explaining purpose and usage")
- `sys.path.insert(0, ...)` shim so the script can import from `backend/` when run as `python backend/scripts/verify_langsmith_routing.py`
- Import `get_settings()` from `config` to read `langsmith_api_key` and project names (env loading is automatic — `config.py:9` calls `load_dotenv` at module-import time)
- `logger = logging.getLogger(__name__)`

#### Analog B — Wait-and-assert idiom + post-deploy verification (`backend/scripts/fly_smoke.sh:18-54`)

```bash
FLY_URL="${1:?usage: fly_smoke.sh <FLY_URL> ...}"
HEALTH_TIMEOUT=60       # seconds total
HEALTH_CADENCE=${HEALTH_CADENCE:-2}        # seconds between polls

# Step 1: trigger work (SSE chat against deployed URL)
# Step 2: poll with timeout + cadence
# Step 3: assert minimum count
# fail() / ok() / log() ANSI-color helpers
```

**What to mirror in the Python script:**
1. Accept `FLY_URL` as a CLI arg (argparse or `sys.argv[1]`) — script must run against any deployed environment, not a hardcoded URL
2. Make one HTTP POST to `${FLY_URL}/api/threads` + one SSE POST to `${FLY_URL}/api/threads/{id}/messages` to produce a LangSmith run (reuse JWT bootstrap from `_lib/get_test_jwt.sh` — call via subprocess OR re-implement in Python using `httpx`)
3. After chat completes, sleep ~5-10s for LangSmith to ingest the run (CONTEXT open question 4 resolves the exact granularity)
4. Call `langsmith.Client().list_runs(project_name="boardgame-rag-prod", start_time=...)` — assert count >= 1
5. Call `langsmith.Client().list_runs(project_name="boardgame-rag-dev", start_time=...)` — assert count == 0
6. Exit non-zero with a clear stderr message on assertion failure (matches `fail()` idiom)

#### Analog C — config + env loading (`backend/config.py:1-9`, `backend/scripts/_lib/get_test_jwt.sh`)

`config.py` loads `.env` automatically via `load_dotenv` at module-import time, so simply `from config import get_settings` is sufficient. The script does NOT need its own `load_dotenv` call — that's already done. Use `settings = get_settings()` then read `settings.langsmith_api_key`.

For JWT acquisition, the established pattern is to reuse `_lib/get_test_jwt.sh` (per Phase 4 D-14). Two options:
- **Subprocess call:** `subprocess.run(["bash", "backend/scripts/_lib/get_test_jwt.sh", ...])` — preserves the single-source-of-truth pattern but requires bash on the host.
- **Python re-implementation:** Use `httpx.post(f"{VITE_SUPABASE_URL}/auth/v1/token?grant_type=password", ...)` — cleaner cross-platform but duplicates logic.

**Recommendation for planner:** Python re-implementation. The script runs on dev machines (Win/Mac/Linux) and is verification-only; cross-platform Python is more durable than shelling to bash. Document the duplication in the script docstring.

#### Adapted shape (sketch):

```python
"""Verify LangSmith routes prod traces to boardgame-rag-prod, NOT boardgame-rag-dev.

Usage:
    python backend/scripts/verify_langsmith_routing.py https://boardgame-rag-prod.fly.dev

Exits 0 on PASS. Non-zero with a clear stderr message on FAIL.
Reads LANGSMITH_API_KEY + LANGSMITH_PROJECT_PROD + LANGSMITH_PROJECT_DEV from .env via config.Settings.
"""
import sys, os, time, logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import get_settings
import httpx
from langsmith import Client

logger = logging.getLogger(__name__)

def main(fly_url: str) -> int:
    settings = get_settings()
    started_at = datetime.now(timezone.utc) - timedelta(seconds=10)  # window slightly before trigger

    # 1. Acquire JWT (reimplemented from _lib/get_test_jwt.sh)
    # 2. POST /api/threads → thread_id
    # 3. POST /api/threads/{id}/messages with SSE accept; consume stream
    # 4. time.sleep(8)  # LangSmith ingest lag — RESEARCH refines
    # 5. client = Client(api_key=settings.langsmith_api_key)
    # 6. prod_runs = list(client.list_runs(project_name="boardgame-rag-prod", start_time=started_at))
    # 7. dev_runs  = list(client.list_runs(project_name="boardgame-rag-dev",  start_time=started_at))
    # 8. assert len(prod_runs) >= 1, "no prod runs landed"
    # 9. assert len(dev_runs) == 0,  "prod traffic leaked into dev project"
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

**Deviation from existing scripts:** unlike `fly_smoke.sh` (bash), this is Python because LangSmith SDK is Python-only. Place at `backend/scripts/verify_langsmith_routing.py` to match the `seed_default_kb.py` directory + naming convention (`snake_case.py`, descriptive verb + noun).

---

### 6. `backend/config.py` — `LANGSMITH_PROJECT` field

**Closest analog:** `backend/config.py:17-19` — `langsmith_api_key` and `langchain_project` fields already exist.

**Current state (`backend/config.py:16-19`):**
```python
    supabase_jwt_secret: str = ""
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: str = "true"
    langchain_project: str = "rag-masterclass"
```

And `backend/services/tracing.py:15` writes it to env:
```python
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
```

**Critical finding:** the existing field is named `langchain_project` (with default `"rag-masterclass"`), NOT `langsmith_project`. CONTEXT.md and Phase 4 SUMMARY both refer to the env var as `LANGSMITH_PROJECT`. Two reconciliation paths:

1. **Rename `langchain_project` → `langsmith_project`** in `config.py` AND `tracing.py`. Update Fly secret name from whatever was set in Phase 4 (CONTEXT.md says "confirm Fly secret state from Phase 4 SUMMARY" — see Phase 4 SUMMARY canonical ref). Pros: matches CONTEXT.md naming. Cons: breaking change to env contract; requires Fly secret rotation.
2. **Keep `langchain_project`** as-is. The SDK reads `LANGCHAIN_PROJECT` env var (set at `tracing.py:15`), and the underlying LangSmith service treats `LANGCHAIN_PROJECT` as the project routing key. Document that CONTEXT.md's "`LANGSMITH_PROJECT`" is a naming inconsistency in the context doc, NOT a real env-var contract.

**Recommendation for planner:** option 2 — keep the existing field and env var. The LangSmith SDK reads `LANGCHAIN_PROJECT`, not `LANGSMITH_PROJECT` (this is a LangChain-era SDK that LangSmith inherited). Document the naming clarification in the plan's deviation log. CONTEXT.md will need a one-line correction in 07-SUMMARY.md at phase end.

**Verification step the planner should add:** check `.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md` (specifically the "24 Fly secrets staged" line at SUMMARY ln 14) for the actual Fly secret name. If it's already `LANGCHAIN_PROJECT=boardgame-rag-prod`, option 2 is zero-code-change.

**Required check in plan:**
```bash
flyctl secrets list -a boardgame-rag-prod | grep -i 'lang.*project'
```

Expected result: `LANGCHAIN_PROJECT` (already set). If absent: `flyctl secrets set LANGCHAIN_PROJECT=boardgame-rag-prod`.

---

### 7. UptimeRobot dashboard configuration (no code)

**Closest analog:** `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md` (CF Pages dashboard checklist) + `.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md` (Fly secrets dashboard work).

**Pattern to mirror — out-of-repo dashboard work is captured as runbook in SUMMARY.md:**

Per `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md:66-67`:
> "**Files modified:** 2 in-repo (the rest is out-of-repo CF Pages project + Fly secret)"

UptimeRobot setup is identical in shape: no in-repo file changes, but the plan task lists explicit dashboard steps (account creation, monitor add, alert contact, downtime simulation) and the SUMMARY captures the final monitor IDs + screenshot evidence of the alert email.

**Planner spec for the UptimeRobot task:**
1. Task-level acceptance: explicit dashboard checklist (monitor 1 URL, monitor 2 URL, interval, alert contact email)
2. Verification step: simulated downtime (CONTEXT.md decision 4, UptimeRobot section, suggests `flyctl machine stop` or a bogus CORS override to force `/api/health` 5xx)
3. Evidence captured in SUMMARY.md: monitor IDs + timestamp of alert email + confirmation revert succeeded

---

## Shared Patterns

### Env-var loading convention

**Source:** `backend/config.py:1-12` (backend) + `frontend/src/lib/supabase.ts:3-4` (frontend)

**Backend:** env vars defined as `Settings` fields with type + default → loaded via `pydantic-settings` + `load_dotenv` at module import. Settings cached via `@lru_cache` on `get_settings()`. Access via `from config import get_settings; settings = get_settings()`.

**Frontend:** env vars read once at module top via `import.meta.env.VITE_*`. Vite reads `envDir: '..'` from `vite.config.ts:7` → single `.env` file at repo root, prefix-filtered (`VITE_*` → bundle; non-prefixed → backend only).

**Apply to Phase 7:**
- `VITE_SENTRY_DSN` → frontend, read in `sentry.ts` via `import.meta.env.VITE_SENTRY_DSN`
- `VITE_GIT_SHA` (alias for `CF_PAGES_COMMIT_SHA`) → frontend release tag, exposed via CF Pages build-time env mapping
- `SENTRY_AUTH_TOKEN` → build-time only, read in `vite.config.ts` via `process.env.SENTRY_AUTH_TOKEN` (Node context, NOT Vite-imported)
- `LANGSMITH_API_KEY`, `LANGCHAIN_PROJECT` → backend, already in Settings

### Local .env vs Fly secrets parity

**Source:** `.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md:13-14`
> "24 Fly secrets staged via flyctl secrets import (9 required + 15 app-config)"

Local devs need `LANGSMITH_API_KEY` + `LANGCHAIN_PROJECT=boardgame-rag-dev` in `.env` (repo root). Fly has `LANGSMITH_API_KEY` (same value) + `LANGCHAIN_PROJECT=boardgame-rag-prod` (different value — this is the routing decision). Service-role keys + DSN are NOT shared — dev never gets the prod DSN.

| Env var | Local `.env` | Fly secret | CF Pages env |
|---------|--------------|------------|--------------|
| `LANGSMITH_API_KEY` | yes (same value) | yes (same value) | n/a |
| `LANGCHAIN_PROJECT` | `boardgame-rag-dev` | `boardgame-rag-prod` | n/a |
| `VITE_SENTRY_DSN` | unset (dev = no Sentry) | n/a | yes (Production scope only) |
| `SENTRY_AUTH_TOKEN` | unset | n/a | yes (Build env only) |

### CF Pages env-var scope convention

**Source:** `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md:28, 46`
> "Frontend env vars baked at build time via CF dashboard (Production scope only); Preview deploys disabled to avoid hash subdomain CORS sprawl"

**Apply:** `VITE_SENTRY_DSN` + `VITE_GIT_SHA` Production scope only, Preview disabled. `SENTRY_AUTH_TOKEN` Build env only (NOT Runtime — it must not reach the browser bundle).

### Logging convention

**Source:** CLAUDE.md "Logging" section + observed pattern across `backend/services/*.py`

- `logger.info()` — successful operations
- `logger.warning()` — fallbacks, missing-optional-config (e.g., `tracing.py` "no-op if LANGSMITH_API_KEY unset" is implicit-warning-via-return; explicit `logger.warning` is acceptable here)
- `logger.error(..., exc_info=True)` — failures with stack trace

**Apply to `/api/health` failure path:** `logger.error(f"/api/health DB probe failed: {e}", exc_info=True)` matches the `services/sql_service.py:66` precedent verbatim.

### SEC-07 leak-grep regression

**Source:** `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md:47`
> "Bundle leak-grep re-run against live URL after every deploy that touches dashboard env vars (defense against paste errors)"

**Apply to Phase 7:** after first CF Pages deploy with `VITE_SENTRY_DSN` + `SENTRY_AUTH_TOKEN` configured, re-run the SEC-07 grep against the deployed bundle. Specifically:
- `VITE_SENTRY_DSN` value MAY appear in the bundle (it's a runtime config, public DSNs are not secret)
- `SENTRY_AUTH_TOKEN` value MUST NOT appear in the bundle (build-time secret) — grep must be clean
- The plan's verification task must call this out as a distinct assertion from the existing SEC-07 grep

---

## No Analog Found

| File / Surface | Reason planner should defer to RESEARCH.md |
|----------------|--------------------------------------------|
| Exact `@sentry/vite-plugin` config block | CONTEXT open question 1 — planner waits for researcher to confirm `release:` shape + source-map deletion-from-dist behavior |
| Exact supabase-py `select 1` invocation | CONTEXT open question 3 — planner waits for researcher; pattern (try/except + structured 503) is set regardless |
| LangSmith `list_runs` `start_time` granularity | CONTEXT open question 4 — planner waits; script skeleton is set |
| Fly auto-stop cold-start vs UptimeRobot 30s timeout | CONTEXT open question 2 — planner waits; may need keep-warm toggle adjustment (out of code scope, fly.toml only) |

---

## Metadata

- **Analog search scope:** `frontend/src/lib/`, `frontend/src/main.tsx`, `frontend/vite.config.ts`, `backend/main.py`, `backend/services/`, `backend/scripts/`, `backend/config.py`, `backend/limiter.py`, `backend/routers/chat.py`, `.planning/phases/04-*`, `.planning/phases/05-*`
- **Files Read:** 14
- **Greps:** 6
- **Stopping rule applied:** strong analog found for 6/7 files within first scan pass; no additional searches required.
- **Pattern extraction date:** 2026-05-15
