---
phase: 11-per-request-key-model-resolution-chat-loop-seam
plan: 06
subsystem: api
tags: [byok, langsmith, tracing, security, kill-switch, supabase, rls, gap-closure]

# Dependency graph
requires:
  - phase: 11-05
    provides: run-level LangSmith gate — tracing_context(enabled=not is_user_key) around the @traceable _traced_turn worker in chat.py, with key resolution hoisted above the traced region
provides:
  - Runtime-flippable GLOBAL LangSmith master toggle — one SQL UPDATE on app_settings flips tracing live within ~15s, no restart, no admin UI
  - supabase/migrations/20240301000034_create_app_settings.sql — global key/value app_settings table, seeded langsmith_enabled=true, RLS enabled with ZERO policies (deny-by-default, service-role only)
  - backend/services/app_settings_service.py — is_langsmith_enabled(db): ~15s TTL-cached service-role flag read, default-on (True) on missing row or ANY read error, never raises
  - chat.py tracing gate refined to the composed rule enabled=langsmith_on and not is_user_key (flag OFF kills ALL runs incl. owner; flag ON preserves the 11-05 BYOK gate exactly)
  - test_app_settings_service.py + test_langsmith_runtime_toggle.py — flag-reader unit coverage + empirical composition truth table + the flag-read-error security invariant + a binding gate tying chat.py to the real flag reader
