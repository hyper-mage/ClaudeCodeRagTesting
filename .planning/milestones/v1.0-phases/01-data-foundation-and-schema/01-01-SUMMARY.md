---
phase: 01-data-foundation-and-schema
plan: 01
subsystem: database
tags: [ltree, postgres, rls, supabase, migrations, system-user, folders]

# Dependency graph
requires: []
provides:
  - ltree extension enabled for materialized path queries
  - System user (00000000-0000-0000-0000-000000000000) for default KB ownership
  - Folders table with ltree paths, GiST index, and mixed-visibility RLS
  - Board Games root folder (a0000000-0000-0000-0000-000000000001) seeded as public
affects: [01-02, phase-02-seeding, phase-04-file-manager-ui]

# Tech tracking
tech-stack:
  added: [ltree]
  patterns: [mixed-visibility-rls, system-user-ownership, deterministic-uuids]

key-files:
  created:
    - supabase/migrations/016_enable_ltree.sql
    - supabase/migrations/017_create_system_user.sql
    - supabase/migrations/018_create_folders_table.sql
  modified: []

key-decisions:
  - "Used deterministic UUIDs for system user and Board Games folder to enable cross-migration references"
  - "RLS UPDATE/DELETE policies restricted to private folders only -- public KB is immutable via RLS"

patterns-established:
  - "Mixed-visibility RLS: SELECT uses (auth.uid() = user_id OR visibility = 'public'), write ops restricted to private"
  - "System user ownership: default KB content owned by 00000000-0000-0000-0000-000000000000"
  - "Deterministic seed UUIDs: a0000000-* prefix for default KB folder seeds"

requirements-completed: [DATA-01, DATA-03]

# Metrics
duration: 1min
completed: 2026-04-08
---

# Phase 01 Plan 01: Folders Foundation Summary

**ltree-based folders table with system user ownership, mixed-visibility RLS, and Board Games root seed**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-08T00:09:10Z
- **Completed:** 2026-04-08T00:10:13Z
- **Tasks:** 2
- **Files created:** 3

## Accomplishments
- Enabled ltree Postgres extension for materialized path folder hierarchy
- Created system user in auth.users and auth.identities with fixed UUID and authenticated aud
- Built folders table with ltree path column, GiST index, self-referential parent_id, and unique path-per-user constraint
- Established mixed-visibility RLS policies (own + public) on folders table
- Seeded Board Games root folder owned by system user with public visibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ltree extension and system user migrations** - `9632f12` (feat)
2. **Task 2: Create folders table with RLS and seed Board Games root folder** - `24f212f` (feat)

## Files Created/Modified
- `supabase/migrations/016_enable_ltree.sql` - Enables ltree extension for materialized path queries
- `supabase/migrations/017_create_system_user.sql` - Creates system user (default-kb@system.internal) with idempotent guard
- `supabase/migrations/018_create_folders_table.sql` - Folders table with ltree, indexes, RLS policies, and Board Games seed

## Decisions Made
- Used deterministic UUIDs for both system user (00000000-...) and Board Games folder (a0000000-...) so downstream migrations and Phase 2 seeding can reference them without queries
- RLS UPDATE and DELETE policies only allow operating on private folders, making public KB content immutable at the database level

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Migrations are ready to apply via Supabase dashboard or CLI.

## Next Phase Readiness
- Folders table and system user are ready for Plan 01-02 (visibility columns, RLS updates, RPC changes)
- Board Games root folder UUID (a0000000-0000-0000-0000-000000000001) available for Phase 2 game subfolder seeding
- System user UUID (00000000-0000-0000-0000-000000000000) available for document ownership in default KB

---
*Phase: 01-data-foundation-and-schema*
*Completed: 2026-04-08*

## Self-Check: PASSED

All 3 migration files exist. Both task commits verified (9632f12, 24f212f). SUMMARY.md created.
