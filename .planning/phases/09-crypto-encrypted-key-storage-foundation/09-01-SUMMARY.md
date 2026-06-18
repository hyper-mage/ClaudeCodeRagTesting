---
phase: 09-crypto-encrypted-key-storage-foundation
plan: 01
subsystem: infra
tags: [cryptography, fernet, multifernet, byok, encryption, key-rotation, pydantic-settings]

# Dependency graph
requires:
  - phase: 08 (v1.1 portfolio deployment)
    provides: dual-env Settings + ENV_FILE override + cryptography 46.0.5 pinned (ES256 JWT path)
provides:
  - "crypto_service: encrypt_key / decrypt_key / rotate_token on MultiFernet (stable API)"
  - "KEY_ENCRYPTION_SECRET setting in Settings (empty default, env-mapped, distinct per env)"
  - "Round-trip + MultiFernet rotation regression gate (pytest)"
  - "KEY-ROTATION-RUNBOOK.md: documented lazy-rotation procedure"
affects: [phase-10-openrouter-oauth, phase-11-per-request-key-resolution, key-storage, byok]

# Tech tracking
tech-stack:
  added: []  # zero new deps — reused already-pinned cryptography 46.0.5
  patterns:
    - "MultiFernet rotation-ready encryption (NEW-KEY-FIRST comma-separated key list)"
    - "Call-time get_settings() read in service module (deferred, lru_cache-clearable in tests)"

key-files:
  created:
    - backend/services/crypto_service.py
    - backend/tests/test_crypto_service.py
    - .planning/phases/09-crypto-encrypted-key-storage-foundation/KEY-ROTATION-RUNBOOK.md
  modified:
    - backend/config.py
    - backend/tests/test_config.py

key-decisions:
  - "MultiFernet from day one (not plain Fernet) — rotation path is free and avoids a painful all-rows migration at first rotation (D-02)"
  - "Service reads KEY_ENCRYPTION_SECRET at call-time inside _multifernet(), never at import — mirrors web_search_service so tests can cache_clear (D-04)"
  - "Secret/plaintext/ciphertext never logged, traced, or returned beyond declared values (D-04, T-09-01)"

patterns-established:
  - "Rotation-ready symmetric encryption: KEY_ENCRYPTION_SECRET = comma-separated url-safe base64 Fernet keys, NEW KEY FIRST; encrypt uses keys[0], decrypt tries all, rotate re-encrypts under keys[0]"
  - "Deferred settings access in service modules (get_settings() inside the function) to keep @lru_cache test-clearable"

requirements-completed: [KEY-02]

# Metrics
duration: 4min
completed: 2026-06-18
---

# Phase 9 Plan 01: Crypto + Encrypted Key Storage Foundation Summary

**App-layer BYOK encryption foundation — crypto_service wrapping MultiFernet (encrypt/decrypt/rotate), a dedicated KEY_ENCRYPTION_SECRET setting, a round-trip + rotation pytest gate, and a lazy-rotation runbook — built on the already-pinned cryptography library with zero new dependencies.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-18T23:19:02Z
- **Completed:** 2026-06-18T23:23:15Z
- **Tasks:** 3
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `crypto_service` with a minimal, stable API (`encrypt_key` / `decrypt_key` / `rotate_token`) on `MultiFernet` — rotation-ready from day one (D-02). Phase 10 will call `encrypt_key` after the OAuth exchange; Phase 11 will call `decrypt_key` per request.
- `KEY_ENCRYPTION_SECRET` wired into `Settings` with an empty default, auto-mapped from the UPPER_SNAKE env var, and a distinct value per environment (D-04).
- TDD regression gate: round-trip (`ciphertext != plaintext`, `decrypt(encrypt(x)) == x`) and full MultiFernet rotation (new key decrypts an old-key token, then re-encrypts under the new key) — both green. Config default + env-override tests added.
- `KEY-ROTATION-RUNBOOK.md`: operational, numbered lazy-rotation procedure documenting NEW-KEY-FIRST ordering, `key_version` bump + the intended `user_api_keys` UPDATE shape, distinct-per-env discipline, and the cross-env-reuse / Fernet-encoding pitfalls.

## Task Commits

Each task was committed atomically (Task 1 was a TDD RED step, Task 2 the GREEN step):

1. **Task 1: Wave 0 — config setting + failing crypto/config tests (RED)** - `bc45e12` (test)
2. **Task 2: Implement crypto_service on MultiFernet (GREEN)** - `1e9522c` (feat)
3. **Task 3: Key-rotation runbook** - `644270b` (docs)

