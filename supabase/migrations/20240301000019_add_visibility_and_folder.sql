-- Add visibility and folder_id columns to existing tables for mixed-visibility KB support (Phase 1).
-- Depends on: 018_create_folders_table.sql (folders table with ltree paths)
-- Per decisions D-07, D-10, D-11 from 01-CONTEXT.md

-- Add folder_id FK (nullable -- existing docs have no folder per D-11)
ALTER TABLE documents
  ADD COLUMN folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;

-- Add visibility column (defaults to 'private' per D-11)
ALTER TABLE documents
  ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private'));

-- Add visibility column to document_chunks (denormalized per D-10)
ALTER TABLE document_chunks
  ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private'));

-- Indexes for visibility-filtered queries
CREATE INDEX idx_documents_folder_id ON documents (folder_id);
CREATE INDEX idx_documents_visibility ON documents (visibility);
CREATE INDEX idx_chunks_visibility ON document_chunks (visibility);

-- Trigger: sync visibility from documents to chunks on UPDATE (per RESEARCH.md "Don't Hand-Roll" section)
CREATE OR REPLACE FUNCTION sync_chunk_visibility()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.visibility IS DISTINCT FROM OLD.visibility THEN
    UPDATE document_chunks
    SET visibility = NEW.visibility
    WHERE document_id = NEW.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sync_chunk_visibility
  AFTER UPDATE OF visibility ON documents
  FOR EACH ROW
  EXECUTE FUNCTION sync_chunk_visibility();

-- Trigger: set chunk visibility from parent document on INSERT
-- Ensures consistency if chunks are bulk-inserted without explicit visibility
CREATE OR REPLACE FUNCTION set_chunk_visibility_on_insert()
RETURNS TRIGGER AS $$
BEGIN
  NEW.visibility := (SELECT visibility FROM documents WHERE id = NEW.document_id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_set_chunk_visibility
  BEFORE INSERT ON document_chunks
  FOR EACH ROW
  EXECUTE FUNCTION set_chunk_visibility_on_insert();
