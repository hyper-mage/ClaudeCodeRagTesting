-- Module 7: Safe read-only SQL execution for Text-to-SQL tool
-- Executes arbitrary SELECT queries with RLS enforcement and row limits

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
