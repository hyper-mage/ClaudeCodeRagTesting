---
phase: 12-model-cache-catalog
plan: 01
subsystem: api
tags: [openrouter, model-catalog, pricing, httpx, pydantic-settings, supabase, pytest, tdd]

# Dependency graph
requires:
  - phase: 06-context-budget
    provides: budget_service.fetch_model_context_length httpx GET pattern (timeout + raise_for_status + swallow-on-failure) that fetch_catalog generalizes
provides:
  - "model_catalog_service.py: pure tag_is_free / price_per_mtok / popularity_for / build_model_response + fetch_catalog (public, no-auth) + refresh_if_stale orchestration"
  - "config.POPULAR_MODELS: ordered curated slug list (10 live ids) for popularity_rank"
  - "config.model_cache_ttl_seconds: injectable 24h TTL (env MODEL_CACHE_TTL_SECONDS)"
  - "Offline OpenRouter fixture (openrouter_models_sample.json) + 10 catalog unit tests + 2 config TTL tests"
affects: [12-02-model-cache-table-and-route, 12-03, model picker (Phase 15), demo free-only filter]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defensive upstream parse: guarded float() in a single helper, .get() for every field, -1 sentinel → None, never crash on a hostile model row (D-11, T-12-V5-01)"
    - "Lazy refresh-if-stale on read: empty-or-aged cache is stale, upsert keyed on model_id (never delete-all), serve stale on fetch failure (D-03/D-04/D-05, Pitfall 5)"
    - "Injectable TTL via get_settings() read at call time so unit tests monkeypatch instead of time-traveling (no freezegun/respx dep)"
    - "Curated popularity as a versioned code-reviewed config constant matched at serve time; absent id → rank None (D-06/D-08/D-09)"

key-files:
  created:
    - backend/services/model_catalog_service.py
    - backend/tests/test_model_catalog.py
    - backend/tests/fixtures/openrouter_models_sample.json
  modified:
    - backend/config.py
    - backend/tests/test_config.py

key-decisions:
  - "Public catalog fetch sends NO Authorization header — decouples the catalog from owner-key availability (the never-empty guarantee, D-05) and matches the verified public-endpoint behavior"
  - "Advisory-lock herd control intentionally omitted: model_id-keyed upsert is idempotent, so a rare concurrent double-fetch is wasteful not incorrect (RESEARCH A2)"
  - "is_free precomputed into the cache row (enables a future SQL-side ?free_only filter, D-02); per-Mtok hints computed at serve time in build_model_response"
  - "POPULAR_MODELS finalized against the LIVE OpenRouter catalog at build time (2026-06-23); claude-3.7-sonnet / gemini-2.0-flash-001 from the RESEARCH skeleton were stale and replaced with confirmed-live slugs"

patterns-established:
  - "build_model_response accepts either a raw OpenRouter object (id/pricing/context_length) or a cached model_cache row (model_id/...) — id resolved from whichever is present"
  - "_parse_ts normalizes Postgres trailing-Z timestamps to +00:00 for Python 3.10 fromisoformat; unparseable/absent fetched_at fails toward stale (freshness)"

requirements-completed: [MODEL-02, MODEL-03, MODEL-04, MODEL-07]

# Metrics
duration: ~15min
completed: 2026-06-23
---

# Phase 12 Plan 01: Model Cache Catalog Core Logic Summary

**Defensive OpenRouter free/paid tagging, guarded per-Mtok price math, curated popularity tagging, and a lazy refresh-if-stale orchestration — all pure/unit-tested offline against a real-shape fixture, plus POPULAR_MODELS and a 24h model_cache_ttl_seconds config.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 (TDD: RED test commit → GREEN feat commit)
- **Files created:** 3
- **Files modified:** 2
- **Tests:** 12 (10 catalog + 2 config) — all green; 54 green across config/catalog/budget with no regressions

