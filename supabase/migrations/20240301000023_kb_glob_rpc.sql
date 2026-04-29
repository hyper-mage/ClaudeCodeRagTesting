-- RPC function for glob-style pattern matching across documents in the knowledge base.
-- Matches documents by their full path (folder hierarchy + filename) using LIKE.
-- Glob patterns: * -> %, ? -> _ for SQL LIKE conversion.
-- Results filtered by visibility (public + user-owned).
-- Depends on: 018_create_folders_table.sql (folders with ltree), 019_add_visibility_and_folder.sql

CREATE OR REPLACE FUNCTION kb_glob_match(
  glob_pattern TEXT,
  filter_user_id UUID,
  match_limit INT DEFAULT 50
)
RETURNS TABLE (
  document_id UUID,
  filename TEXT,
  file_size BIGINT,
  folder_name TEXT,
  folder_path ltree,
  full_path TEXT
)
LANGUAGE plpgsql AS $$
DECLARE
  like_pattern TEXT;
BEGIN
  -- Convert glob to LIKE pattern: * -> %, ? -> _
  like_pattern := glob_pattern;
  like_pattern := replace(like_pattern, '*', '%');
  like_pattern := replace(like_pattern, '?', '_');

  RETURN QUERY
  WITH RECURSIVE folder_paths AS (
    -- Base case: root folders (no parent)
    SELECT
      fld.id,
      fld.name,
      fld.path,
      fld.parent_id,
      fld.name AS display_path
    FROM folders fld
    WHERE fld.parent_id IS NULL

    UNION ALL

    -- Recursive case: child folders
    SELECT
      child.id,
      child.name,
      child.path,
      child.parent_id,
      fp.display_path || '/' || child.name AS display_path
    FROM folders child
    JOIN folder_paths fp ON child.parent_id = fp.id
  )
  SELECT
    d.id AS document_id,
    d.filename,
    d.file_size,
    fp.name AS folder_name,
    fp.path AS folder_path,
    fp.display_path || '/' || d.filename AS full_path
  FROM documents d
  JOIN folder_paths fp ON d.folder_id = fp.id
  WHERE (fp.display_path || '/' || d.filename) ILIKE like_pattern
    AND (d.user_id = filter_user_id OR d.visibility = 'public')
    AND d.status = 'completed'
  ORDER BY full_path
  LIMIT match_limit;
END;
$$;
