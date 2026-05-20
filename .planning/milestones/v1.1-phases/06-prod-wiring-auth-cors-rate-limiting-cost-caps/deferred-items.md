# Deferred Items — Phase 06

Pre-existing issues discovered during execution but out of scope per scope-boundary rule.

## Pre-existing test collection / setup errors (unrelated to Phase 06)

- `tests/test_e2e_subagent.py` — collection fails with `KeyError: 'VITE_SUPABASE_URL'`. Test is a true e2e against a running server + real Supabase; not safe to run in the unit-test pass.
- `tests/test_record_manager.py::test_check_duplicate_integration` — setup error (env-dependent integration test).
- `tests/test_record_manager.py::test_find_previous_version_integration` — setup error (env-dependent integration test).

These exist on `main` independent of Phase 06 changes. They should be either gated (`pytest.mark.skipif`) or moved into a separate `integration/` folder with its own opt-in marker. Tracked for future cleanup.