affects: [v1.2-milestone-audit, prod-redeploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Global deny-by-default settings table: RLS ENABLED with zero CREATE POLICY statements — anon/authenticated read nothing, only the service-role client (bypasses RLS) reads it; satisfies the all-tables-need-RLS rule for non-user-scoped config"
    - "Module-level TTL cache (NOT @lru_cache) for runtime-flippable flags: time-bounded reads make a DB flip go live without restart while capping per-turn DB load to one read per window"
    - "Fail-safe composition: default-on flag reads are safe ONLY because the security conjunct (not is_user_key) is resolved locally and independently — a broken flag read can never widen the BYOK gate"

key-files:
  created:
    - supabase/migrations/20240301000034_create_app_settings.sql
    - backend/services/app_settings_service.py
    - backend/tests/test_app_settings_service.py
    - backend/tests/test_langsmith_runtime_toggle.py
  modified:
    - backend/routers/chat.py

key-decisions:
  - "TTL is a module constant (_TTL_SECONDS = 15), NOT a config.py env field — no per-deploy reason to tune it and env drift would only obscure the flip latency (Claude's discretion, as directed by the plan)"
  - "Default-on (True) on missing row or read error — default-off would silently kill owner observability on a transient DB blip; default-on is safe because the locally-resolved `not is_user_key` conjunct keeps BYOK turns untraced regardless of the flag read outcome (T-11-06-04 accept-with-control)"
  - "Flip mechanism is the Supabase SQL editor only — an owner-guarded HTTP flip endpoint is explicitly out of scope for this plan"
  - "Prod application of migration 034 deliberately deferred — ships with the next prod deploy alongside the 11-05 fix (D-03 dual-env discipline)"

patterns-established:
  - "Runtime kill-switch above a security gate composes by AND, never OR: enabled = master_flag and security_conjunct — the master flag can only narrow, never widen, the traced set"

requirements-completed: [SEC-01 — code-level complete; milestone closure gated on prod human UAT re-verify after redeploy (same gate as 11-05)]

# Metrics
duration: ~10min agent execution + human-action checkpoint (dev db push) + ~5min continuation bookkeeping
completed: 2026-07-10
---

# Phase 11 Plan 06: Runtime LangSmith Master Toggle Summary

**DB-backed live LangSmith kill-switch: a single SQL UPDATE on the new deny-by-default app_settings table flips tracing for everyone within ~15s (TTL-cached is_langsmith_enabled read), composed into 11-05's run gate as `enabled=langsmith_on and not is_user_key` so flag OFF silences even owner runs while BYOK turns stay untraced under every flag state — including failed flag reads.**

## Performance

- **Duration:** ~10 min agent execution (commits 07:52–07:56 local), then a blocking human-action checkpoint (dev db push, verified 17:12 UTC), then ~5 min continuation bookkeeping
- **Completed:** 2026-07-10
- **Tasks:** 3 (2 TDD auto tasks + 1 blocking human-action checkpoint)
- **Files:** 4 created, 1 modified

## Accomplishments

- **Migration 034 (`20240301000034_create_app_settings.sql`):** generic global `app_settings(key text PK, value jsonb, updated_at)` table, seeded `langsmith_enabled='true'::jsonb` with `ON CONFLICT (key) DO NOTHING`, `ENABLE ROW LEVEL SECURITY` with deliberately ZERO `CREATE POLICY` statements — deny-by-default means anon/authenticated clients see nothing; only the backend service-role client (bypasses RLS) reads the flag. Idempotent for `db push` replay; header documents the SQL-editor flip statements and the D-03 dev-now/prod-at-deploy note.
- **Flag reader (`app_settings_service.py`):** `is_langsmith_enabled(db) -> bool` with a module-level TTL cache (`_TTL_SECONDS = 15`, `time.monotonic()` stamp — NOT `@lru_cache`, so a flip goes live without restart), defensive `_coerce_bool` jsonb coercion (bool / "true"/"false" case-insensitive / 0/1, unrecognized -> True), missing row or ANY exception -> True with a `logger.warning` and never raises, plus a `_reset_cache()` test hook.
- **Composed gate (`chat.py`):** module-level `from services.app_settings_service import is_langsmith_enabled` (patchable/assertable as `chat.is_langsmith_enabled`); per-turn `langsmith_on = is_langsmith_enabled(db)` (line 871) read after key resolution + the `no_key` refusal and OUTSIDE the traced region; 11-05's gate refined to exactly one `with tracing_context(enabled=langsmith_on and not is_user_key):` (line 1421). No other chat.py behavior touched — `_traced_turn`, SSE yields, and every `trace=(not is_user_key)` defense-in-depth argument left intact.
- **Security invariant proven in-process:** `test_flag_read_error_defaults_true_byok_still_gated` drives the real `is_langsmith_enabled` against a raising db stub — the read defaults to True, yet the composed gate still yields `get_current_run_tree() is None` for a BYOK turn. A broken flag read can never trace a user-key turn.
- **Dev DB applied and live-flip proven end-to-end** at the Task 3 checkpoint (evidence below): migration pushed, seed row confirmed via the service-role client, OFF->ON flip smoke test passed, flag restored to True.

## Task Commits

TDD gate sequence (RED test commit precedes GREEN feat commit for both tasks):

1. **Task 1 (RED): failing unit tests for is_langsmith_enabled** - `00f9871` (test)
2. **Task 1 (GREEN): migration 034 + TTL-cached flag reader** - `03011da` (feat)
3. **Task 2 (RED): runtime-toggle truth table + invariant + binding gate** - `b5dd312` (test)
4. **Task 2 (GREEN): composed gate `enabled=langsmith_on and not is_user_key` in chat.py** - `64a9849` (feat)
5. **Task 3: dev DB apply** — operational only (no repo file changes); evidence recorded below.

**Worktree merge:** `a579688` (chore: merge executor worktree) — all four task commits verified on master.

## TDD Gate Compliance

RED gate (`test(...)` commits `00f9871`, `b5dd312`) and GREEN gate (`feat(...)` commits `03011da`, `64a9849`) both present and correctly ordered per task. No REFACTOR commits needed.

## Files Created/Modified

- `supabase/migrations/20240301000034_create_app_settings.sql` — global app_settings table + seed + deny-by-default RLS (structural gates: 1x CREATE TABLE IF NOT EXISTS, 1x ENABLE ROW LEVEL SECURITY, 1x ON CONFLICT (key) DO NOTHING, 0x CREATE POLICY)
- `backend/services/app_settings_service.py` — TTL-cached, default-on, never-raising flag reader
- `backend/tests/test_app_settings_service.py` — 14 passing tests across 7 functions: row true/false, missing row (None AND empty-list data shapes) -> True, db exception -> True without raising, parametrized jsonb coercion, deterministic TTL hit-then-expiry (monkeypatched monotonic time, no sleeps)
- `backend/tests/test_langsmith_runtime_toggle.py` — 6 tests: the 4-cell composition truth table (flag x is_user_key) asserted empirically via `get_current_run_tree()` under `chat.tracing_context`, the flag-read-error security-invariant test, and `test_chat_binds_app_settings_flag_reader` (asserts `chat.is_langsmith_enabled is app_settings_service.is_langsmith_enabled`)
- `backend/routers/chat.py` — one import + one per-turn flag read + the one-line gate refinement

## Task 3 Checkpoint Evidence (dev DB apply — recorded verbatim)

Operator response: **approved** — the operator ran the push and the orchestrator verified the seed row and live-flip. Evidence:

1. `supabase db push` (dev project, default .env — Claude RAG dummy project ntkkmljbariflblldmha) output:
```
Connecting to remote database...
Do you want to push these migrations to the remote database?
 • 20240301000034_create_app_settings.sql
 [Y/n]
Applying migration 20240301000034_create_app_settings.sql...
Finished supabase db push.
```
(First attempts failed with `unexpected login role status 544: Connection terminated due to connection timeout` — dev project was unreachable/paused; succeeded after retry. CLI v2.95.4.)

2. Seed row confirmation via service-role client:
```
[{'key': 'langsmith_enabled', 'value': True, 'updated_at': '2026-07-10T17:12:59.210682+00:00'}]
```

3. Live-flip smoke test (service-role update, then restored):
```
after OFF : [{'key': 'langsmith_enabled', 'value': False}]
after ON  : [{'key': 'langsmith_enabled', 'value': True}]
```
Flag is currently True (restored). Prod deliberately NOT touched — migration 034 ships to prod with the next deploy alongside the 11-05 fix (D-03 dual-env discipline).

## Deviations from Plan

None material — plan executed as written. One in-spirit coverage addition during Task 1: an extra defensive unit test (`test_missing_row_empty_list_defaults_true`) covers the empty-list `.data` shape alongside the specified None-data case; both assert the default-on contract. No scope creep; no files touched outside the five plan files.

## Verification Results

Re-verified on merged master (post-merge `a579688`) by the continuation agent:

- `test_app_settings_service.py` — **14 passed** (row true/false, missing row -> True, exception -> True no-raise, jsonb coercion matrix, TTL hit + deterministic expiry).
- `test_langsmith_runtime_toggle.py` — **6 passed** (4-cell truth table + flag-read-error security invariant + binding structural gate).
- Regression: `test_langsmith_run_gate.py` + `test_langsmith_gate.py` + `test_key_model_resolution.py` + `test_deprecated_model_fallback.py` — **25 passed**, zero failures.
- Migration structural gates: `MIGRATION_GATES_OK` (exactly 1 CREATE TABLE IF NOT EXISTS, 1 ENABLE ROW LEVEL SECURITY, 1 ON CONFLICT (key) DO NOTHING, 0 CREATE POLICY).
- chat.py structural gates (comment-excluded): `CHAT_GATES_OK` — `is_langsmith_enabled(db)` count = 1, `langsmith_on and not is_user_key` count = 1 (exactly one composed gate).
- Dev apply confirmed at the checkpoint (seed row + live-flip smoke, evidence above); prod deferred to deploy.

## Known Stubs

None — no placeholder/empty-data stubs introduced.

## Threat Flags

None — all new surface (global app_settings table at the RLS trust boundary, per-turn flag read) was pre-registered in the plan's threat model (T-11-06-01..05) with mitigations implemented and test-covered as specified.

## Next Phase Readiness

- **HUMAN RE-VERIFY (downstream, blocking SEC-01 milestone closure — same gate as 11-05):** after the prod backend is redeployed (which also applies migration 034 to prod), re-run the SEC-01 (a) manual UAT against the LIVE prod LangSmith project — a BYOK turn must produce ZERO runs; additionally the SQL flip toggle can then be smoke-tested against prod. REQUIREMENTS.md SEC-01 stays gated until that passes (v1.2 audit owns the gate).
- The 11-05 + 11-06 pair closes the code-level side of both SEC-01 gap items; phase 11 gap-closure execution is complete pending the milestone audit's prod re-verify.

## Self-Check: PASSED

- FOUND: supabase/migrations/20240301000034_create_app_settings.sql
- FOUND: backend/services/app_settings_service.py
- FOUND: backend/tests/test_app_settings_service.py
- FOUND: backend/tests/test_langsmith_runtime_toggle.py
- FOUND: backend/routers/chat.py (modified — lines 19, 871, 1421)
- FOUND commits on master: 00f9871, 03011da, b5dd312, 64a9849, merge a579688

---
*Phase: 11-per-request-key-model-resolution-chat-loop-seam*
*Completed: 2026-07-10*
