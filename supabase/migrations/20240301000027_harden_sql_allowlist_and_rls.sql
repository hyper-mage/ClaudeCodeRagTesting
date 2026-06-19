-- SEC-02 Gate 2 (D-01) HARDENING + RLS fix — supersedes migration 026's
-- allowlist loop and patches the user_api_keys UPDATE policy.
--
-- WHY A NEW MIGRATION: migrations 025 and 026 are ALREADY APPLIED to dev. Editing
-- them does not re-run. This migration uses CREATE OR REPLACE for the RPC and
-- DROP/CREATE POLICY for RLS so a single forward apply lands all fixes.
--
-- Fixes (from 09-REVIEW.md):
--   CR-01  FROM-table allowlist bypassed by comma cross-join (`from a, b`).
--   CR-02  Schema-qualified names mis-parsed (`auth.users`, `messages.user_api_keys`).
--   WR-02  Legitimate comma-join queries inconsistently validated (same root cause).
--   WR-04  user_api_keys UPDATE policy missing WITH CHECK.
--
-- A regex CANNOT fully parse SQL; the durable defense remains Gate 1 — the
-- `REVOKE SELECT ON user_api_keys FROM authenticated` in migration 025, enforced
-- by the engine BEFORE RLS regardless of query shape. This hardened textual
-- allowlist is defense-in-depth (Gate 2): it now (a) inspects commas inside the
-- FROM clause (not the SELECT list), (b) rejects any non-`public` schema and
-- validates the TABLE part of `public.x`, and (c) FAILS CLOSED — any identifier
-- in table position outside {threads, messages, documents, document_chunks} is
-- rejected, and a FROM clause yielding no parseable source is rejected too.
--
-- The Python mirror backend/services/sql_service.py::is_query_allowlisted uses
-- the SAME two-step shape (isolate FROM region, then scan sources) and MUST be
-- kept in lockstep with this loop.
-- Depends on: 20240301000026_harden_sql_tool_allowlist.sql,
--             20240301000025_create_user_api_keys.sql

CREATE OR REPLACE FUNCTION execute_readonly_query(
  query_text TEXT,
  max_rows INT DEFAULT 50,
  calling_user_id UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  result JSONB;
  sanitized TEXT;
  -- SEC-02 Gate 2 allowlist scratch vars
  from_region TEXT;
  region_match TEXT[];
  source_match TEXT[];
  qualifier TEXT;   -- schema part when a source is `schema.table`
  tbl TEXT;         -- resolved table name to check against the allowlist
  any_source BOOLEAN := false;
BEGIN
  -- 1. Strip leading/trailing whitespace
  sanitized := trim(query_text);

  -- 2. Block non-SELECT statements (allow CTEs with WITH)
  IF NOT (lower(sanitized) ~ '^(select|with)\s') THEN
    RAISE EXCEPTION 'Only SELECT queries are allowed';
  END IF;

  -- 3. Block dangerous keywords
  IF lower(sanitized) ~ '\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|execute|copy)\b' THEN
    RAISE EXCEPTION 'Query contains disallowed keywords';
  END IF;

  -- 3b. SEC-02 Gate 2 (D-01): hardened positive default-deny FROM-table
  -- allowlist. Inspect the inner `sanitized` SQL (NOT the wrapper). Two steps,
  -- mirroring backend/services/sql_service.py::is_query_allowlisted:
  --
  --   Step 1 — isolate each FROM-clause REGION: the text after a `from`
  --   keyword up to the next clause-terminating keyword (where/group/order/
  --   having/limit/offset/union/intersect/except/window/fetch/for), a closing
  --   paren, semicolon, or end-of-string. Each subquery has its own `from`, so
  --   a smuggled `from (select * from user_api_keys) sub` exposes the inner
  --   `from user_api_keys` region and is rejected.
  --
  --   Step 2 — within each region, a table SOURCE is the token at the region
  --   start, after a `join` keyword, or after a comma (implicit cross-join —
  --   CR-01). Each source may be schema-qualified (CR-02): only the `public`
  --   schema is allowed, and the TABLE part is checked. Any other schema (auth,
  --   storage, ...) or any non-allowlisted table is rejected. A region with no
  --   parseable source fails closed.
  --
  -- This runs BEFORE the RLS context is set, so a non-allowlisted query never
  -- reaches execution.
  FOR region_match IN
    SELECT regexp_matches(
      sanitized,
      'from(.*?)(?=\mwhere\M|\mgroup\M|\morder\M|\mhaving\M|\mlimit\M|\moffset\M|\munion\M|\mintersect\M|\mexcept\M|\mwindow\M|\mfetch\M|\mfor\M|\)|;|$)',
      'gis'
    )
  LOOP
    from_region := region_match[1];
    FOR source_match IN
      SELECT regexp_matches(
        from_region,
        '(?:^|\mjoin\M|,)\s*"?([a-z_][a-z0-9_]*)"?(?:\s*\.\s*"?([a-z_][a-z0-9_]*)"?)?',
        'gi'
      )
    LOOP
      -- source_match[1] = first identifier; source_match[2] = optional `.table`
      IF source_match[1] IS NULL OR source_match[1] = '' THEN
        CONTINUE;
      END IF;
      any_source := true;
      qualifier := lower(source_match[1]);
      IF source_match[2] IS NOT NULL AND source_match[2] <> '' THEN
        -- schema-qualified: qualifier.table — only the public schema is allowed
        IF qualifier <> 'public' THEN
          RAISE EXCEPTION 'Query references a non-public schema: %', qualifier;
        END IF;
        tbl := lower(source_match[2]);
      ELSE
        tbl := qualifier;
      END IF;
      IF tbl NOT IN ('threads', 'messages', 'documents', 'document_chunks') THEN
        RAISE EXCEPTION 'Query references a non-allowlisted table: %', tbl;
      END IF;
    END LOOP;
  END LOOP;

  -- Fail closed: a SELECT/WITH that has a FROM but yields no parseable source is
  -- a shape the allowlist cannot reason about, so it is rejected. (A SELECT with
  -- NO from at all — e.g. `select 1` — reads no table and is allowed through;
  -- the inner EXECUTE still runs under the authenticated RLS context.)
  IF lower(sanitized) ~ '\mfrom\M' AND NOT any_source THEN
    RAISE EXCEPTION 'Query FROM clause could not be validated against the allowlist';
  END IF;

  -- 4. Set RLS context so the query only sees this user's data
  PERFORM set_config('request.jwt.claim.sub', calling_user_id::text, true);
  SET LOCAL role = 'authenticated';

  -- 5. Execute with row limit
  EXECUTE format(
    'SELECT COALESCE(jsonb_agg(row_to_json(t)), ''[]''::jsonb) FROM (SELECT * FROM (%s) sub LIMIT %s) t',
    sanitized,
    max_rows
  ) INTO result;

  -- 6. Reset role
  RESET role;

  RETURN result;
END;
$$;

-- WR-04: the user_api_keys UPDATE policy in migration 025 specifies only
-- USING (auth.uid() = user_id). USING gates which existing rows are updatable;
-- WITH CHECK gates the NEW row values. Without WITH CHECK a user could write a
-- row whose user_id is someone else's (re-owning the row). Redefine the policy
-- to enforce ownership on both the old and new row. Service-role backend bypasses
-- RLS and is unaffected; this hardens the user-JWT contract.
DROP POLICY IF EXISTS "Users can update own key row" ON user_api_keys;
CREATE POLICY "Users can update own key row"
  ON user_api_keys FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
