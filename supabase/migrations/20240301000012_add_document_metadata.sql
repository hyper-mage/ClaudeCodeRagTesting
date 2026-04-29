-- 1. Add metadata JSONB column to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- 2. GIN index on document_chunks.metadata for @> containment queries
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata
ON document_chunks USING GIN (metadata);

-- 3. Drop old function signature to avoid PostgREST overload ambiguity
DROP FUNCTION IF EXISTS match_document_chunks(vector, int, uuid);

-- 4. Create RPC with optional filter_metadata parameter
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
  WHERE dc.user_id = filter_user_id
    AND (filter_metadata IS NULL OR dc.metadata @> filter_metadata)
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
