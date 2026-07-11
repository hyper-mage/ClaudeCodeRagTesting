---
phase: 9
slug: crypto-encrypted-key-storage-foundation
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-18
last_audit: 2026-06-19
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `09-RESEARCH.md` → "## Validation Architecture".
> Audited 2026-06-19 (State A, post-execution): all automatable requirements COVERED;
> two live-DB facets remain manual-only and were verified live in `09-03-SUMMARY.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 (+ pytest-asyncio 0.23.8, asyncio mode=auto) `[VERIFIED: live run 2026-06-19]` |
| **Config file** | `backend/pytest.ini` present (rootdir `backend/`); `backend/tests/conftest.py` does `sys.path` insert |
| **Quick run command** | `cd backend && venv/Scripts/python.exe -m pytest tests/test_crypto_service.py tests/test_config.py -x` |
| **Phase-9 unit set** | `cd backend && venv/Scripts/python.exe -m pytest tests/test_crypto_service.py tests/test_config.py tests/test_sql_keys_lockdown.py -q` → **15 passed (0.79s)** |
| **Full suite command** | `cd backend && venv/Scripts/python.exe -m pytest tests/ -q` |
| **Estimated runtime** | < 1s (Phase-9 unit set); full suite a few seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_crypto_service.py tests/test_config.py -x` (sub-second; crypto + config)
- **After every plan wave:** Run `pytest tests/test_crypto_service.py tests/test_config.py tests/test_sql_keys_lockdown.py -q` (full Phase 9 unit set)
- **Before `/gsd-verify-work`:** Full backend suite green (`pytest tests/ -q`) PLUS manual dev-apply checks for migration + REVOKE (D-05 — manual prod check at deploy)
- **Max feedback latency:** < 1 second (Phase-9 unit set)

---

## Per-Task Verification Map

> Audited post-execution 2026-06-19. Statuses reflect the live `pytest -v` run (15 passed).

| Requirement | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|-------------|----------|------------|-----------------|-----------|-------------------|--------|
| KEY-02 (crypto) | Encrypt→decrypt round-trip via `crypto_service` | — | ciphertext ≠ plaintext; round-trip equal | unit | `pytest tests/test_crypto_service.py::test_encrypt_decrypt_roundtrip -x` | ✅ green |
| KEY-02 (rotation) | Second key decrypts + `.rotate()` re-encrypts | T-09-03 | old-key token decrypts under `[new, old]`, re-encrypts to new | unit | `pytest tests/test_crypto_service.py::test_rotation_decrypts_old_and_reencrypts -x` | ✅ green |
| KEY-02 (unset-guard) | Unset `KEY_ENCRYPTION_SECRET` raises a clear error (WR-03) | T-09-02 | no silent empty-key crypto; explicit raise | unit | `pytest tests/test_crypto_service.py::test_unset_secret_raises_clear_error -x` | ✅ green |
| KEY-02 (config) | `KEY_ENCRYPTION_SECRET` default + env override | T-09-02 | empty default; env value loads | unit | `pytest tests/test_config.py::test_key_encryption_secret_default tests/test_config.py::test_key_encryption_secret_env_override -x` | ✅ green |
| SEC-02 (allowlist) | `select * from user_api_keys` rejected by FROM-table allowlist | T-09-06 | query blocked | unit | `pytest tests/test_sql_keys_lockdown.py::test_keys_table_query_blocked -x` | ✅ green |
| SEC-02 (bypass: comma cross-join) | `select * from threads, user_api_keys` rejected (CR-01) | T-09-06/08 | comma cross-join blocked | unit | `pytest tests/test_sql_keys_lockdown.py::test_comma_cross_join_blocked -x` | ✅ green |
| SEC-02 (bypass: schema-qualified) | `select * from public.user_api_keys` rejected (CR-02) | T-09-06/08 | schema-qualified blocked | unit | `pytest tests/test_sql_keys_lockdown.py::test_schema_qualified_keys_blocked -x` | ✅ green |
| SEC-02 (bypass: subquery) | subquery exfil rejected | T-09-06/08 | subquery FROM blocked | unit | `pytest tests/test_sql_keys_lockdown.py::test_subquery_exfil_blocked -x` | ✅ green |
| SEC-02 (no regression) | legit threads/messages/documents/document_chunks pass | T-09-08 | allowlisted tables accepted | unit | `pytest tests/test_sql_keys_lockdown.py::test_allowlisted_queries_pass -x` | ✅ green |
| KEY-02 (storage) | Migration applies; ciphertext-only column; RLS present | T-09-10 | schema stores only ciphertext + `key_version`; per-user RLS | manual/SQL | live dev apply (`...025`) + schema inspect | ✅ manual — verified live `09-03` |
| SEC-02 (REVOKE) | Live `authenticated` role denied SELECT on keys table | T-09-06/07 | permission error / empty under user JWT | manual/live | live dev probe | ✅ manual — verified live `09-03` (`P0001`) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements — COMPLETE

