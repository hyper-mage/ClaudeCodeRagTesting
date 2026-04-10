-- RPC function for regex search across document chunks in the knowledge base.
-- Searches chunk content using PostgreSQL's ~* operator (case-insensitive POSIX regex).
-- Results include file path context and are filtered by visibility (public + user-owned).
-- Depends on: 019_add_visibility_and_folder.sql (visibility columns), 018_create_folders_table.sql (folders)

CREATE OR REPLACE FUNCTION kb_grep_regex(
  pattern TEXT,
  filter_user_id UUID,
  search_path TEXT DEFAULT NULL,
  match_limit INT DEFAULT 20
)
RETURNS TABLE (
  document_id UUID,
  chunk_id UUID,
  content TEXT,
  chunk_index INT,
  filename TEXT,
  folder_name TEXT,
  folder_path ltree
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.document_id,
    dc.id AS chunk_id,
    dc.content,
    dc.chunk_index,
    d.filename,
    f.name AS folder_name,
    f.path AS folder_path
  FROM document_chunks dc
  JOIN documents d ON dc.document_id = d.id
  LEFT JOIN folders f ON d.folder_id = f.id
  WHERE dc.content ~* pattern
    AND (dc.user_id = filter_user_id OR dc.visibility = 'public')
    AND (search_path IS NULL OR f.path <@ search_path::ltree)
  ORDER BY d.filename, dc.chunk_index
  LIMIT match_limit;

EXCEPTION WHEN invalid_regular_expression THEN
  RAISE EXCEPTION 'Invalid regex pattern: %', pattern;
END;
$$;
