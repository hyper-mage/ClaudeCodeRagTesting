-- Folders table for hierarchical document organization using ltree materialized paths.
-- Supports unlimited nesting depth with GiST-indexed path queries.
-- RLS policies enforce mixed visibility: users see their own folders + public folders.
-- Depends on: 016_enable_ltree.sql (ltree extension), 017_create_system_user.sql (system user)

CREATE TABLE folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id),
  name TEXT NOT NULL,
  path ltree NOT NULL,
  parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
  visibility TEXT NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('public', 'private')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT unique_path_per_user UNIQUE (user_id, path)
);

-- Indexes for efficient tree traversal and lookups
CREATE INDEX idx_folders_path_gist ON folders USING GIST (path);
CREATE INDEX idx_folders_user_id ON folders (user_id);
CREATE INDEX idx_folders_parent_id ON folders (parent_id);

-- Enable Row Level Security
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;

-- SELECT: users see their own folders AND public folders (default KB)
CREATE POLICY "Users can view own or public folders"
  ON folders FOR SELECT
  USING (auth.uid() = user_id OR visibility = 'public');

-- INSERT: users can only create folders they own
CREATE POLICY "Users can insert own folders"
  ON folders FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- UPDATE: users can only update their own private folders (not public KB)
CREATE POLICY "Users can update own folders"
  ON folders FOR UPDATE
  USING (auth.uid() = user_id AND visibility = 'private');

-- DELETE: users can only delete their own private folders (not public KB)
CREATE POLICY "Users can delete own folders"
  ON folders FOR DELETE
  USING (auth.uid() = user_id AND visibility = 'private');

-- Seed the default KB root folder: "Board Games"
-- Owned by the system user, visible to all authenticated users.
-- Uses a deterministic UUID so Phase 2 can reference it for seeding game subfolders.
INSERT INTO folders (id, user_id, name, path, parent_id, visibility)
VALUES (
  'a0000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'Board Games',
  'board_games',
  NULL,
  'public'
);
