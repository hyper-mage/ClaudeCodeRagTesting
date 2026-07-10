-- Global key/value app settings table (Phase 11-06, SEC-01 runtime LangSmith toggle).
-- Generic (key text PK, value jsonb, updated_at) so future global flags reuse it;
-- seeded with the langsmith_enabled=true master-toggle row read once per chat turn
-- (~15s TTL cache) by backend/services/app_settings_service.py.
--
-- RLS is enabled DELIBERATELY WITHOUT any anon/authenticated policy statements:
-- deny-by-default means ordinary clients read/write ZERO rows. Only the backend
-- service-role client (which bypasses RLS) reads the flag, and the owner flips it
-- in the Supabase SQL editor:
--   UPDATE app_settings SET value='false'::jsonb, updated_at=now() WHERE key='langsmith_enabled';
--   UPDATE app_settings SET value='true'::jsonb,  updated_at=now() WHERE key='langsmith_enabled';
-- This satisfies the all-tables-need-RLS rule for a GLOBAL (non-user-scoped) table.
--
-- Idempotent (IF NOT EXISTS + ON CONFLICT DO NOTHING) for safe `db push` replay.
-- Applied to DEV this phase; prod is deferred to deploy (D-03 dual-env discipline).

CREATE TABLE IF NOT EXISTS app_settings (
    key text PRIMARY KEY,
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Seed the master toggle ON (default-on mirrors the service's fail-safe default).
INSERT INTO app_settings (key, value)
VALUES ('langsmith_enabled', 'true'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- Deny-by-default: enable RLS and add NO policies (service-role access only).
ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;
