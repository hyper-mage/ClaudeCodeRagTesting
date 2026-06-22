---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 01
subsystem: testing
tags: [pydantic-settings, secret-scrubbing, regex, pytest, byok, openrouter, sse, config]

# Dependency graph
requires:
  - phase: 09-byok-key-encryption
    provides: "crypto_service round-trip + get_settings.cache_clear() test pattern (test_crypto_service.py)"
  - phase: 10-observability
    provides: "frontend sk-or-v1- scrub regex in sentry.ts mirrored (broadened) on the backend"
provides:
  - "Settings.demo_fallback_enabled (default False, D-09 fail-closed) + Settings.demo_fallback_model (:free slug, D-06)"
  - "backend/services/log_scrub.py::scrub_secrets() — backend sk-or- redaction primitive (SEC-01)"
  - "4 Wave 0 test scaffolds with 12 named stubs matching the RESEARCH Test Map verbatim"
  - "conftest mock_stream_chat_completion.set_usage() — optional trailing usage event for D-04"
affects: [11-02-migration, 11-03-llm-client-seam, 11-04-resolution-and-error-surfacing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Backend secret-scrub primitive mirrors FE sentry.ts regex, broadened to sk-or- per D-11"
    - "Wave 0 collected-but-skipped test scaffolds — downstream plans un-skip + implement"
    - "Additive fixture extension (set_usage) leaves existing controller callers untouched"

key-files:
  created:
    - backend/services/log_scrub.py
    - backend/tests/test_key_model_resolution.py
    - backend/tests/test_langsmith_gate.py
    - backend/tests/test_error_surfacing.py
    - backend/tests/test_usage_capture.py
  modified:
    - backend/config.py
    - backend/tests/test_config.py
    - backend/tests/conftest.py

key-decisions:
  - "demo_fallback_enabled defaults False in dev AND prod this phase (D-09) — fail-closed cost bound; flip is a Phase 15 / SEC-03 decision"
  - "Backend scrub regex broadened to sk-or-[A-Za-z0-9_-]+ (D-11) vs the FE sk-or-v1- form — catches any future OpenRouter key prefix"
  - "Scrub + config tests kept in test_config.py (single file, Claude's Discretion) rather than a separate test_log_scrub.py"
  - "Wave 0 stubs use @pytest.mark.skip + raise NotImplementedError body so they collect green and fail loudly if un-skipped without an implementation"

patterns-established:
  - "Wave 0 stub scaffold: @pytest.mark.skip(reason='Wave 0 stub …') with NotImplementedError body and a module docstring naming the requirement(s)"
  - "set_usage(usage_per_call) controller method appends a trailing usage event per call index, None to skip"

requirements-completed: [SEC-01, DEMO-03]

# Metrics
duration: ~25min
completed: 2026-06-22
---

# Phase 11 Plan 01: Per-request key/model resolution Wave 0 + config foundation Summary

**Demo-fallback Settings fields (OFF by default, :free model), a broadened backend `scrub_secrets()` sk-or- redaction primitive, and 12 collected-but-skipped Wave 0 test stubs that plans 03/04 will turn green.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-22T20:40Z (approx)
- **Completed:** 2026-06-22T21:06Z
- **Tasks:** 2
- **Files modified:** 8 (5 created, 3 modified)

## Accomplishments
- Added `demo_fallback_enabled: bool = False` (D-09 fail-closed) and `demo_fallback_model: str = "meta-llama/llama-3.3-70b-instruct:free"` (D-06) to `Settings`, env-driven, with no resolution method and no new `@lru_cache` (Pitfall 8 respected).
- Created `backend/services/log_scrub.py` with `scrub_secrets()` — compiles `sk-or-[A-Za-z0-9_-]+` once at module scope, substitutes `[redacted-key]`, passes non-str through unchanged (SEC-01 chokepoint, broadened from FE per D-11).
- Created 4 new Wave 0 test files with all 12 RESEARCH Test Map function names (incl. `test_logging_filter_scrubs_exc_info`), each marked skipped so the suite stays green and downstream plans can un-skip + implement.
- Extended conftest `mock_stream_chat_completion` with `set_usage()` so D-04 usage-capture tests can drive a trailing `{"type":"usage","usage":{…}}` event — additive, existing callers unaffected.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add demo-fallback config fields + scrub_secrets helper** - `ce1798a` (feat) — TDD: tests written RED (AttributeError on missing field), then config fields + helper added GREEN (6/6 tests pass). Test + impl committed together as one task commit per single-file scope.
2. **Task 2: Wave 0 test scaffolds + conftest usage event** - `8bd4cea` (test)

**Plan metadata:** committed by the worktree metadata step (SUMMARY.md).

## Files Created/Modified
- `backend/config.py` - Added `demo_fallback_enabled` + `demo_fallback_model` Settings fields with D-06/D-09 doc comments.
- `backend/services/log_scrub.py` - NEW. `scrub_secrets()` SEC-01 primitive, broadened sk-or- regex compiled at module scope.
- `backend/tests/test_config.py` - Added 4 config default/env-override tests + 2 scrub tests (6 total).
- `backend/tests/test_key_model_resolution.py` - NEW. 6 DEMO-03/SEC-04/D-03 stubs.
- `backend/tests/test_langsmith_gate.py` - NEW. 1 SEC-01 wrap-gate stub.
- `backend/tests/test_error_surfacing.py` - NEW. 3 stubs (scrub-in-SSE, 429/402 codes, logging.Filter exc_info).
- `backend/tests/test_usage_capture.py` - NEW. 2 D-04 usage stubs.
- `backend/tests/conftest.py` - Extended `mock_stream_chat_completion` with `set_usage()` + `_usage_per_call` trailing-event support.

## Decisions Made
- Kept the 2 scrub tests in `test_config.py` alongside the config tests rather than a separate `test_log_scrub.py` (plan allowed Claude's Discretion) — single import surface, both target the new Phase 11 config/security primitives.
- Wave 0 stub bodies `raise NotImplementedError` under `@pytest.mark.skip` so that if a downstream plan un-skips without implementing, the test fails loudly instead of passing vacuously.

## Deviations from Plan

None - plan executed exactly as written. (TDD Task 1 wrote tests RED then implementation GREEN within a single task commit, as its files were a single cohesive config+helper unit.)

## Issues Encountered
- **Worktree lacks `.env` → import-time `KeyError: 'VITE_SUPABASE_URL'` in `test_e2e_subagent.py` during full-suite collection.** This file reads `os.environ["VITE_SUPABASE_URL"]` at module top; the gitignored `.env` exists only in the shared checkout, not the worktree. Resolved for the verification run by exporting non-secret placeholder VITE vars (`http://placeholder.local` / `placeholder-anon-key`) so collection completes — NOT by reading the restricted `.env`. This is an environment artifact of the worktree, not a code regression, and does not affect any committed file.
- **Backend venv lives only in the shared checkout** (gitignored). Ran the plan's `venv/Scripts/python` verify commands via the shared `backend/venv/Scripts/python.exe` interpreter with cwd set to the worktree backend, so the worktree's source `config.py`/`services/` were exercised.

## TDD Gate Compliance
Task 1 (`tdd="true"`) followed RED → GREEN: the 6 config/scrub tests were authored first and confirmed failing (`AttributeError: 'Settings' object has no attribute 'demo_fallback_enabled'`) before the `Settings` fields and `log_scrub.py` were added to turn them green. Because the test file and implementation form one tightly-scoped config unit, they share a single `feat(11-01)` task commit (`ce1798a`) rather than separate test/feat commits; the RED→GREEN sequence was verified live during execution.

## Pre-existing / Deferred (out of scope)
Logged to `.planning/phases/11-.../deferred-items.md`:
- `backend/tests/test_record_manager.py::test_check_duplicate_integration` and `::test_find_previous_version_integration` error at setup (`fixture 'user_id' not found`). Pre-existing on the plan base commit, in a file NOT in this plan's `files_modified` — out of scope, not fixed.

## Verification Results
- `pytest tests/test_config.py -x -q -k "demo_fallback or scrub"` → 6 passed.
- `pytest tests/test_key_model_resolution.py tests/test_langsmith_gate.py tests/test_error_surfacing.py tests/test_usage_capture.py -q` → 12 skipped (no red, no collection error).
- `pytest --collect-only` lists all 6 / 3 / 2 / 1 named functions per file (12 total).
- Full suite `pytest tests/ -q` → **162 passed, 12 skipped**, 2 pre-existing out-of-scope errors (record_manager) — green for everything in scope; conftest extension broke no existing caller.
- `grep -nE "sk-or-\[A-Za-z0-9_-\]\+" backend/services/log_scrub.py` → matches the broadened backend regex.

## Next Phase Readiness
- **11-02** (migration) and **11-03/11-04** (LLM-client seam, resolution + error surfacing) can now reference the two config fields, `scrub_secrets()`, and the 12 named stubs — all `<verify>` targets in plans 03/04 resolve.
- `set_usage()` is ready for the D-04 usage-capture tests in plan 03/04 to drive trailing usage events.
- No blockers introduced.

## Self-Check: PASSED

All claimed files exist and both task commits are present:
- FOUND: backend/services/log_scrub.py, test_key_model_resolution.py, test_langsmith_gate.py, test_error_surfacing.py, test_usage_capture.py, config.py, test_config.py, conftest.py, 11-01-SUMMARY.md
- FOUND commits: ce1798a (Task 1), 8bd4cea (Task 2)

---
*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Completed: 2026-06-22*
