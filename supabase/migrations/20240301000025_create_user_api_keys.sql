-- BYOK encrypted key store (Phase 9 — KEY-02 storage half).
-- Ciphertext-only: holds Fernet-encrypted OpenRouter keys, NEVER plaintext.
-- One key row per user (PK = user_id). Per-user own-row RLS (no public rows —
-- a user's key is NEVER visible to anyone else).
-- SEC-02 Gate 1 (D-01): SELECT is REVOKED from the `authenticated` role so the
-- Text-to-SQL tool (which runs as `authenticated`) cannot read this table even
-- under the user's own JWT. Privilege is checked BEFORE RLS, so the REVOKE
-- denies the read path outright; the own-row RLS policy is defense-in-depth.
-- The service-role backend bypasses both REVOKE and RLS and is unaffected.
-- Each migration runs as one transaction (Supabase default).
-- Depends on: auth.users (Supabase Auth)

CREATE TABLE user_api_keys (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL DEFAULT 'openrouter',
  encrypted_key TEXT NOT NULL,           -- Fernet ciphertext — NEVER plaintext
  key_version INTEGER NOT NULL DEFAULT 1, -- D-02: which master key encrypted this row
  key_label TEXT,                         -- nullable; OpenRouter display label (Phase 10)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE user_api_keys ENABLE ROW LEVEL SECURITY;

-- Own-row only — there is NO public clause; a user's key is never shared.

-- SELECT: users can see only their own key row
CREATE POLICY "Users can view own key row"
  ON user_api_keys FOR SELECT
  USING (auth.uid() = user_id);

-- INSERT: users can only create a key row they own
CREATE POLICY "Users can insert own key row"
  ON user_api_keys FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- UPDATE: users can only update their own key row
CREATE POLICY "Users can update own key row"
  ON user_api_keys FOR UPDATE
  USING (auth.uid() = user_id);

-- DELETE: users can only delete their own key row
CREATE POLICY "Users can delete own key row"
  ON user_api_keys FOR DELETE
  USING (auth.uid() = user_id);

-- SEC-02 Gate 1 (D-01): revoke the SQL-tool read path entirely.
-- Table-level privilege is enforced BEFORE RLS, so this denies any SELECT by the
-- `authenticated` role regardless of RLS — the Text-to-SQL tool cannot read the
-- keys table even for the calling user's own row. The service-role backend is
-- unaffected (it bypasses RLS and table grants by design).
REVOKE SELECT ON user_api_keys FROM authenticated;
