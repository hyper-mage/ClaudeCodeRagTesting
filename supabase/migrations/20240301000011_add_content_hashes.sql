-- File-level content hash (SHA-256 of raw file bytes)
ALTER TABLE documents ADD COLUMN content_hash TEXT;

-- Chunk-level content hash (SHA-256 of chunk text)
ALTER TABLE document_chunks ADD COLUMN content_hash TEXT;

-- Unique index: same user can't have two documents with identical content
-- Partial index (WHERE NOT NULL) so existing rows without hashes are unaffected
CREATE UNIQUE INDEX idx_documents_user_content_hash
  ON documents (user_id, content_hash)
  WHERE content_hash IS NOT NULL;

-- Index for fast chunk hash lookups during incremental updates
CREATE INDEX idx_chunks_content_hash
  ON document_chunks (document_id, content_hash);
