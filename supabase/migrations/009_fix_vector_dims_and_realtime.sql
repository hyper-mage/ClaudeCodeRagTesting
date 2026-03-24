-- Fix vector dimensions for Nemotron embedding model (2048 instead of 1536)
-- Drop the existing index first
DROP INDEX IF EXISTS document_chunks_embedding_idx;

-- Alter the column to use VECTOR(2048)
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE VECTOR(2048);

-- Recreate the index
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Update the match function to use VECTOR(2048)
CREATE OR REPLACE FUNCTION match_document_chunks(
  query_embedding VECTOR(2048),
  match_count INT DEFAULT 5,
  filter_user_id UUID DEFAULT NULL
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
  ORDER BY dc.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- Enable Realtime on the documents table
ALTER PUBLICATION supabase_realtime ADD TABLE documents;
