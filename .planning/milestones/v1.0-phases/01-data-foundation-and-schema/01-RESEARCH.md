# Phase 01: Data Foundation and Schema - Research

**Researched:** 2026-04-07
**Domain:** PostgreSQL schema design (ltree, RLS, mixed-visibility), Supabase migrations
**Confidence:** HIGH

## Summary

This phase is purely database schema and migration work. The existing codebase has 15 migrations establishing tables for `documents`, `document_chunks`, `threads`, and `messages` with single-user RLS policies (`auth.uid() = user_id`). The phase must: (1) enable the `ltree` extension for materialized paths, (2) create a `folders` table with ltree paths and GiST index, (3) add `folder_id` and `visibility` columns to `documents` and `document_chunks`, (4) replace all RLS policies to support mixed visibility (public default KB + private user docs), (5) update both search RPC functions and the readonly query RPC, and (6) create a system user in `auth.users` to own default KB content.

The primary risk is the RLS policy transition -- dropping and recreating policies on tables that already have data. The migration must be atomic (single transaction) to avoid a window where RLS is disabled. The system user creation requires inserting directly into `auth.users` and `auth.identities` tables, which is a Supabase-internal schema operation that must match the current auth schema format.

**Primary recommendation:** Structure migrations as 4-5 sequential SQL files (016-020): extension enablement, folders table, column additions, RLS policy replacement, and RPC function updates. Create the system user via a seed-style migration that inserts into `auth.users` with a fixed UUID.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use a dedicated system user account (e.g., `default-kb@system.internal`) to own all default KB content. Keeps `user_id` NOT NULL across all tables.
- **D-02:** Add a `visibility` column to `documents` and `folders` tables. Default KB = `visibility='public'`, user uploads = `visibility='private'`.
- **D-03:** RLS policies: users see rows where `user_id = auth.uid()` OR `visibility = 'public'`. Applies to `documents`, `document_chunks`, and both search RPCs.
- **D-04:** `execute_readonly_query` RPC needs visibility awareness to prevent leaking private data through SQL queries.
- **D-05:** Use `ltree` Postgres extension for materialized paths. Enable via `CREATE EXTENSION IF NOT EXISTS ltree;`.
- **D-06:** `folders` table with: `id`, `user_id`, `name`, `path` (ltree), `parent_id` (self-ref FK, nullable for roots), `visibility`, `created_at`, `updated_at`. GiST index on `path`.
- **D-07:** Add `folder_id` FK to `documents` table (nullable -- existing docs have no folder initially).
- **D-08:** Unlimited nesting depth.
- **D-09:** Each user gets a pre-created "My Documents" root folder on signup (or first login). Default KB appears as a top-level "Board Games" root folder owned by system user with `visibility='public'`.
- **D-10:** Add columns to existing tables. `documents` gets `folder_id` and `visibility`. `document_chunks` gets `visibility` (denormalized for RPC performance).
- **D-11:** Existing documents get `folder_id = NULL` and `visibility = 'private'`. No backfill into folders.
- **D-12:** RLS policies must be replaced (DROP old + CREATE new) to add visibility check.
- **D-13:** Both search RPCs updated to include visibility-aware filtering: return chunks where `user_id = filter_user_id` OR `visibility = 'public'`.

### Claude's Discretion
- Visibility column values: likely `public`/`private` with room to extend
- Storage path design: how folder hierarchy maps to Supabase Storage paths
- Migration numbering and ordering (016+)
- Whether to add `visibility` column to `document_chunks` directly or rely on JOIN to `documents` (Decision D-10 says direct -- denormalized)
- Folder table constraints and indexes beyond the GiST on path

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | User can create folders and subfolders to organize their documents | `folders` table with ltree paths, self-referential `parent_id` FK, and GiST index enables hierarchical folder creation. Backend needs a folder creation endpoint. |
| DATA-03 | System stores folder hierarchy in Supabase with materialized paths for efficient tree queries | ltree extension with GiST index. Operators `@>` (ancestor) and `<@` (descendant) for tree traversal. `nlevel()` for depth queries. |
| DATA-05 | All authenticated users can read the default KB content (shared visibility) | `visibility = 'public'` column + RLS policy: `auth.uid() = user_id OR visibility = 'public'` on SELECT. System user owns default KB rows. |
| DATA-06 | User's uploaded documents remain private (only visible to that user) | `visibility = 'private'` default on INSERT + RLS policy restricts SELECT to owner-only for private rows. |
| DATA-07 | RLS policies enforce mixed visibility (default KB readable by all, private docs per-user) | Replace existing single-user policies on `documents` and `document_chunks`. Update search RPCs to filter by `user_id = param OR visibility = 'public'`. Update `execute_readonly_query` to enforce visibility via RLS context. |
</phase_requirements>

