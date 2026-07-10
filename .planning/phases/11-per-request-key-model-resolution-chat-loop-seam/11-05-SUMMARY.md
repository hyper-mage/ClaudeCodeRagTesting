---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 05
subsystem: api
tags: [byok, langsmith, tracing, security, sse, fastapi, gap-closure]

# Dependency graph
requires:
  - phase: 11-04
    provides: _resolve_key_and_model (api_key, model, mode, is_user_key) + trace=(not is_user_key) threading into all four LLM call sites
provides:
  - run-LEVEL LangSmith gate at the chat parent seam — tracing_context(enabled=not is_user_key) around a @traceable inner _traced_turn worker
  - send_message endpoint no longer @traceable-wrapped (body.content never captured into an ungated run)
  - key/model resolution hoisted ABOVE the traced region; no_key refusal opens no run
  - test_langsmith_run_gate.py — run-level SEC-01 regression coverage (structural + behavioral incl. threaded tool dispatch + owner-not-regressed guards)
affects: [11-06-runtime-langsmith-toggle, v1.2-milestone-audit, prod-redeploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Run-layer tracing gate: resolve trust tier FIRST, then wrap the turn in tracing_context(enabled=...) around a @traceable inner worker — one contextvar suppresses parent + asyncio.to_thread children + wrap_openai spans"
    - "Deterministic async-generator teardown: drive the inner worker via `async for` inside try/finally with `await worker.aclose()` so GeneratorExit still reaches the worker's finally"

key-files:
  created:
    - backend/tests/test_langsmith_run_gate.py
  modified:
    - backend/routers/chat.py

key-decisions:
  - "Gate lives at the parent seam only — explorer_service.py / subagent_service.py / tracing.py / llm_service.py untouched; the enabled=False contextvar provably suppresses their @traceable runs through asyncio.to_thread (guardrail test pins them as @traceable)"
  - "The inner _traced_turn worker takes no explicit args (closure capture) so owner-turn runs no longer record request content as inputs on entry"
  - "REQUIREMENTS.md SEC-01 checkbox deliberately NOT flipped — the plan's success criteria gate SEC-01 (a) closure on the downstream human prod-LangSmith UAT re-verify after redeploy (v1.2 audit owns that gate)"

patterns-established:
  - "Resolve-before-trace: any per-request trust decision that gates observability must be computed before the first traced region opens"

requirements-completed: [SEC-01 (a) code-level — prod human UAT re-verify pending]

# Metrics
duration: ~15min
completed: 2026-07-10
---

# Phase 11 Plan 05: Run-level LangSmith gate (SEC-01 a) Summary

**Dropped the ungated `@traceable` endpoint decorator, hoisted key resolution above the traced region, and wrapped the whole turn in `tracing_context(enabled=not is_user_key)` around a `@traceable` inner worker — a BYOK turn now opens ZERO LangSmith runs (parent + both `asyncio.to_thread` subagents + wrap_openai spans) while owner/demo turns stay fully traced.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-10
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files:** 1 created, 1 modified

## Accomplishments

- **The leak (found by the v1.2 milestone audit / 11-HUMAN-UAT):** Phase 11 gated only the inner `wrap_openai` client spans; a pre-existing `@traceable(name="chat_send_message")` on the endpoint (present since Module 1) plus global `LANGCHAIN_TRACING_V2=true` opened an ungated run for EVERY turn, capturing `body.content` on entry — so BYOK prompts/responses landed in the owner's prod LangSmith project. Two subagent `@traceable` sites leaked the same way on tool turns.
- **The fix (all in `backend/routers/chat.py`):**
  1. Removed the endpoint `@traceable` decorator (`@limiter.limit` stays adjacent to the raw fn per slowapi #2128).
  2. Added a module-level `tracing_context` import with an ImportError no-op `@contextlib.contextmanager` fallback (module attribute — the regression test binds to `chat.tracing_context`).
  3. Hoisted `_resolve_key_and_model` + the `no_key` refusal to the very top of `event_generator` — `is_user_key` is known before any run can open, and a refused turn opens no run.
  4. Moved the entire turn body into a nested `@traceable(name="chat_send_message")` `async def _traced_turn()` (closure capture; `nonlocal model` for the deprecated-pin override) driven by `with tracing_context(enabled=not is_user_key): async for ev in worker: yield ev` with `await worker.aclose()` in a finally.
- **Verified live against langsmith 0.3.42:** `enabled=False` yields `get_current_run_tree() is None` at the parent, a direct child, AND an `asyncio.to_thread` child; `enabled=True` yields RunTree at all three — the exact explorer/doc-analysis dispatch pattern.
- **Owner observability preserved:** parent run, both subagent runs, wrap_openai spans, and the cap-hit `get_current_run_tree().add_metadata(...)` all still fire for `is_user_key=False`; every existing `trace=(not is_user_key)` argument kept as defense-in-depth.

## Task Commits

Each task was committed atomically (TDD gate sequence):

1. **Task 1 (RED): failing run-level SEC-01 regression test** - `d4a3fbd` (test) — structural test failed on the shipped decorator; both behavioral tests failed with `AttributeError: module 'routers.chat' has no attribute 'tracing_context'`; guardrail passed — exactly the predicted RED signature.
2. **Task 2 (GREEN): move the LangSmith gate to the run layer** - `84fff14` (feat)

## Files Created/Modified

- `backend/tests/test_langsmith_run_gate.py` — 4 tests: `test_endpoint_handler_not_traceable` (structural), `test_subagent_sites_remain_traceable` (guardrail pinning the parent-seam coverage assumption), `test_user_key_turn_creates_zero_runs` (full user-key turn incl. direct + threaded child dispatch → zero runs at every site), `test_owner_turn_still_traced` (owner runs restored at every site). Offline/deterministic: dummy LangSmith env + neutered `Client.create_run/update_run`.
- `backend/routers/chat.py` — the four edits above; no functional chat change (SSE event shapes, error codes, retry/dedup, notice rows, budget, usage persistence, `mode:"demo"` done signal all preserved).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical error handling] Hoisted resolution wrapped in its own try/except**
- **Found during:** Task 2 (edit 3)
- **Issue:** Pre-change, a `_resolve_key_and_model` exception (e.g. decrypt/DB failure) was caught by `event_generator`'s generic `except Exception` and surfaced as a scrubbed SSE error event. Hoisting it above the traced worker moved it outside that try — an exception would have crashed the SSE stream with no structured event.
- **Fix:** Wrapped the hoisted call in a try/except mirroring the worker's generic branch (same scrubbed SSE error shape; no assistant row exists yet so nothing to mark).
- **Files modified:** backend/routers/chat.py
- **Commit:** 84fff14

**2. [Rule 2 - Missing critical cleanup] Deterministic `worker.aclose()` on client disconnect**
- **Found during:** Task 2 (edit 4)
- **Issue:** The plan's driving snippet (`async for ev in _traced_turn(): yield ev`) leaves GeneratorExit raised at the OUTER yield on client disconnect — the inner worker's finally (the `[Response interrupted]` stamp) would only run at GC time, a regression vs. the pre-change single-generator layout.
- **Fix:** Drive the worker inside try/finally with `await worker.aclose()`, throwing GeneratorExit into `_traced_turn` at its suspension point so its finally cleanup runs deterministically and the traceable wrapper closes the parent run.
- **Files modified:** backend/routers/chat.py
- **Commit:** 84fff14

---

**Total deviations:** 2 auto-fixed (both behavior-preservation requirements of the seam restructure). No scope creep; no changes outside the two plan files.

## Verification Results

- `test_langsmith_run_gate.py` **4/4** + `test_langsmith_gate.py` **1/1** green.
- Regression: `test_key_model_resolution.py` + `test_deprecated_model_fallback.py` + `test_explorer_integration.py` + `test_error_surfacing.py` — **32 passed**, zero failures.
- Full backend suite (excluding the two env-only live-integration files, per 11-04 precedent): **241 passed, 2 errors** — both are the known pre-existing `test_record_manager` `user_id`-fixture errors (STATE.md pending todo, out of scope).
- Structural: comment-excluded grep for `tracing_context(enabled=not is_user_key)` = 1; `@traceable(name="chat_send_message")` count = exactly 1 (on the inner worker); `chat.send_message` carries no `__langsmith_traceable__`.
- No edits to `explorer_service.py`, `subagent_service.py`, `tracing.py`, `llm_service.py`, `test_langsmith_gate.py` (git-verified clean).

## Environment Note

The worktree has no `backend/venv` (gitignored); tests ran with the shared-checkout venv python (`backend/venv/Scripts/python.exe` from the main checkout) with cwd in the worktree `backend/` — conftest.py's sys.path insertion resolves `routers`/`services` to the worktree sources (same approach as 11-04).

## Known Stubs

None — no placeholder/empty-data stubs introduced.

## Next Phase Readiness

- **HUMAN RE-VERIFY (downstream, blocking SEC-01 milestone closure):** after this ships and the prod backend is redeployed, re-run the SEC-01 (a) manual UAT gate against the LIVE prod LangSmith project with a real OAuth-provisioned OpenRouter key + a free model — a BYOK "hi" turn (and an explore_kb tool turn) must produce ZERO runs in prod LangSmith. REQUIREMENTS.md SEC-01 stays `Pending` until that gate passes.
- Plan 11-06 (runtime LangSmith master toggle) composes cleanly with this seam: the per-turn `enabled=not is_user_key` gate is orthogonal to a global master toggle.

## Self-Check: PASSED

- FOUND: backend/tests/test_langsmith_run_gate.py
- FOUND: backend/routers/chat.py (modified)
- FOUND: 11-05-SUMMARY.md
- FOUND commits: d4a3fbd (Task 1 test), 84fff14 (Task 2 feat)

---
*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Completed: 2026-07-10*
