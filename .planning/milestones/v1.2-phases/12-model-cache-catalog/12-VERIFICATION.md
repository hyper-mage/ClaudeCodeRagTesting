---
phase: 12-model-cache-catalog
verified: 2026-06-23T16:40:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "GET /api/models serves a catalog that is never empty / survives Fly suspend (D-05) — CR-01 closed by design (name coalesce + migration 031 + empty-catalog guard + constraint-aware regression test)"
  gaps_remaining: []
  regressions: []
gaps: []
human_verification: []
---

# Phase 12: Model Cache + Catalog Verification Report

**Phase Goal:** Users can browse a searchable, current catalog of OpenRouter models with free/paid tags, curated popularity marking, and context-length/price hints — served from a Supabase-backed cache that refreshes lazily and survives Fly suspend.
**Verified:** 2026-06-23T16:40:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 12-04 executed and merged: CR-01 / truth #5 fix)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /api/models` serves the full catalog from `model_cache`, frontend reads only via backend (SC#1, MODEL-01) | ✓ VERIFIED (regression check) | `routers/models.py` is a thin seam composing `refresh_if_stale` + `build_model_response`; `response_model=list[ModelResponse]`; wired in `main.py`. `fetch_catalog` is backend-only (no auth header, no frontend OpenRouter call). Unchanged since initial verification; route tests green. |
| 2 | Each model correctly tagged free/paid from defensively-parsed string pricing + shows context-length + per-Mtok hints (SC#2, MODEL-02/07) | ✓ VERIFIED (regression check) | `tag_is_free` uses guarded `.get()` + verified rule (`:free` OR `prompt=="0" AND completion=="0"`); `price_per_mtok` never blind-`float()`s (`-1`/missing/non-str → None); `context_length` null-safe. Unit tests green (32 passed). |
| 3 | Popular models marked from a curated config allowlist; degrades gracefully when absent (SC#3, MODEL-03) | ✓ VERIFIED (regression check) | `POPULAR_MODELS` (config.py:60-71, 10 slugs) → `popularity_for` returns index else `(None,"curated")`. No crash on absent id. Unchanged since initial verification. |
| 4 | A newly added model appears after TTL lapses via lazy refresh-if-stale on read; catalog persists across cold starts (SC#4, MODEL-04) | ✓ VERIFIED (regression check) | `refresh_if_stale` is read-triggered (no scheduler); `_is_stale` treats empty + age>TTL + unparseable-ts as stale; serves stale unchanged on fetch failure. TTL now `Field(default=86400, ge=0)` (bounded, WR-04). Persistence is Postgres (`model_cache`), not process memory. |
| 5 | The catalog is **never empty** on first request / survives Fly suspend (D-05, part of SC#1 + goal "current catalog") | ✓ VERIFIED | **CR-01 closed BY DESIGN.** `_to_cache_row` now coalesces `name → model_id` (`model_catalog_service.py:197` — no bare `model.get("name")` write); corrective migration `031` relaxes `name` to nullable (single `ALTER COLUMN ... DROP NOT NULL`, RLS untouched); `refresh_if_stale` has an `if not cache_rows:` empty-catalog guard before the upsert (line 235) + honest distinct warnings (WR-01/WR-02); a constraint-aware regression test (`test_nameless_model_coalesces_to_model_id`) drives a REAL upsert→re-select with a nameless model against a stub that rejects null names (live pre-031 posture) and asserts it persists with `name == model_id`. Seed `main()` is try/except-wrapped with a POSIX exit code (IN-01). Never-empty no longer rests on luck of upstream data. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/services/model_catalog_service.py` | name coalesce + empty-catalog guard + honest fail-path warnings | ✓ VERIFIED | 254 lines. `_to_cache_row` line 197: `"name": model.get("name") or str(model.get("id") or "")`. `refresh_if_stale` line 235: `if not cache_rows:` guard → distinct empty-catalog warning + `return rows` (no blind `upsert([])`); except branch distinguishes cold-empty failure (line 246-250) from serve-stale (line 252). No-auth-header `fetch_catalog`. No debt markers. |
| `supabase/migrations/20240301000031_allow_null_model_cache_name.sql` | Corrective migration: name → nullable, RLS-preserved | ✓ VERIFIED | Single `ALTER TABLE model_cache ALTER COLUMN name DROP NOT NULL;` (line 29). Grep confirms ZERO `CREATE POLICY`/`DROP POLICY`/`FOR INSERT|UPDATE|DELETE`. Next free number after 030. Applied live to dev per SUMMARY (db push --linked + cleaned-up NULL probe). |
| `backend/scripts/seed_model_cache.py` | Non-crashing seed (IN-01) | ✓ VERIFIED | `main()` body wrapped in try/except (lines 54-77), logs with `exc_info=True`, returns POSIX exit code (0 success/no-op, 1 failure); `sys.exit(main())` at line 81. Reuses `_to_cache_row` (inherits the coalesce). |
| `backend/config.py` | Bounded TTL (WR-04) + POPULAR_MODELS | ✓ VERIFIED | `from pydantic import Field` (line 1); `model_cache_ttl_seconds: int = Field(default=86400, ge=0)` (line 51); `POPULAR_MODELS` 10 slugs (lines 60-71). |
| `backend/tests/fixtures/openrouter_models_sample.json` | 5 rows incl. a nameless edge row | ✓ VERIFIED | 5 `data` rows; the 5th (`vendor/nameless-edge`, lines 43-51) has `id`+`pricing`+`context_length` but NO `name` key — surfaces CR-01 offline. |
| `backend/tests/test_model_catalog.py` | CR-01 regression + empty-catalog guard + WR-05 + WR-04 | ✓ VERIFIED | `_constraint_aware_stub_db` raises on null/empty name (live pre-031 posture). `test_nameless_model_coalesces_to_model_id` drives the REAL upsert→re-select and asserts `name == "vendor/nameless-edge"` (its model_id). Plus empty-catalog-guard, empty-and-failed-distinct-warning, no-auth-header, negative-TTL tests. |
| `backend/tests/test_models_api.py` | WR-03 upsert assertion | ✓ VERIFIED | `test_first_request_populate` (lines 160-168) now asserts `upsert.assert_called_once()`, inspects the payload, and requires `fixture_ids <= upserted_ids` — a regression skipping the upsert/re-select path FAILS. |
| `backend/routers/models.py` | GET /api/models[?free_only] router | ✓ VERIFIED (regression check) | Thin seam; typed-bool `free_only` server-side filter; auth-gated; composes `refresh_if_stale` + `build_model_response`. |
| `backend/models/schemas.py` | ModelResponse | ✓ VERIFIED (regression check) | `name: str | None = None` — now in lockstep with the relaxed DB column. |
| `supabase/migrations/20240301000030_create_model_cache.sql` | model_cache table + permissive SELECT RLS | ✓ VERIFIED (regression check) | Unchanged. ENABLE RLS + one `USING (true)` SELECT + zero write policy. The `name TEXT NOT NULL` it declared is now corrected by 031 (shipped as a new migration since 030 is already applied). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `model_catalog_service.py (_to_cache_row)` | `model_cache.name` column | name coalesced to model_id + column relaxed to nullable | ✓ WIRED | `grep 'model.get("name") or'` matches line 197; migration 031 `DROP NOT NULL` matches. Lockstep confirmed. |
| `model_catalog_service.py (refresh_if_stale)` | never-empty guarantee (D-05) | empty-catalog guard before blind upsert | ✓ WIRED | `if not cache_rows:` at line 235 returns `rows` with a distinct warning; except branch honest about cold-empty (line 246). |
| `migration 031` | dev Supabase Postgres | `supabase db push --linked` (BLOCKING) | ✓ WIRED | SUMMARY records live apply + a cleaned-up service-role `name=None` upsert probe ("live dev model_cache.name accepts NULL"). Not independently re-probed here (would mutate live state); the regression test + migration shape are the by-design proof. |
| `routers/models.py` | `refresh_if_stale + build_model_response` | router composes pure fns | ✓ WIRED | Imported line 29, called lines 49-50. |
| `seed_model_cache.py` | `model_cache` write path | reuses `_to_cache_row` | ✓ WIRED | Inherits the coalesce; `main()` try/except + `sys.exit(main())`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `routers/models.py` (GET /api/models) | `rows` / `models` | `refresh_if_stale(db)` → `model_cache` ← live OpenRouter fetch (via `_to_cache_row` coalesce) | ✓ Yes (initial verification: live 0→338; offline: 32 tests incl. nameless-row populate) | ✓ FLOWING — a nameless upstream row now degrades to `name=model_id` instead of nuking the batch, so the never-empty path is robust by design. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase-12 test subset (mandated invocation) | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 venv/Scripts/python.exe -m pytest -p pytest_asyncio tests/test_model_catalog.py tests/test_models_api.py tests/test_config.py -q` | 32 passed, 2 warnings, 1.43s | ✓ PASS |
| Name coalesce present | `grep 'model.get("name") or' model_catalog_service.py` | match at line 197 | ✓ PASS |
| Empty-catalog guard present | `grep 'if not cache_rows' model_catalog_service.py` | match at line 235 | ✓ PASS |
| Migration 031 shape (RLS-preserved) | grep for CREATE/DROP POLICY + FOR INSERT/UPDATE/DELETE | zero matches; single ALTER COLUMN DROP NOT NULL | ✓ PASS |
| Seed try/except + exit code | read `seed_model_cache.py` main() | try/except + `return 1` on failure + `sys.exit(main())` | ✓ PASS |
| TTL bounded | `grep Field(default=86400, ge=0)` config.py | match at line 51 + `from pydantic import Field` line 1 | ✓ PASS |
| Fixture nameless row | read fixture | 5 rows; `vendor/nameless-edge` has no `name` key | ✓ PASS |
| No debt markers in phase-12 files | grep TBD/FIXME/XXX/HACK across modified files | zero matches | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared or implied for this phase (pytest-based validation per 12-VALIDATION.md). The mandated pytest selection was run in-process — 32 passed. Step 7c: not applicable.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MODEL-01 | 12-02, 12-03, 12-04 | Browse a searchable list of OpenRouter models | ✓ SATISFIED | GET /api/models serves model_cache (backend-only); cold-cache populate now robust by design (CR-01 closed). |
| MODEL-02 | 12-01 | Each model tagged free or paid | ✓ SATISFIED | `tag_is_free` verified matrix; sentinel not free; tests green. |
| MODEL-03 | 12-01 | Popular models marked (curated) | ✓ SATISFIED | POPULAR_MODELS → popularity_rank; absent → None. |
| MODEL-04 | 12-01, 12-03, 12-04 | List auto-refreshes to pick up new models | ✓ SATISFIED | Lazy refresh-if-stale on read, bounded 24h TTL (ge=0), serve-stale-on-failure; persists in Postgres; cold-cache robustness now by design. |
| MODEL-07 | 12-01, 12-03, 12-04 | Context-length + per-Mtok price hints | ✓ SATISFIED | build_model_response surfaces ctx + per-Mtok; null-safe. |

All 5 phase-12 requirement IDs (MODEL-01/02/03/04/07) are claimed across plan frontmatter (12-01: MODEL-02/03/04/07; 12-02: MODEL-01; 12-03 & 12-04: MODEL-01/04/07) and map to Phase 12 in REQUIREMENTS.md. No orphaned requirements (MODEL-05/06 are Phase 13, MODEL-08 is Phase 15 — correctly absent).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (general) | — | No `TODO`/`FIXME`/`XXX`/`HACK`/`TBD` debt markers in any phase-12 modified file | ℹ️ Info | Clean — debt-marker gate passes. |
| `model_catalog_service.py` | 197 | (RESOLVED) prior CR-01 `model.get("name")` no-fallback write | ✓ Fixed | Now coalesces to model_id; no longer a blocker. |
| `model_catalog_service.py` | 235 | (RESOLVED) prior WR-01 blind `upsert([])` | ✓ Fixed | Guarded; no blind empty upsert. |
| `seed_model_cache.py` | 54-77 | (RESOLVED) prior IN-01 no try/except | ✓ Fixed | Wrapped, returns exit code. |
| `config.py` | 51 | (RESOLVED) prior WR-04 unbounded TTL | ✓ Fixed | `Field(ge=0)`. |

All prior anti-patterns from the initial verification are resolved. No new anti-patterns introduced.

### Human Verification Required

None. The closed gap (CR-01 / truth #5) is verifiable programmatically: the by-design proof is the name coalesce + the nullable-relaxing migration shape + the empty-catalog guard + a constraint-aware regression test that drives the real upsert→re-select path. The 32-test phase-12 subset passes. The live dev migration apply + NULL probe are recorded in 12-04-SUMMARY (not re-probed here to avoid mutating live state; the offline constraint-aware test reproduces the live pre-031 posture, so the fix is provable without the live DB). Prod migration 031 apply is a deferred deploy-time ops step (D-03 dual-env), not a dev-phase blocker.

### Gaps Summary

No gaps. The single gap from the initial verification (truth #5 / CR-01 — the "never empty / survives suspend" guarantee held only by luck of present upstream data) is now **closed by design** via plan 12-04:

1. **Defense-in-depth at write:** `_to_cache_row` coalesces a missing/empty upstream `name` to the `model_id` (`model.get("name") or str(model.get("id") or "")`), so a nameless upstream model can never write a NULL name and can never fail the single-statement batch upsert.
2. **Schema lockstep:** corrective migration `031` relaxes `model_cache.name` to nullable (`ALTER COLUMN name DROP NOT NULL`) — a single statement that touches NO RLS policy (grep-confirmed: zero CREATE/DROP POLICY, zero FOR INSERT/UPDATE/DELETE), preserving the inverted permissive-SELECT / service-role-only-write posture from 030.
3. **Honest never-empty fail path:** `refresh_if_stale` guards `if not cache_rows:` before the upsert (no blind `upsert([])`) and logs a distinct empty-catalog warning; the except branch distinguishes a cold-empty-cache failure from genuine serve-stale.
4. **Regression lock:** a constraint-aware test (`_constraint_aware_stub_db` raises on null/empty name, mirroring the live pre-031 DB) drives the REAL upsert→re-select with a nameless fixture row and asserts the model persists with `name == model_id`. This is NOT a mock that ignores the upsert — without the coalesce it fails RED. WR-03 is closed by the route test's new `upsert.assert_called_once()` + payload assertion.
5. **Operational robustness:** the deploy seed `main()` is try/except-wrapped with a POSIX exit code (IN-01), and the TTL is bounded `Field(ge=0)` (WR-04).

The 32-test phase-12 subset (`test_model_catalog` + `test_models_api` + `test_config`) passes green. All 5 success-criteria truths are verified; all 5 requirement IDs are satisfied. Phase goal achieved.

---

_Verified: 2026-06-23T16:40:00Z_
_Verifier: Claude (gsd-verifier)_
