---
phase: "07"
slug: observability-baseline
created: 2026-05-15
requirements:
  - OBS-01
  - OBS-02
  - OBS-03
  - OBS-04
---

<domain>
Phase 7 — Observability Baseline. Before the prod URL is shared publicly, uncaught frontend errors (Sentry), backend traces (LangSmith prod project, isolated from dev), and uptime monitoring (UptimeRobot) all flow to dedicated prod channels. `/api/health` upgrades from a process-liveness ping to a DB-reachability probe so monitor success also keeps the Supabase free-tier project from auto-pausing after 7 days idle.
</domain>

<canonical_refs>
- `.planning/ROADMAP.md` — Phase 7 success criteria (lines 120–128)
- `.planning/REQUIREMENTS.md` — OBS-01 through OBS-04 (lines 32–35)
- `.planning/codebase/STACK.md` — current LangSmith wiring via `backend/services/tracing.py`
- `backend/main.py:65` — existing `/api/health` returning `{"status":"ok"}` (replaced this phase)
- `backend/routers/chat.py:24` — `from langsmith import traceable` (existing tracing entry point)
- `.planning/phases/06-prod-wiring-auth-cors-rate-limiting-cost-caps/06-04-VERIFICATION.md` — Auth URL config pattern (Supabase dashboard) reused for Sentry/UptimeRobot dashboard work
- `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-01-SUMMARY.md` — CF Pages env var injection pattern (Production scope) for `VITE_SENTRY_DSN` + `VITE_GIT_SHA`
- `.planning/phases/04-deploy-backend-to-fly-io/04-02-SUMMARY.md` — Fly secret pattern for `LANGSMITH_PROJECT`
</canonical_refs>

<decisions>

## Sentry (OBS-01)

- **Scope:** Frontend only. Backend errors stay in Fly logs + LangSmith traces; no `sentry-sdk[fastapi]` on backend.
- **Tier:** Free Developer (5k errors/mo, 1 user, 30d retention) — sufficient for portfolio traffic.
- **Project:** Single project, name TBD by user during plan execution (`boardgame-rag-frontend` recommended).
- **Source maps:** Uploaded at build time via `@sentry/vite-plugin` configured in `frontend/vite.config.ts`. Plugin reads `SENTRY_AUTH_TOKEN` (CF Pages Build env, NOT runtime).
- **Release tagging:** Git SHA. CF Pages provides `CF_PAGES_COMMIT_SHA` at build; vite-plugin injects it as the release identifier so each deploy is a distinct release in Sentry. No semantic versioning.
- **PII scrub (beforeSend / beforeBreadcrumb):**
  - **MUST scrub:** Auth JWTs (Authorization header, `sb-*-auth-token` localStorage), user email, Supabase user UUID. No `Sentry.setUser({...})` calls — events stay anonymous.
  - **ALLOWED to send:** Chat message content (prompts + assistant responses), document file names + folder paths, error stacks, navigation breadcrumbs. Debug value outweighs privacy concern for a portfolio app handling non-sensitive board-game KB data.
- **Env vars (frontend):** `VITE_SENTRY_DSN` (Production scope only, Preview disabled per Phase 5 convention).

## /api/health (OBS-04)

- **Probe:** `select 1` issued via the existing `supabase-py` service-role client at module level. No new tables, no RLS dependency, no RPC indirection. Lightest possible verification that Postgres is reachable + auth credentials valid.
- **Success response:** HTTP 200 + JSON `{"status": "ok"}` (preserves existing contract).
- **Failure response:** HTTP 503 + JSON `{"status": "degraded", "db": "unreachable"}`. Non-2xx triggers UptimeRobot alert. Process still alive but DB unreachable is the failure mode this catches.
- **Auth:** Public, unauthenticated.
- **Rate limit:** EXCLUDED from slowapi rate limiter added in Phase 6. UptimeRobot pings from rotating IPs without auth headers; rate-limit 429s would corrupt uptime ratio and mask real outages. Acceptable DoS exposure because `select 1` is O(microseconds).
- **OBS-04 side effect:** Every 5-min ping issues a DB query → keeps Supabase free-tier project active (7-day idle pause prevented).

