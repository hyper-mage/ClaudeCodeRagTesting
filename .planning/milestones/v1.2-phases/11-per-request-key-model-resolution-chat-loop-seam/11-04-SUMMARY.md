---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 04
subsystem: api
tags: [byok, openrouter, fastapi, sse, logging, security, fernet]

# Dependency graph
requires:
  - phase: 11-01
    provides: scrub_secrets primitive, demo_fallback_enabled/demo_fallback_model settings, Wave-0 test stubs
  - phase: 11-02
    provides: messages.usage JSONB column
  - phase: 11-03
    provides: api_key/model/trace params on stream_chat_completion, run_exploration, run_document_analysis, search_documents/rerank; drain-and-capture usage event
provides:
  - _resolve_key_and_model() — single per-request, fail-closed three-branch key + three-tier model resolver
  - resolved key/model threaded into the budget lookup and all four LLM call sites
  - scrubbed + structured SSE error path (no_api_key / rate_limit / payment_required)
  - _ScrubFilter logging.Filter closing the exc_info traceback leak (SEC-01 "never in logs")
  - summed OpenRouter usage persisted to messages.usage + mode:"demo" signal on the done event
affects: [phase-12-model-selection, phase-13-user-preferences, phase-15-demo-banner-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-request fail-closed resolution: module-level helper (never @lru_cache'd) returning (api_key, model, mode, is_user_key)"
    - "logging.Filter on ROOT handlers + the emitting logger (routers.chat) to scrub the formatted record incl. the exc_info traceback"
    - "Typed OpenRouter error catch order: RateLimitError (429) BEFORE APIStatusError.status_code==402 (no 402 subclass)"

key-files:
  created: []
  modified:
    - backend/routers/chat.py
    - backend/tests/test_key_model_resolution.py
    - backend/tests/test_error_surfacing.py
    - backend/tests/test_usage_capture.py
    - backend/tests/test_chat_cap.py
    - backend/tests/test_chat_retry.py
    - backend/tests/test_explorer_integration.py

key-decisions:
  - "Empty-row guard requires isinstance(row.data, dict) — a list/None means no user key, fall through (defends against supabase chain shape variance)"
  - "Legacy chat tests (chat_cap/chat_retry/explorer) stub _resolve_key_and_model to the owner-key user path since they predate BYOK; resolution itself is covered by test_key_model_resolution.py"
  - "Reworded the helper docstring to remove the literal 'user_key or owner_key' phrase — the fail-closed static assertion strips only #-comment lines, not docstrings"

patterns-established:
  - "Pattern 1: fail-closed three-branch key resolution — if user_key / elif demo_flag_on / else refuse (no fail-open one-liner)"
  - "Pattern 2: belt-and-suspenders secret scrub — inline scrub_secrets on the message string PLUS a _ScrubFilter that scrubs the exc_info traceback"
  - "Pattern 3: capture-sum usage across every tool-loop iteration; cost authoritative, token sub-fields tolerated"

requirements-completed: [SEC-04, SEC-01, DEMO-03]

# Metrics
duration: ~40min (resumed from partial)
completed: 2026-06-22
---

# Phase 11 Plan 04: Per-request key+model resolution chat-loop seam Summary

**A single fail-closed `_resolve_key_and_model` helper threads the per-request OpenRouter key+model into the budget lookup and all four LLM call sites, scrubs SSE/log errors (incl. the exc_info traceback via a logging.Filter), surfaces distinct 429/402 codes, and persists summed usage with a demo-mode signal.**

## Performance

- **Duration:** ~40 min (resumed from a partial that died on a rate limit at ~40%)
- **Completed:** 2026-06-22
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- `_resolve_key_and_model(db, user_id, thread_row, body) -> (api_key, model, mode, is_user_key)`: module-level, not cached, fail-closed three-branch key (user → demo → refuse) and three-tier model (body → thread.model → user_preferences.default_model → owner default) tolerant of the absent P13 schema.
- Switched the budget context-length lookup to the resolved key+model — the easy-to-miss fifth owner-key read (Pitfall 1) — and threaded `api_key/model/trace=(not is_user_key)` into `stream_chat_completion`, `run_exploration`, `run_document_analysis`, and `execute_tool`→`search_documents`.
- Fail-closed `no_api_key` SSE refusal (DEMO-03): a keyless user with the demo flag OFF gets a structured error and no LLM call is made.
- SEC-01 closure: `scrub_secrets(str(e))` on the SSE error payload + log message, distinct `rate_limit`(429)/`payment_required`(402) structured codes, and a `_ScrubFilter` logging.Filter installed on the ROOT handlers + the `routers.chat` logger that scrubs the formatted record AND the `exc_info` traceback (where a decrypted key can sit as a stack-frame local).
- Summed OpenRouter usage persisted to `messages.usage` and surfaced on the `done` event with a `mode:"demo"` signal when applicable.
- All 12 Wave-0 stubs un-skipped + passing across four test files.

## Task Commits

Each task was committed atomically:

1. **Task 1: _resolve_key_and_model helper + budget switch + call-site threading** - `6acf84b` (feat)
2. **Task 2: scrubbed/structured SSE errors + exc_info log filter** - `73877b5` (test)
3. **Task 3: usage summed across loop, persisted to messages.usage** - `2cf1f11` (test)

_Note: the chat.py runtime changes for the error path (Task 2) and usage path (Task 3) landed in the Task 1 commit because chat.py is a single file; the per-task test files were committed separately._

## Files Created/Modified

- `backend/routers/chat.py` - `_resolve_key_and_model` + `_safe_thread_model` + `_safe_user_default_model` helpers; `_ScrubFilter` + `_install_scrub_filter`; `_sse_error` + `_mark_error_row`; `_accumulate_usage`; budget switch; call-site threading; typed 429/402 catches; usage capture/persist/done signal.
- `backend/tests/test_key_model_resolution.py` - 6 resolution tests un-skipped (no_key refuse, demo free model, fail-closed no-or shape, no cross-user bleed, model fallthrough, threaded-to-all-sites).
- `backend/tests/test_error_surfacing.py` - 3 tests un-skipped: sk-or- scrubbed in SSE, distinct 429/402 codes, end-to-end exc_info log-filter scrub.
- `backend/tests/test_usage_capture.py` - `test_usage_persisted_to_messages` un-skipped: summed usage persisted + on the done event.
- `backend/tests/test_chat_cap.py`, `backend/tests/test_chat_retry.py`, `backend/tests/test_explorer_integration.py` - legacy-test compatibility: stub `_resolve_key_and_model` (predate BYOK) + accept the new `api_key/model/trace` stream kwargs.

## Decisions Made

- Empty-row guard hardened to `isinstance(row.data, dict)` so a supabase chain returning a list/MagicMock `.data` correctly falls through to demo/no_key rather than crashing.
- Legacy chat tests stub the resolver to the owner-key `user` path; their job is the cap/retry/explorer behaviors, not key resolution (covered by `test_key_model_resolution.py`).
- The fail-closed static assertion in `test_fail_closed_no_or_fallback` strips only `#`-comment lines, not docstrings — so the helper docstring was reworded to remove the literal `user_key or owner_key` phrase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fail-closed static assertion tripped by the docstring phrase**
- **Found during:** Task 1 (resuming the partial)
- **Issue:** The partial's helper docstring contained the literal `NEVER \`user_key or owner_key\``, which survived the test's `#`-comment stripping and tripped `test_fail_closed_no_or_fallback`.
- **Fix:** Reworded the docstring line to "NEVER a fail-open one-liner".
- **Files modified:** backend/routers/chat.py
- **Verification:** `grep -v '^#' | grep -c "user_key or owner_key"` → 0; the 6 resolution tests pass.
- **Committed in:** 6acf84b (Task 1 commit)

**2. [Rule 1 - Bug] Empty-row guard crashed on non-dict .data**
- **Found during:** Full-suite regression check (test_explorer_integration)
- **Issue:** `row.data.get("encrypted_key")` raised `AttributeError: 'list' object has no attribute 'get'` when a test's generic supabase chain returned a list `.data` for the `user_api_keys` read.
- **Fix:** Guarded with `isinstance(row.data, dict)` before `.get(...)`.
- **Files modified:** backend/routers/chat.py
- **Verification:** test_explorer_integration + full suite pass.
- **Committed in:** 6acf84b (Task 1 commit)

**3. [Rule 3 - Blocking] Legacy chat tests refused after resolution wiring**
- **Found during:** Full-suite regression check
- **Issue:** Wiring the resolver into `event_generator` made keyless legacy chat tests (cap/retry/explorer) hit the `no_api_key` fail-closed refusal, so their loops never ran.
- **Fix:** Stubbed `_resolve_key_and_model` to the owner-key `user` path in those tests and extended the explorer stream stub to accept the new `api_key/model/trace` kwargs.
- **Files modified:** test_chat_cap.py, test_chat_retry.py, test_explorer_integration.py
- **Verification:** all 11 tests in those files pass.
- **Committed in:** 73877b5 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All auto-fixes were necessary for correctness or to keep the pre-existing suite green. No scope creep — the security shape of the helper is unchanged.

## Issues Encountered

- The worktree has no `venv` and no repo-root `.env` (gitignored, read-denied by policy). Tests were run with the shared-checkout `backend/venv` python and cwd in the worktree backend. Two live-integration files (`test_e2e_subagent.py`, `test_tracing.py`) read `os.environ["VITE_SUPABASE_URL"]` at import and require real credentials; they are environmental, not chat-related, and were excluded from the regression run (they collect cleanly once env is present).

## Test Results

- `test_key_model_resolution.py` (6), `test_error_surfacing.py` (3), `test_usage_capture.py` (2), `test_langsmith_gate.py` (1) — **12 passed**.
- Full suite (excluding the two env-only live-integration files): **170 passed, 2 errors** — the 2 errors are the known pre-existing `test_record_manager` integration fixture errors (`fixture 'user_id' not found`), unrelated to this plan.

## Known Stubs

None — no placeholder/empty-data stubs introduced. The `mode:"demo"` banner UI is intentionally deferred to Phase 15 (the backend signal rides the `done` event now; `useChat.ts:185` keys only on `message_id` so the extra key is inert).

## Next Phase Readiness

- The resolution seam is complete: future model-selection (P12) and user-preferences (P13) work can populate `body.model` / `thread.model` / `user_preferences.default_model` and the three-tier resolver will pick them up with no further chat.py changes.
- Manual prod-LangSmith validation (a BYOK turn produces zero user-key runs; a tripped free-model rate cap shows distinct 402/429 copy; a logged key-bearing exception shows `[redacted-key]` in the traceback) remains flagged as manual-only per the plan's VALIDATION notes.

## Self-Check: PASSED

- FOUND: backend/routers/chat.py + the 7 modified files
- FOUND: 11-04-SUMMARY.md
- FOUND commits: 6acf84b (Task 1), 73877b5 (Task 2), 2cf1f11 (Task 3), ccc3b87 (docs)

---
*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Completed: 2026-06-22*
