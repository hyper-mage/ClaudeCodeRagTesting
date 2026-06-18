-- SEC-02 Gate 2 (D-01): harden execute_readonly_query with a positive,
-- default-deny FROM-table allowlist. This is the SECOND independent gate after
-- the REVOKE SELECT ON user_api_keys FROM authenticated in migration 025
-- (defense-in-depth). The allowlist excludes user_api_keys by default — any
-- table not explicitly listed is rejected.
--
-- Reconciled allowlist (RESEARCH Open Question 1, CLOSED): exactly
-- {threads, messages, documents, document_chunks} — matching QUERYABLE_SCHEMA in
-- backend/services/sql_service.py and the ALLOWED_SQL_TABLES Python set
-- (unit-tested in backend/tests/test_sql_keys_lockdown.py). NOT the RESEARCH-era
-- {documents, document_chunks, folders}: folders is navigated via the KB
-- tree/grep/glob tools (not Text-to-SQL), so it is intentionally excluded.
--
-- CREATE OR REPLACE redefines the WHOLE body, preserving every gate from
-- migration 015 verbatim (SELECT/WITH-only, dangerous-keyword block including
-- grant|revoke, RLS context via set_config + SET LOCAL role, subquery-wrap +
-- LIMIT, RESET role). The NEW allowlist loop is inserted AFTER the keyword block
-- and BEFORE SET LOCAL role, inspecting the inner `sanitized` SQL (the user's
-- query) — NOT the wrapper.
--
-- CTE handling (RESEARCH Pitfall 4): a WITH-clause name referenced as `FROM x`
-- will appear as a FROM target and be rejected (default-deny). We deliberately
-- do NOT tolerate self-referencing CTE aliases — widening the allowlist to admit
-- arbitrary CTE names would let an attacker alias a real non-allowlisted table
-- (e.g. WITH t AS (SELECT * FROM user_api_keys) SELECT * FROM t) past the gate.
-- The legitimate Text-to-SQL surface (the four advertised tables) does not rely
-- on CTE self-references, so strict default-deny preserves security without
-- breaking real queries.
-- Depends on: 20240301000015_execute_readonly_query.sql

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
  referenced_table TEXT;
  match_row TEXT[];
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

  -- 3b. SEC-02 Gate 2 (D-01): positive default-deny FROM-table allowlist.
  -- Inspect the inner `sanitized` SQL (NOT the wrapper). Every identifier
  -- following a FROM or JOIN keyword must be in the allowlist
  -- {threads, messages, documents, document_chunks}; any other table (e.g.
  -- user_api_keys, or a CTE alias) is rejected. This runs BEFORE the RLS
  -- context is set, so a non-allowlisted query never reaches execution.
  FOR match_row IN
    SELECT regexp_matches(sanitized, '(?:from|join)\s+"?([a-z_][a-z0-9_]*)', 'gi')
  LOOP
    referenced_table := lower(match_row[1]);
    IF referenced_table NOT IN ('threads', 'messages', 'documents', 'document_chunks') THEN
      RAISE EXCEPTION 'Query references a non-allowlisted table: %', referenced_table;
    END IF;
  END LOOP;

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
