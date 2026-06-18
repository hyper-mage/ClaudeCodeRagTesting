---
phase: 9
slug: crypto-encrypted-key-storage-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `09-RESEARCH.md` → "## Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 (+ pytest-asyncio 0.23.8) `[VERIFIED: backend/requirements.txt]` |
| **Config file** | none — `backend/tests/conftest.py` does `sys.path` insert; no `pytest.ini`/`pyproject.toml [tool.pytest]` |
| **Quick run command** | `cd backend && venv/Scripts/python.exe -m pytest tests/test_crypto_service.py tests/test_config.py -x` |
| **Full suite command** | `cd backend && venv/Scripts/python.exe -m pytest tests/ -q` |
| **Estimated runtime** | ~1–3 seconds (unit set); full suite a few seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_crypto_service.py tests/test_config.py -x` (sub-second; crypto + config)
- **After every plan wave:** Run `pytest tests/test_crypto_service.py tests/test_config.py tests/test_sql_keys_lockdown.py -q` (full Phase 9 unit set)
- **Before `/gsd-verify-work`:** Full backend suite green (`pytest tests/ -q`) PLUS manual dev-apply checks for migration + REVOKE (D-05 — manual prod check at deploy)
- **Max feedback latency:** ~3 seconds

---

## Per-Task Verification Map

> Task IDs finalized by the planner; rows below map each phase requirement to its
> automated proof. Planner/checker align task IDs to these requirement rows.

| Requirement | Behavior | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|------------|-----------------|-----------|-------------------|-------------|--------|
| KEY-02 (crypto) | Encrypt→decrypt round-trip via `crypto_service` | — | ciphertext ≠ plaintext; round-trip equal | unit | `pytest tests/test_crypto_service.py::test_encrypt_decrypt_roundtrip -x` | ❌ W0 | ⬜ pending |
| KEY-02 (rotation) | Second key decrypts + `.rotate()` re-encrypts | — | old-key token decrypts under `[new, old]`, re-encrypts to new | unit | `pytest tests/test_crypto_service.py::test_rotation_decrypts_old_and_reencrypts -x` | ❌ W0 | ⬜ pending |
| KEY-02 (config) | `KEY_ENCRYPTION_SECRET` default + env override | — | empty default; env value loads | unit | `pytest tests/test_config.py::test_key_encryption_secret_env_override -x` | ⚠️ extend existing | ⬜ pending |
| KEY-02 (storage) | Migration applies; ciphertext-only column; RLS present | — | schema stores only ciphertext + `key_version`; per-user RLS | manual/SQL | apply `...025` to dev; inspect schema | ❌ manual (D-03/D-05) | ⬜ pending |
| SEC-02 (allowlist) | `select * from user_api_keys` rejected by FROM-table allowlist | T-09 exfiltration | query blocked / empty | unit | `pytest tests/test_sql_keys_lockdown.py::test_keys_table_query_blocked -x` | ❌ W0 | ⬜ pending |
| SEC-02 (REVOKE) | Live `authenticated` role denied SELECT on keys table | T-09 exfiltration | permission error under user JWT | integration (opt)/manual | live dev probe; or verify REVOKE in dashboard | ❌ manual (D-05) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_crypto_service.py` — KEY-02 round-trip + rotation (NEW file)
- [ ] `tests/test_sql_keys_lockdown.py` — SEC-02 allowlist probe (NEW file)
- [ ] Extend `tests/test_config.py` — `KEY_ENCRYPTION_SECRET` default + env-override (mirror `chat_max_iterations` pattern; call `get_settings.cache_clear()` after `monkeypatch.setenv`)
- [ ] No shared crypto fixture needed — tests self-generate keys via `Fernet.generate_key()`
- [ ] Framework install: none — pytest already present
- [ ] (Optional, deferred) live-DB integration test for the REVOKE — gate behind an env flag / pytest marker so CI without DB creds skips it

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `...025` migration applies; ciphertext-only schema + RLS | KEY-02 | Requires live dev Supabase project (D-03 applies dev only this phase) | Apply migration to dev; inspect `\d user_api_keys` / dashboard: only `encrypted_key`, `key_version`, timestamps; per-user RLS policies present; sample row `encrypted_key` is opaque Fernet token |
| Live `authenticated` role denied SELECT on keys table | SEC-02 | REVOKE effect is a DB-level privilege, observable only against live DB | Run `select * from user_api_keys` probe via SQL tool against dev under user JWT → permission error / empty (D-05; prod re-checked at deploy) |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (2 new test files + 1 extended)
- [ ] No watch-mode flags
- [ ] Feedback latency < 3s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
