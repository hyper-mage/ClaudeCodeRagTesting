# Phase 9: Crypto + Encrypted Key Storage Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 9-crypto-encrypted-key-storage-foundation
**Areas discussed:** SQL-tool lockdown depth, Key rotation scope, Migration rollout (dev/prod), SEC-02 verification

---

## SQL-tool lockdown depth (SEC-02)

| Option | Description | Selected |
|--------|-------------|----------|
| REVOKE + RPC table allowlist | REVOKE SELECT on user_api_keys from `authenticated` AND add FROM-table allowlist to execute_readonly_query (only documents/document_chunks/folders). Keys + future user_preferences excluded by default. | ✓ |
| REVOKE only | Just REVOKE SELECT on the keys table/secret column from `authenticated`. Simpler, single mechanism; RPC stays table-agnostic. | |

**User's choice:** REVOKE + RPC table allowlist (defense-in-depth)
**Notes:** Grounded in the verified RPC behavior — `execute_readonly_query` runs with `SET LOCAL role = 'authenticated'`, so own-row ciphertext is otherwise reachable. Two independent gates chosen for the highest-value secret.

---

## Key rotation scope (KEY-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Full via MultiFernet | key_version column + MultiFernet (current + previous) decrypt + lazy re-encrypt on read + runbook. Satisfies SC#4. | ✓ |
| Minimal — column + runbook only | key_version column reserved + documented runbook; defer re-encrypt tooling until first real rotation. Softens SC#4. | |

**User's choice:** Full via MultiFernet
**Notes:** Chosen because MultiFernet makes multi-key decrypt trivial, so full rotation is cheap and keeps ROADMAP success criterion #4 intact.

---

## Migration rollout (dev/prod)

| Option | Description | Selected |
|--------|-------------|----------|
| Dev now, prod at deploy step | Apply user_api_keys migration to dev (.env) this phase; prod (.env.prod) at ship time. Distinct KEY_ENCRYPTION_SECRET per env. | ✓ |
| Both dev + prod now | Apply to both Supabase projects immediately. | |

**User's choice:** Dev now, prod at deploy step
**Notes:** Aligns with dual-Supabase-env discipline (.env dev / .env.prod prod). KEY_ENCRYPTION_SECRET is a distinct 32-byte key per env — dev in .env, prod in .env.prod + Fly secret; never shared.

---

## SEC-02 verification

| Option | Description | Selected |
|--------|-------------|----------|
| Automated pytest: probe + round-trip | pytest that prompt-injects `select * from user_api_keys` (asserts empty/error) + encrypt/decrypt round-trip, in backend/tests/. | ✓ |
| Both automated + manual checklist | Automated pytest PLUS manual verification against dev (and prod at deploy). | |
| Manual checklist only | Documented manual probe + round-trip; no automated test. | |

**User's choice:** Automated pytest: probe + round-trip
**Notes:** Durable regression gate in backend/tests/; manual prod confirmation folds into the deploy step.

## Claude's Discretion

- Exact column names/types, migration filename (`...025`), `crypto_service` function signatures, pytest fixture wiring — left to planner/executor, following existing conventions.

## Deferred Ideas

None — discussion stayed within phase scope. Observability `sk-or-` scrub → Phase 11; OAuth/connect → Phase 10 (per research mapping).
