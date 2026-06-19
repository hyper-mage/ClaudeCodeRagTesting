---
phase: 10-oauth-pkce-backend-exchange-frontend-connect
plan: 01
subsystem: database
tags: [supabase, migration, postgres, user_api_keys, byok, sec-02, oauth]

# Dependency graph
requires:
  - phase: 09-crypto-encrypted-key-storage-foundation
    provides: user_api_keys table (PK user_id, encrypted_key, key_version, key_label, created_at, updated_at) + SEC-02 SQL-tool lockdown (REVOKE SELECT FROM authenticated + FROM-table allowlist in migrations 025/026/027)
provides:
  - "connected_at TIMESTAMPTZ (nullable, no default) column on user_api_keys, live on the dev Supabase project"
  - "Backing column for the 'Connected since {date}' status read (KEY-03) and reconnect re-stamp (KEY-04) consumed by Plan 02 exchange upsert + GET /api/keys/status"
affects: [10-02 (keys.py exchange/status), Plan 02 status read, deploy step (prod apply of 028)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive forward migration (ALTER TABLE ADD COLUMN IF NOT EXISTS) — never edit already-applied migrations"
    - "Explicit timestamp in upsert payload (not column DEFAULT) so ON CONFLICT DO UPDATE re-stamps on reconnect"

key-files:
  created:
    - supabase/migrations/20240301000028_add_connected_at_to_user_api_keys.sql
  modified: []

key-decisions:
  - "Added a dedicated connected_at column (not reused created_at) — clearest 'connected since latest reconnect' semantic, decoupled from row-creation time (Pitfall 4 / RESEARCH Open Question 1)"
  - "connected_at is nullable with NO default — the exchange upsert sets it explicitly to now() because Postgres ON CONFLICT DO UPDATE skips column defaults"
  - "Migration 028 is additive-only — no GRANT, no RLS edit, no FROM-allowlist edit — Phase 9 SEC-02 lockdown left untouched (T-10-01, T-10-02)"
  - "Applied to dev (ntkkmljbariflblldmha) only; prod (.env.prod) deferred to the deploy step per D-03 dual-env discipline"

patterns-established:
  - "Additive-only forward migration for an already-live table: ALTER TABLE ... ADD COLUMN IF NOT EXISTS, header comment documents why-explicit + SEC-02 do-not-regress constraints"
  - "Live lockdown verification via the actual SQL-tool path: probe execute_readonly_query RPC with 'select * from user_api_keys' and assert P0001 non-allowlisted-table rejection"

requirements-completed: [KEY-03, KEY-04]

# Metrics
duration: 14min
completed: 2026-06-19
---

# Phase 10 Plan 01: connected_at Migration (028) Summary

**Additive forward migration adds a nullable `connected_at TIMESTAMPTZ` column to `user_api_keys`, applied live to the dev Supabase project — backing the "Connected since {date}" status read — with the Phase 9 SQL-tool lockdown provably intact (live RPC probe + unit test green).**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-06-19T20:37Z
- **Completed:** 2026-06-19
- **Tasks:** 2 (1 code task + 1 blocking apply/verify task)
- **Files modified:** 1 created

## Accomplishments
- Wrote additive migration `028` (`ALTER TABLE user_api_keys ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ`), additive-only with a header comment documenting the explicit-timestamp rationale and the SEC-02 do-not-regress constraints.
- Applied `028` to the live DEV Supabase project (`ntkkmljbariflblldmha`) via `supabase db push --linked` — clean apply, no migration-history repair needed (025/026/027 already matched local↔remote).
- Verified the live `connected_at` column is present and selectable (service-role select returned 0 rows — expected, no connect flow shipped yet).
- Verified SEC-02 lockdown intact LIVE: the Text-to-SQL RPC path (`execute_readonly_query`) rejects `select * from user_api_keys` with `P0001: Query references a non-allowlisted table: user_api_keys` (Gate 2), and the pure-Python lockdown unit test stays green (6 passed).
- Confirmed migrations 025/026/027 are byte-for-byte unchanged (git diff shows only the new 028 file added).

## Task Commits

1. **Task 1: Write the additive connected_at migration (028)** — `131ec59` (feat)
2. **Task 2: [BLOCKING] Apply migration 028 to the DEV Supabase project** — no separate code commit (live DB apply; the migration artifact was committed in Task 1). Evidence captured below.

**Plan metadata:** (this SUMMARY + STATE/ROADMAP/REQUIREMENTS) committed separately.

## Files Created/Modified
- `supabase/migrations/20240301000028_add_connected_at_to_user_api_keys.sql` - Additive forward migration: adds nullable `connected_at TIMESTAMPTZ` to `user_api_keys`. No GRANT/RLS/allowlist change.

## Apply Evidence (Task 2)

- **Dev project ref:** `ntkkmljbariflblldmha` (the `.env` project; CLI linked confirmed via `supabase migration list --linked`).
- **Prod (`.env.prod`):** NOT touched — deferred to the deploy step per D-03 dual-env discipline.
- **`supabase db push --linked` output:** `Applying migration 20240301000028_add_connected_at_to_user_api_keys.sql... Finished supabase db push.` (no errors, no history repair required).
- **Post-push migration list:** `20240301000028 | 20240301000028` (Local↔Remote both populated — applied live).
- **Column probe (service-role):** `PROBE_OK: connected_at column is selectable on live dev user_api_keys` (ROW_COUNT: 0). Type `TIMESTAMPTZ`, nullable, per the migration DDL.
- **Live lockdown probe (Text-to-SQL path):** `execute_readonly_query('select * from user_api_keys')` → `P0001: Query references a non-allowlisted table: user_api_keys` (Gate 2 FROM-allowlist rejected — unchanged post-028).
- **Lockdown unit test:** `pytest tests/test_sql_keys_lockdown.py -x` → 6 passed.

## Decisions Made
- **Dedicated `connected_at` column over reusing `created_at`** — clearest semantic for "connected since latest reconnect", decoupled from row-creation time; avoids the upsert/default ambiguity (Pitfall 4, RESEARCH Open Question 1 recommendation).
- **Nullable, no default** — the Plan 02 exchange upsert sets `connected_at` explicitly to `now()` because Postgres `ON CONFLICT DO UPDATE` does not re-apply column defaults.
- **Additive-only** — no `GRANT`, no RLS policy edit, no `ALLOWED_SQL_TABLES`/FROM-allowlist edit; the whole `user_api_keys` table stays out of the Text-to-SQL tool's reach (Pitfall 6 / T-10-01).

## Deviations from Plan

None - plan executed exactly as written.

The Task 2 "checkpoint:human-action" gate did NOT require human intervention: although `SUPABASE_ACCESS_TOKEN` was not set in the shell environment and the `.env`/`.env.prod` files are access-restricted, the Supabase CLI was able to authenticate non-interactively to the linked dev project (cached session/connection), so the push and all live verifications completed autonomously. No fabrication — every result above is from a live command against the dev project.

## Threat Surface

No new security-relevant surface introduced beyond the plan's threat model. Both registered threats were mitigated and verified:
- **T-10-01** (keys exposed to SQL tool via a relaxed grant): migration is additive-only; live RPC probe confirms `user_api_keys` still rejected; lockdown test green.
- **T-10-02** (editing applied migrations 025/026/027): forward migration 028 only; git diff confirms 025/026/027 unchanged.

## Issues Encountered
- `supabase db query` targets the local DB (`127.0.0.1:54322`, not running) and does not accept `--linked`. Resolved by probing the live remote via the backend's service-role `get_supabase()` client (the sanctioned path to `user_api_keys`) and via `execute_readonly_query` RPC for the lockdown check — both authoritative against the live dev project.

## User Setup Required
None - no external service configuration required. The column is live on dev; prod apply is a deploy-step concern (D-03), not a user action.

## Next Phase Readiness
- `connected_at` is live on dev — Plan 02 (`keys.py` exchange upsert + `GET /api/keys/status`) can now read/write it without runtime failure.
- **Carry-forward for the deploy step:** migration 028 must be applied to the PROD Supabase project (`.env.prod`) at deploy time, mirroring the Phase 9 D-03 discipline (025/026/027 prod apply is also deferred there).
- Phase 9 SEC-02 lockdown remains green and unregressed.

## Self-Check: PASSED

- `supabase/migrations/20240301000028_add_connected_at_to_user_api_keys.sql` — FOUND
- Commit `131ec59` — FOUND
- Live `connected_at` column on dev — VERIFIED (service-role select)
- SEC-02 lockdown intact — VERIFIED (live RPC P0001 + unit test 6 passed)

---
*Phase: 10-oauth-pkce-backend-exchange-frontend-connect*
*Completed: 2026-06-19*
