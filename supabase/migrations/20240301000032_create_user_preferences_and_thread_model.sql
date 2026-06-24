-- Phase 13 — preferences + per-thread model (additive, single transaction).
-- THREE additive statements, no backfill, no destructive change to existing data:
--   (1) user_preferences table + own-row RLS (per-user default_model + theme).
--   (2) threads.model nullable column (per-thread model pin; resolves via the
--       default tier when null — D-05).
--   (3) widen the messages.role CHECK to allow the persisted deprecation 'notice'
--       row (D-06) alongside 'user' / 'assistant'.
-- Each migration runs as one transaction (Supabase default).
-- Depends on: auth.users (Supabase Auth), threads, messages.
-- This file is authored by Plan 13-01; it is APPLIED by Plan 13-02 (`db push`).

-- =====================================================================
-- (1) user_preferences — one row per user (PK = user_id). Own-row RLS.
-- =====================================================================
-- Non-secret, unlike user_api_keys: we DELIBERATELY do NOT REVOKE SELECT from
-- `authenticated` (T-13-03 accept) — preferences carry no key material, so the
-- SQL-tool read path does not need to be sealed here. Own-row RLS is the only
-- isolation needed (T-13-02 mitigate).
-- default_model is intentionally NOT a FK to model_cache (D-06): a model can be
-- deprecated and disappear from the cache while a user's pin must persist as a
-- plain string (so the deprecation-fallback notice can fire instead of a FK error).
CREATE TABLE user_preferences (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  default_model TEXT,                       -- nullable: null = owner default (D-05); NOT a FK (D-06)
  theme TEXT NOT NULL DEFAULT 'dark'        -- invalid-theme poisoning backstop (T-13-01)
    CHECK (theme IN ('light','dark')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Own-row only — there is NO public clause; a user's preferences are their own.
-- Mirrors the user_api_keys own-row policy set (auth.uid() = user_id on all ops).

-- SELECT: users can see only their own preferences row
CREATE POLICY "Users can view own preferences row"
  ON user_preferences FOR SELECT
  USING (auth.uid() = user_id);

-- INSERT: users can only create a preferences row they own
CREATE POLICY "Users can insert own preferences row"
  ON user_preferences FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- UPDATE: users can only update their own preferences row
CREATE POLICY "Users can update own preferences row"
  ON user_preferences FOR UPDATE
  USING (auth.uid() = user_id);

-- DELETE: users can only delete their own preferences row
CREATE POLICY "Users can delete own preferences row"
  ON user_preferences FOR DELETE
  USING (auth.uid() = user_id);

-- =====================================================================
-- (2) threads.model — per-thread model pin (nullable, no DEFAULT, no backfill).
-- =====================================================================
-- Existing threads keep model = NULL and resolve through the default tier (D-05).
-- Inherits the existing own-row threads RLS automatically (no new policy needed).
ALTER TABLE threads ADD COLUMN model TEXT;

-- =====================================================================
-- (3) messages.role — widen the CHECK to allow the deprecation 'notice' row.
-- =====================================================================
-- Migration 000002 created an INLINE unnamed CHECK (role in ('user','assistant'))
-- which Postgres auto-names `messages_role_check`. Drop and re-add it as an
-- explicit allowlist that adds 'notice' — the persisted deprecation-fallback line
-- (D-06), rendered as a system line and EXCLUDED from the LLM history map.
ALTER TABLE messages DROP CONSTRAINT messages_role_check;
ALTER TABLE messages ADD CONSTRAINT messages_role_check
  CHECK (role in ('user', 'assistant', 'notice'));
