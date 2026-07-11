---
status: complete
phase: 09-crypto-encrypted-key-storage-foundation
source: [09-01-SUMMARY.md, 09-02-SUMMARY.md, 09-03-SUMMARY.md]
started: 2026-06-19T15:00:08Z
updated: 2026-06-19T15:18:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: From a clean state the backend imports config + crypto_service + sql_service with no error (`python -c "import config, services.crypto_service, services.sql_service; print('boot ok')"` → "boot ok"). Migrations 025/026/027 already applied to dev.
result: pass

### 2. Encrypt/Decrypt Round-Trip + Rotation
expected: `cd backend && venv/Scripts/python.exe -m pytest tests/test_crypto_service.py -v` → 3 passed. A plaintext key encrypts to opaque ciphertext (ciphertext ≠ plaintext), decrypts back exactly; a new master key decrypts an old-key token then re-encrypts under the new key (MultiFernet rotation).
result: pass

### 3. KEY_ENCRYPTION_SECRET Config + Unset Guard
expected: `pytest tests/test_config.py -k key_encryption -v` → 2 passed (empty default, env override loads). With the secret UNSET, crypto raises a clear error rather than silently using an empty key (`test_unset_secret_raises_clear_error`, WR-03). The secret is never logged/echoed.
result: pass
note: First run used system Python (bare `pytest`) which crashed on a broken `dash` plugin (INTERNALERROR) — not a code defect. Re-run under `venv/Scripts/python.exe -m pytest` → 2 passed; unset-guard green in full suite.

### 4. SEC-02 — Keys-Table Exfiltration Blocked (live dev)
expected: A prompt-injected `select * from user_api_keys` through the SQL-tool path is rejected — `success=False`, `P0001: Query references a non-allowlisted table: user_api_keys`, `rows=[]`. The model gets nothing. (Verified live on dev in 09-03; re-confirm via the allowlist unit test `pytest tests/test_sql_keys_lockdown.py -v` → 6 passed, incl. comma cross-join / schema-qualified / subquery bypass variants.)
result: pass
note: venv run → 6 passed. Only warning is a pre-existing `gotrue` deprecation from the supabase package (transitive, unrelated to Phase 9).

### 5. No Regression — Legitimate SQL Still Allowlisted
expected: Legitimate queries against `threads / messages / documents / document_chunks` are NOT rejected by the allowlist (they pass Gate 2). `is_query_allowlisted("select count(*) from threads")` → True; `select * from folders` and `user_api_keys` → rejected. Unit-covered in `test_allowlisted_queries_pass`.
result: pass

### 6. Key-Rotation Runbook Present & Operational
expected: `.planning/phases/09-crypto-encrypted-key-storage-foundation/KEY-ROTATION-RUNBOOK.md` documents the lazy MultiFernet rotation as numbered steps: generate per-env key, set `KEY_ENCRYPTION_SECRET` NEW-KEY-FIRST (`new,old`), deploy, lazy re-encrypt via `rotate_token` + `key_version` bump, drop old key. References `encrypt_key`/`decrypt_key`/`rotate_token` by name; distinct-per-env rule stated (never reuse dev key in prod).
result: pass
note: grep confirms all required tokens present (rotate_token, encrypt_key, decrypt_key, KEY_ENCRYPTION_SECRET, MultiFernet, key_version, NEW-KEY-FIRST).

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
