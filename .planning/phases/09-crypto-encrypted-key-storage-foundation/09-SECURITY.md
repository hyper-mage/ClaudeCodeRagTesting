---
phase: 09
slug: crypto-encrypted-key-storage-foundation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-19
---

# Phase 9 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

**Audit date:** 2026-06-19
**Auditor:** gsd-security-auditor (verification pass, State B → audited)
**Disposition:** SECURED — 14/14 threats CLOSED
**ASVS Level:** 1 (default; config unset)
**Block-on:** unset (default — block on HIGH/critical implementation gaps); none found

This audit VERIFIES that each declared mitigation in the plan-time STRIDE register is
actually present in the implemented code. Documentation/intent was not accepted as
evidence — every `mitigate` threat was confirmed against a file:line in the
implementation, and every `accept` threat's rationale was confirmed valid against the
code (no custom crypto, REVOKE in migration not RPC).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env/secret store → backend process | `KEY_ENCRYPTION_SECRET` crosses here; backend-only secret, distinct per environment (D-04). | Fernet master key(s) |
| backend memory → logs/traces/responses | Plaintext key + master secret exist only transiently in backend memory; must NOT cross into logs, LangSmith traces, or any response. | Plaintext OpenRouter key |
| LLM-authored SQL → execute_readonly_query | Untrusted, prompt-injectable SQL crosses here under the user's JWT (role = authenticated). The SEC-02 exfiltration surface. | Arbitrary SELECT text |
| authenticated role → user_api_keys | The SQL tool runs as `authenticated`; this boundary must deny all access to the keys table. | Ciphertext key rows |
| service-role backend → user_api_keys | Trusted; bypasses RLS + REVOKE by design (server-side write/read). Not a threat surface this phase. | Ciphertext key rows |
| repo migration files → live dev Supabase | Written SQL must actually be applied; an unapplied REVOKE is a false-positive. | DDL / RPC bodies |

---

## Important migration-numbering note (verified, not a gap)

The plan-time register cites migrations **025** and **026**. The implementation also
contains migration **027** (`20240301000027_harden_sql_allowlist_and_rls.sql`), which
`backend/services/sql_service.py` and `backend/tests/test_sql_keys_lockdown.py` both name
as "the hardened replacement of 026". This is expected, not drift:

- `09-REVIEW.md` (2026-06-18) raised CR-01 (comma cross-join bypass), CR-02
  (schema-qualified mis-parse), WR-02 (legit comma-join false-negative), and WR-04
  (UPDATE policy missing `WITH CHECK`) against the migration-026 / pre-fix parser.
- Migration **027** is the forward-only fix (migrations 025/026 were already applied to
  dev, so they could not be edited in place). It `CREATE OR REPLACE`s
  `execute_readonly_query` with the two-step FROM-region parser (handles commas, schema
  qualifiers, subqueries, fails closed) and `DROP/CREATE`s the UPDATE policy with
  `WITH CHECK` (WR-04).
- Migration 027 **preserves every migration-015 gate verbatim** (SELECT/WITH-only,
  dangerous-keyword block incl. `grant|revoke`, `set_config` + `SET LOCAL role`,
  subquery-wrap + LIMIT, `RESET role`) — confirmed line-by-line against migration 015.
- The Python mirror `is_query_allowlisted` (sql_service.py:54-96) and the expanded
  `test_sql_keys_lockdown.py` (comma cross-join, schema-qualified, subquery, regression)
  target the **027** shape and pass.