## Standard Stack

### Core
| Library/Extension | Version | Purpose | Why Standard |
|-------------------|---------|---------|--------------|
| ltree (Postgres) | Built-in (PG 14+) | Materialized path hierarchical data type | Purpose-built for tree queries. GiST-indexed `@>` / `<@` operators for ancestor/descendant lookups in single query. Available natively in Supabase. |
| pgvector (existing) | Supabase built-in | Vector similarity search | Already enabled in migration 004. No changes needed. |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| Supabase SQL Editor / CLI | N/A | Apply migrations | Run migration files against the Supabase project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ltree materialized paths | Adjacency list (parent_id only) | Adjacency lists require recursive CTEs for tree queries -- slower, harder to index, no pattern matching |
| ltree materialized paths | Nested sets | Fast reads but very expensive inserts/moves (must renumber). Folder reorganization would be painful. |
| Denormalized `visibility` on chunks | JOIN to `documents` in RPC | JOIN in RPC adds latency to every search call; denormalized column keeps search queries flat and fast |

**Installation:**
```sql
-- In Supabase SQL editor or migration file
CREATE EXTENSION IF NOT EXISTS ltree;
```

No npm/pip packages needed for this phase -- purely SQL migrations.

## Architecture Patterns

### Migration File Structure
```
supabase/migrations/
  016_enable_ltree.sql              # Enable ltree extension
  017_create_system_user.sql        # Insert system user into auth.users + auth.identities
  018_create_folders_table.sql      # folders table with ltree, RLS, indexes
  019_add_visibility_and_folder.sql # Add columns to documents + document_chunks, set defaults
  020_update_rls_policies.sql       # DROP old + CREATE new RLS policies for mixed visibility
  021_update_search_rpcs.sql        # Update match_document_chunks, keyword_search_chunks, execute_readonly_query
```

### Pattern 1: System User Creation
**What:** Insert a row into `auth.users` and `auth.identities` with a fixed UUID to own default KB content.
**When to use:** Once, in a migration, before any default KB data is created.
**Example:**
```sql
-- Source: Supabase GitHub discussions on programmatic user creation
-- Use a deterministic UUID so it's idempotent and referenceable
DO $$
DECLARE
  system_user_id UUID := '00000000-0000-0000-0000-000000000000';
BEGIN
  -- Only insert if not exists (idempotent)
  IF NOT EXISTS (SELECT 1 FROM auth.users WHERE id = system_user_id) THEN
    INSERT INTO auth.users (
      instance_id, id, aud, role, email,
      encrypted_password, email_confirmed_at,
      created_at, updated_at, confirmation_token,
      raw_app_meta_data, raw_user_meta_data
    ) VALUES (
      '00000000-0000-0000-0000-000000000000',
      system_user_id,
      'authenticated',
      'authenticated',
      'default-kb@system.internal',
      crypt('SYSTEM_USER_NO_LOGIN_' || gen_random_uuid()::text, gen_salt('bf')),
      now(),
      now(),
      now(),
      '',
      '{"provider": "email", "providers": ["email"]}'::jsonb,
      '{"is_system_user": true}'::jsonb
    );

    INSERT INTO auth.identities (
      id, user_id, identity_data, provider, provider_id,
      last_sign_in_at, created_at, updated_at
    ) VALUES (
      gen_random_uuid(),
      system_user_id,
      jsonb_build_object('sub', system_user_id::text, 'email', 'default-kb@system.internal'),
      'email',
      system_user_id::text,
      now(),
      now(),
      now()
    );
  END IF;
END $$;
```

