---
phase: 15-options-ui-capstone-demo-gating
plan: 02
subsystem: backend
tags: [python, fastapi, byok, demo-fallback, model-cache, security, tdd, sec-03]

# Dependency graph
requires:
  - phase: 12-model-catalog
    provides: "model_cache table with precomputed is_free column (migration 030, model_catalog_service._to_cache_row)"
  - phase: 11-byok-usage-capture
    provides: "_resolve_key_and_model seam (fail-closed key resolution), SEC-03 killswitch test trio, scrub_secrets logging house style"
provides:
  - "_demo_model_for(db, model, settings): D-03 server-side free-guard — picked model runs ONLY when model_cache.is_free is True; paid/unknown/non-dict/error -> pinned demo_fallback_model (unknown != free)"
  - "D-11 use_demo override in _resolve_key_and_model: getattr(body,'use_demo',False) AND settings.demo_fallback_enabled in ONE condition, positioned BEFORE the user-key branch; flag OFF -> completely inert"
  - "Resolution order: use_demo+flagON -> demo | user key -> user | flagON keyless -> demo | no_key"
  - "7 new resolution tests + model_cache branch in the _db_with_key_row test dispatcher (cache_is_free / cache_raises params)"
affects: [15-07, 15-08, frontend-use-demo-retry, demo-banner]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Server-side freeness guard reads model_cache.is_free only (never pricing or the :free suffix); defensive maybe_single shape `row and isinstance(row.data, dict) and row.data.get('is_free') is True`"
    - "Request-body override gated on its server flag in the SAME condition as the override read (never a separate nested check that could drift)"

key-files:
  created: []
  modified:
    - backend/routers/chat.py
    - backend/tests/test_key_model_resolution.py

key-decisions:
  - "Both demo entries (use_demo override + keyless fallback) route through the single _demo_model_for helper so the free-guard can never be skipped on one path (RESEARCH Pitfall 4)"
  - "Cache-read failure logs logger.warning with scrub_secrets(str(e)) and falls back to the pinned model — mirrors the T-13-CRASH tolerance shape; a cold/mid-refresh cache never 500s a turn (T-15-07)"
  - "requirements.mark-complete deliberately NOT run: DEMO-01 is shared with parallel plan 15-01 and pending plans 15-07/15-08, SEC-03 with 15-08 — marking here would be premature and would merge-conflict sibling worktrees; orchestrator owns REQUIREMENTS.md"

patterns-established:
  - "model_cache branch in the _db_with_key_row test dispatcher: cache_is_free=True/False -> row dict, None -> .data None (unknown), cache_raises=True -> execute() raises"

requirements-completed: []
requirements-progressed: [DEMO-01, SEC-03]

# Metrics
duration: ~8min
completed: 2026-07-05
---

# Phase 15 Plan 02: Demo Free-Guard + use_demo Override Summary

**Demo turns now run the user's PICKED model on the owner key only when `model_cache.is_free is True` (server-side D-03 guard — paid/unknown/cache-error fall back to the pinned `demo_fallback_model`), and a `use_demo: true` request body short-circuits to the demo branch before the user-key branch ONLY while `demo_fallback_enabled` is ON — SEC-03 fail-closed posture byte-identical when OFF.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-07-06T01:21:45Z
- **Completed:** 2026-07-06T01:30Z (approx)
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments
- `_demo_model_for(db, model, settings)` added above `_resolve_key_and_model` in `backend/routers/chat.py`: one-row `model_cache` read (`select("is_free").eq("model_id", model).maybe_single()`), returning the picked model ONLY on `row and isinstance(row.data, dict) and row.data.get("is_free") is True`; ANY other outcome — `is_free=False`, `.data is None` (unknown ≠ free), non-dict data, or an exception — returns `settings.demo_fallback_model`. Exceptions log scrubbed (`scrub_secrets(str(e))`), never escape.
- D-11 `use_demo` override inserted after the model-tier resolution and BEFORE the `user_api_keys` read: `if getattr(body, "use_demo", False) and settings.demo_fallback_enabled` → `(settings.resolved_llm_api_key, _demo_model_for(...), "demo", False)`. Flag OFF → the condition is false and resolution proceeds exactly as before (inert both keyed and keyless).
- Keyless demo branch re-routed through the same `_demo_model_for` helper instead of pinning; user-key branch and `no_key` tail left byte-identical. Final order: `use_demo+flagON → demo` › `user key → user` › `flagON keyless → demo` › `no_key`.
- Test scaffolding: `_db_with_key_row` gained `cache_is_free: bool | None = None` and `cache_raises: bool = False` params plus a `model_cache` dispatcher branch; `user_api_keys`/`user_preferences` branches untouched so all prior mocks resolve unchanged.
- 7 new tests (4 free-guard + 3 override), all green; full file 15/15 passed.

