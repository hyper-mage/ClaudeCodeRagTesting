# Deferred Items — Phase 11

Out-of-scope discoveries logged during execution (NOT fixed — pre-existing, unrelated to the current task's changes).

## From 11-01 execution

- **Pre-existing collection errors in `backend/tests/test_record_manager.py`** (lines 83, 120): `test_check_duplicate_integration` and `test_find_previous_version_integration` fail at setup with `fixture 'user_id' not found`. These are pre-existing failures present on the plan base commit, in a file NOT part of plan 11-01's `files_modified`. They predate this work and are out of scope. The rest of the suite (150 tests) passes. Fix belongs to whoever owns `test_record_manager.py` (likely a renamed/removed `user_id` fixture).

## From 11-03 execution

- **Pre-existing collection error in `backend/tests/test_e2e_subagent.py`** (line 11): `KeyError: 'VITE_SUPABASE_URL'`. This is a live E2E test that reads `os.environ["VITE_SUPABASE_URL"]` at import and hits `localhost:8000` + a real Supabase project. It errors at collection when `.env` is absent (e.g. an isolated worktree). Not part of plan 11-03's `files_modified`; environmental, not a code defect — out of scope. The `test_record_manager.py` integration errors (above) also recurred for the same reason. The rest of the unit suite is green (165 passed, 9 Wave-0 stubs skipped).

## D-11-A: Two MANDATORY SEC-01 manual sign-off gates — deferred to BYOK prod deploy

Phase 11 verification is `human_needed` (4/4 must-haves automated-verified; code complete + merged; suite 174 passed). Two SEC-01 gates have no automated substitute and require BYOK running live with a real OAuth-provisioned key against live LangSmith + log sinks — which does not exist until BYOK is deployed to prod. **Deferred by user decision 2026-06-22; resurface at the BYOK prod deploy step.**

1. **prod-LangSmith zero-user-key-run** — send a BYOK chat turn on a real user key; confirm ZERO runs appear in the prod LangSmith project for that turn (the `wrap_openai` gate is off when `trace=False`). Highest-blast-radius (A5/D-10).
2. **live `exc_info` traceback redaction** — force a logged exception carrying an `sk-or-` token on the chat path; confirm the live log sink shows `[redacted-key]`, not the raw token (`_ScrubFilter` end-to-end).

**Where tracked:** `11-HUMAN-UAT.md` (test steps), `11-VALIDATION.md` (marked MANDATORY), `11-VERIFICATION.md` (status `human_needed`), memory `project_phase11_execution`.

**To close:** when BYOK is live in prod, run both; on pass, flip Phase 11 verification `human_needed → passed`. Phase 11 advances WITHOUT this (the automated 4/4 are green). NOT the same as SEC-03 (the separate demo-fallback cost-guardrail gate, backlog 999.2, that hard-blocks Phase 15).