**Critical details:**
- `aud` MUST be `'authenticated'` (not empty string) or Supabase auth will not recognize the user
- `encrypted_password` uses a random unguessable password -- this user should never log in via the frontend
- `instance_id` should be `'00000000-0000-0000-0000-000000000000'` for Supabase hosted projects
- Use a fixed UUID (`00000000-0000-0000-0000-000000000000`) so other migrations can reference it without queries

### Pattern 2: ltree Path Convention
**What:** Consistent path format for folder hierarchy.
**When to use:** Every folder creation.

```
-- Label format: alphanumeric + underscores + hyphens (ltree rules)
-- Root folders: single label
-- Subfolders: dot-separated path

-- System user's default KB root:
board_games

-- Subfolder example:
board_games.catan
board_games.catan.expansions

-- User root folder:
my_documents

-- User subfolder:
my_documents.strategy_games
```

**Key constraint:** ltree labels only support `A-Za-z0-9_-` (no spaces, dots, or special characters). Folder names with spaces or special chars must be stored in the `name` column; the `path` column uses a sanitized slug. The planner must include a path-sanitization utility.

### Pattern 3: Mixed-Visibility RLS
**What:** RLS policies that allow reading public content while restricting private content to owners.
**When to use:** All SELECT policies on `documents`, `document_chunks`, and `folders`.
**Example:**
```sql
-- Source: Supabase RLS documentation
-- SELECT: see own rows OR public rows
CREATE POLICY "Users can view own or public documents"
  ON documents FOR SELECT
  USING (auth.uid() = user_id OR visibility = 'public');

-- INSERT: users can only insert their own private rows
CREATE POLICY "Users can insert own documents"
  ON documents FOR INSERT
  WITH CHECK (auth.uid() = user_id AND visibility = 'private');

-- UPDATE: users can only update their own rows (not public KB)
CREATE POLICY "Users can update own documents"
  ON documents FOR UPDATE
  USING (auth.uid() = user_id AND visibility = 'private');

-- DELETE: users can only delete their own rows (not public KB)
CREATE POLICY "Users can delete own documents"
  ON documents FOR DELETE
  USING (auth.uid() = user_id AND visibility = 'private');
```