- [x] `tests/test_crypto_service.py` — KEY-02 round-trip + rotation + unset-guard (3 tests, green)
- [x] `tests/test_sql_keys_lockdown.py` — SEC-02 allowlist probe + 3 bypass variants + regression (6 tests, green)
- [x] Extend `tests/test_config.py` — `KEY_ENCRYPTION_SECRET` default + env-override (2 tests, green; `get_settings.cache_clear()` after `monkeypatch.setenv`)
- [x] No shared crypto fixture needed — tests self-generate keys via `Fernet.generate_key()`
- [x] Framework install: none — pytest already present
- [~] (Optional, deferred) live-DB integration test for the REVOKE — NOT added as automated; covered by the manual live probe (09-03). Gate behind an env flag / pytest marker if ever automated.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Status / Evidence |
|----------|-------------|------------|-------------------|
| `...025` migration applies; ciphertext-only schema + RLS | KEY-02 | Requires live dev Supabase project (D-03 applies dev only this phase) | ✅ Applied live to dev `ntkkmljbariflblldmha` (`09-03-SUMMARY.md`); schema is `encrypted_key` + `key_version` only, no plaintext column, per-user RLS present. **Prod deferred to deploy (D-05).** |
| Live `authenticated` role denied SELECT on keys table | SEC-02 | REVOKE is a DB-level privilege, observable only against live DB | ✅ Live probe (`09-03-SUMMARY.md`): `select * from user_api_keys` → `success=False`, `P0001: Query references a non-allowlisted table: user_api_keys`, `rows=[]`; `folders` also rejected; allowlisted `threads` passed Gate 2. **Prod re-probe deferred to deploy (D-05).** |

---

## Validation Audit 2026-06-19

| Metric | Count |
|--------|-------|
| Requirements audited | 2 (KEY-02, SEC-02) |
| Automated facets COVERED | 9/9 (15 tests, all green) |
| Manual-only facets | 2 (live-DB; verified live in 09-03) |
| Gaps found | 0 |
| Resolved | 0 (none required) |
| Escalated | 0 |

State A audit: plan-time draft had all rows ⬜ pending; post-execution all automatable facets are ✅ green and the two live-DB facets are verified via the 09-03 live probe. Three tests exist beyond the original map (`test_unset_secret_raises_clear_error` for WR-03; `test_comma_cross_join_blocked` + `test_schema_qualified_keys_blocked` + `test_subquery_exfil_blocked` for the CR-01/CR-02 review fixes folded into migration 027).

---

## Validation Sign-Off

- [x] All tasks have automated verify or documented manual-only carve-out
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (2 new test files + 1 extended) — complete
- [x] No watch-mode flags
- [x] Feedback latency < 3s (< 1s actual)
- [x] `nyquist_compliant: true` set in frontmatter (all automatable requirements covered; 2 live-DB facets manual-only, verified)

**Approval:** verified 2026-06-19
