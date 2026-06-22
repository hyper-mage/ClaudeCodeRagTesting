---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 02
subsystem: database
tags: [supabase, migration, messages, usage-accounting, byok, dual-env]

# Dependency graph
requires: []
provides:
  - "messages.usage — additive nullable JSONB column on the messages table (D-04), applied LIVE to the dev Supabase project"
affects: [11-04, phase-14]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive nullable JSONB column, IF NOT EXISTS guard for idempotent db push replay"
    - "Dual-env discipline: apply to dev only; prod deferred to deploy (D-03)"

key-files:
  created:
    - supabase/migrations/20240301000029_add_usage_to_messages.sql
  modified: []

requirements-completed: [DEMO-03]
---

# Plan 11-02 Summary — Migration 029: usage column on messages

**Tasks:** 2/2 complete (Task 1 autonomous; Task 2 human-action checkpoint — dev push)

## What shipped
- **`supabase/migrations/20240301000029_add_usage_to_messages.sql`** (NEW): a single additive
  `ALTER TABLE messages ADD COLUMN IF NOT EXISTS usage JSONB DEFAULT NULL;`. Mirrors the
  `024_add_tools_used` shape (same table, same additive-nullable-JSONB pattern, no backfill);
  `IF NOT EXISTS` guard for idempotent `db push` replay (per the 028 precedent). Leading comment
  documents: additive nullable, old rows keep `usage = NULL`, inherits the existing messages RLS
  (migration 002 unchanged), persisted by Phase 11 / read by Phase 14 (D-04).
- **Live dev apply:** `supabase db push` applied migration 029 to the **dev** Supabase project
  (ntkkmljbariflblldmha). Prod deferred to deploy (D-03 dual-env discipline) — NOT touched.

## Verification
- Task 1 (automated): `test -f` + `grep -qE "ADD COLUMN IF NOT EXISTS usage"` → MIGRATION_OK;
  `grep -cE "DROP|POLICY|user_api_keys"` → 0 (no RLS/other-table changes); 029 is the next free number.
- Task 2 (human-action checkpoint): user applied the migration to dev. Column presence confirmed
  authoritatively via the backend dev service-role client — `db.table('messages').select('usage')`
  succeeded (a missing column would raise PostgREST 42703). The `usage` column is PRESENT on dev,
  proving the push reached 029 (not a half-applied short-circuit). Existing messages RLS intact;
  prod untouched.

## Notes for the orchestrator
- **Requirements completed:** DEMO-03 (provides the durable `messages.usage` column that plan 11-04's
  fail-closed resolution path persists captured usage into).
- Plan 11-04 (Wave 3) can now persist the summed OpenRouter `usage` object to a real column —
  no false-positive verification state.
- **Threat model honored:** migration touches no RLS policy, no `user_api_keys` table, no Phase 9
  SEC-02 lockdown (T-11-04); stored `usage` is token counts + cost only, no secret (T-11-05);
  dev-only apply, prod deferred (T-11-06).