### Pattern 4: Visibility-Aware Search RPCs
**What:** Update search RPCs to return both user's private chunks AND public default KB chunks.
**When to use:** Both `match_document_chunks` and `keyword_search_chunks`.
**Example:**
```sql
-- Replace the WHERE clause in both RPCs:
-- OLD: WHERE dc.user_id = filter_user_id
-- NEW: WHERE (dc.user_id = filter_user_id OR dc.visibility = 'public')

CREATE OR REPLACE FUNCTION match_document_chunks(
  query_embedding VECTOR(2048),
  match_count INT DEFAULT 5,
  filter_user_id UUID DEFAULT NULL,
  filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
  id UUID, document_id UUID, content TEXT, chunk_index INT, similarity FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT dc.id, dc.document_id, dc.content, dc.chunk_index,
    1 - (dc.embedding <=> query_embedding) AS similarity
  FROM document_chunks dc
  WHERE (dc.user_id = filter_user_id OR dc.visibility = 'public')
    AND (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

### Anti-Patterns to Avoid
- **Dropping RLS before creating new policies:** Never have a window where RLS is enabled but no policies exist -- all rows become invisible. Use `DROP POLICY IF EXISTS` + `CREATE POLICY` in the same transaction.
- **Using NULL for visibility:** Use explicit `'private'` default, not NULL. NULL comparisons with `=` are always false, which would silently hide rows.
- **Storing ltree path as TEXT:** Use the actual `ltree` data type, not a TEXT column with dot-separated values. TEXT loses all GiST index benefits and operator support.
- **Hardcoding system user UUID in application code:** Define it as a constant in `backend/config.py` (or `.env`) so it's referenceable from both migrations and Python code.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tree traversal queries | Recursive CTEs with parent_id | ltree `@>` / `<@` operators | Single indexed query vs multi-step recursion |
| Path sanitization for ltree | Custom regex replacer | Simple function: `re.sub(r'[^A-Za-z0-9_-]', '_', name).strip('_')` | ltree labels have strict format rules; a tested sanitizer prevents runtime errors |
| Visibility enforcement | Application-level filtering | Postgres RLS policies | RLS enforces at DB level -- impossible to bypass even via direct SQL |
| Denormalized visibility sync | Manual UPDATE triggers | Postgres trigger on `documents` that propagates `visibility` to `document_chunks` | Keeps denormalized data consistent without application code |

**Key insight:** This phase is database-only work. Every feature is implemented via SQL migrations and Postgres-native capabilities (ltree extension, RLS policies, triggers). No application code is needed to enforce the security model -- RLS does it at the database level.

## Common Pitfalls

### Pitfall 1: RLS Policy Drop/Create Race Condition
**What goes wrong:** Dropping old RLS policies before creating new ones creates a window where the table has RLS enabled but zero policies. In Postgres, RLS-enabled tables with no policies deny ALL access (not allow all).
**Why it happens:** Migrations that DROP then CREATE in separate statements outside a transaction.
**How to avoid:** Wrap the entire DROP + CREATE sequence in a single transaction (which Supabase migrations do by default -- each file is one transaction). Verify by testing immediately after migration.
**Warning signs:** All document queries return empty after migration.

### Pitfall 2: System User aud Field
**What goes wrong:** System user cannot be referenced properly if `aud` field is empty or wrong.
**Why it happens:** The `aud` column in `auth.users` controls which Postgres role the user accesses the DB as. An empty `aud` value prevents the user from being treated as `authenticated`.
**How to avoid:** Set `aud = 'authenticated'` explicitly in the INSERT.
**Warning signs:** Default KB content is invisible even though `visibility = 'public'`.

### Pitfall 3: ltree Label Format Violations
**What goes wrong:** Runtime errors when inserting folder paths with invalid characters (spaces, dots, Unicode).
**Why it happens:** ltree labels only allow `A-Za-z0-9_-` in C locale. Folder names like "Board Games" or "Catan: Seafarers" contain spaces and colons.
**How to avoid:** Always sanitize the `name` to create a valid `path` label. Store the display name in `name`, the sanitized slug in `path`.
**Warning signs:** `INSERT` fails with "syntax error in ltree" or similar.

### Pitfall 4: Forgetting to Update execute_readonly_query
**What goes wrong:** Users can craft SQL queries via the Text-to-SQL tool that bypass visibility and read other users' private documents.
**Why it happens:** `execute_readonly_query` sets `SET LOCAL role = 'authenticated'` and injects the user's JWT claim, but the existing RLS policies it relies on will change. If the RPC is not updated in sync with RLS changes, it could leak data.
**How to avoid:** After updating RLS policies, `execute_readonly_query` automatically benefits because it uses `SET LOCAL role = 'authenticated'` + `set_config('request.jwt.claim.sub', ...)` which triggers the updated RLS policies. Verify by testing a query as user A that should not see user B's docs.
**Warning signs:** SQL tool returns documents from other users.

### Pitfall 5: Existing Unique Index Conflict
**What goes wrong:** The existing unique index `idx_documents_user_content_hash` on `(user_id, content_hash)` may need consideration when the system user uploads default KB content that could collide with user uploads.
**Why it happens:** If a user uploads the same file that exists in the default KB (owned by system user), the hashes are scoped by user_id so there's no conflict. But if the system user re-uploads, it would conflict.
**How to avoid:** This is actually fine -- the unique index is scoped by user_id, so system user and regular users have independent hash namespaces. Just be aware of it.
**Warning signs:** None expected, but worth verifying.

### Pitfall 6: Vector Index Performance with OR Clauses
**What goes wrong:** The IVFFlat index on `embedding` may not be used efficiently when the WHERE clause has an OR condition (`user_id = X OR visibility = 'public'`).
**Why it happens:** IVFFlat indexes work best with simple conditions. Complex OR clauses can cause the planner to fall back to sequential scan.
**How to avoid:** For the search RPCs, the vector distance ordering (`ORDER BY embedding <=> query_embedding`) is the primary index usage. The WHERE clause filters are applied post-scan. With small-to-medium datasets (board game KB), this is unlikely to be a bottleneck. If performance becomes an issue, consider using HNSW index instead of IVFFlat, or restructuring the query as a UNION of two queries.
**Warning signs:** Slow search queries after adding visibility filter.

## Code Examples

### Folders Table Creation
```sql
-- Source: PostgreSQL ltree docs + CONTEXT.md decisions D-05, D-06
CREATE EXTENSION IF NOT EXISTS ltree;

