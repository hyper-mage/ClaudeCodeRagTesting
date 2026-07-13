---
phase: 17-agent-personas
plan: 08
subsystem: database
tags: [supabase, migration, postgres, ddl, env, pydantic-settings]

# Dependency graph
requires:
  - phase: 17-05
    provides: migration 20240301000035 file (additive persona pin columns)
provides:
  - threads.persona and user_preferences.default_persona columns live on the dev Supabase project
  - local .env freed of the SYSTEM_PROMPT shadow so the refactored operational base reaches the running dev app
affects: [17-09, 17-10, 17-11]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Operational DB migration applied via linked `supabase db push` (no history repair needed when remote head is in sync)"

key-files:
  created: []
  modified:
    - "supabase/migrations/20240301000035_add_persona_columns.sql (applied to dev DB — authored in 17-05)"
    - ".env (local, gitignored — SYSTEM_PROMPT override removed; .env.bak backup)"

key-decisions:
  - "Migration-repair guard skipped: `supabase migration list` showed remote head clean through 034, 035 the only pending file — plain `db push` applied only 035, zero replay risk."
  - "Prod (.env.prod) NOT migrated — deferred to deploy per dual-env discipline; .env.prod SYSTEM_PROMPT removal is also a deploy-time action."
  - "requirements-completed left empty — PERS-01/04/05 stay Pending until 17-09 pickers ship and 17-11 validates end-to-end (matches the phase's Wave-0-onward convention)."

patterns-established:
  - "Blocking operational checkpoint executed inline by the orchestrator (no subagent): outward-facing DDL applied with explicit user authorization, verified via PostgREST select."

requirements-completed: []

# Metrics
duration: ~15min
completed: 2026-07-13
---

# Phase 17-08: Apply Migration 035 to Dev + Remove SYSTEM_PROMPT Shadow

**Persona pin columns (`threads.persona`, `user_preferences.default_persona`) applied to the dev Supabase project and the local SYSTEM_PROMPT env-shadow removed — the backend persist/resolve seam is now backed by live columns.**

## Performance

- **Duration:** ~15 min (checkpoint plan, orchestrator-inline)
- **Completed:** 2026-07-13T21:49:35Z
- **Tasks:** 3 (Task 1 .env fix — user-executed; Task 2 db push — orchestrator; Task 3 human-verify — approved)
- **Files modified:** 1 repo file applied (migration), 1 local gitignored file (.env)

## Accomplishments
- Migration `20240301000035_add_persona_columns.sql` applied to the **dev** project via linked `supabase db push` — `supabase migration list` now shows `035` on both local and remote.
- Column existence verified programmatically: a PostgREST select of `threads.persona` and `user_preferences.default_persona` returns rows (prints `COLUMNS_EXIST`; a missing column would raise 42703).
- Local `.env` SYSTEM_PROMPT override removed (backed up to `.env.bak`) so the 17-04 refactored operational base is what pydantic-settings loads at runtime.
- Prod deferral recorded — `.env.prod` and the prod project remain unmigrated (deploy-time action).

## Task Commits

No production code commits — the migration SQL was committed in 17-05 (`54c5870`), the `db push` is a DB-side action, and `.env` is gitignored. Tracking/SUMMARY commit only.

1. **Task 1: Remove SYSTEM_PROMPT from local .env** — user-executed via session command; `.env.bak` backup created; no repo change (gitignored).
2. **Task 2: [BLOCKING] Apply migration 035 to dev Supabase** — `supabase db push` (linked dev project); `COLUMNS_EXIST` verified.
3. **Task 3: Human-verify columns + prod deferral** — user approved.

## Files Created/Modified
- `supabase/migrations/20240301000035_add_persona_columns.sql` — applied to dev DB (two additive nullable TEXT columns, no backfill/constraint/FK; own-row RLS from migration 032 inherited).
- `.env` (local, gitignored) — `SYSTEM_PROMPT=` line removed; `.env.bak` preserved for rollback.

## Decisions Made
- **No migration-history repair needed.** MEMORY/Pitfall 7 warned that `db push` can replay old migrations ("already exists"). `supabase migration list` showed remote synced through `034` with `035` the sole pending file, so a plain `db push` applied only `035` — the repair guard was correctly skipped.
- **Dev only.** Push targeted the linked dev project (`.env`); prod (`.env.prod`) explicitly untouched per dual-env discipline (T-17-24).
- **RLS unchanged.** Additive columns inherit the own-row policies already on `threads`/`user_preferences` (migration 032) — no new policy (D-08 / T-17-25).

## Deviations from Plan
None — plan executed as written. The migration-repair guard (Task 2 conditional) was a no-op because remote history was already clean; this is the intended fast path, not a deviation.

## Issues Encountered
- Orchestrator Bash writes/reads against `.env` were permission-gated (secret-bearing file), so Task 1 was handed to the user as a single session command (`cp .env .env.bak && grep -v '^SYSTEM_PROMPT=' ...`) rather than applied directly. User ran it and approved. If persona voices appear stale during 17-11 UAT, re-verify `.env` has no `SYSTEM_PROMPT=` line.

## User Setup Required
None outstanding for dev. **Deploy-time carry-forward:** apply migration 035 to the **prod** project and remove `SYSTEM_PROMPT` from `.env.prod` during the milestone deploy (verify prod against `.env.prod`).

## Next Phase Readiness
- Backend persist/resolve seam (17-05/06/07) is now backed by live dev columns — a real PATCH `/api/threads/{id} {persona}` / PUT `/api/preferences {default_persona}` no longer 42703s.
- Wave 4 (17-09 persona pickers) and Wave 5 (17-10 wiring) can proceed; end-to-end UAT is 17-11.

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
