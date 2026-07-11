# Phase 999.2 — Deferred Items

Out-of-scope discoveries logged during execution. NOT fixed here (SCOPE BOUNDARY:
only auto-fix issues directly caused by the current task's changes).

## D-999.2-A: `test_config::test_key_encryption_secret_default` fails on a populated `.env`

- **Found during:** Plan 999.2-01 full-suite verification.
- **Symptom:** `tests/test_config.py::test_key_encryption_secret_default` asserts
  `Settings().key_encryption_secret == ""` but the loaded dev `.env` now has
  `KEY_ENCRYPTION_SECRET` set (Phase 9 / "Prod BYOK secrets applied" work), so the
  default-empty assertion fails. Reproduces in isolation; fails independently of this
  plan's changes (config.py and test_config.py untouched here).
- **Why out of scope:** Pre-existing, environment-dependent test design (it assumes a
  clean env with no `KEY_ENCRYPTION_SECRET`). Orthogonal to SEC-03 / the burn script.
- **Suggested fix (future):** Have the test clear `KEY_ENCRYPTION_SECRET` from the env
  (monkeypatch.delenv) + `get_settings.cache_clear()` before constructing `Settings()`,
  or assert on a fresh `Settings(_env_file=None)`.

## D-999.2-B: `test_record_manager` integration fixtures missing `user_id`

- **Found during:** Plan 999.2-01 full-suite verification.
- **Symptom:** `tests/test_record_manager.py::test_check_duplicate_integration` and
  `::test_find_previous_version_integration` ERROR at setup — they reference a missing
  `user_id` fixture (conftest provides only `test_user_id` / `mock_user_id`).
- **Why out of scope:** Pre-existing fixture debt, already tracked in STATE.md "Pending
  Todos" (pre-dates v1.1). Unrelated to this plan's files.
- **Suggested fix (future):** Add a `user_id` fixture alias in conftest, or rename the
  fixture references in the two integration tests.