The 09-03 live probe ran against 025+026 and proved a direct `select * from user_api_keys`
is rejected (`P0001 non-allowlisted table`) — that direct-FROM rejection is unchanged in
027. 027 additionally closes the bypasses that affected *other* non-allowlisted tables.

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (evidence: file:line) | Status |
|-----------|----------|-----------|-------------|----------------------------------|--------|
| T-09-01 | Information Disclosure | crypto_service logging/return surface | mitigate | No `logger.*`/`print` call exists in the module (logger declared `crypto_service.py:16`, never invoked); sole `raise` at :29-31 is a static string with no key/plaintext/ciphertext interpolation; `encrypt_key`/`decrypt_key`/`rotate_token` (:37,:42,:47) return only declared values | CLOSED |
| T-09-02 | Information Disclosure | KEY_ENCRYPTION_SECRET custody | mitigate | `config.py:23` `key_encryption_secret: str = ""` empty default, pydantic env-mapped, never echoed; `test_config.py:35-47` asserts default + override; read at call time `crypto_service.py:27` only | CLOSED |
| T-09-03 | Tampering / Info Disclosure | master-key compromise, no rotation | mitigate | `crypto_service.py:47` `rotate_token`→`MultiFernet.rotate()`; `key_version` migration 025:17; runbook Steps 1-5 (dual-key decrypt + lazy re-encrypt); `test_crypto_service.py:23-41` | CLOSED |
| T-09-04 | Information Disclosure | cross-env key reuse (dev key in prod) | mitigate | `KEY-ROTATION-RUNBOOK.md:20-22,50-58,113-118` mandates separate `Fernet.generate_key()` per env; `config.py:7-9` ENV_FILE override isolates `.env` vs `.env.prod` | CLOSED |
| T-09-05 | Spoofing / Tampering | hand-rolled crypto (IV reuse, padding oracle) | accept | `crypto_service.py:12` imports only `cryptography.fernet.{Fernet, MultiFernet}` (audited AES-128-CBC + HMAC-SHA256); no custom IV/padding/cipher anywhere in module | CLOSED |
| T-09-06 | Information Disclosure | prompt-injected `select * from user_api_keys` via execute_readonly_query | mitigate | Gate 1: REVOKE `migration 025:53`. Gate 2: positive default-deny FROM-table allowlist `migration 027:62-124` excluding `user_api_keys` + Python mirror `is_query_allowlisted` sql_service.py:54-96; `test_sql_keys_lockdown.py:19-30` | CLOSED |
| T-09-07 | Information Disclosure | own-row ciphertext returnable under user JWT via RLS-only | mitigate | `migration 025:53` REVOKE removes the `authenticated` read path entirely (privilege precedes RLS); own-row RLS policy (025:29-31) is defense-in-depth; 09-03 probe confirmed own row denied | CLOSED |
| T-09-08 | Tampering | allowlist regex too loose / too strict | mitigate | `ALLOWED_SQL_TABLES` sql_service.py:17; enforcing `IN (...)` migration 027:112; `test_sql_keys_lockdown.py:77-118` asserts legit pass + `user_api_keys`/`folders` rejected + exact-4 set | CLOSED |
| T-09-09 | Elevation of Privilege | issuing REVOKE/GRANT through the RPC | accept | `grant\|revoke` keyword block present migration 015:26, preserved migration 027:58; REVOKE itself lives in migration 025:53, never via the RPC | CLOSED |
| T-09-10 | Information Disclosure | plaintext-at-rest in keys table | mitigate | `migration 025:13-21` — `encrypted_key TEXT` only (commented "Fernet ciphertext — NEVER plaintext") + `key_version`; no plaintext column in schema | CLOSED |
| T-09-11 | Information Disclosure | un-applied REVOKE (false-positive verification) | mitigate | `09-03-SUMMARY.md:54-75` records 025/026 applied live to dev (`ntkkmljbariflblldmha`) + live probe; code gates confirmed: REVOKE 025:53, allowlist 027:60-124; probe returned real `P0001`/`42501` codes | CLOSED |
| T-09-12 | Tampering | applying migration to WRONG project (prod) | mitigate | `09-03-SUMMARY.md:54,107` — dev ref derived from `.env`; `.env.prod` untouched; D-03 dev-only; `config.py:7-9` ENV_FILE isolates envs | CLOSED |
| T-09-13 | Information Disclosure | live own-row ciphertext returnable via SQL tool | mitigate | REVOKE precedes RLS (migration 025:48-53); 09-03 probe #1 `select * from user_api_keys` → `rows=[]` (non-allowlisted rejection) even under calling user id | CLOSED |
| T-09-14 | Tampering | live dev RPC drifted from migration 015 (silent CREATE OR REPLACE overwrite) | mitigate | `09-03-SUMMARY.md:88,97` verified live RPC matched 015 before patch (A3); migration 027:49-128 preserves all 015 gates verbatim — line-by-line vs 015:17-46 | CLOSED |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale (verified in code) | Accepted By | Date |
|---------|------------|------------------------------|-------------|------|
| AR-09-01 | T-09-05 | No custom cryptography present. All encrypt/decrypt/rotate goes through `cryptography.fernet` (`crypto_service.py:12,37,42,47`). Reliance on the audited Fernet construction (AES-128-CBC + HMAC-SHA256) is accepted. | gsd-security-auditor | 2026-06-19 |
| AR-09-02 | T-09-09 | The RPC cannot issue REVOKE/GRANT — blocked by the `grant\|revoke` keyword filter (migration 027:58). The REVOKE is a one-time DDL statement in migration 025:53, not reachable through the user-facing RPC. | gsd-security-auditor | 2026-06-19 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None. SUMMARY files contain no `## Threat Flags` section; `09-01-SUMMARY.md:112`
explicitly states "No new security surface introduced beyond what the threat model
already covers — no Threat Flags." No new attack surface appeared during implementation
that lacks a threat mapping.

---

## Deferred / out-of-scope items observed (not Phase-9 threats)

- `deferred-items.md` D-09-A: pre-existing `42501: cannot set parameter "role" within
  security-definer function` at `SET LOCAL role = 'authenticated'`. This line is
  IDENTICAL in migrations 015, 026, and 027 — it pre-dates Phase 9 and is the RLS-context
  mechanism, not the SEC-02 allowlist. It does not weaken any Phase-9 threat mitigation
  (the REVOKE and the allowlist both run/are enforced before this line). Tracked for
  Phase 11 / a dedicated RPC-fix plan. Not a Phase-9 blocker.
- WR-05 / `key_version` is a Phase-9 placeholder not yet maintained by any writer (no
  Phase-9 code reads/sets/increments it). Documented in `KEY-ROTATION-RUNBOOK.md:26-36`;
  does not affect any declared Phase-9 threat (T-09-03's rotation rests on
  `MultiFernet.rotate()`, which operates on the token, not the version column).

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-19 | 14 | 14 | 0 | gsd-security-auditor (State B create) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-06-19

*Audited: 2026-06-19 — gsd-security-auditor*
