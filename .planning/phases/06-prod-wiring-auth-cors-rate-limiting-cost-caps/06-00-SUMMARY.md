---
phase: 06
plan: 00
subsystem: backend-tests
tags: [phase-06, wave-0, test-scaffolding, sec-04, sec-05, nyquist]
requires: []
provides:
  - mock_stream_chat_completion fixture (drives routers/chat.py inner generator)
  - mock_user_id, mock_jwt, mock_request_with_user, mock_request_no_user fixtures
  - mock_langsmith_run fixture (SEC-05 LangSmith metadata mock)
  - 6 SEC-04 placeholder tests in tests/test_rate_limit.py
  - 4 SEC-05 placeholder tests in tests/test_chat_cap.py
  - 4 SEC-04/SEC-05 config defaults placeholders in tests/test_config.py
affects:
  - backend/tests/conftest.py (extended, not replaced)
  - backend/tests/ (3 new files)
tech-stack:
  added: []
  patterns:
    - pytest.mark.skip placeholders (Wave-0 collectable + green pattern)
    - monkeypatch.setattr at imported-symbol module (routers.chat.stream_chat_completion)
    - MagicMock controller object pattern (programmable per-call event sequences)
key-files:
  created:
    - backend/tests/test_rate_limit.py
    - backend/tests/test_chat_cap.py
    - backend/tests/test_config.py
  modified:
    - backend/tests/conftest.py
decisions:
  - "Patch stream_chat_completion at routers.chat.* (post-import reference), not services.llm_service.* — guards against the most common slowapi-fixture mistake"
  - "Use @pytest.mark.skip(reason='Wave 1 06-0X: ...') for all placeholders so CI is green from day 0; Wave 1 removes one decorator per implementation task"
  - "MagicMock controller exposes set_default_tool_call() / set_events() methods for deterministic generator drivers"
metrics:
  duration_minutes: ~5
  completed: 2026-05-09
---

# Phase 6 Plan 00: Test Scaffolding Summary

Pure additive Wave 0 test scaffolding for SEC-04 (rate limiting) and SEC-05 (chat tool-loop cap) — 14 placeholder tests + 6 fixtures landed across 1 conftest extension and 3 new test files. All placeholders skip cleanly so CI stays green; Wave 1 (06-01, 06-02) flips them to passing as each behavior lands.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0-1 | Extend conftest.py with rate-limit + cap-hit fixtures | `45ba767` | backend/tests/conftest.py |
| 0-2 | Create test_rate_limit.py with SEC-04 placeholders | `d5da80a` | backend/tests/test_rate_limit.py |
| 0-3 | Create test_chat_cap.py + test_config.py with SEC-05 placeholders | `af251f3` | backend/tests/test_chat_cap.py, backend/tests/test_config.py |

## Verification Results

```
$ pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -v
============================= 14 skipped in 0.05s =============================
```

- 14 placeholder tests collected, 14 SKIPPED, 0 FAILED, 0 ERRORS
- Pre-existing collection errors in other tests/* files (missing `pydantic_settings`, `supabase`, `openai` modules) are environmental — out of scope per Rule SCOPE BOUNDARY (worktree lacks `backend/venv/`; main-repo install state unaffected by this plan).

## Acceptance Criteria — All Met

**Task 0-1 (conftest.py):**
- 5 new fixture defs (`mock_user_id`, `mock_jwt`, `mock_request_with_user`, `mock_request_no_user`, `mock_langsmith_run`) + the critical `mock_stream_chat_completion` = 6 total new fixture defs.
- Patch target string `routers.chat.stream_chat_completion` present (correct post-import patching).
- Existing `test_user_id` and `explorer_scenarios` fixtures preserved.

**Task 0-2 (test_rate_limit.py):**
- 6 test functions: `test_limiter_module_importable`, `test_user_id_key_func`, `test_user_id_key_func_fallback`, `test_chat_route_decorated`, `test_429_response_shape`, `test_auth_fail_does_not_tick`.
- 6 `@pytest.mark.skip(reason="Wave 1 06-01: ...")` decorators.

**Task 0-3 (test_chat_cap.py + test_config.py):**
- test_chat_cap.py: 4 functions (`test_cap_hit_graceful_exit`, `test_cap_hit_logs_warning`, `test_cap_hit_langsmith_tag`, `test_voluntary_stop_preserved`) — `test_cap_hit_graceful_exit` correctly references `mock_stream_chat_completion` in its signature.
- test_config.py: 4 functions (`test_chat_max_iterations_default`, `test_chat_max_iterations_env_override`, `test_chat_rate_limit_default`, `test_chat_rate_limit_env_override`).
- All 8 marked `@pytest.mark.skip(reason="Wave 1 06-0X: ...")`.

## Key Design Choices

1. **Patch site discipline.** `routers/chat.py` does `from services.llm_service import stream_chat_completion`, so the symbol bound inside `routers.chat` is what the loop calls. Patching `services.llm_service.stream_chat_completion` would be too late (the import already copied the reference). Fixture explicitly patches `routers.chat.stream_chat_completion` and the docstring calls this out so future agents don't "fix" it the wrong way.

2. **Controller object pattern.** `mock_stream_chat_completion` returns a MagicMock-with-methods controller (`.set_default_tool_call()`, `.set_events([...])`, `.call_count`) instead of a raw callable. Lets each Wave 1 test configure event sequences inline without redefining the patcher.

3. **Skip-from-day-0.** Every placeholder is `@pytest.mark.skip(reason="Wave 1 06-0X: ...")` (not `xfail`) so CI exit code stays 0 throughout Wave 0. Wave 1 task acceptance criteria require removing the decorator AND making the body pass — explicit, atomic flip.

4. **`del req.state.user_id` in `mock_request_no_user`.** MagicMock auto-creates attrs on access; `del` removes them so subsequent `getattr(req.state, "user_id", None)` returns `None`, exercising the limiter's `'anonymous'` fallback path correctly.

## Deviations from Plan

None — plan executed exactly as written. No bugs found, no missing functionality, no architectural changes needed. (Pure test scaffolding, no production code touched.)

## Authentication Gates

None encountered (no external services touched).

## Known Stubs

None. All placeholders are `@pytest.mark.skip` with explicit Wave 1 references — they are intentional scaffolding tracked by the per-task validation map in `06-VALIDATION.md`. They do NOT block Phase 6 goal achievement; rather, they are the gating mechanism that forces Wave 1 implementation tasks to flip them green one-by-one.

## Threat Flags

None — Wave 0 is test-only; introduces no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

**Files verified:**
- `backend/tests/conftest.py` — FOUND (extended, 175 total lines)
- `backend/tests/test_rate_limit.py` — FOUND (85 lines, 6 tests, 6 skips)
- `backend/tests/test_chat_cap.py` — FOUND (66 lines, 4 tests, 4 skips)
- `backend/tests/test_config.py` — FOUND (39 lines, 4 tests, 4 skips)

**Commits verified in git log:**
- `45ba767` — FOUND (conftest.py extension)
- `d5da80a` — FOUND (test_rate_limit.py)
- `af251f3` — FOUND (test_chat_cap.py + test_config.py)

**Test outcome verified:**
- `pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -v` → 14 skipped, 0 failed, 0 errored, exit 0.
