-- Fix: change VECTOR(1536) to VECTOR(2048)
-- No vector index — pgvector on Supabase limits indexes to 2000 dims.
-- Sequential scan is fine for small-to-medium document sets.

-- Drop ALL indexes on the embedding column
DO $$
DECLARE
    idx RECORD;
BEGIN
    FOR idx IN
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'document_chunks'
        AND indexdef LIKE '%embedding%'
    LOOP
        EXECUTE 'DROP INDEX IF EXISTS ' || idx.indexname;
    END LOOP;
END $$;

-- Alter column to 2048 dimensions
ALTER TABLE document_chunks ALTER COLUMN embedding TYPE VECTOR(2048);
