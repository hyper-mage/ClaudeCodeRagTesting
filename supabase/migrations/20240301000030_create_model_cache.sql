-- Global OpenRouter model catalog cache (Phase 12 — MODEL-01 persistence half).
-- GLOBAL shared, non-user-scoped, non-secret catalog. Every authenticated user
-- sees the SAME list (no per-user rows). Data lives in Postgres so it survives
-- Fly suspend / cold starts — process memory does not (D-05).
--
-- Row-per-model shape (PK = model_id) over a single JSON-blob row: enables
-- SQL-side `?free_only` filtering, per-model indexing, and per-model upsert
-- without read-modify-write races. Raw OpenRouter pricing strings are retained
-- verbatim in `pricing` (D-10). The whole table shares one logical fetch time:
-- every refresh rewrites all rows in one batch and restamps `fetched_at`, which
-- acts as the staleness marker (`SELECT max(fetched_at)` / `count==0` → stale).
--
-- RLS posture — the INVERSE of migration 025's own-row `user_api_keys` pattern:
--   user_api_keys is OWN-ROW (USING auth.uid() = user_id) + REVOKE SELECT because
--   it holds secrets. model_cache is the mirror image — GLOBAL, non-secret,
--   identical for every user → ONE permissive SELECT policy (USING (true)) and
--   crucially NO INSERT/UPDATE/DELETE policy for `authenticated`. With RLS enabled
--   and no write policy, RLS denies ALL client writes by default — a client cannot
--   poison the model list (T-12-V4-01). The service-role backend
--   (database.get_supabase()) bypasses RLS and owns ALL writes.
--
-- Each migration runs as one transaction (Supabase default). Additive — no backfill.
-- Applied to DEV this phase; prod is deferred to deploy (D-03 dual-env discipline).

CREATE TABLE model_cache (
  model_id         TEXT PRIMARY KEY,                  -- OpenRouter `id` (e.g. openai/gpt-4o-mini)
  name             TEXT NOT NULL,
  context_length   INTEGER,                           -- nullable-defensive (docs allow null; live data int)
  pricing          JSONB NOT NULL,                    -- raw OpenRouter pricing strings (D-10 keeps raw)
  is_free          BOOLEAN NOT NULL DEFAULT false,    -- precomputed at write → enables SQL-side ?free_only
  raw              JSONB,                             -- optional: full raw model object for future fields
  fetched_at       TIMESTAMPTZ NOT NULL DEFAULT now() -- staleness marker, restamped every refresh
);

-- GLOBAL shared catalog — NOT user-scoped. Read-only to clients; only service-role writes.
ALTER TABLE model_cache ENABLE ROW LEVEL SECURITY;

-- Public read: every authenticated user sees the same catalog (shared, no per-user rows).
CREATE POLICY "Anyone can read model catalog"
  ON model_cache FOR SELECT
  USING (true);

-- No INSERT/UPDATE/DELETE policy for `authenticated` → RLS denies client writes by default
-- (T-12-V4-01). The service-role backend (database.get_supabase()) bypasses RLS and owns
-- all writes. A logged-in client — including the Text-to-SQL tool — cannot poison the list.
