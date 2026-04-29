-- Add full-text search support to document_chunks for hybrid search (Module 6)

-- 1. Add tsvector column
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_tsv tsvector;

-- 2. Backfill existing chunks
UPDATE document_chunks SET content_tsv = to_tsvector('english', content) WHERE content_tsv IS NULL;

-- 3. GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_tsv ON document_chunks USING GIN (content_tsv);

-- 4. Trigger to auto-populate on INSERT/UPDATE
CREATE OR REPLACE FUNCTION document_chunks_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.content_tsv := to_tsvector('english', NEW.content);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_document_chunks_tsv ON document_chunks;
CREATE TRIGGER trg_document_chunks_tsv
  BEFORE INSERT OR UPDATE OF content ON document_chunks
  FOR EACH ROW EXECUTE FUNCTION document_chunks_tsv_trigger();
