---
phase: 01-data-foundation-and-schema
plan: 02
subsystem: database
tags: [postgres, rls, supabase, migrations, visibility, mixed-visibility, triggers]

# Dependency graph
requires:
  - phase: 01-data-foundation-and-schema plan 01
    provides: folders table (018), system user (017), ltree extension (016)
provides:
  - visibility and folder_id columns on documents and document_chunks tables
  - Mixed-visibility RLS policies replacing single-user policies
  - Visibility-aware search RPCs (match_document_chunks, keyword_search_chunks)
  - Triggers to sync chunk visibility with parent document visibility
affects: [phase-02-seeding, phase-03-backend-services, phase-04-file-manager-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [mixed-visibility-rls, visibility-sync-triggers, visibility-aware-rpcs]

key-files:
  created:
    - supabase/migrations/019_add_visibility_and_folder.sql
    - supabase/migrations/020_update_rls_policies.sql
    - supabase/migrations/021_update_search_rpcs.sql
  modified: []

key-decisions:
  - "INSERT policies have no visibility restriction so backend service role can insert public docs for default KB"
  - "execute_readonly_query needs no code changes -- updated RLS policies automatically enforce visibility"

patterns-established:
  - "Visibility sync trigger: document visibility changes propagate to child chunks automatically"
  - "Chunk visibility on insert: BEFORE INSERT trigger inherits visibility from parent document"
  - "RPC visibility filter: (dc.user_id = filter_user_id OR dc.visibility = 'public') in WHERE clause"

requirements-completed: [DATA-05, DATA-06, DATA-07]

# Metrics
duration: 1min
completed: 2026-04-08
---

# Phase 01 Plan 02: Mixed-Visibility Schema Summary

**Visibility columns, mixed-visibility RLS policies, and visibility-aware search RPCs for shared default KB + private user docs**

## Performance

- **Duration:** 1 min
- **Started:** 2026-04-08T00:11:45Z
- **Completed:** 2026-04-08T00:12:58Z
- **Tasks:** 3
- **Files created:** 3

## Accomplishments
- Added folder_id FK and visibility column to documents table, visibility column to document_chunks (denormalized)
- Replaced all 7 RLS policies on documents and document_chunks with mixed-visibility versions in a single transaction (no zero-policy window)
- Updated both search RPCs (match_document_chunks, keyword_search_chunks) with visibility-aware WHERE clauses
- Created triggers to sync chunk visibility with parent document on both UPDATE and INSERT
- Documented that execute_readonly_query automatically benefits from updated RLS policies

## Task Commits

Each task was committed atomically:

1. **Task 1: Add visibility and folder_id columns** - `c197b29` (feat)
2. **Task 2: Replace RLS policies for mixed visibility** - `221e49b` (feat)
3. **Task 3: Update search RPCs for visibility-aware filtering** - `bb1b5ca` (feat)

## Files Created/Modified
- `supabase/migrations/019_add_visibility_and_folder.sql` - Adds folder_id FK and visibility columns to documents and document_chunks, creates indexes and sync triggers
- `supabase/migrations/020_update_rls_policies.sql` - Drops 7 old single-user RLS policies, creates 7 new mixed-visibility policies in same transaction
- `supabase/migrations/021_update_search_rpcs.sql` - Updates match_document_chunks and keyword_search_chunks with visibility filter, documents execute_readonly_query unchanged

## Decisions Made
- INSERT policies intentionally have no visibility restriction (only `auth.uid() = user_id` check) so the backend service role can insert public documents for the default KB
- execute_readonly_query does not need code changes because it already uses `SET LOCAL role = 'authenticated'` + `set_config('request.jwt.claim.sub', ...)` which triggers the updated RLS policies

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Migrations are ready to apply via Supabase dashboard or CLI.

## Next Phase Readiness
- All Phase 1 schema work is complete (migrations 016-021)
- Database supports mixed visibility: public default KB readable by all, private docs scoped per user
- Search RPCs return both private and public content for any authenticated user
- Ready for Phase 2 (default KB seeding) -- system user, folders, and visibility infrastructure are in place

---
*Phase: 01-data-foundation-and-schema*
*Completed: 2026-04-08*

## Self-Check: PASSED

All 3 migration files exist. All 3 task commits verified (c197b29, 221e49b, bb1b5ca). SUMMARY.md created.
