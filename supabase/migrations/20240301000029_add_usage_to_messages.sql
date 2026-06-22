-- Add usage JSONB column to messages table for persisting OpenRouter usage/cost.
-- Stores the summed OpenRouter `usage` dict for an assistant turn (prompt/completion/
-- total tokens + `cost`), accumulated across all tool-loop iterations of the turn.
-- Persisted by Phase 11 (per-request key/model resolution chat-loop seam, D-04);
-- read + rendered by Phase 14 (usage/cost display) — no re-plumbing needed there.
--
-- Additive nullable, no backfill: existing rows keep usage = NULL. The column inherits
-- the existing per-user messages RLS (migration 002) unchanged, so a user only ever reads
-- their own usage. No key, prompt body, or other secret is stored here. IF NOT EXISTS makes
-- the migration idempotent for safe `db push` replay. Applied to DEV this phase; prod is
-- deferred to deploy (D-03 dual-env discipline).

ALTER TABLE messages ADD COLUMN IF NOT EXISTS usage JSONB DEFAULT NULL;
