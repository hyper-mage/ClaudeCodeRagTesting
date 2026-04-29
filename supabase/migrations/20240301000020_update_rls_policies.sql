-- Replace single-user RLS policies with mixed-visibility policies (Phase 1, per D-03, D-12).
-- DROP + CREATE in same transaction to avoid zero-policy window.
-- Supabase runs each migration file as a single transaction by default.
-- Depends on: 019_add_visibility_and_folder.sql (visibility column)

-- ============================================================================
-- DOCUMENTS TABLE: Drop all 4 existing policies
-- ============================================================================
DROP POLICY IF EXISTS "Users can select own documents" ON documents;
DROP POLICY IF EXISTS "Users can insert own documents" ON documents;
DROP POLICY IF EXISTS "Users can update own documents" ON documents;
DROP POLICY IF EXISTS "Users can delete own documents" ON documents;

-- ============================================================================
-- DOCUMENTS TABLE: Create 4 new mixed-visibility policies
-- ============================================================================

-- SELECT: own rows OR public rows (per D-03)
CREATE POLICY "Users can view own or public documents"
  ON documents FOR SELECT
  USING (auth.uid() = user_id OR visibility = 'public');

-- INSERT: users insert their own rows only (visibility defaults to 'private')
CREATE POLICY "Users can insert own documents"
  ON documents FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- UPDATE: users can only update their own private rows (not public KB)
CREATE POLICY "Users can update own documents"
  ON documents FOR UPDATE
  USING (auth.uid() = user_id AND visibility = 'private');

-- DELETE: users can only delete their own private rows (not public KB)
CREATE POLICY "Users can delete own documents"
  ON documents FOR DELETE
  USING (auth.uid() = user_id AND visibility = 'private');

-- ============================================================================
-- DOCUMENT_CHUNKS TABLE: Drop all 3 existing policies
-- ============================================================================
DROP POLICY IF EXISTS "Users can select own chunks" ON document_chunks;
DROP POLICY IF EXISTS "Users can insert own chunks" ON document_chunks;
DROP POLICY IF EXISTS "Users can delete own chunks" ON document_chunks;

-- ============================================================================
-- DOCUMENT_CHUNKS TABLE: Create 3 new mixed-visibility policies
-- ============================================================================

-- SELECT: own chunks OR public chunks (per D-03)
CREATE POLICY "Users can view own or public chunks"
  ON document_chunks FOR SELECT
  USING (auth.uid() = user_id OR visibility = 'public');

-- INSERT: users insert their own chunks only
CREATE POLICY "Users can insert own chunks"
  ON document_chunks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- DELETE: users can only delete their own private chunks
CREATE POLICY "Users can delete own chunks"
  ON document_chunks FOR DELETE
  USING (auth.uid() = user_id AND visibility = 'private');
