---
status: complete
phase: 07-observability-baseline
source:
  - 07-01-SUMMARY.md
  - 07-02-SUMMARY.md
  - 07-03-SUMMARY.md
  - 07-04-SUMMARY.md
  - 07-05-SUMMARY.md
started: "2026-05-20T17:30:00.000Z"
updated: "2026-05-20T17:48:00.000Z"
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Backend container boots from scratch on Fly with no errors. GET /api/health returns 200 with a healthy status payload while the prod Supabase DB is reachable.
result: pass

### 2. Sentry frontend error capture (OBS-01)
expected: An uncaught frontend error (or a chat failure) on the deployed app produces an event in the dedicated Sentry project. The `beforeSend` PII scrub strips JWT/email/UUID. (Independently observed this session — Phase 8 UAT item 9 confirmed a live Sentry event from a forced chat error.)
result: pass

### 3. /api/health DB-reachability probe (OBS-04)
expected: GET /api/health checks real Supabase DB reachability — returns 200 healthy when the DB responds, and 503 with `{"status":"degraded","db":"unreachable"}` when it does not. Not just process liveness.
result: pass
note: Verified via live curl (200 {"status":"ok"}) + code review of backend/main.py:88-97 — line 90 runs a real `documents` count query; 200 is conditional on DB success. 503 degraded path code-verified, not drilled (would require breaking prod DB).

### 4. LangSmith prod trace routing (OBS-02)
expected: Backend chat requests on prod emit traces to the dedicated prod LangSmith project (separate from the dev/local project), configured via env vars only.
result: pass

### 5. UptimeRobot monitors + downtime alert (OBS-03)
expected: Two UptimeRobot monitors ping the Fly backend /api/health and the Cloudflare Pages frontend at a ≤5-minute interval. Owner receives an email alert on downtime. (Independently confirmed this session — monitor API key retrieved, uptime badge renders 97.194%.)
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