**Plan metadata:** _(final docs commit — this SUMMARY + STATE/ROADMAP/REQUIREMENTS)_

_Note: Task 1+2 form the TDD RED→GREEN cycle. No REFACTOR commit was needed — the implementation matched the verified Pattern 1 shape directly._

## Files Created/Modified

- `backend/services/crypto_service.py` (created) - `_multifernet()` helper + `encrypt_key` / `decrypt_key` / `rotate_token`; reads `get_settings().key_encryption_secret` at call time; no logging of secret/plaintext/ciphertext.
- `backend/config.py` (modified) - added `key_encryption_secret: str = ""` to `Settings` with a D-04 comment, alongside the other empty-default secret fields.
- `backend/tests/test_crypto_service.py` (created) - `test_encrypt_decrypt_roundtrip` + `test_rotation_decrypts_old_and_reencrypts`; `get_settings.cache_clear()` after every `monkeypatch.setenv`.
- `backend/tests/test_config.py` (modified) - added `test_key_encryption_secret_default` + `test_key_encryption_secret_env_override`, mirroring the `chat_max_iterations` pair (uses `Settings()` directly, no cache_clear).
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/KEY-ROTATION-RUNBOOK.md` (created) - lazy MultiFernet rotation runbook.

## Decisions Made

None beyond the plan-specified decisions (D-02, D-04, crypto half of D-05). Implementation followed the verified Pattern 1 shape and the documented interface names exactly. The stable API (`encrypt_key` / `decrypt_key` / `rotate_token`) is locked for the Phase 10/11 consumers.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

- RED gate (`test(09-01)`, `bc45e12`): config tests pass; crypto tests fail with `ImportError: cannot import name 'crypto_service'` — failing for the correct reason (service absent), not a false-passing test.
- GREEN gate (`feat(09-01)`, `1e9522c`): all 8 crypto + config tests pass.
- REFACTOR gate: not required — minimal implementation, no cleanup needed.

## Issues Encountered

The full backend suite (`pytest tests/ -q`) shows **143 passed, 2 errors**. The 2 errors are `test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration`, both failing on a missing `user_id` fixture. This is **pre-existing test debt** explicitly documented in STATE.md → Pending Todos ("pre-dates v1.1 — fix in a future plan-checker pass"). It is out of scope (SCOPE BOUNDARY): not caused by this plan's config field (an empty-default setting cannot affect fixture resolution), and not touched. No action taken; already tracked in STATE.md.

## Security / Threat-Model Notes

- **T-09-01 (info disclosure via logging):** verified by grep — no `logger.*` / `print()` in `crypto_service.py` interpolates the secret, plaintext, or ciphertext. Functions return only their declared values.
- **T-09-02 (KEY_ENCRYPTION_SECRET custody):** empty default in `Settings`, loaded only from env via pydantic-settings; distinct-per-env documented in the runbook.
- **T-09-03 (master-key compromise / no rotation):** MultiFernet `.rotate()` + `key_version` + documented dual-key decrypt window (runbook).
- No new security surface introduced beyond what the threat model already covers — no Threat Flags.

## User Setup Required

None this plan. NOTE for the phase deploy step: a dev `KEY_ENCRYPTION_SECRET` must be generated and added to `.env` before any encrypt/decrypt path runs (Phase 10+). Generate with:
`cd backend && venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. A SEPARATE value is generated for prod at the deploy step (D-04). The empty default means the service raises until the secret is set — by design.

## Next Phase Readiness

- crypto API is stable and ready for Phase 10 (`encrypt_key` after OAuth exchange) and Phase 11 (`decrypt_key` per request).
- This plan covers the crypto half of Phase 9. The remaining Phase 9 work (the `user_api_keys` migration + SEC-02 SQL-tool lockdown: REVOKE + FROM-table allowlist, plus the SEC-02 exfiltration probe) lands in the subsequent plan(s) of this phase.
- ROADMAP criterion #1 (round-trip via dedicated KEY_ENCRYPTION_SECRET) and the crypto half of criterion #4 (MultiFernet rotation + runbook) are satisfied.

## Self-Check: PASSED

All created files exist on disk (crypto_service.py, test_crypto_service.py, KEY-ROTATION-RUNBOOK.md, 09-01-SUMMARY.md) and all three task commits (bc45e12, 1e9522c, 644270b) are present in git history.

---
*Phase: 09-crypto-encrypted-key-storage-foundation*
*Completed: 2026-06-18*
