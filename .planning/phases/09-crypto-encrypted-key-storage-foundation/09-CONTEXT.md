# Phase 9: Crypto + Encrypted Key Storage Foundation - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend foundation for BYOK: a user's OpenRouter key can be safely persisted server-side — encrypted at rest (ciphertext only), RLS-scoped to the owning user, and provably unreachable by the chat's Text-to-SQL tool — BEFORE any provisioning (Phase 10) or chat-resolution (Phase 11) path depends on it.

**In scope:** `crypto_service` (Fernet/MultiFernet encrypt/decrypt), `KEY_ENCRYPTION_SECRET` config, `user_api_keys` migration (table + per-user RLS + `key_version`), SQL-tool lockdown (REVOKE + RPC table allowlist), key-rotation path, automated verification.
**Out of scope (later phases):** OAuth PKCE exchange / connect UI (Phase 10), per-request key+model resolution + observability scrub (Phase 11), any frontend. Requirements: **KEY-02, SEC-02**.

</domain>

<decisions>
## Implementation Decisions

### SQL-tool lockdown (SEC-02)
- **D-01:** Defense-in-depth — BOTH `REVOKE SELECT ON user_api_keys FROM authenticated` AND add an explicit FROM-table allowlist to `execute_readonly_query` so the Text-to-SQL tool can only query `documents`, `document_chunks`, `folders`. The keys table (and the future `user_preferences` table) are excluded by default, not by enumeration.
- Rationale: `execute_readonly_query` does `SET LOCAL role = 'authenticated'` (verified in `supabase/migrations/20240301000015_execute_readonly_query.sql`), so RLS is active during execution — but a user's OWN-row ciphertext would still be returnable to the model under their JWT. REVOKE removes that path; the allowlist is a second independent gate.

### Key rotation (KEY-02)
- **D-02:** Full rotation path this phase via Fernet `MultiFernet` — `key_version` column on `user_api_keys`; decrypt accepts current + previous key; lazy re-encrypt on read when a row is on an older key; rotation runbook documented. Satisfies ROADMAP success criterion #4. Cheap because MultiFernet handles multi-key decrypt natively.

### Migration rollout & secret management (KEY-02)
- **D-03:** Apply the `user_api_keys` migration to the **dev** Supabase project (`.env`) during this phase; **prod** (`.env.prod`) is applied at the phase's deploy step, not now — keeps prod data/keys isolated per the dual-env discipline. See [[project_dual_supabase_envs]].
- **D-04:** `KEY_ENCRYPTION_SECRET` is a **distinct 32-byte key per environment** — dev value in `.env`, a SEPARATE prod value in `.env.prod` and the Fly secret store. Never share the dev key with prod. Add to `Settings` in `backend/config.py` (empty default, like other secrets). Decrypt happens only in-backend per request; the secret is never logged, traced, or returned.

### Verification (SEC-02 acceptance gate)
- **D-05:** Automated `pytest` in `backend/tests/`: (a) a probe that drives the SQL tool / `execute_readonly_query` with `select * from user_api_keys` and asserts empty result or error; (b) an encrypt → decrypt round-trip test (incl. a MultiFernet rotation round-trip). This is the durable regression gate; manual prod check happens at the deploy step.

### Carried forward (locked by research — do not re-litigate)
- Fernet via the already-pinned `cryptography 46.0.5` — **no new dependency** (same lib used for ES256 JWT in `backend/auth.py`).
- One OpenRouter key per user → `user_api_keys` PK = `user_id` (FK to auth.users). Multi-provider / multiple keys are out of scope (anti-feature).
- Table stores ciphertext only + `key_version` + created/updated timestamps; per-user RLS mirrors the existing mixed-visibility policy pattern.

### Claude's Discretion
- Exact column names/types, migration filename (next is `20240301000025_*`), `crypto_service` function signatures, and pytest fixture wiring — planner/executor decide, following existing conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` — Phase 9 entry (goal, 4 success criteria, depends-on Phase 8)
- `.planning/REQUIREMENTS.md` — KEY-02, SEC-02 (definitions + traceability)

### Research (milestone-level, milestone-aware)
- `.planning/research/SUMMARY.md` — synthesis; encryption choice, security blockers, build order
- `.planning/research/ARCHITECTURE.md` — `user_api_keys` schema, RLS, crypto path, integration points
- `.planning/research/PITFALLS.md` — secret-custody pitfalls (esp. #2 SQL-tool exfiltration, #4/#5 enc-key hygiene/rotation)
- `.planning/research/STACK.md` — Fernet/MultiFernet rationale, why not Supabase Vault, no new deps

### Code to modify / mirror
- `supabase/migrations/20240301000015_execute_readonly_query.sql` — the RPC to harden with the FROM-table allowlist (D-01)
- `supabase/migrations/20240301000020_update_rls_policies.sql` — existing per-user / mixed-visibility RLS pattern to mirror for `user_api_keys`
- `backend/config.py` — `Settings` + `get_settings()` (lru_cache) + `ENV_FILE` dual-env override; add `KEY_ENCRYPTION_SECRET` here (D-04)
- `backend/auth.py` — existing `cryptography` usage (ES256/JWT) confirming the dep is present
- `backend/database.py` — service-role Supabase client pattern (bypasses RLS; how the backend reads/writes the table)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cryptography 46.0.5` already pinned and imported (JWT path) → reuse for `Fernet`/`MultiFernet`, zero new deps.
- `Settings` / `get_settings()` lru_cache pattern in `backend/config.py` → add `key_encryption_secret: str = ""` alongside other secrets.
- `ENV_FILE` override (`config.py:8`) already powers dev/prod env selection → reuse for the per-env secret + migration rollout (D-03/D-04).
- `backend/tests/` exists → home for the SEC-02 probe + round-trip pytest (D-05).

### Established Patterns
- Migrations are sequentially numbered `20240301000NNN_*.sql`; next free number is `...025`. Each file runs as one transaction.
- RLS policies use `auth.uid() = user_id` (see migration 020). `user_api_keys` needs SELECT/INSERT/UPDATE/DELETE policies all gated on `auth.uid() = user_id` (own-row only; no public visibility).
- `execute_readonly_query` is `SECURITY DEFINER`, sets `role = authenticated` + jwt sub, keyword-allowlisted but **table-agnostic** today → the lockpoint for D-01.

### Integration Points
- Backend writes/reads `user_api_keys` via the service-role client (RLS bypassed server-side) — RLS is defense-in-depth; the frontend must never touch this table.
- `crypto_service` is consumed later by Phase 10 (encrypt exchanged key) and Phase 11 (decrypt per request) — keep its API minimal and stable.

</code_context>

<specifics>
## Specific Ideas

- SQL-tool allowlist should be exactly `{documents, document_chunks, folders}` — the legitimate Text-to-SQL surface today. Anything new (keys, preferences) is excluded unless explicitly added later.
- Rotation runbook lives with the phase docs; MultiFernet key order = `[new_key, old_key]` for decrypt, encrypt always with `new_key`.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Observability `sk-or-` scrub belongs to Phase 11 per research; OAuth/connect to Phase 10.)

</deferred>

---

*Phase: 9-crypto-encrypted-key-storage-foundation*
*Context gathered: 2026-06-18*
