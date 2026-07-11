---
phase: 12-model-cache-catalog
plan: 04
subsystem: backend
tags: [model-cache, openrouter, supabase, migration, rls, regression-test, gap-closure]

# Dependency graph
requires:
  - phase: 12-model-cache-catalog
    provides: "model_cache table (migration 030, live on dev), model_catalog_service, GET /api/models router, seed script (12-01/02/03, merged)"
provides:
  - "Nameless-upstream-model resilience: _to_cache_row coalesces a missing name to the model_id so one partial row can no longer fail the whole batch upsert (CR-01 closed by design, not by luck)"
  - "Corrective migration 031 (model_cache.name nullable) applied LIVE to dev — DB constraint in lockstep with the nullable-defensive write contract"
  - "Honest never-empty fail path: empty-catalog guard before the blind upsert (WR-01) + distinct empty-and-fetch-failed warning (WR-02)"
  - "Non-crashing deploy seed: seed_model_cache.main() returns a POSIX exit code, logs + exits non-zero on failure (IN-01)"
  - "Bounded TTL (Field ge=0, WR-04) + a no-auth-header invariant test locking D-05 (WR-05)"
  - "Constraint-aware CR-01 regression test + WR-03 upsert assertion so the fix cannot silently regress"
affects: [14-usage-cost, 15-options-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth on an untrusted-upstream write: coalesce-at-write (code) + relax-the-constraint (schema), so a partial row degrades gracefully instead of nuking the batch"
    - "Constraint-aware test stub: a MagicMock upsert that mimics the live NOT NULL posture, so the unit test catches what a constraint-free route mock cannot (closes WR-03)"

key-files:
  created:
    - supabase/migrations/20240301000031_allow_null_model_cache_name.sql
  modified:
    - backend/services/model_catalog_service.py
    - backend/scripts/seed_model_cache.py
    - backend/config.py
    - backend/tests/fixtures/openrouter_models_sample.json
    - backend/tests/test_model_catalog.py
    - backend/tests/test_models_api.py

key-decisions:
  - "Dual-layer CR-01 fix per the plan: coalesce name→model_id in _to_cache_row (defense-in-depth, name never NULL in practice) AND a corrective migration 031 relaxing the column to nullable (removes the schema-level contradiction). Both ship together."
  - "Empty-catalog and empty-and-failed paths get DISTINCT honest warnings — a blind upsert([]) is never issued, and a cold-cache fetch failure is logged as 'returning empty' rather than the misleading 'serving stale'."
  - "Migration 031 touches ONLY the name NOT-NULL constraint — zero RLS change (no CREATE/DROP POLICY, no write policy), preserving the inverted permissive-SELECT / service-role-only-write posture from 030 (T-12-V5-02)."
  - "Seed main() returns an int exit code and is wrapped in try/except so a deploy seed failure is a logged non-zero exit, never a bare traceback (IN-01); the first-request populate (D-05) remains the correctness guarantee."

patterns-established:
  - "Coalesce-at-write + relax-the-constraint as paired mitigations for untrusted partial upstream data crossing into a batch upsert"
  - "Constraint-aware unit stub to surface a defect that a constraint-free route mock structurally cannot (WR-03)"

requirements-completed: [MODEL-01, MODEL-04, MODEL-07]

# Metrics
duration: ~25min
completed: 2026-06-23
---

# Phase 12 Plan 04: Gap Closure — Nameless-Model Resilience Summary

**Closed the single confirmed Phase 12 gap (VERIFICATION truth #5 / code-review CR-01): a nameless upstream OpenRouter model can no longer fail the whole batch upsert and strand a cold cache empty — fixed dual-layer with a `name → model_id` coalesce at write AND a corrective migration 031 (applied live to dev) relaxing `model_cache.name` to nullable, plus honest never-empty fail-path warnings, a non-crashing seed, a bounded TTL, and constraint-aware regression tests that lock the fix against silent regression.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-23
- **Completed:** 2026-06-23
- **Tasks:** 3
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- **CR-01 root fix (Task 1):** `_to_cache_row` now writes `"name": model.get("name") or str(model.get("id") or "")` — a missing upstream name coalesces to the model_id, mirroring the existing model_id derivation. One nameless model can no longer NULL its row and fail the single-statement batch upsert (T-12-V5-01).
- **Honest never-empty fail path (Task 1):** `refresh_if_stale` adds an `if not cache_rows:` guard BEFORE the upsert (no more blind `upsert([])` — WR-01) with a distinct "got an empty catalog, serving stale" warning; the `except` branch now distinguishes a cold-cache failure ("failed on an EMPTY cache, returning empty catalog") from genuine serve-stale (WR-02).
- **Non-crashing seed (Task 1, IN-01):** `seed_model_cache.main()` is wrapped in try/except, returns a POSIX exit code (0 success / empty no-op, 1 on failure), logs with `exc_info=True`, and the `__main__` guard now `sys.exit(main())`. A deploy seed failure is visible, never a bare traceback.
- **Bounded TTL (Task 1, WR-04):** `model_cache_ttl_seconds = Field(default=86400, ge=0)` (added `from pydantic import Field`) — a negative TTL now fails Settings validation loudly instead of hammering upstream every read (T-12-V5-04).
- **Fixture + regression tests (Task 1):** added a 5th nameless fixture row (`vendor/nameless-edge`, id present, no `name` key); added a constraint-aware CR-01 regression (`_constraint_aware_stub_db` rejects a null name like the pre-031 live DB), an empty-catalog guard test, an empty-and-failed distinct-warning test, a no-auth-header invariant test (WR-05), a TTL-bound test (WR-04), and a WR-03 upsert assertion in `test_first_request_populate` so a regression that skips the upsert/re-select path FAILS.
- **Corrective migration 031 (Task 2):** `supabase/migrations/20240301000031_allow_null_model_cache_name.sql` — `ALTER TABLE model_cache ALTER COLUMN name DROP NOT NULL`, header mirrors 030's style, zero RLS change (grep gate confirms no CREATE/DROP POLICY, no write policy — T-12-V5-02).
- **Live dev apply + probe (Task 3, BLOCKING):** applied 031 to dev (`ntkkmljbariflblldmha`) via `supabase db push --linked` (dry-run showed a clean history — only 031 pending, no `migration repair` needed). Proved the live column accepts NULL via a service-role upsert of `{"model_id": "zzz/null-name-probe", "name": None, ...}`, asserted persistence, then deleted the probe row (no residual side-effect; confirmed dev target + zero residual).

## Task Commits

Each task was committed atomically:

1. **Task 1: coalesce + empty-catalog/empty-fail guards + seed try/except + TTL bound + fixture + regression tests** — `1374325` (fix)
2. **Task 2: corrective migration 031 — relax model_cache.name to nullable** — `096acc8` (feat)
3. **Task 3: [BLOCKING] apply migration 031 to dev Supabase + live NULL probe** — no file commit (live `db push` + cleaned-up probe only; the migration file was committed in Task 2). Mirrors how 12-02 handled its BLOCKING apply task.

## Files Created/Modified

- `supabase/migrations/20240301000031_allow_null_model_cache_name.sql` (created) — corrective migration relaxing `name` to nullable; RLS untouched.
- `backend/services/model_catalog_service.py` — `_to_cache_row` name coalesce; `refresh_if_stale` empty-catalog guard + distinct empty-and-failed warning.
- `backend/scripts/seed_model_cache.py` — `main()` wrapped in try/except, returns an exit code; `sys.exit(main())`.
- `backend/config.py` — `from pydantic import Field`; `model_cache_ttl_seconds = Field(default=86400, ge=0)`.
- `backend/tests/fixtures/openrouter_models_sample.json` — added the nameless 5th row.
- `backend/tests/test_model_catalog.py` — CR-01 regression, empty-catalog guard, empty-and-failed warning, no-auth-header invariant, TTL-bound tests + the `_constraint_aware_stub_db` harness.
- `backend/tests/test_models_api.py` — WR-03 upsert assertion in `test_first_request_populate`.

## Decisions Made

- **Dual-layer fix, both shipped:** the plan called for coalesce (code) AND nullable column (schema). The coalesce keeps `name` non-null in practice; the migration removes the schema contradiction so a NULL can never trip the batch upsert even if the coalesce were ever bypassed. Defense-in-depth, not redundancy.
- **Migration 031 is RLS-silent:** scoped to a single `ALTER COLUMN ... DROP NOT NULL`; the inverted RLS posture from 030 (permissive SELECT, zero write policy) is left entirely untouched (T-12-V5-02 mitigation).
- **Constraint-aware test stub for WR-03:** the route test's mock DB enforces no constraint, so it cannot surface CR-01. A dedicated `_constraint_aware_stub_db` whose upsert raises on a null/empty name reproduces the live pre-031 posture, making the regression meaningful at the unit level.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were required and no Rule 4 architectural decision arose. The dry-run showed a clean dev migration history, so the project-memory `migration repair` caveat did not need to be exercised (same as 12-02).

## Authentication / Live-Op Notes

- The live `supabase db push --linked` and the service-role NULL probe both ran against dev (`ntkkmljbariflblldmha`). The supabase CLI used a stored session (no `SUPABASE_ACCESS_TOKEN` needed in env). No auth gate blocked execution.
- **Worktree `.env` constraint (handled):** config.py loads `.env` relative to the backend dir; the worktree has no `.env` (gitignored, not part of the worktree), so the live probe was run from the MAIN repo's `backend/` (where the dev `.env` lives), identical to how 12-02 ran its live apply from the linked main repo. The `db push` link state also lives in the main repo (`supabase/.temp/project-ref`). A temporary copy of migration 031 was placed in the main repo solely to run `db push`, then removed — the canonical committed copy lives on this worktree branch and reaches main on merge.

## Ops Note — Prod Deploy (deferred, D-03 dual-env discipline)

Prod is NOT pushed in this plan. At deploy time, apply migration 031 to the prod Supabase project (`ybehhhduhynsdujmxdzx` / boardgame-rag-prod) by targeting `.env.prod` (NOT `.env`). Per project memory [Supabase migration history repair], if `db push` tries to replay old migrations or errors "already exists", run `supabase migration repair --status applied <prior 001-030 range>` against prod first, then re-push. Prod already has migrations 025-028 + 030 applied per memory; confirm 030 is present before 031 so the column exists to relax.

## Verification Evidence

- Task 1: `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 venv/Scripts/python.exe -m pytest -p pytest_asyncio tests/test_model_catalog.py tests/test_models_api.py tests/test_config.py -q` → **32 passed** (run from the worktree backend against the worktree source).
- Task 1 grep gates: coalesce, `if not cache_rows`, seed try/except, `from pydantic import Field` + `Field(default=86400, ge=0)`, and the 5-row fixture-with-nameless-row assertion all pass.
- Task 2: migration shape verify echoes "corrective migration shape OK (relaxes name, no RLS change)".
- Task 3 (BLOCKING): live probe printed "live dev model_cache.name accepts NULL; probe row cleaned up"; a follow-up check confirmed the dev project ref + zero probe residual.

## Threat Mitigations Confirmed

- **T-12-V5-01 (DoS — nameless model nukes the batch):** mitigated by the coalesce + nullable column; verified by the CR-01 regression + the live-NULL probe.
- **T-12-V5-02 (Tampering — RLS weakening via the column migration):** mitigated — 031 changes no policy; the Task 2 grep gate forbids any policy clause; the live probe writes via the service-role client only.
- **T-12-V5-03 (Spoofing/Info-disclosure — auth coupling on fetch):** mitigated by the WR-05 no-auth-header invariant test.
- **T-12-V5-04 (DoS — negative TTL):** mitigated by `Field(ge=0)` failing loudly at Settings init (WR-04 test).

## Next Phase Readiness

- VERIFICATION truth #5 / CR-01 is closed by design: a nameless upstream model degrades gracefully (name → model_id) and the live dev column accepts NULL. The never-empty guarantee no longer rests on the luck of present upstream data.
- No blockers introduced. Prod apply tracked as the ops note above for the deploy step.

## Known Stubs

None — no stub/placeholder patterns were introduced. All changes are real code with live verification.

## Self-Check: PASSED

- FOUND: `supabase/migrations/20240301000031_allow_null_model_cache_name.sql`
- FOUND: `backend/services/model_catalog_service.py` (coalesce + guard)
- FOUND: `backend/scripts/seed_model_cache.py` (try/except)
- FOUND: `backend/config.py` (Field ge=0)
- FOUND: `backend/tests/fixtures/openrouter_models_sample.json` (5 rows, nameless present)
- FOUND: `backend/tests/test_model_catalog.py` + `backend/tests/test_models_api.py` (regression + WR-03)
- FOUND: `.planning/phases/12-model-cache-catalog/12-04-SUMMARY.md`
- FOUND: commit `1374325` (Task 1 — fix)
- FOUND: commit `096acc8` (Task 2 — migration 031)
- Live verification: migration 031 applied to dev; service-role `name=None` upsert succeeded and the probe row was cleaned up (no residual)

---
*Phase: 12-model-cache-catalog*
*Completed: 2026-06-23*
