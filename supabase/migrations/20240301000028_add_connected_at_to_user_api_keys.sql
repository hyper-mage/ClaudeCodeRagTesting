-- Phase 10 (KEY-03/KEY-04) — add an explicit connected_at timestamp to
-- user_api_keys. Backs the "Connected since {date}" display on /settings (KEY-03)
-- and re-stamps on reconnect (KEY-04).
--
-- WHY EXPLICIT (not a DEFAULT): the exchange handler upserts on PK = user_id
-- (one key per user). Postgres ON CONFLICT DO UPDATE does NOT re-apply column
-- defaults, so a nullable column with `DEFAULT now()` would only stamp on the
-- first-ever INSERT and keep the original value on every reconnect-UPDATE. The
-- exchange upsert therefore sets connected_at EXPLICITLY to now() so "connected
-- since" tracks the latest connect/reconnect (Pitfall 4). The column is nullable
-- with NO default — the application owns the value.
--
-- WHY A NEW MIGRATION (028): migrations 025/026/027 are ALREADY APPLIED to dev.
-- Editing them does not re-run. A forward additive migration is the only
-- mechanism. 028 is the next free number after the Phase 9 set (025/026/027).
--
-- key_label (the masked-tail display column) ALREADY EXISTS from migration 025 —
-- DO NOT re-add it here.
--
-- SEC-02 lockdown (Phase 9) is UNCHANGED and must stay so: this migration adds
-- NO grant (the migration-025 `REVOKE SELECT ON user_api_keys FROM authenticated`
-- stays in force), touches NO RLS policy, and touches NO FROM-table allowlist
-- (migrations 026/027). user_api_keys remains unreachable by the Text-to-SQL tool.
-- Additive + nullable: forward-compatible with the live (empty) table.
-- Depends on: 20240301000025_create_user_api_keys.sql

ALTER TABLE user_api_keys
  ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ;
