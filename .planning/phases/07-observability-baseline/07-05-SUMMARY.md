# Plan 07-05 SUMMARY — UptimeRobot setup + simulated downtime drill

**Completed:** 2026-05-16/17
**Plan:** `.planning/phases/07-observability-baseline/07-05-PLAN.md`
**Requirements:** OBS-03
**Type:** Manual dashboard work (no autonomous execution)

## Outcome

✅ Two UptimeRobot monitors live at 5-min interval against Fly backend + CF Pages frontend. Owner email Alert Contact verified. Downtime drill exercised via accidental 405 (HEAD vs GET — see below); recovery email + monitor Up transition confirmed. OBS-03 satisfied.

## Monitors

| ID | Friendly name | URL | Interval | Type | Current state |
|---|---|---|---|---|---|
| 803088267 | `boardgame-rag-prod fly /api/health` | https://boardgame-rag-prod.fly.dev/api/health | 5 min | HTTP(s) status | Up |
| 803088282 | `boardgame-rag-prod cf-pages root` | https://boardgame-rag-prod.pages.dev/ | 5 min | HTTP(s) status | Up |

## Alert contact

- Single email contact: `mlynn808138@gmail.com` (verified)
- Both monitors share this single Alert Contact
- No SMS, no webhook, no Slack/Discord
- No public status page

## Notable bug surfaced + fixed during drill

**Symptom:** Monitor 1 (`/api/health`) showed an open incident for 4h 32m with root cause `405 Method Not Allowed`.

**Root cause:** UptimeRobot's free-tier HTTP monitor defaults to `HEAD` requests (bandwidth-efficient). The original Plan 07-02 handler used `@app.get("/api/health")` which only registers GET → HEAD requests returned 405. Sentry-side: harmless. UR-side: counted as Down for the entire post-deploy window.

**Fix:** Commit `8300fd3` — `fix(07-02): allow HEAD on /api/health for UptimeRobot`. Switched to `@app.api_route(methods=["GET", "HEAD"])`. Same handler body; HEAD inherits status code (200/503) but returns no body, which is exactly what UR wants. All 4 Plan 07-02 tests still pass after the change. Deployed via `flyctl deploy`. Monitor flipped Up within one poll cycle; recovery email arrived.

**Why we didn't catch it pre-deploy:** Plan 07-02 tests use `TestClient.get(...)` only — no HEAD coverage. UR's HEAD default isn't documented prominently. Real integration with UR surfaced it on first poll. Acceptable cost; the fix is one line + 4 chars.

## Simulated downtime drill — alternate path

The CONTEXT-specified drill (flip `SUPABASE_URL` to bogus → force 503) was attempted but the backend's supabase-py client init eagerly validates connection params, so a bad URL crashed uvicorn at boot rather than producing the desired 503 from a still-alive process. Same issue with bogus `SUPABASE_SERVICE_ROLE_KEY` (JWT format validation at client construct).

Tried `flyctl machine stop` — Fly's `auto_stop_machines=suspend` config (Phase 04) auto-restarts the machine on the next inbound request, so the stop is undone before UR's next poll.

The 405 incident above served as a real-world downtime test: 4h+ Down state → email alerts received → fix deployed → recovery email arrived → monitor flipped Up. End-to-end alerting path proven. Formal pause-Fly-secret drill skipped per user decision after email alerting confirmed working.

## Verification matrix

| Check | Result |
|---|---|
| Two monitors created at 5-min interval | ✅ IDs 803088267, 803088282 |
| Owner email Alert Contact verified | ✅ confirmation link clicked |
| Both monitors share single email contact | ✅ |
| No SMS / webhook / Slack | ✅ |
| No public status page | ✅ |
| Real Down → email → Up → recovery email cycle exercised | ✅ via 405 incident (4h 32m) then 8300fd3 deploy |
| `/api/health` returns 200 on GET + HEAD post-fix | ✅ `curl -sI` returns HTTP/1.1 200 with JSON content-type |
| Monitor 1 uptime stat | 0.656% over last 7 days (1 incident, 4h 42m 52s down — captured during this plan) |
| Monitor 2 uptime stat | Not separately recorded — Up since creation |

## OBS-04 side effect (Supabase active-keep)

Each 5-min Monitor 1 ping triggers the supabase-py head-only count on `documents` (Plan 07-02 handler). 288 DB queries/day resets the 7-day idle clock → Supabase free-tier project will not auto-pause. User experienced this exact failure mode on the old dev project earlier in this session (DNS NXDOMAIN after pause), validating the design.

## Caveats / follow-ups

- UR free tier dropped keyword check capability (now Solo+ only). Monitor 1 cannot verify response body shape — only status code. Mitigation: handler ALWAYS returns 503 on DB fail (Plan 07-02), so status-code check is sufficient signal.
- Fly cold-start interaction with UR 30s timeout: untested in this drill but RESEARCH §Q2 predicts ~2s suspend-resume (well under 30s). Will be observed naturally over the next month of monitoring.

## Commits

- `8300fd3` — `fix(07-02): allow HEAD on /api/health for UptimeRobot`
