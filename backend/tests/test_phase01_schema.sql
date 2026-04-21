-- Phase 01: Data Foundation & Schema — Regression Test Queries
-- Run against Supabase SQL Editor to verify schema integrity after migrations 016-021

-- 1. ltree extension exists
SELECT * FROM pg_extension WHERE extname = 'ltree';

-- 2. System user created with correct fields
SELECT id, email, aud FROM auth.users WHERE email = 'default-kb@system.internal';
-- Expect: id = 00000000-0000-0000-0000-000000000000, aud = 'authenticated'

-- 3. Board Games root folder seeded
SELECT * FROM folders WHERE name = 'Board Games';
-- Expect: visibility = 'public', path = 'board_games', user_id = 00000000-...

-- 4. ltree query works
SELECT * FROM folders WHERE path <@ 'board_games';
-- Expect: at least 1 row (the root folder)

-- 5. New columns on documents
SELECT column_name FROM information_schema.columns
WHERE table_name = 'documents' AND column_name IN ('folder_id', 'visibility');
-- Expect: 2 rows

-- 6. New column on document_chunks
SELECT column_name FROM information_schema.columns
WHERE table_name = 'document_chunks' AND column_name = 'visibility';
-- Expect: 1 row

-- 7. RLS policies replaced (mixed visibility)
SELECT policyname, tablename, cmd FROM pg_policies
WHERE tablename IN ('documents', 'document_chunks', 'folders')
ORDER BY tablename, cmd;
-- Expect: SELECT policies contain 'public' visibility logic

-- 8. Visibility sync trigger exists
SELECT trigger_name, event_object_table FROM information_schema.triggers
WHERE trigger_name IN ('trg_sync_chunk_visibility', 'trg_set_chunk_visibility');
-- Expect: 2 rows

-- 9. Search RPCs exist with correct signatures
SELECT routine_name FROM information_schema.routines
WHERE routine_name IN ('match_document_chunks', 'keyword_search_chunks', 'execute_readonly_query');
-- Expect: 3 rows
