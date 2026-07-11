---
phase: 09-crypto-encrypted-key-storage-foundation
plan: 02
subsystem: backend-security
tags: [sec-02, key-02, byok, sql-tool, rls, allowlist, defense-in-depth]
requires:
  - "supabase/migrations/20240301000015_execute_readonly_query.sql (RPC being hardened)"
  - "supabase/migrations/20240301000018_create_folders_table.sql (table+RLS analog)"
  - "backend/services/sql_service.py QUERYABLE_SCHEMA (allowlist source set)"
provides:
  - "user_api_keys ciphertext-only table schema (KEY-02 storage shape) — migration 025"
  - "REVOKE SELECT ON user_api_keys FROM authenticated (SEC-02 Gate 1) — migration 025"
  - "execute_readonly_query FROM-table allowlist (SEC-02 Gate 2) — migration 026"
  - "ALLOWED_SQL_TABLES + is_query_allowlisted() Python source of truth — sql_service.py"
  - "SEC-02 exfiltration probe (allowlist seam) — test_sql_keys_lockdown.py"
affects:
  - "Plan 09-03 (live dev apply of migrations 025+026 + live REVOKE/allowlist probe)"
  - "Phase 10 (BYOK key write/read against user_api_keys via service role)"
tech-stack:
  added: []
  patterns:
    - "Defense-in-depth DB gates: table-privilege REVOKE (precedes RLS) + positive default-deny FROM-table allowlist"
    - "Single Python source of truth mirroring a SQL allowlist for deterministic CI testing"
key-files:
  created:
    - "supabase/migrations/20240301000025_create_user_api_keys.sql"
    - "supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql"
    - "backend/tests/test_sql_keys_lockdown.py"
  modified:
    - "backend/services/sql_service.py"
decisions:
  - "Allowlist reconciled to {threads, messages, documents, document_chunks} (RESEARCH Open Question 1 closed) — matches QUERYABLE_SCHEMA, drops RESEARCH-era folders"
  - "CTE self-referencing aliases are NOT tolerated (default-deny) — admitting arbitrary CTE names would let an attacker alias a non-allowlisted table past the gate"
  - "Allowlist helper is additive-only; NOT wired into execute_sql runtime path — the DB RPC remains the enforcing gate"
metrics:
  duration_minutes: 3
  completed: "2026-06-18"
  tasks: 3
  files: 4
---

# Phase 09 Plan 02: SQL-Tool Exfiltration Defense + Keys-Table Schema Summary

Two independent DB-layer gates make `user_api_keys` provably unreachable by the chat's Text-to-SQL tool — a `REVOKE SELECT ... FROM authenticated` (privilege precedes RLS) plus a positive default-deny FROM-table allowlist — alongside the ciphertext-only `user_api_keys` table schema, with the allowlist set unit-tested at a deterministic Python seam.

## What Was Built

- **Migration 025 (`user_api_keys` table):** ciphertext-only key store. PK = `user_id` (FK `auth.users` ON DELETE CASCADE), `encrypted_key TEXT NOT NULL` (Fernet ciphertext — no plaintext column), `key_version INTEGER DEFAULT 1` (D-02), plus `provider`, `key_label`, and timestamps. RLS enabled with four own-row policies (`auth.uid() = user_id`, no public clause). Final statement: `REVOKE SELECT ON user_api_keys FROM authenticated` (SEC-02 Gate 1 / D-01).
- **Migration 026 (`execute_readonly_query` hardening):** `CREATE OR REPLACE` of the RPC preserving every gate from migration 015 verbatim (SELECT/WITH-only check, dangerous-keyword block, `set_config` + `SET LOCAL role = 'authenticated'` RLS context, subquery-wrap + LIMIT, `RESET role`). New positive default-deny FROM/JOIN allowlist loop inserted after the keyword block and before `SET LOCAL role`, inspecting the inner `sanitized` SQL and RAISEing on any table outside `{threads, messages, documents, document_chunks}` (SEC-02 Gate 2 / D-01).
- **`sql_service.py` allowlist seam:** module-level `ALLOWED_SQL_TABLES` frozenset (exactly the four advertised tables) + `is_query_allowlisted(query)` mirroring the SQL allowlist regex. Additive only — not wired into `execute_sql`'s runtime path; the DB RPC stays the enforcing gate.
- **`test_sql_keys_lockdown.py`:** three tests asserting the keys-table query is rejected, the four legitimate tables (incl. a `documents JOIN document_chunks`) pass, and `user_api_keys`/`folders` are not in the allowlist set.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Wave 0 — SEC-02 lockdown probe + allowlist seam | `9001bfb` | `backend/services/sql_service.py`, `backend/tests/test_sql_keys_lockdown.py` |
| 2 | Migration 025 — user_api_keys table + RLS + REVOKE | `ed5126d` | `supabase/migrations/20240301000025_create_user_api_keys.sql` |
| 3 | Migration 026 — execute_readonly_query FROM-table allowlist | `7e5bd01` | `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql` |

