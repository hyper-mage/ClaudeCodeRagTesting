---
phase: 12-model-cache-catalog
plan: 03
subsystem: api
tags: [openrouter, model-catalog, fastapi, pydantic, supabase, sse-free, seed-script, pytest, tdd]

# Dependency graph
requires:
  - phase: 12-model-cache-catalog
    provides: "plan 12-01 model_catalog_service (refresh_if_stale, build_model_response, fetch_catalog, _to_cache_row) + config.model_cache_ttl_seconds/POPULAR_MODELS"
  - phase: 12-model-cache-catalog
    provides: "plan 12-02 live model_cache table (model_id PK, pricing/is_free/fetched_at) + inverted global-read/service-role-write RLS"
  - phase: 10-byok-keys
    provides: "routers/keys.py auth-gated router pattern (Depends(get_user_id) + get_supabase service-role client) mirrored here"
provides:
  - "GET /api/models[?free_only=true] FastAPI router: refresh-if-stale over model_cache, composes plan-01 pure fns into ModelResponse rows, auth-gated"
  - "ModelResponse Pydantic model (D-10 render-ready fields, raw pricing retained)"
  - "scripts/seed_model_cache.py: idempotent deploy-time model_cache warm-up (ENV_FILE-aware)"
  - "main.py wiring: app.include_router(models.router)"