## Accomplishments
- `price_per_mtok` defensive parse: `"0.00000015"` → `0.15`, `"0.0000006"` → `0.60`; returns `None` for the `-1` sentinel, missing keys, `None`, and non-numeric/non-str input — never raises (D-11, MODEL-07)
- `tag_is_free` implements the verified matrix: `:free` suffix OR `prompt=="0" AND completion=="0"`; `openrouter/auto` (`-1`) correctly NOT free; missing `pricing` key returns False without KeyError (MODEL-02)
- `popularity_for` returns `(index, "curated")` from `POPULAR_MODELS` or `(None, "curated")` when absent — forward-compatible shape, graceful degradation (MODEL-03, D-06/D-08/D-09)
- `refresh_if_stale(db)` treats empty cache and TTL-lapsed cache as stale, fetches the FULL catalog (no subset), upserts keyed on `model_id` (never delete-all), and serves the existing stale rows unchanged when the upstream fetch raises (MODEL-04, D-01/D-03/D-04/D-05)
- `fetch_catalog` sends no Authorization header and never logs the response body; `build_model_response` composes `is_free` + per-Mtok hints + null-safe `context_length` + popularity while retaining raw pricing (D-10)
- `config.model_cache_ttl_seconds` (86400, env-overridable) + `POPULAR_MODELS` (10 confirmed-live slugs)

## Task Commits

Each task was committed atomically (TDD plan):

1. **Task 1: Wave 0 — offline fixture + RED unit-test scaffolds** - `badcc23` (test) — fixture + test_model_catalog.py (10 node IDs) + test_config.py TTL tests; RED (`ModuleNotFoundError: services.model_catalog_service`)
2. **Task 2: config POPULAR_MODELS/TTL + model_catalog_service pure fns + fetch + refresh-if-stale** - `e5a696f` (feat) — all 12 tests GREEN

_TDD gate sequence satisfied: test (RED) → feat (GREEN). No refactor commit needed (implementation was clean on first GREEN)._

## Files Created/Modified
- `backend/services/model_catalog_service.py` - fetch_catalog (public, no-auth) + price_per_mtok/tag_is_free/popularity_for/build_model_response pure fns + refresh_if_stale orchestration
- `backend/tests/test_model_catalog.py` - 10 unit tests (tagging, Mtok, popularity, context null-safe, refresh stale/within-TTL/serve-stale-on-failure)
- `backend/tests/fixtures/openrouter_models_sample.json` - 4 real-shape edge rows: gpt-4o-mini, a `:free` model, openrouter/auto `-1` sentinel, a missing-pricing/missing-context edge
- `backend/config.py` - added model_cache_ttl_seconds (86400) + POPULAR_MODELS ordered list
- `backend/tests/test_config.py` - added model_cache_ttl_seconds default + env-override tests

## Decisions Made
- **No auth header on the catalog fetch** — the endpoint is public; coupling to an owner key would break the never-empty guarantee (D-05). Verified live: HTTP 200 with no header.
- **No advisory lock** — idempotent model_id-keyed upsert makes a rare concurrent double-fetch merely wasteful (RESEARCH A2); kept minimum surface.
- **POPULAR_MODELS refreshed against live ids** — `anthropic/claude-3.7-sonnet` and `google/gemini-2.0-flash-001` from the RESEARCH skeleton are NOT in the current live catalog; replaced with confirmed-live slugs (claude-sonnet-4.5, gpt-5.1, gemini-2.5-pro, etc.). A stale slug self-heals to `popularity_rank None` per D-09, so this is forward-safe.

## Deviations from Plan

None - plan executed exactly as written. The curated `POPULAR_MODELS` slugs were finalized against the live catalog at build time, which is the explicitly planned executor responsibility (Task 2 action + Assumption A5), not a deviation.

## Issues Encountered
- The global Python 3.10.5 interpreter has a broken auto-loaded `dash.testing.plugin` pytest plugin that crashes collection with an INTERNALERROR. Resolved by running the project's `backend/venv` interpreter with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -p pytest_asyncio` (the worktree has no venv of its own; the main checkout venv carries the project deps). This is a local-environment quirk, not a code issue — the tests themselves are clean.

## User Setup Required
None - no external service configuration required. (The `MODEL_CACHE_TTL_SECONDS` env var is optional; it defaults to 86400.)

## Next Phase Readiness
- Plan 12-02 can build the `model_cache` migration + `GET /api/models` router on top of `refresh_if_stale` and `build_model_response`. `refresh_if_stale` already calls `db.table("model_cache").select("*")` / `.upsert(..., on_conflict="model_id")`, so the table needs PK `model_id` and columns `name, context_length, pricing, is_free, raw, fetched_at`.
- The route layer (`test_models_api.py`, MODEL-01/D-02/D-05) is a separate Wave-0 file not in this plan's scope — owned by a later plan in the phase.

## Self-Check: PASSED

---
*Phase: 12-model-cache-catalog*
*Completed: 2026-06-23*
