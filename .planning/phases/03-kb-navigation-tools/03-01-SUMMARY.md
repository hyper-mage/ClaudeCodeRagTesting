---
phase: 03-kb-navigation-tools
plan: 01
subsystem: api
tags: [supabase, ltree, rpc, postgresql, regex, glob]

requires:
  - phase: 01-rls-and-folder-structure
    provides: folders table with ltree paths, visibility columns on documents/chunks
  - phase: 02-default-kb-and-ingestion-extensions
    provides: seeded Board Games folder hierarchy with game subfolders
provides:
  - 5 KB navigation tool functions (kb_ls, kb_tree, kb_read, kb_grep, kb_glob)
  - Path resolution utility for human-readable paths to folder/document IDs
  - Supabase RPCs for regex search and glob matching
affects: [03-03, chat-loop, tool-definitions]

tech-stack:
  added: []
  patterns: [name+parent_id path walking, virtual root resolution, BFS tree building]

key-files:
  created:
    - backend/services/kb_tools_service.py
    - supabase/migrations/022_kb_grep_regex_rpc.sql
    - supabase/migrations/023_kb_glob_rpc.sql
  modified: []

key-decisions:
  - "Path resolution walks name+parent_id chain, not ltree string manipulation, per D-06"
  - "Two virtual roots: Board Games (public) and My Documents (private user content)"
  - "kb_read auto-truncates at 200 lines with continuation hint per D-13"
  - "kb_grep regex mode uses RPC for Postgres-side ~* matching, then Python re for line-level formatting"
  - "kb_glob uses recursive CTE in RPC to build full display paths from folder hierarchy"

patterns-established:
  - "Virtual root pattern: map human-readable root names to folder IDs or virtual markers"
  - "Visibility filter pattern: .or_(f'user_id.eq.{user_id},visibility.eq.public') on all queries"
  - "Tree building: BFS with box-drawing characters for hierarchical display"

requirements-completed: [TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06]

duration: 5min
completed: 2026-04-09
---

# Plan 03-01: KB Navigation Tool Functions Summary

**5 KB navigation tools (ls, tree, read, grep, glob) with Supabase RPCs for regex search and glob matching against hierarchical folder structure**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files created:** 3

## Accomplishments
- kb_grep_regex RPC for case-insensitive POSIX regex search with ltree path scoping
- kb_glob_match RPC with recursive CTE for full display path construction
- All 5 KB tool functions with human-readable path resolution via name+parent_id walking
- Mixed-visibility filtering (public + user-owned) on all query paths

## Task Commits

1. **Task 1: Supabase RPC migrations** - `f394930` (feat)
2. **Task 2: kb_tools_service.py** - `cea92a1` (feat)

## Files Created/Modified
- `supabase/migrations/022_kb_grep_regex_rpc.sql` - RPC for regex search across chunks
- `supabase/migrations/023_kb_glob_rpc.sql` - RPC for glob pattern matching with CTE paths
- `backend/services/kb_tools_service.py` - All 5 KB tool functions + path resolution

## Decisions Made
- Used name+parent_id chain walking instead of ltree string manipulation per D-06
- kb_grep formats output ripgrep-style with 1 line of context above/below matches
- kb_glob uses ILIKE for case-insensitive path matching
- My Documents virtual root includes unfiled documents (folder_id IS NULL)

## Deviations from Plan
None - plan executed as specified.

## Issues Encountered
None.

## User Setup Required
None - SQL migrations need to be applied to Supabase but no new env vars or external config.

## Next Phase Readiness
- All 5 tools ready for integration into chat loop (Plan 03-03)
- RPCs need to be applied to Supabase before runtime testing

---
*Phase: 03-kb-navigation-tools*
*Completed: 2026-04-09*
