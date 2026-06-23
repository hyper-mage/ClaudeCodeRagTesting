---
phase: 12-model-cache-catalog
plan: 02
subsystem: database
tags: [supabase, postgres, migration, rls, model-cache, openrouter, jsonb]

# Dependency graph
requires:
  - phase: 09-crypto-encrypted-key-storage
    provides: "migration 025 user_api_keys own-row RLS pattern (mirrored-and-inverted here)"
provides:
  - "model_cache table (model_id PK, name, context_length, pricing JSONB, is_free, raw JSONB, fetched_at) live on dev Supabase"
  - "Inverted RLS posture: permissive SELECT USING (true) + zero client write policies -> service-role-only writes"
  - "Persistence layer for GET /api/models that survives Fly suspend / cold starts (data in Postgres, not process memory)"
affects: [12-03-model-route-seed, 12-04-config-refresh, 14-usage-cost, 15-options-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Global shared catalog RLS: permissive SELECT USING (true) + no write policy = service-role-only writes (inverse of own-row secret pattern)"
    - "Row-per-model cache shape with shared fetched_at staleness marker"

key-files:
  created:
    - supabase/migrations/20240301000030_create_model_cache.sql
  modified: []

key-decisions:
  - "model_cache RLS is the INVERSE of user_api_keys: GLOBAL non-secret -> permissive SELECT USING (true), NO INSERT/UPDATE/DELETE policy (RLS denies client writes by default), service-role owns all writes (T-12-V4-01)"
  - "Row-per-model (PK = model_id) over single JSON-blob row: enables SQL-side ?free_only filtering, indexing, and race-free per-model upsert"
  - "is_free precomputed at write (Open Q1) to enable SQL-side free_only filtering"
  - "context_length nullable-defensive (Pitfall 4 — OpenRouter docs allow null)"
  - "Raw OpenRouter pricing strings retained verbatim in pricing JSONB (D-10) plus optional raw JSONB for future fields"
  - "Migration applied LIVE to dev (ntkkmljbariflblldmha) — clean history, no repair needed; prod deferred to deploy (D-03)"

patterns-established:
  - "Inverted-RLS global catalog: ENABLE RLS + one permissive SELECT + zero write policies = read-for-all, write-for-service-role-only"
  - "BLOCKING live migration push when build/type checks would otherwise pass as a false positive"

requirements-completed: [MODEL-01]

# Metrics
duration: ~12min
completed: 2026-06-23
---

# Phase 12 Plan 02: Model Cache Table + Inverted RLS Summary

**Created Supabase migration 030 (`model_cache`: row-per-model catalog with raw pricing JSONB + shared `fetched_at` staleness marker and an inverted permissive-SELECT / service-role-only-write RLS posture) and applied it LIVE to the dev project so the table physically exists before plan 12-03's route tests.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-23
- **Completed:** 2026-06-23
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments
- New migration `20240301000030_create_model_cache.sql`: `model_cache` table with `model_id TEXT PRIMARY KEY`, `name`, nullable-defensive `context_length`, raw `pricing JSONB` (D-10), precomputed `is_free`, optional `raw JSONB`, and `fetched_at TIMESTAMPTZ` staleness marker.
- Inverted RLS posture vs the own-row `user_api_keys` (migration 025): RLS enabled, ONE permissive SELECT policy `USING (true)`, and ZERO client write policies — RLS denies all `authenticated` writes by default while the service-role backend bypasses RLS and owns writes (mitigates T-12-V4-01).
- Migration applied LIVE to the dev Supabase project (`ntkkmljbariflblldmha`) via `supabase db push --linked`; service-role probe confirms `model_cache` is reachable (count = 0, no relation-does-not-exist error) — closing the false-positive-verification gap before plan 12-03.

## Task Commits

Each task was committed atomically:

1. **Task 1: migration 030 — model_cache table + inverted RLS** - `3f90e6d` (feat)
2. **Task 2: [BLOCKING] apply migration 030 to dev Supabase** - no file commit (live `db push` only; the migration file was committed in Task 1, the apply produced no new files)

## Files Created/Modified
- `supabase/migrations/20240301000030_create_model_cache.sql` - Creates the global `model_cache` catalog table with inverted (global-read, service-role-write) RLS.

## Decisions Made
- **Inverted RLS over own-row:** model_cache is global and non-secret, so it gets `USING (true)` SELECT and no write policy — the mirror image of `user_api_keys` which is own-row + REVOKE SELECT because it holds secrets.
- **Row-per-model over JSON-blob row:** enables SQL-side `?free_only` filtering, per-model indexing, and race-free per-model upsert; the table shares one logical `fetched_at` because every refresh rewrites all rows in one batch.
- **No extra index beyond the PK:** kept additive and minimal per the plan; a partial `is_free` index was optional and deferred.
- **Migration history was clean:** `db push --dry-run` showed only 030 pending (001-029 already recorded applied on dev), so the project-memory `migration repair` caveat did not need to be exercised this plan.

## Deviations from Plan

None - plan executed exactly as written. The migration shape, RLS posture, and live dev apply all matched the plan; no Rule 1/2/3 auto-fixes were required and no Rule 4 architectural decision arose.

## Issues Encountered
- **cwd-drift inside the worktree (#3097, handled):** The first migration Write landed in the MAIN repo (the project root) rather than the worktree root, because the worktree's git context only resolves correctly from `.claude/worktrees/agent-a60256ac8f8e0677b`. Detected via the git-dir / `.git`-is-a-file check, removed the stray untracked main-repo file, re-wrote the migration to the worktree root, and committed from there. No work lost.
- **Live apply runs from the linked main repo:** `supabase db push` requires a linked supabase dir, and the CLI link state lives in the MAIN repo (`supabase/.temp/project-ref` = `ntkkmljbariflblldmha`). Copied the committed migration into the main repo solely to run the live `db push`, verified the apply with a service-role probe, then removed the temporary copy. The canonical committed copy lives in the worktree branch and will reach the main repo on merge.

## Ops Note — Prod Deploy (deferred, D-03)
Prod is NOT pushed in this plan. At deploy time, apply migration 030 to the prod Supabase project by targeting `.env.prod` (NOT `.env`), and be ready for the known `db push` replay / "already exists" condition: if the push tries to replay old migrations, run `supabase migration repair --status applied <prior 001-029 range>` against prod first, then re-push. Per project memory, prod (`ybehhhduhynsdujmxdzx` / boardgame-rag-prod) is a separate project from dev (`ntkkmljbariflblldmha`).

## Next Phase Readiness
- `model_cache` is live on dev and reachable via the service-role client — plan 12-03's route + seed tests can now read/write a real table (the BLOCKING push closed the false-positive-verification gap).
- No blockers introduced. Prod apply tracked as the ops note above for the deploy step.

---
*Phase: 12-model-cache-catalog*
*Completed: 2026-06-23*