## Verification Results

- `pytest tests/test_sql_keys_lockdown.py -x` → 3 passed (allowlist rejects `user_api_keys`, accepts the four legitimate tables).
- `pytest tests/ -q` → 146 passed, 2 errors. The 2 errors are the pre-existing `test_record_manager.py` `user_id` fixture debt (documented in STATE.md Pending Todos; pre-dates v1.1) — out of scope for this plan and unaffected by these additive changes.
- Migration 025 grep checks: `create table user_api_keys`, `revoke select on user_api_keys from authenticated`, `key_version` all present.
- Migration 026 grep checks: `create or replace function execute_readonly_query`, `documents`, `non-allowlisted table` all present; allowlist `IN` clause is exactly `('threads', 'messages', 'documents', 'document_chunks')` (no `folders`, no `user_api_keys`).

## Deviations from Plan

None — plan executed exactly as written.

## Decisions Made

- **Allowlist reconciled to `{threads, messages, documents, document_chunks}`** (RESEARCH Open Question 1, closed): matches the live `QUERYABLE_SCHEMA`; the RESEARCH-era `folders` was dropped (folders is navigated via the KB tree/grep/glob tools, not Text-to-SQL).
- **CTE self-referencing aliases are not tolerated** (default-deny): a `WITH x AS (...) ... FROM x` would surface `x` as a FROM target and be rejected. Widening to admit arbitrary CTE names would let an attacker alias a non-allowlisted table (`WITH t AS (SELECT * FROM user_api_keys) SELECT * FROM t`) past the gate. The legitimate Text-to-SQL surface does not rely on CTE self-references.
- **Allowlist helper is additive-only**: `is_query_allowlisted` exists as a single Python source of truth for the allowlist set and a deterministic CI seam (RESEARCH Pitfall 5 — avoid a false PASS against a mocked DB return). It is intentionally NOT wired into `execute_sql`'s runtime path; the DB RPC remains the enforcing gate.

## Threat Mitigations Implemented

- **T-09-06 / T-09-07 (Information Disclosure — keys exfiltration via Text-to-SQL):** two independent gates — REVOKE SELECT (migration 025) and FROM-table allowlist (migration 026). Allowlist seam unit-tested.
- **T-09-08 (Tampering — allowlist too loose/strict):** positive default-deny of exactly the QUERYABLE_SCHEMA set; regression test asserts legitimate queries pass AND `user_api_keys` is rejected.
- **T-09-09 (EoP — REVOKE/GRANT via RPC):** already mitigated by the existing keyword block; the REVOKE lives in the migration file, never via the RPC. No new code.
- **T-09-10 (Information Disclosure — plaintext at rest):** schema has no plaintext column — only `encrypted_key` (Fernet ciphertext) + `key_version`.

## Notes for Next Plan (09-03)

- This plan WROTE the SQL only. Migrations 025 and 026 are NOT yet applied to any live DB. Plan 09-03 (blocking) applies them to dev via `supabase db push` and runs the LIVE probe proving the REVOKE + allowlist actually deny `select * from user_api_keys` against the dev Supabase project (ROADMAP success criteria #2 and #3).
- RESEARCH Assumption A3: verify the dev `execute_readonly_query` matches migration 015 verbatim before applying 026 (the `CREATE OR REPLACE` would silently overwrite an out-of-band variant).

## Self-Check: PASSED

All created/modified files exist on disk and all three task commits (`9001bfb`, `ed5126d`, `7e5bd01`) are present in git history.
