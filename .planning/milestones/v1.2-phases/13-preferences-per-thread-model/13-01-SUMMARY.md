---
phase: 13-preferences-per-thread-model
plan: 01
subsystem: database
tags: [supabase, postgres, rls, pydantic, pytest, migration, preferences, model-pinning, tdd]

# Dependency graph
requires:
  - phase: 11-per-request-resolution
    provides: _resolve_key_and_model three-tier model resolution (body → thread.model → user_preferences.default_model → owner default) that this plan's schema makes real
  - phase: 12-model-cache
    provides: model_cache table the deprecation check reads to detect a deprecated pin
provides:
  - "Migration 20240301000032 — user_preferences table (own-row RLS, non-secret), threads.model nullable column, messages.role CHECK widened to allow 'notice' (authored, NOT applied)"
  - "Pydantic contracts: PreferencesResponse, PreferencesUpdate (theme Literal), ThreadModelUpdate, ThreadResponse.model"
  - "8 Wave 0 RED backend test scaffolds across 4 files (MODEL-05, MODEL-06, PREF-02, SC#4)"
affects: [13-02-apply-migration, 13-03-preferences-and-patch-endpoints, 13-04-deprecation-fallback]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Own-row RLS mirror of user_api_keys but WITHOUT REVOKE SELECT — non-secret tables stay readable by the SQL tool (T-13-03 accept)"
    - "Partial-update Pydantic (both fields default None → endpoint model_dump(exclude_unset=True)) vs explicit-null update (ThreadModelUpdate writes model even when null)"
    - "Interface-first Wave 0: RED tests author the downstream contract before any endpoint/behavior exists"

key-files:
  created:
    - supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql
    - backend/tests/test_preferences_api.py
    - backend/tests/test_thread_model_patch.py
    - backend/tests/test_deprecated_model_fallback.py
  modified:
    - backend/models/schemas.py
    - backend/tests/test_key_model_resolution.py

key-decisions:
  - "user_preferences does NOT REVOKE SELECT (unlike user_api_keys) — preferences are non-secret (T-13-03 accept); own-row RLS is the only isolation"
  - "default_model is a plain TEXT, intentionally NOT a FK to model_cache (D-06) so a deprecated-but-pinned slug persists and the fallback notice can fire"
  - "threads.model added nullable with no DEFAULT and no backfill — existing threads resolve via the default tier (D-05)"
  - "messages_role_check (auto-named by Postgres from migration 000002's inline CHECK) is DROP+re-ADD with an explicit allowlist ('user','assistant','notice')"
  - "PreferencesUpdate.theme is a Literal['light','dark'] (422 before paint, T-13-01); ThreadModelUpdate.model null is an explicit clear-to-default, not exclude_unset"

patterns-established:
  - "Non-secret own-row RLS table: mirror user_api_keys policies, omit the REVOKE"
  - "Partial vs explicit-null request models: exclude_unset for PUT preferences, explicit write for PATCH thread model"

requirements-completed: [MODEL-05, MODEL-06, PREF-02]

# Metrics
duration: 5min
completed: 2026-06-24
---

# Phase 13 Plan 01: Preferences + Per-Thread Model Contracts Summary

**One additive migration (user_preferences own-row RLS table + nullable threads.model + 'notice'-widened messages.role CHECK), three Pydantic contracts, and 8 RED Wave 0 backend tests that downstream Plans 03/04 turn green.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-24T23:13:45Z
- **Completed:** 2026-06-24T23:18:56Z
- **Tasks:** 3
- **Files modified:** 6 (4 created, 2 modified)

## Accomplishments
- Authored migration `20240301000032` — `user_preferences` (own-row RLS, no REVOKE), `threads.model` nullable column, and `messages_role_check` widened to allow `'notice'`. File only; Plan 13-02 owns the `db push`.
- Added Pydantic `PreferencesResponse` / `PreferencesUpdate` (theme `Literal['light','dark']`) / `ThreadModelUpdate`, and exposed `model: str | None` on `ThreadResponse` (inherited by `ThreadWithMessages`).
- Created 4 backend test files carrying the 8 named cases from 13-VALIDATION.md — all RED as expected for Wave 0, while the full suite (205 tests) still collects clean and the existing resolution suite stays green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Combined additive migration** - `eb29d07` (feat)
2. **Task 2: Pydantic schemas + ThreadResponse.model** - `db3e658` (feat) — TDD: RED (import fails) → GREEN (verify passes); no refactor needed
3. **Task 3: Wave 0 RED test scaffolds** - `df052d4` (test)

**Plan metadata:** (this commit) (docs: complete plan)