## TDD Gate Compliance
- RED gate: `test(15-02)` commit `10fc92c` — 2 tests failed for the right reason (`test_demo_runs_picked_free_model`: demo branch pinned the fallback; `test_use_demo_override_beats_user_key_when_flag_on`: no override existed), killswitch trio green, 5 new tests passing as regression guards of preserved behavior.
- GREEN gate: `feat(15-02)` commit `a5cd828` — all 15 tests green.
- REFACTOR: not needed (implementation matched the RESEARCH code example shape directly).

## Task Commits

1. **Task 1 (RED): extend resolution test scaffolding + failing free-guard/override tests** - `10fc92c` (test)
2. **Task 2 (GREEN): _demo_model_for free-guard + flag-gated use_demo override** - `a5cd828` (feat)

## Files Created/Modified
- `backend/routers/chat.py` - Added `_demo_model_for` helper (D-03 guard, T-15-07 tolerance); D-11 override before the user-key branch; keyless demo branch routed through the guard; resolver docstring updated to the four-branch order.
- `backend/tests/test_key_model_resolution.py` - `model_cache` branch in the `_table` dispatcher (per-test configurable: free/paid/unknown/raising); 7 new tests covering picked-free, paid-fallback, unknown-fallback, cache-error-fallback, override-beats-user-key, flag-OFF-inert (keyed + keyless).

## Decisions Made
- Both demo entry points share the single `_demo_model_for` helper — structurally impossible to skip the free-guard on one path (Pitfall 4 mitigation).
- Kept the override's flag check inside the same `if` condition (not nested) so a future edit cannot separate the override from its gate without failing the pinned inert tests.
- Skipped `requirements.mark-complete` (see key-decisions): DEMO-01/SEC-03 are multi-plan requirements still carried by 15-01/15-07/15-08; marking is the orchestrator's post-wave call.

## Deviations from Plan

None - plan executed exactly as written. The RED state had 2 of 7 new tests failing (not all 7) because the paid/unknown/error-fallback and flag-OFF-inert tests assert behavior the pre-change resolver already exhibited — they are regression pins, and the plan's verify gate (`-k` selection exits non-zero) was satisfied as specified.

## Verification Results
- `pytest tests/test_key_model_resolution.py -q` → 15 passed (was 8 at baseline).
- Killswitch trio (`test_sec03_killswitch_no_owner_spend_when_flag_off`, `test_no_key_flag_off_refuses`, `test_fail_closed_no_or_fallback`): `git diff 8c0fcde..HEAD` touches ZERO lines of those three function bodies; all three green.
- Acceptance greps: `def _demo_model_for(` (chat.py:152), `.get("is_free") is True` (chat.py:170), combined `getattr(body, "use_demo", False) and settings.demo_fallback_enabled` (chat.py:212, before the user_api_keys read at ~line 226). `settings.resolved_llm_api_key` is returned at exactly 2 sites (lines 214, 243), both governed by `demo_fallback_enabled` (Pitfall 4 warning-sign clear).
- Wave-1 merge gate (full backend suite) intentionally NOT run in-task per plan (shared working tree; 2 pre-existing record_manager errors documented as permitted).

## Security (threat model verification)
- T-15-05 (EoP, use_demo override): flag checked in the same condition before the user-key branch; inert tests (keyed + keyless) + killswitch trio pinned green. Mitigated.
- T-15-06 (Tampering, FE-forged free model): `is_free is True` validated server-side against model_cache; every other outcome pins the fallback — owner spend structurally bounded to the free model. Mitigated.
- T-15-07 (DoS, cache read in-turn): try/except around the read; failure → pinned fallback, never a 500. Mitigated (test_demo_cache_error_falls_back).
- T-15-08 (Info disclosure, new logging): the only new log line uses `scrub_secrets(str(e))`, no `exc_info` near key material. Mitigated.
- T-15-09 (cost DoS backstop): transferred to the provider $0.10 guardrail per the register — no code change required.

## Known Stubs
None — no placeholder values, empty-data wires, or TODO/FIXME markers introduced.

## Issues Encountered
- The worktree has no `backend/venv` (gitignored); ran the main checkout's venv Python with cwd inside the worktree's `backend/` — `tests/conftest.py` inserts the worktree backend dir at `sys.path[0]`, so the worktree's `routers.chat` was the module under test (same approach as prior wave executions).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 15-07 (retry UI) can send `use_demo: true` on the retry path — the resolver honors it iff the flag is ON; `MessageCreate.use_demo` field lands in 15-01 (this resolver already tolerates its absence via `getattr`).
- Plan 15-08 (prod flip) inherits the guard unchanged; the pinned `demo_fallback_model` remains the worst-case cost bound.
- STATE.md / ROADMAP.md / REQUIREMENTS.md intentionally NOT modified (worktree mode — orchestrator owns post-wave shared writes).

## Self-Check: PASSED

Both modified files exist on disk (`backend/routers/chat.py`, `backend/tests/test_key_model_resolution.py`); both task commits reachable (`10fc92c` test, `a5cd828` feat); full resolution test file 15/15 green; killswitch trio diff-clean vs base `8c0fcde`.

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-05*