## LangSmith (OBS-02)

- **Routing:** Single LangSmith API key in account. Project name routed via `LANGSMITH_PROJECT` env var per environment.
  - Local dev (`.env`): `LANGSMITH_PROJECT=boardgame-rag-dev`
  - Fly prod secret: `LANGSMITH_PROJECT=boardgame-rag-prod`
- **Existing wiring untouched:** `backend/services/tracing.py` already reads project from env; no SDK code change required. Phase work is dashboard setup + Fly secret confirmation.
- **Verification:** Automated. Plan must include a verification step that:
  1. Sends a chat request against the deployed Fly URL.
  2. Calls `langsmith.Client().list_runs(project_name="boardgame-rag-prod", start_time=now-5min)` and asserts at least one run exists.
  3. Calls `list_runs(project_name="boardgame-rag-dev", start_time=now-5min)` and asserts zero matching runs.
  - Script lives under `backend/scripts/`; runs from local against the prod Fly URL.

## UptimeRobot (OBS-03)

- **Tier:** Free. 50-monitor cap, 5-min minimum interval, email alerts.
- **Monitor count:** 2.
  - Monitor 1: `GET https://boardgame-rag-prod.fly.dev/api/health` — HTTP-status check (200 = up, 503 = down).
  - Monitor 2: `GET https://boardgame-rag-prod.pages.dev/` — HTTP-status check on CF Pages root.
- **Interval:** 5 minutes.
- **Alert contact:** Single email `mlynn808138@gmail.com`. No SMS. No webhook.
- **Public status page:** NOT created. UptimeRobot dashboard is private to owner.
- **Verification (success criterion #3 simulated downtime):**
  - `flyctl machine stop` on the prod machine briefly (or set CORS to a bogus value to force `/api/health` 5xx without taking down the machine — cleaner since it leaves the process running).
  - Wait ≤10 min, confirm alert email arrives.
  - Revert.

</decisions>

<deferred>
- **Backend Sentry integration** — captured as future optional enhancement. Phase 7 ships frontend-only.
- **LangSmith automated daily digest / cost report** — out of scope; LangSmith already shows per-trace cost.
- **UptimeRobot public status page** — explicitly rejected for now; can be added later if portfolio polish phase wants it (Phase 8 could revisit).
- **Backend log shipping (e.g., to Logtail, Axiom)** — Fly logs sufficient at this scale.
- **SLO / error budget tracking** — premature for a solo portfolio.
</deferred>

<constraints_carried_forward>
- **No new backend deps on Fly** beyond `langsmith` (already present); Sentry stays on frontend bundle only.
- **CF Pages env var Production scope only** — Preview deploys disabled (Phase 5 decision); `VITE_SENTRY_DSN` follows the same rule.
- **Free-tier first** — Sentry Developer, UptimeRobot Free, LangSmith free. Matches portfolio cost ceiling.
- **No PII identity attached to error events** — `Sentry.setUser` MUST NOT be called with email or UUID.
</constraints_carried_forward>

<open_questions_for_research>
- Exact `@sentry/vite-plugin` configuration shape for source-map upload — confirm with Sentry docs that `release: process.env.CF_PAGES_COMMIT_SHA` is the correct knob and that the plugin uploads source maps + then deletes them from the dist bundle so they aren't publicly served.
- Confirm UptimeRobot accepts the Fly auto-stop/suspend pattern — when Fly machine is in suspended state, does `/api/health` cold-start within the 30s UptimeRobot timeout, or does the first ping after idle reliably fail? May need keep-warm toggle or 2nd machine.
- supabase-py syntax for raw `select 1` — confirm whether to use `supabase.rpc(...)` indirection or a lower-level postgrest client method.
- LangSmith `list_runs` time filter granularity — confirm `start_time` accepts ISO-8601 with timezone or expects Unix epoch.
</open_questions_for_research>

<next_steps>
1. Run `/gsd:plan-phase 7` to produce plans from this CONTEXT.md.
2. Researcher will resolve the 4 open questions before plan-checker review.
</next_steps>