## Files Created/Modified
- `supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql` - user_preferences table + 4 own-row policies, threads.model column, messages.role CHECK widened to 'notice'
- `backend/models/schemas.py` - PreferencesResponse / PreferencesUpdate / ThreadModelUpdate + ThreadResponse.model field
- `backend/tests/test_preferences_api.py` - PUT/GET default_model, new-user defaults, theme persist + JWT-bound user_id (IDOR mitigation)
- `backend/tests/test_thread_model_patch.py` - PATCH set / null-clear / 404-non-owned (ownership re-check)
- `backend/tests/test_deprecated_model_fallback.py` - notice insert + fallback model + notice excluded from LLM history
- `backend/tests/test_key_model_resolution.py` - added test_thread_model_wins_when_set (per-thread pin wins, no regression)

## Decisions Made
- Mirrored the `user_api_keys` own-row RLS policy set on `user_preferences` but deliberately omitted the `REVOKE SELECT` — preferences carry no key material (T-13-03 accept), so the SQL tool read path is intentionally left open. Rationale documented inline in the migration.
- `default_model` kept as a plain TEXT (no FK to `model_cache`, D-06) so a deprecated-but-pinned slug survives in the DB and the at-send deprecation-fallback notice (Plan 04) can fire instead of a FK error.
- `messages.role` CHECK widened by DROP + re-ADD on the Postgres-auto-named `messages_role_check` constraint (the inline unnamed CHECK from migration 000002), confirming RESEARCH Assumption A1.

## Deviations from Plan

None - plan executed exactly as written. Three tasks, six files, all acceptance criteria met without auto-fixes.

## Issues Encountered
None. The `Glob` tool initially returned no migration files (path resolution quirk on the workspace root); resolved by listing the migrations directory directly to confirm the latest existing migration was `...000031`, validating the `...000032` choice.

## Wave 0 RED Baseline (expected)

The 8 new cases are RED by design — endpoints/behavior land in Plans 03/04. Recorded baseline:

```
FAILED tests/test_preferences_api.py::test_put_then_get_default_model    - ModuleNotFoundError: routers.preferences
FAILED tests/test_preferences_api.py::test_get_defaults_for_new_user     - ModuleNotFoundError: routers.preferences
FAILED tests/test_preferences_api.py::test_theme_persist_and_validate    - ModuleNotFoundError: routers.preferences
FAILED tests/test_thread_model_patch.py::test_patch_sets_model           - no PATCH route (non-200)
FAILED tests/test_thread_model_patch.py::test_patch_null_clears          - no PATCH route (non-200)
FAILED tests/test_thread_model_patch.py::test_patch_404_non_owned        - no PATCH route (non-200)
FAILED tests/test_deprecated_model_fallback.py::test_inserts_notice_and_falls_back  - notice row not inserted
FAILED tests/test_deprecated_model_fallback.py::test_notice_excluded_from_history   - 'notice' leaks into LLM history (current map includes all roles)
8 failed in 3.59s
```

`test_key_model_resolution.py` — **7 passed** (6 existing + new `test_thread_model_wins_when_set`); no regression. Full backend suite: **205 tests collected, no collection errors.**

## Verification Results
- Task 1 token check returned **4/4** (CREATE TABLE user_preferences, ADD COLUMN model, notice role CHECK, theme CHECK).
- Task 2 schema verify: `model` in `ThreadResponse.model_fields` (True), `PreferencesUpdate(theme="purple")` → ValidationError (literal_ok), `PreferencesUpdate(theme="dark").model_dump(exclude_unset=True) == {"theme":"dark"}`, `ThreadModelUpdate(model=None)` valid.
- Task 3 collect-only verify returned **8/8** named cases.

## TDD Gate Compliance
Task 2 (`tdd="true"`): RED gate confirmed (`ImportError` before implementation) → GREEN gate confirmed (verify command passes after edit). REFACTOR skipped — schemas are minimal. Per-plan TDD was a single feature; no separate `test(...)` commit was warranted because Task 2's verify is an inline import/validation assertion (the dedicated test files belong to Task 3, committed as `test(13-01)` `df052d4`).

## User Setup Required
None - no external service configuration required. Plan 13-02 (next wave, human-action) applies this migration via `supabase db push`.

## Next Phase Readiness
- Migration file ready for Plan 13-02 to apply (`db push`) — additive-only, single transaction, idempotent in intent.
- Schemas + 8 RED tests are the locked contract for Plan 13-03 (preferences GET/PUT + threads PATCH) and Plan 13-04 (deprecation fallback + notice). Each downstream plan implements against the named cases and flips them green.
- No blockers. Nothing applied to any database.

## Self-Check: PASSED

All 5 created files present; all 3 task commits (eb29d07, db3e658, df052d4) found in git log.

---
*Phase: 13-preferences-per-thread-model*
*Completed: 2026-06-24*
