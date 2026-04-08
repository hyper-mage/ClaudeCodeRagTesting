-- Update search RPCs to return both user's private chunks AND public default KB chunks (Phase 1, per D-13).
-- Depends on: 019_add_visibility_and_folder.sql (visibility column on document_chunks)

-- ============================================================================
-- match_document_chunks: Drop old signature then recreate with visibility filter
-- ============================================================================

-- Drop old function signature to avoid PostgREST overload ambiguity
-- (same pattern as migration 012)
DROP FUNCTION IF EXISTS match_document_chunks(vector, int, uuid, jsonb);

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

-- ============================================================================
-- keyword_search_chunks: Recreate with visibility filter
-- ============================================================================

CREATE OR REPLACE FUNCTION keyword_search_chunks(
  search_query TEXT,
  match_count INT DEFAULT 20,
  filter_user_id UUID DEFAULT NULL,
  filter_metadata JSONB DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  document_id UUID,
  content TEXT,
  chunk_index INT,
  rank FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.id,
    dc.document_id,
    dc.content,
    dc.chunk_index,
    ts_rank_cd(dc.content_tsv, websearch_to_tsquery('english', search_query))::FLOAT AS rank
  FROM document_chunks dc
  WHERE (dc.user_id = filter_user_id OR dc.visibility = 'public')
    AND dc.content_tsv @@ websearch_to_tsquery('english', search_query)
    AND (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;

-- ============================================================================
-- execute_readonly_query: No changes needed
-- ============================================================================

-- NOTE: execute_readonly_query (migration 015) already enforces RLS via
-- SET LOCAL role = 'authenticated' + set_config('request.jwt.claim.sub', ...).
-- The updated RLS policies from migration 020 automatically apply to queries
-- executed through this function. No changes needed to the function body.
-- Per D-04: visibility is enforced by the updated RLS policies on documents
-- and document_chunks tables.