CREATE TABLE folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  name TEXT NOT NULL,
  path ltree NOT NULL,
  parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
  visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT unique_path_per_user UNIQUE (user_id, path)
);

CREATE INDEX idx_folders_path_gist ON folders USING GIST (path);
CREATE INDEX idx_folders_user_id ON folders (user_id);
CREATE INDEX idx_folders_parent_id ON folders (parent_id);
```

### Adding Columns to Existing Tables
```sql
-- documents: add folder_id and visibility
ALTER TABLE documents
  ADD COLUMN folder_id UUID REFERENCES folders(id) ON DELETE SET NULL,
  ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private'));

-- document_chunks: add visibility (denormalized from documents)
ALTER TABLE document_chunks
  ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private'));

-- Index for visibility-filtered queries
CREATE INDEX idx_documents_visibility ON documents (visibility);
CREATE INDEX idx_chunks_visibility ON document_chunks (visibility);
```

### Replacing RLS Policies (Atomic)
```sql
-- Documents table: drop all old policies, create new ones
-- This runs in a single transaction (Supabase migration default)
DROP POLICY IF EXISTS "Users can select own documents" ON documents;
DROP POLICY IF EXISTS "Users can insert own documents" ON documents;
DROP POLICY IF EXISTS "Users can update own documents" ON documents;
DROP POLICY IF EXISTS "Users can delete own documents" ON documents;

CREATE POLICY "Users can view own or public documents"
  ON documents FOR SELECT
  USING (auth.uid() = user_id OR visibility = 'public');

CREATE POLICY "Users can insert own documents"
  ON documents FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own documents"
  ON documents FOR UPDATE
  USING (auth.uid() = user_id AND visibility = 'private');

CREATE POLICY "Users can delete own documents"
  ON documents FOR DELETE
  USING (auth.uid() = user_id AND visibility = 'private');
```

### ltree Query Examples
```sql
-- Find all subfolders of "board_games"
SELECT * FROM folders WHERE path <@ 'board_games';

-- Find direct children only (depth = parent depth + 1)
SELECT * FROM folders
WHERE path <@ 'board_games'
  AND nlevel(path) = nlevel('board_games'::ltree) + 1;

-- Find all ancestors of a path
SELECT * FROM folders WHERE path @> 'board_games.catan.expansions';

-- Pattern matching: all folders matching "board_games.*.expansions"
SELECT * FROM folders WHERE path ~ 'board_games.*.expansions';
```

### Visibility Sync Trigger (document_chunks)
```sql
-- When a document's visibility changes, propagate to its chunks
CREATE OR REPLACE FUNCTION sync_chunk_visibility()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.visibility IS DISTINCT FROM OLD.visibility THEN
    UPDATE document_chunks
    SET visibility = NEW.visibility
    WHERE document_id = NEW.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_chunk_visibility
  AFTER UPDATE OF visibility ON documents
  FOR EACH ROW
  EXECUTE FUNCTION sync_chunk_visibility();
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-user RLS (`auth.uid() = user_id`) | Mixed-visibility RLS (`auth.uid() = user_id OR visibility = 'public'`) | This phase | All SELECT policies and search RPCs must be updated |
| No folder organization | ltree-based folder hierarchy | This phase | New `folders` table, `folder_id` FK on documents |
| All documents private | Public/private visibility model | This phase | System user for default KB, `visibility` column on documents + chunks |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend/tests/ exists) |
| Config file | None detected -- may need pytest.ini or pyproject.toml |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | Folder creation persists with materialized paths | SQL verification | Manual: run INSERT + SELECT in Supabase SQL editor | N/A (SQL migration) |
| DATA-03 | ltree paths support ancestor/descendant queries | SQL verification | Manual: run ltree queries after migration | N/A (SQL migration) |
| DATA-05 | Public visibility readable by all authenticated users | RLS test | Manual: query as different user, verify public rows visible | N/A (SQL migration) |
| DATA-06 | Private documents invisible to other users | RLS test | Manual: query as user B, verify user A's private docs hidden | N/A (SQL migration) |
| DATA-07 | Mixed visibility enforced in search RPCs | RLS + RPC test | Manual: call RPCs as different users, verify correct results | N/A (SQL migration) |

