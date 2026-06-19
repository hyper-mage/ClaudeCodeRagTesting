---
phase: 09-crypto-encrypted-key-storage-foundation
verified: 2026-06-18T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: "Initial verification. Code review (09-REVIEW.md) found 2 BLOCKERs (CR-01 comma cross-join, CR-02 schema-qualified bypass) which were fixed in migration 027 + Python mirror + hardened tests before this verification."
deferred:
  - truth: "Success criteria #1 and #2 prod halves (KEY_ENCRYPTION_SECRET + migrations 025/026/027 applied + re-probed against the PROD Supabase project)"
    addressed_in: "Phase deploy step (D-03)"
    evidence: "09-CONTEXT.md D-03: 'Apply to dev during this phase; prod (.env.prod) is applied at the phase's deploy step, not now — keeps prod data/keys isolated.' D-05: 'manual prod check happens at the deploy step.' ROADMAP SC wording 'across dev and prod' is satisfied for dev now; prod is an explicit, documented in-milestone deferral, not scope-trimming."
---

# Phase 9: Crypto + Encrypted Key Storage Foundation Verification Report

**Phase Goal:** A user's OpenRouter key can be safely persisted server-side — encrypted at rest, RLS-scoped, and provably unreachable by the Text-to-SQL tool — before any provisioning or chat path depends on it.
**Verified:** 2026-06-18
**Status:** passed
**Re-verification:** No — initial verification (post-code-review-fix)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | A plaintext key encrypts/decrypts round-trip via `crypto_service` (Fernet) using a dedicated `KEY_ENCRYPTION_SECRET` | ✓ VERIFIED | `crypto_service.py` implements `encrypt_key`/`decrypt_key`/`rotate_token` on `MultiFernet`, reading `get_settings().key_encryption_secret` at call-time (`_multifernet()`). `config.py:23` has `key_encryption_secret: str = ""`. `test_encrypt_decrypt_roundtrip` PASSES; live behavioral spot-check: `ciphertext_differs=True`, `roundtrip_ok=True`. Prod verification deferred (see Deferred). |
| 2 | The `user_api_keys` migration (table + per-user RLS + `key_version`) applies cleanly, storing ciphertext only | ✓ VERIFIED (dev) | Migration 025: `user_api_keys` with `encrypted_key TEXT NOT NULL` (no plaintext column), `key_version INTEGER NOT NULL DEFAULT 1`, PK=`user_id` FK `auth.users` ON DELETE CASCADE, `ENABLE ROW LEVEL SECURITY`, 4 own-row `auth.uid() = user_id` policies. Migration 027 adds the missing UPDATE `WITH CHECK` (WR-04 fix). Orchestrator confirms 025/026/027 applied LIVE to dev project `ntkkmljbariflblldmha`. Prod deferred (D-03). |
| 3 | A prompt-injected `select * from user_api_keys` via Text-to-SQL returns nothing (REVOKE + FROM-table allowlist) | ✓ VERIFIED | Gate 1: `REVOKE SELECT ON user_api_keys FROM authenticated` (migration 025:53). Gate 2: FROM-table allowlist in migration 027 (supersedes 026's vulnerable regex). The 2 REVIEW BLOCKERs (comma cross-join CR-01, schema-qualified CR-02) are FIXED in 027 + Python mirror. Live dev probe: `P0001 non-allowlisted table` for keys/comma/schema/auth.users. My spot-checks: `keys_blocked`, `comma_bypass_blocked`, `schema_bypass_blocked`, `auth_users_blocked`, `subquery_blocked` all True. |
| 4 | A second master key decrypts + lazily re-encrypts a stored token (rotation path); runbook documented | ✓ VERIFIED | `test_rotation_decrypts_old_and_reencrypts` PASSES (encrypt under old key → set `new,old` → `rotate_token` → decrypt under new alone). `KEY-ROTATION-RUNBOOK.md` documents the full lazy MultiFernet procedure (NEW-KEY-FIRST ordering, 5-step rotation, `key_version` bump, per-env discipline, cross-env-reuse + encoding pitfalls). |

**Score:** 4/4 truths verified

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC #1/#2 PROD halves (apply + re-probe against `.env.prod` Supabase project) | Phase deploy step | 09-CONTEXT.md D-03 + D-05: prod is explicitly applied at deploy, not in this phase. Dev half proven now. |

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `backend/services/crypto_service.py` | encrypt/decrypt/rotate on MultiFernet | ✓ VERIFIED | 48 lines; 3 public fns + `_multifernet()` helper; call-time `get_settings()`; WR-03 RuntimeError on unset secret. Imported by tests; consumed by Phase 10/11. |
| `backend/config.py` | `key_encryption_secret` setting | ✓ VERIFIED | Line 23, empty default, pydantic auto-maps `KEY_ENCRYPTION_SECRET`. Read by `crypto_service._multifernet()` (WIRED). |
| `backend/tests/test_crypto_service.py` | round-trip + rotation gate | ✓ VERIFIED | 3 tests (roundtrip, rotation, WR-03 unset-error) — all PASS. |
| `backend/tests/test_config.py` | config default/override | ✓ VERIFIED | `test_key_encryption_secret_default` + `_env_override` — PASS. |
| `KEY-ROTATION-RUNBOOK.md` | documented rotation procedure | ✓ VERIFIED | Contains `MultiFernet`, `KEY_ENCRYPTION_SECRET`, `rotate_token`, `key_version`, `encrypt_key`/`decrypt_key`, NEW-KEY-FIRST + per-env rule. |
| `supabase/migrations/...025_create_user_api_keys.sql` | table + RLS + REVOKE | ✓ VERIFIED | Ciphertext-only, key_version, 4 policies, REVOKE present. |
| `supabase/migrations/...026_harden_sql_tool_allowlist.sql` | RPC allowlist (Gate 2) | ⚠️ SUPERSEDED | Contains the original FROM/JOIN-only regex (vulnerable to comma/schema bypass per CR-01/CR-02). Intentionally superseded by 027 via CREATE OR REPLACE (027 runs after 026). Not a gap — 027 is the live enforcing definition. |
| `supabase/migrations/...027_harden_sql_allowlist_and_rls.sql` | hardened allowlist + WITH CHECK | ✓ VERIFIED | Two-step FROM-region parser handles commas + schema-qualified + subqueries + fail-closed; mirrors `is_query_allowlisted`. Adds UPDATE WITH CHECK. |
| `backend/tests/test_sql_keys_lockdown.py` | SEC-02 exfil probe | ✓ VERIFIED | 6 tests incl. comma, schema, subquery bypass cases (WR-01 fix) — all PASS. |
| `backend/services/sql_service.py` (`ALLOWED_SQL_TABLES`, `is_query_allowlisted`) | Python allowlist source of truth | ✓ VERIFIED | Frozenset = exactly {threads, messages, documents, document_chunks}; hardened parser mirrors migration 027. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `crypto_service.py` | `config.py` | `get_settings().key_encryption_secret` in `_multifernet()` | ✓ WIRED | Read at call-time; lru_cache-clearable in tests; spot-check confirms live read. |
| migration 027 RPC | `execute_readonly_query` | FROM-region allowlist before `SET LOCAL role` | ✓ WIRED | Allowlist loop placed after keyword block, before RLS context — rejects non-allowlisted tables at P0001 before execution (live dev probe). |
| migration 025 REVOKE | `authenticated` role | `REVOKE SELECT ON user_api_keys FROM authenticated` | ✓ WIRED | Privilege checked before RLS — denies the read path. Gate 1 of defense-in-depth. |
| `is_query_allowlisted` | migration 027 SQL loop | mirrored two-step FROM-region parse | ✓ WIRED | Both updated together (commit 91425fe); behavioral spot-checks confirm parity. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `crypto_service.encrypt_key` | `KEY_ENCRYPTION_SECRET` | `get_settings()` from env/`.env` | Yes (real Fernet token) | ✓ FLOWING — spot-check produced a real ciphertext that round-trips |
| `execute_readonly_query` allowlist | `sanitized` (user SQL) | RPC arg `query_text` | Yes (live P0001 on dev) | ✓ FLOWING — live dev probe rejected keys/comma/schema queries |

N/A: `user_api_keys.encrypted_key` has no write path yet (Phase 10 lands the upsert) — this is by-design phase scope, not a hollow artifact.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Crypto round-trip | `encrypt_key` then `decrypt_key` via venv | `ciphertext_differs=True`, `roundtrip_ok=True` | ✓ PASS |
| Keys-table exfil blocked | `is_query_allowlisted('select * from user_api_keys')` | `False` | ✓ PASS |
| Comma cross-join bypass blocked | `is_query_allowlisted('select * from threads, user_api_keys')` | `False` | ✓ PASS |
| Schema-qualified bypass blocked | `is_query_allowlisted('select * from messages.user_api_keys')` | `False` | ✓ PASS |
| `auth.users` cross-join blocked | `is_query_allowlisted('select t.id from threads t, auth.users u')` | `False` | ✓ PASS |
| Subquery smuggle blocked | `is_query_allowlisted('select * from (select * from user_api_keys) sub')` | `False` | ✓ PASS |
| Legitimate query passes | `is_query_allowlisted('select count(*) from threads')` | `True` | ✓ PASS |
| Legitimate JOIN passes | documents JOIN document_chunks | `True` | ✓ PASS |
| Phase-9 unit gate | `pytest test_crypto_service test_sql_keys_lockdown test_config` | 15 passed | ✓ PASS |
| Full backend suite | `pytest tests/ -q` | 150 passed, 2 pre-existing errors | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| Live dev SEC-02 probe | `execute_sql(..., 'select * from user_api_keys')` against dev (orchestrator-run + summary) | `P0001: non-allowlisted table: user_api_keys`, rows=[] | PASS (live, orchestrator-supplied + re-probed post-fix) |

No `scripts/*/tests/probe-*.sh` conventional probes exist in this repo; the SEC-02 live probe is driven through `execute_sql` and was re-run by the orchestrator after the migration-027 fix. No standalone probe script remained (ephemeral `_sec02_probe.py` removed per 09-03 self-check).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| KEY-02 | 09-01, 09-02, 09-03 | User's OpenRouter key stored encrypted at rest, RLS-scoped, never returned to frontend | ✓ SATISFIED | crypto_service (encrypt at rest) + migration 025 ciphertext-only table + per-user RLS. No frontend touch this phase. REQUIREMENTS.md marks Complete. |
| SEC-02 | 09-02, 09-03 | Text-to-SQL tool cannot read user-keys table (REVOKE + RPC allowlist) | ✓ SATISFIED | Gate 1 REVOKE + Gate 2 allowlist (migration 027, post-fix); live dev probe + unit tests confirm rejection. REQUIREMENTS.md marks Complete. |

No orphaned requirements: REQUIREMENTS.md maps exactly {KEY-02, SEC-02} to Phase 9; both are claimed in plan frontmatter and verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TODO/FIXME/XXX/HACK/TBD in any Phase 9 modified file | — | crypto_service.py, sql_service.py, migrations 025/026/027 are clean |

`crypto_service.py` declares a module `logger` but never invokes it — no secret/plaintext/ciphertext is logged, traced, or returned (D-04 / T-09-01 honored, confirmed by grep). The empty-secret crash (WR-03) is fixed with a clear RuntimeError that leaks no key material.

### Human Verification Required

None. All four success criteria are verifiable programmatically (crypto round-trip, allowlist logic, rotation) or via the orchestrator-supplied live dev probe (which I independently re-confirmed at the deterministic Python seam). The prod half of SC #1/#2 is a documented deferral to the deploy step (D-03), not a human-test gap for this phase.

### Gaps Summary

No blocking gaps. The phase goal — a user's OpenRouter key can be safely persisted server-side (encrypted at rest, RLS-scoped, provably unreachable by Text-to-SQL) before any consumer depends on it — is achieved on dev:

- Encryption foundation (crypto_service + MultiFernet rotation) is complete, tested, and stable for Phase 10/11.
- The `user_api_keys` table is ciphertext-only with per-user RLS, applied live to dev.
- The SEC-02 lockdown is genuinely effective post-fix: the 2 code-review BLOCKERs (comma cross-join, schema-qualified bypass) were the difference between a false-PASS gate and a real one — they are fixed in migration 027 + the Python mirror + hardened tests, and independently re-verified here. Gate 1 (REVOKE) backstops Gate 2 regardless of query shape.

Two items are explicitly out of this phase's scope and do NOT count as gaps:
1. **Prod apply/probe** — deferred to the deploy step per D-03 (documented phase decision; dev half proven).
2. **D-09-A** (pre-existing `42501: cannot set parameter "role"` in the SECURITY DEFINER RPC) — predates Phase 9 (identical in migration 015), orthogonal to the keys-reachability goal, logged for Phase 11 triage. The SEC-02 gates fire BEFORE that line, so the lockdown is unaffected.

Note also: the 2 failing `test_record_manager.py` errors (missing `user_id` fixture) are pre-existing debt — last touched in commit `c46981a` ("module 3 completed"), well before Phase 9. Not caused by and not in scope for this phase.

---

_Verified: 2026-06-18_
_Verifier: Claude (gsd-verifier)_
