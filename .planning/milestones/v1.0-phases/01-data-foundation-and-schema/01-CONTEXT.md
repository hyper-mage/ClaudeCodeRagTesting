# Phase 1: Data Foundation and Schema - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the database schema and RLS restructuring needed to support hierarchical folder organization with mixed-visibility content (shared default KB readable by all + private user docs scoped per user). No UI, no ingestion changes, no tools -- purely schema/migration work.

</domain>

<decisions>
## Implementation Decisions

### Default KB Ownership
- **D-01:** Use a dedicated system user account (e.g., `default-kb@system.internal`) to own all default KB content. This keeps `user_id` as NOT NULL across all tables (no schema-breaking change).
- **D-02:** Add a `visibility` column to the `documents` table (and `folders` table). Default KB rows get `visibility='public'`, user uploads get `visibility='private'`.
- **D-03:** RLS policies must be updated: users see rows where `user_id = auth.uid()` OR `visibility = 'public'`. This applies to `documents`, `document_chunks`, and both search RPC functions (`match_document_chunks`, `keyword_search_chunks`).
- **D-04:** The `execute_readonly_query` RPC also needs awareness of visibility to prevent leaking private data through SQL queries.

### Folder Structure
- **D-05:** Use the `ltree` Postgres extension for materialized paths. Enable via `CREATE EXTENSION IF NOT EXISTS ltree;` in migration. Supabase supports this natively.
- **D-06:** Create a `folders` table with: `id`, `user_id`, `name`, `path` (ltree), `parent_id` (self-ref FK, nullable for roots), `visibility`, `created_at`, `updated_at`. GiST index on `path`.
- **D-07:** Add `folder_id` FK to the `documents` table (nullable -- existing docs have no folder initially).
- **D-08:** Unlimited nesting depth. No artificial limits on folder hierarchy.
- **D-09:** Each user gets a pre-created "My Documents" root folder on signup (or first login). Default KB appears as a top-level "Board Games" root folder owned by the system user with `visibility='public'`.

### Migration Strategy
- **D-10:** Add columns to existing tables (not separate tables). `documents` gets `folder_id` and `visibility` columns. `document_chunks` gets `visibility` column (denormalized for RPC performance).
- **D-11:** Existing documents without folders get `folder_id = NULL` and `visibility = 'private'`. No backfill into folders required -- they'll appear as "unfiled" until the user organizes them in Phase 4.
- **D-12:** RLS policies on `documents` and `document_chunks` must be replaced (DROP old + CREATE new) to add the visibility check.
- **D-13:** Both search RPC functions (`match_document_chunks`, `keyword_search_chunks`) must be updated to include visibility-aware filtering: return chunks where `user_id = filter_user_id` OR `visibility = 'public'`.

### Claude's Discretion
- Visibility column values: Claude picks the best set (likely `public`/`private` for simplicity, with room to extend later)
- Storage path design: Claude decides how folder hierarchy maps to Supabase Storage paths
- Migration numbering and ordering (016+)
- Whether to add `visibility` column to `document_chunks` directly or rely on JOIN to `documents`
- Folder table constraints and indexes beyond the GiST on path

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database Schema
- `supabase/migrations/005_create_documents.sql` -- Current documents table schema with RLS
- `supabase/migrations/006_create_document_chunks.sql` -- Current chunks table with RLS
- `supabase/migrations/008_match_chunks_function.sql` -- Vector search RPC (needs visibility update)
- `supabase/migrations/014_keyword_search_function.sql` -- Keyword search RPC (needs visibility update)
- `supabase/migrations/015_execute_readonly_query.sql` -- SQL execution RPC (needs visibility awareness)

### Backend Integration Points
- `backend/database.py` -- Supabase client factory (service role key)
- `backend/auth.py` -- JWT verification (system user may need special handling)
- `backend/routers/documents.py` -- Document upload router (needs folder_id support)
- `backend/services/retrieval_service.py` -- Search service calling RPCs (needs visibility-aware calls)

### Research
- `.planning/research/STACK.md` -- ltree and pg_trgm recommendations
- `.planning/research/ARCHITECTURE.md` -- Component boundaries and build order
- `.planning/research/PITFALLS.md` -- RLS mixed-visibility risks

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Supabase client with service role key (`backend/database.py`) -- bypasses RLS for server-side operations, useful for system user setup
- Existing RLS policy pattern (`auth.uid() = user_id`) -- extend rather than replace
- Migration file convention (`NNN_description.sql`) -- continue with 016+

### Established Patterns
- All tables use `user_id UUID NOT NULL REFERENCES auth.users(id)` -- system user must be a real auth.users entry
- RPC functions accept `filter_user_id` parameter -- extend to include visibility check
- Backend uses service role key for all DB operations -- RLS only enforced on frontend/RPC calls
- `document_chunks` has `user_id` denormalized from `documents` -- follow same pattern for `visibility`

### Integration Points
- `documents.py` router: upload endpoint needs `folder_id` parameter
- `retrieval_service.py`: calls `match_document_chunks` and `keyword_search_chunks` RPCs
- `ingestion_service.py`: creates document records (needs folder_id)
- `record_manager.py`: checks for duplicates by hash + user_id (may need visibility awareness)
- Frontend `useDocuments.ts`: document listing (will need folder filtering in Phase 4)

</code_context>

<specifics>
## Specific Ideas

- System user should be created via seed script or migration, not manually
- "Board Games" root folder for default KB should be visually distinct (Phase 4 handles UI, but schema should support a flag or rely on visibility='public')
- Existing unfiled documents should gracefully coexist with the new folder system (folder_id nullable)

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 01-data-foundation-and-schema*
*Context gathered: 2026-04-07*
