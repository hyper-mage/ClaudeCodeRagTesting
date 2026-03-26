-- Keyword search RPC function for hybrid search (Module 6)

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
  WHERE dc.user_id = filter_user_id
    AND dc.content_tsv @@ websearch_to_tsquery('english', search_query)
    AND (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
  ORDER BY rank DESC
  LIMIT match_count;
END;
$$;
