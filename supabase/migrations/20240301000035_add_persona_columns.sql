-- Phase 17 — persona pin columns (additive, single transaction; mirrors migration 032's
-- threads.model add). TWO additive statements, no backfill, no destructive change:
--   (1) threads.persona            — per-thread persona pin (nullable).
--   (2) user_preferences.default_persona — the user-level persona (nullable).
--
-- Both columns are plain nullable TEXT with no backfill: existing threads and
-- preference rows keep NULL and resolve to the system fallback persona via the
-- resolver tier chain (D-08). They are DELIBERATELY unconstrained — no validity
-- constraint and no foreign key — because a persona id that is later removed from the
-- code registry must still persist and resolve to the system fallback, never raise
-- (D-10); validation lives at read time in the resolver (17-06), not the DB.
-- No new row-level policy is added: the own-row RLS already on threads and
-- user_preferences (migration 032) covers every column of the row, so a new column
-- inherits it automatically.
--
-- This file is authored by Plan 17-05; it is APPLIED by the [BLOCKING] Plan 17-08 (`db push`).
-- Depends on: threads, user_preferences (migration 032).

ALTER TABLE threads ADD COLUMN persona TEXT;
ALTER TABLE user_preferences ADD COLUMN default_persona TEXT;
