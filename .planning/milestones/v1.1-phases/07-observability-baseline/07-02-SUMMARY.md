---
phase: "07"
plan: "02"
subsystem: backend
tags: [observability, health-check, fastapi, supabase, OBS-04]
requires:
  - backend/main.py /api/health stub (pre-Plan-07-02 200 + {"status":"ok"} handler)
  - backend/database.py get_supabase() service-role factory
  - SlowAPI per-route opt-in invariant from Phase 6 SEC-04
provides:
  - /api/health DB-reachability probe (OBS-04 backend half)
  - 503 + {"status":"degraded","db":"unreachable"} contract for UptimeRobot
  - Test suite pinning the locked probe shape + limiter-exemption invariant
affects:
  - backend/main.py (handler upgraded, no breaking change to 200 success contract)
  - backend/tests/test_health.py (new — 4 tests, 124 lines)
tech_stack_added: []
tech_stack_patterns:
  - supabase-py head-only count probe (db.table.select(count="exact", head=True).limit(1).execute)
  - JSONResponse-based degraded envelope (try/except → fixed-shape 503 response)
  - logger.error(..., exc_info=True) for DB probe failures (matches sql_service.py convention)
  - main.get_supabase patch target for FastAPI handler unit tests (import-time symbol)
key_files:
  created:
    - backend/tests/test_health.py
  modified:
    - backend/main.py
decisions:
  - Patch `main.get_supabase` (not `database.get_supabase`) — Python mock lookup follows the import-time binding in the calling module
  - No timeout wrapper — supabase-py head-only count is O(microseconds); full unreachability already caught by Exception handler
  - No @limiter.exempt decorator — slowapi is per-route opt-in; absence of @limiter.limit IS the exemption (RESEARCH Pitfall 7)
  - Probe `documents` table — public-visibility KB seeded in Phase 3, ≥10 rows guaranteed, service-role bypasses RLS
metrics:
  duration_seconds: 483
  tasks_completed: 2
  tests_added: 4
  files_modified: 1
  files_created: 1
  completed_at: "2026-05-16"
---

# Phase 07 Plan 02: /api/health DB-Reachability Probe Summary

Upgrade `/api/health` from a static 200/`{"status":"ok"}` ping to a real Supabase
head-only count probe that returns 503 + `{"status":"degraded","db":"unreachable"}`
on any DB exception, closing the backend half of OBS-04. UptimeRobot dashboard
provisioning is Plan 07-05.

## What Was Built

**Backend handler** (`backend/main.py`):

- Added `import logging` + `logger = logging.getLogger(__name__)` at module top
- Added `from database import get_supabase` to local imports
- Replaced the 3-line stub handler with a 27-line probe:
  - Docstring explaining OBS-04 contract, table choice rationale, and rate-limit-exempt rationale
  - `try`: `db.table("documents").select("id", count="exact", head=True).limit(1).execute()` → `return {"status": "ok"}` (FastAPI serializes to JSON 200, preserving the existing contract)
  - `except Exception as e`: `logger.error("Health check DB probe failed: %s", e, exc_info=True)` → `return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})`
- Did NOT add `@limiter.limit` (preserves Phase 6 invariant; UptimeRobot 288/day cadence never trips a 429)
- Did NOT add a timeout wrapper (RESEARCH Pitfall 4 — head-only is O(microseconds), full unreachability already covered by Exception)

**Test module** (`backend/tests/test_health.py`, 124 lines, 4 tests):

| Test | What it pins |
|------|--------------|
| `test_health_ok` | Success path: 200 + `{"status": "ok"}` with mocked supabase chain |
| `test_health_degraded_when_supabase_raises` | Failure path: 503 + locked degraded envelope when `.execute()` raises |
| `test_health_actually_calls_supabase_documents_table` | Probe shape pinned exactly: `db.table("documents").select("id", count="exact", head=True).limit(1).execute()` — defends T-07-11 (refactor silently weakening probe to no-op) |
| `test_health_route_has_no_limiter_decorator` | Rate-limit exemption pinned two ways: (1) endpoint has no slowapi `_rate_limits` attr, (2) source-grep of `main.py` finds no `@limiter.limit` / `@limiter.exempt` in the 3 lines above `async def health` |

