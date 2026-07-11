---
phase: 13-preferences-per-thread-model
plan: 02
status: complete
autonomous: false
checkpoint: human-action (resolved automation-first)
requirements_completed: [MODEL-05, MODEL-06, PREF-02]
key_files:
  created: []
  modified: []
  applied:
    - supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql
---

# 13-02 SUMMARY — [BLOCKING] Apply migration 000032 to dev Supabase

**Result:** Migration `20240301000032_create_user_preferences_and_thread_model.sql` applied LIVE to the dev Supabase project (`ntkkmljbariflblldmha`, the `.env` project — prod untouched, deferred to deploy per Phase 9/10/12 convention).

## Apply path used
**Clean CLI `supabase db push`** — no `migration repair` required.

- Pre-apply `supabase migration list` showed remote in sync through `...000031`, with `...000032` pending (Local set / Remote empty). Because remote history was already consistent, the known replay / `42P07 already-exists` caveat (RESEARCH Pitfall 1 + MEMORY migration-repair note) did **not** trigger — no repair of the prior range was needed.
- `supabase db push` (CLI authed via stored session; confirmation auto-answered) applied only `...000032`. Exit 0, "Finished supabase db push."
- Post-apply `supabase migration list` shows `000032` in both Local and Remote columns; `supabase db push --dry-run` → "Remote database is up to date".

## Probe results
Supabase migrations apply transactionally (a single failing statement rolls back the whole file), so the clean `db push` success is positive proof that every statement in `000032` landed:
- `user_preferences` table created (PK `user_id` → `auth.users`, `default_model` nullable, `theme NOT NULL DEFAULT 'dark' CHECK theme IN ('light','dark')`, timestamps).
- `user_preferences` RLS enabled + 4 own-row policies (`auth.uid() = user_id`); no `REVOKE SELECT` (non-secret).
- `threads.model` column added (nullable, no backfill).
- `messages_role_check` widened to `('user','assistant','notice')`.

## Prod runbook (for deploy)
At prod deploy, apply `000032` to the prod project (`.env.prod`) the same way: confirm prod migration history is in sync first (`supabase migration list` against the prod link), then `supabase db push`. If prod history is out of sync, `supabase migration repair --status applied <range-through-000031>` before pushing only `000032`. Dashboard SQL-editor application of the single file is the established fallback if the CLI can't run non-interactively.

## Gate
Schema is genuinely live (not just type-checkable) — Plans 13-03 (endpoints) and 13-04 (deprecation fallback) now read/write real data instead of the pre-P13 tolerant-fallback path. No regression to the Phase 9 SEC-02 lockdown (additive only; does not touch `user_api_keys` grants or the SQL-tool allowlist).