### Sampling Rate
- **Per migration:** Run verification queries in Supabase SQL editor
- **Phase gate:** Full RLS verification matrix (user A sees own + public, user B sees own + public, neither sees other's private)

### Wave 0 Gaps
- [ ] No automated RLS test exists -- verification is manual SQL queries
- [ ] Consider adding a Python test that uses the Supabase client to verify RLS enforcement programmatically
- [ ] Verification SQL scripts should be included alongside migrations for repeatable testing

## Open Questions

1. **auth.users Schema Compatibility**
   - What we know: System user requires INSERT into `auth.users` and `auth.identities` tables
   - What's unclear: The exact column set in `auth.users` may vary by Supabase version. The migration should handle missing optional columns gracefully.
   - Recommendation: Use `IF NOT EXISTS` guard and only set columns known to be required (`id`, `aud`, `role`, `email`, `encrypted_password`, `email_confirmed_at`, `created_at`, `updated_at`, `raw_app_meta_data`, `raw_user_meta_data`). Test on the actual Supabase instance before committing.

2. **Default Root Folders Creation Timing**
   - What we know: D-09 says each user gets "My Documents" on signup/first login. Default KB gets "Board Games" folder owned by system user.
   - What's unclear: Whether "My Documents" creation belongs in this phase (schema) or Phase 4 (UI). The "Board Games" folder should be created in Phase 2 (seeding) alongside default KB content.
   - Recommendation: This phase creates the `folders` table and the system user. Create the "Board Games" root folder in the migration alongside the system user (it's foundational). Defer per-user "My Documents" to Phase 4 or a backend hook.

3. **Storage Path Design**
   - What we know: Current storage paths are `{user_id}/{doc_id}/{filename}`. Folders add hierarchy.
   - What's unclear: Whether storage paths should mirror the folder hierarchy or remain flat.
   - Recommendation: Keep storage paths flat (`{user_id}/{doc_id}/{filename}`) for this phase. The folder hierarchy is a database concern, not a storage concern. Changing storage paths would require migrating existing files. Storage path redesign can happen later if needed.

## Sources

### Primary (HIGH confidence)
- [PostgreSQL ltree documentation](https://www.postgresql.org/docs/current/ltree.html) -- label format, operators, index types, functions
- [Supabase RLS documentation](https://supabase.com/docs/guides/database/postgres/row-level-security) -- policy syntax, mixed visibility patterns
- [Supabase Extensions](https://supabase.com/docs/guides/database/extensions) -- ltree availability confirmation
- Existing codebase migrations (005, 006, 008, 011, 012, 013, 014, 015) -- current schema, RLS patterns, RPC signatures

### Secondary (MEDIUM confidence)
- [Supabase Discussion #5043](https://github.com/orgs/supabase/discussions/5043) -- programmatic user creation patterns (auth.users + auth.identities insert)
- [Supabase Discussion #9251](https://github.com/orgs/supabase/discussions/9251) -- seeding auth users locally
- `.planning/research/STACK.md` -- prior research on ltree, pg_trgm, folder schema

### Tertiary (LOW confidence)
- System user `auth.users` column requirements -- may vary by Supabase version. Needs validation against the actual project instance.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- ltree is well-documented, Supabase-native, verified in prior research
- Architecture: HIGH -- migration patterns are established in the existing codebase (15 migrations as precedent)
- Pitfalls: HIGH -- RLS race condition and ltree label format are well-known issues in the Postgres community
- System user creation: MEDIUM -- auth.users schema varies by Supabase version; the INSERT pattern is community-sourced

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (stable domain -- Postgres extensions and Supabase RLS are mature)
