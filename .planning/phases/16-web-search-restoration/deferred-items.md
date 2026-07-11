# Phase 16 — Deferred Items (out-of-scope discoveries during execution)

Logged per the executor scope-boundary rule. These are pre-existing failures NOT
caused by any Phase 16 change — do NOT fix them in this phase.

| Discovered in | Item | Evidence it is pre-existing | Disposition |
|---------------|------|-----------------------------|-------------|
| 16-01 Task 2 | `tests/test_config.py::test_key_encryption_secret_default` FAILS — asserts `Settings().key_encryption_secret == ""` but the local `.env` has `KEY_ENCRYPTION_SECRET` set (v1.2 BYOK), so pydantic-settings loads it. | `git stash` of my Task 2 edit → the test still fails at HEAD. Untouched by my append (I added functions after `test_model_cache_ttl_env_override`). | Environmental test debt; the assertion assumes a clean env. Not a Phase 16 concern. |
| 16-01 (full-suite run) | `tests/test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` ERROR (missing `user_id` fixture). | Already recorded in STATE.md / PROJECT.md known tech debt: "test_record_manager.py fixture debt (pre-v1.1)". | Pre-existing; tracked in the milestone deferred-items table. |