All tests patch `main.get_supabase` (not `database.get_supabase`) — the symbol
resolved at import time inside `main.py` is what the handler actually calls.

## Verification

| Check | Result |
|-------|--------|
| `pytest tests/test_health.py -x -v` | 4 passed, 0 failed (2.33s) |
| `pytest tests/` (full backend suite, excluding env-dependent `test_e2e_subagent.py`) | 121 passed, 0 failed (43.70s) |
| `pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_health.py` | 14 passed (Phase 6 SEC-04/SEC-05 still green — no regressions) |
| Grep `documents.*count=.exact.*head=True` in `backend/main.py` | 1 match (line 89) |
| Grep `status_code=503` in `backend/main.py` | 1 match (line 94) |
| Grep `@limiter\.(limit|exempt)` in `backend/main.py` | 0 matches |
| Grep `from database import get_supabase` in `backend/main.py` | 1 match (line 12) |
| Grep `logger\.error.*Health check.*exc_info=True` in `backend/main.py` | 1 match (line 92) |
| TestClient smoke against handler with no `.env` loaded | Returns 503 + correct degraded envelope (failure path proven end-to-end) |

### Out-of-Scope Pre-Existing Issues (Not Caused By This Plan)

- `tests/test_e2e_subagent.py` fails collection (`KeyError: 'VITE_SUPABASE_URL'`) — it's an E2E test that loads `.env` from `../../.env`; the worktree context lacks that file. Pre-existing, not regression.
- `tests/test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` error at setup (`fixture 'user_id' not found`) — pre-existing fixture wiring issue, not regression.

Both issues exist in the codebase before Plan 07-02; they are unrelated to `/api/health` or anything modified in this plan.

## Deviations from Plan

None — plan executed exactly as written.

One small editorial adjustment inside `main.py` (not a deviation, just a code-style call): the docstring originally drafted said `"@limiter.limit"` to describe the absence of a decorator. To keep the `@limiter\.(limit|exempt)` final-verification grep at literal 0 matches (and avoid a false positive from a docstring mention), the docstring was rephrased to `"no limiter.limit decorator"`. Semantic intent unchanged.

## Threat Model Mitigations Applied

- **T-07-08 (Info Disclosure):** Fixed JSON envelope `{"status":"degraded","db":"unreachable"}` — no exception text leaks to caller; stack trace goes only to `logger.error(..., exc_info=True)` server-side.
- **T-07-09 (DoS via rate limiter):** Handler has no `@limiter.limit` decorator. `test_health_route_has_no_limiter_decorator` pins this both at the slowapi attribute level and via main.py source-grep.
- **T-07-11 (Tampering / silent no-op):** `test_health_actually_calls_supabase_documents_table` asserts exact call args `("documents",)`, `select("id", count="exact", head=True)`, `limit(1)`, and `execute()` — any future refactor that omits the DB call (or changes the table/select shape) will fail CI.

## Commits

| Commit | Message |
|--------|---------|
| `fdf788f` | feat(07-02): upgrade /api/health to DB-reachability probe (OBS-04) |
| `44ab07b` | test(07-02): cover /api/health OBS-04 envelope + limiter exemption |

## Files

- **Modified:** `backend/main.py` (3-line stub → 30-line probe handler + 3 imports/logger setup)
- **Created:** `backend/tests/test_health.py` (124 lines, 4 tests)

## Self-Check: PASSED

- `backend/main.py` — exists, contains all required tokens
- `backend/tests/test_health.py` — exists, 124 lines, 4 `def test_` matches
- Commit `fdf788f` (feat) — verified in `git log --oneline`
- Commit `44ab07b` (test) — verified in `git log --oneline`
- 4 new tests pass, full suite green (excluding pre-existing env-dependent test_e2e_subagent.py and pre-existing test_record_manager fixture errors)