affects: [14-usage-cost, 15-options-ui, model picker (Phase 15), demo free-only filter (Phase 11)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin-router-as-seam: the route composes plan-01 pure functions (refresh_if_stale + build_model_response) and reimplements NONE of the tag/price/popularity/refresh logic"
    - "Server-side ?free_only filter via a typed bool query param (FastAPI coerces/rejects non-bool — input-validation control T-12-V5-03); client never recomputes is_free (D-02)"
    - "Belt-and-suspenders catalog warm-up: deploy seed (latency belt) + router first-request populate (correctness suspenders, never empty D-05)"

key-files:
  created:
    - backend/routers/models.py
    - backend/scripts/seed_model_cache.py
    - backend/tests/test_models_api.py
  modified:
    - backend/models/schemas.py
    - backend/main.py

key-decisions:
  - "Router COMPOSES plan-01 helpers (refresh_if_stale + build_model_response) — no duplicated tagging/pricing/refresh; the route is a pure seam (D-08/D-10/D-11 already proven in plan 12-01)"
  - "?free_only is a typed bool param filtered server-side (D-02) — non-bool input rejected by FastAPI coercion (T-12-V5-03); the client never recomputes is_free"
  - "Endpoint auth-gated via Depends(get_user_id) per codebase norm (A4) even though the catalog is non-secret (T-12-V4-03 → accept)"
  - "Seed reuses fetch_catalog + _to_cache_row from model_catalog_service (no re-implemented parse/write); idempotent model_id-keyed upsert, never delete-all (Pitfall 5)"
  - "Open Q2: NO fly.toml [deploy] release_command added in Phase 12 — first-request populate (D-05) is the correctness guarantee; the seed stays a manual/optional warm-up, recorded as a future ops optimization"

patterns-established:
  - "Catalog read is backend-only (Success Criterion #1): the frontend reads GET /api/models, NEVER OpenRouter directly"
  - "Mock-db chain in route tests drives cache state via .table().select('*').execute().data; fetch monkeypatched at services.model_catalog_service.fetch_catalog (where the service imports it); TTL forced to 0 to exercise the stale path offline"

requirements-completed: [MODEL-01, MODEL-04, MODEL-07]

# Metrics
duration: ~8min
completed: 2026-06-23
---

# Phase 12 Plan 03: Model Catalog Read API + Deploy Seed Summary

**Shipped GET /api/models[?free_only=true] — an auth-gated FastAPI router that runs refresh-if-stale over the model_cache table and composes the plan-01 pure functions into render-ready ModelResponse rows (never empty, serves stale on upstream failure), plus a ModelResponse schema and an idempotent ENV_FILE-aware deploy seed.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-23T15:32:58Z
- **Completed:** 2026-06-23T15:40:32Z
- **Tasks:** 3 (Task 1+2 are a TDD RED→GREEN pair)
- **Files created:** 3
- **Files modified:** 2

## Accomplishments
- `GET /api/models` serves the full catalog from `model_cache` as `ModelResponse` rows (id, name, context_length, is_free, price_per_mtok_prompt/completion, popularity_rank/source, raw pricing) — the frontend's ONLY catalog read path (Success Criterion #1, MODEL-01/MODEL-07).
- `?free_only=true` filters to free models SERVER-SIDE via a typed `bool` param (D-02) — non-bool input rejected by FastAPI coercion (T-12-V5-03); the `:free` fixture row qualifies, paid `gpt-4o-mini` and the `-1`-sentinel `openrouter/auto` are excluded.
- An empty `model_cache` populates synchronously on the first read (never empty, D-05); a stale cache refreshes on read; a failed upstream fetch serves the existing stale rows with a 200 (D-04) — all driven through the plan-01 `refresh_if_stale` (no reimplementation).
- `ModelResponse` Pydantic model added to `schemas.py` (D-10, raw pricing retained; frontend renders, never recomputes).
- `scripts/seed_model_cache.py` — idempotent deploy-time warm-up reusing `fetch_catalog` + `_to_cache_row`, model_id-keyed upsert (never delete-all), honoring `ENV_FILE` (.env dev / .env.prod prod).
- `main.py` wires `app.include_router(models.router)`.

## Task Commits

Each task was committed atomically (Tasks 1+2 are a TDD RED→GREEN pair):

1. **Task 1: Wave 0 — RED route tests (free_only, first-request populate, serve-stale)** - `8266dde` (test) — `test_models_api.py`; RED via `ModuleNotFoundError: routers.models`
2. **Task 2: ModelResponse schema + models.py router + main.py wiring** - `73861ae` (feat) — all 3 route tests GREEN
3. **Task 3: idempotent deploy-time seed (seed_model_cache.py)** - `f30d993` (chore) — parses + imports cleanly, reuses plan-01 helpers
4. **Out-of-scope log** - `21a2e0c` (docs) — `deferred-items.md` for two pre-existing env-dependent test failures

_TDD gate sequence satisfied: test (RED, 8266dde) → feat (GREEN, 73861ae). No refactor commit needed — the router was a clean seam on first GREEN._

## Files Created/Modified
- `backend/routers/models.py` - GET /api/models[?free_only] router; composes refresh_if_stale + build_model_response; auth-gated; server-side free filter.
- `backend/models/schemas.py` - added `class ModelResponse` (D-10 render-ready fields, raw pricing retained).
- `backend/main.py` - added `models` to the routers import + `app.include_router(models.router)`.
- `backend/scripts/seed_model_cache.py` - idempotent ENV_FILE-aware deploy seed reusing fetch_catalog + _to_cache_row.
- `backend/tests/test_models_api.py` - 3 route tests: test_free_only_filter, test_first_request_populate, test_serve_stale_on_fetch_failure.

## Decisions Made
- **Router is a pure seam:** it imports and composes `refresh_if_stale` + `build_model_response` from plan 12-01; zero duplicated tagging/pricing/popularity/refresh logic. The defensive parse + serve-stale guarantees were already unit-proven in plan 12-01.
- **Typed-bool `?free_only` filtered server-side (D-02):** FastAPI coerces/rejects non-bool query input (T-12-V5-03); the client never recomputes `is_free`.
- **Auth-gated (A4):** every router in this app is `Depends(get_user_id)`-gated; the catalog is non-secret so the disposition is accept (T-12-V4-03), but the gate stays for consistency.
- **Seed reuses plan-01 write path:** `fetch_catalog` + `_to_cache_row` + a model_id-keyed upsert (never delete-all, Pitfall 5); idempotent on re-run.
- **Open Q2 — no `[deploy] release_command` in fly.toml this phase:** the router's first-request populate (D-05) is the correctness guarantee, so the seed stays manual/optional. Adding `[deploy] release_command = "python -m scripts.seed_model_cache"` to `fly.toml` is an available, idempotent latency optimization for a future ops pass (recorded here per the Task 3 instruction).

## Deviations from Plan

None - plan executed exactly as written. All three tasks landed as specified; no Rule 1/2/3 auto-fix and no Rule 4 architectural decision arose. (The two pre-existing test failures below are explicitly out of scope per the SCOPE BOUNDARY rule, not deviations.)

## Issues Encountered
- **No venv in the worktree:** the worktree carries no `backend/venv`; ran the MAIN checkout's `backend/venv/Scripts/python.exe` with cwd set to the worktree backend so pytest picks up the worktree's source. The `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ... -p pytest_asyncio` quirk (broken global `dash.testing.plugin`) was honored as noted in the test-env note.
- **Two pre-existing out-of-scope test failures (logged to `deferred-items.md`, NOT fixed):** `tests/test_e2e_subagent.py` errors at collection on `KeyError: 'VITE_SUPABASE_URL'` (an E2E test requiring the repo-root `.env` + a running server at localhost:8000, neither present in the worktree); `tests/test_record_manager.py::{test_check_duplicate_integration, test_find_previous_version_integration}` error with `fixture 'user_id' not found` (live-Supabase integration tests). Both predate this plan and are unrelated to the router/schema/main changes. Offline suite excluding these: **189 passed**, including all 3 new route tests + the 10 plan-01 catalog tests — no regressions attributable to this plan.

## User Setup Required
None - no external service configuration required. (`MODEL_CACHE_TTL_SECONDS` remains optional, default 86400 from plan 12-01.) The deploy seed is optional; the first-request populate guarantees a non-empty catalog without it.

## Next Phase Readiness
- The full catalog read path is live: Phase 15's model picker and Phase 11's demo free-only filter can consume `GET /api/models[?free_only=true]` from this one cache — frontend reads here only, never OpenRouter directly.
- Prod note (inherited from plan 12-02): migration 030 (`model_cache`) must be applied to prod (`.env.prod`) at deploy. Optionally run `ENV_FILE=.env.prod python -m scripts.seed_model_cache` post-deploy to warm prod; the first-request populate otherwise fills it on the first read.
- No blockers introduced.

## Threat Flags

None — no new security surface beyond the plan's `<threat_model>`. The single new endpoint (`GET /api/models`) is auth-gated, serves only the non-secret public catalog, and the `free_only` param is typed-bool (covered by T-12-V5-03/V5-04/V4-03 in the plan).

## Self-Check: PASSED

- FOUND: backend/routers/models.py
- FOUND: backend/scripts/seed_model_cache.py
- FOUND: backend/tests/test_models_api.py
- FOUND: backend/models/schemas.py (ModelResponse) + backend/main.py (models.router)
- FOUND: commit 8266dde (test RED), 73861ae (feat GREEN), f30d993 (chore seed), 21a2e0c (docs deferred)
- Tests: 13 green (3 route + 10 catalog); full offline suite 189 passed, no regressions

---
*Phase: 12-model-cache-catalog*
*Completed: 2026-06-23*
