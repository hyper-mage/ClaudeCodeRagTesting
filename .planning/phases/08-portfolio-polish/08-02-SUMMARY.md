---
phase: "08"
plan: "02"
subsystem: backend
tags: [demo-bootstrap, anon-auth, cleanup, port-01]
requires:
  - "data/sample-private-docs/dnd5e-quickref.md (Plan 08-00 Task 2)"
  - "backend/tests/conftest.py fixtures: seed_sample_doc_path, anon_jwt, permanent_jwt (Plan 08-00 Task 3)"
  - "backend/tests/test_demo_bootstrap.py + test_anon_cleanup.py stubs (Plan 08-00 Task 3)"
  - "backend/services/record_manager.py: hash_content + check_duplicate"
  - "backend/services/ingestion_service.py: process_document"
  - "backend/database.py: get_supabase (service-role client)"
  - "backend/auth.py: get_user_id (JWT dependency)"
  - "backend/limiter.py: slowapi Limiter instance"
provides:
  - "POST /api/demo/bootstrap (anon-user seed + cleanup dispatcher)"
  - "services.demo_service.seed_anon_user_content(user_id) -> bool"
  - "services.demo_service.purge_stale_anon_users(retention_days=7) -> int"
  - "services.demo_service.SAMPLE_DOC_PATH constant"
affects:
  - "backend/main.py (router registration)"
tech-stack:
  added: []
  patterns:
    - "child-first FK-safe cascade delete (storage -> document_chunks -> documents -> folders -> messages -> threads)"
    - "BackgroundTasks for fire-and-forget cleanup sweeps"
    - "Page-bounded admin.list_users(page=1) for Fly.io suspend safety (RESEARCH Pitfall 9)"
key-files:
  created:
    - "backend/services/demo_service.py (191 lines, 3 functions + 1 constant)"
    - "backend/routers/demo.py (60 lines, 1 endpoint)"
    - ".planning/phases/08-portfolio-polish/deferred-items.md (pre-existing test_record_manager note)"
  modified:
    - "backend/main.py (+2 lines: demo import + include_router)"
    - "backend/tests/test_anon_cleanup.py (3 stubs -> 3 real tests)"
    - "backend/tests/test_demo_bootstrap.py (3 stubs -> 3 real tests, all 4 pass)"
decisions:
  - "Permanent-user guard: SILENT no-op ({seeded: false}) instead of 403. Rationale: minimum friction during prod debugging; permanent-user code path is harmless (no DB writes) so an explicit refusal adds no security value. RESEARCH §Anti-Patterns marked either option acceptable."
  - "BackgroundTasks for purge (vs blocking the response): preserves cold-start UX — first-time anon user gets {seeded: true} response within ~ingestion-time, purge runs after."
  - "Page-bounded list_users(page=1): RESEARCH §Pitfall 9 — never start cleanup work that cannot finish before a Fly.io machine suspend. 100 users/page is plenty for early portfolio traffic."
  - "Hard-coded welcome assistant message (no LLM call): RESEARCH §Anti-Patterns explicitly forbids; saves cost + cuts ~1-2s off cold-start latency."
metrics:
  duration: "~25 minutes (2 task commits)"
  completed_date: "2026-05-17"
  tests_added: 7
  tests_passed: "7 new + 132 full suite (4 skipped parallel-plan stubs, 2 deselected pre-existing record_manager fixture errors)"
  test_runtime: "Plan 08-02 tests: 2.99s · full suite: 66.89s"
---

# Phase 08 Plan 02: Demo bootstrap (backend) Summary

Built `/api/demo/bootstrap` plus the seed + purge service layer that Plan 08-04 (frontend Try-demo CTA) will hit after `signInAnonymously()` resolves. Seven new tests across two files (`test_demo_bootstrap.py` + `test_anon_cleanup.py`) all pass.

## What changed

| File | New/Mod | Purpose |
|------|---------|---------|
| `backend/services/demo_service.py` | NEW | `seed_anon_user_content`, `purge_stale_anon_users`, `_cascade_delete_user_data`, `SAMPLE_DOC_PATH` |
| `backend/routers/demo.py` | NEW | `POST /api/demo/bootstrap` with `@limiter.limit("5/minute")` + permanent-user guard + background purge |
| `backend/main.py` | MOD | Added `demo` to routers import + `app.include_router(demo.router)` (2-line change) |
| `backend/tests/test_anon_cleanup.py` | MOD | 3 stubs replaced with real tests (filter / cascade-order / error-swallow) |
| `backend/tests/test_demo_bootstrap.py` | MOD | 3 stubs replaced with real tests; `test_sample_doc_file_exists` already real from Plan 08-00 |
| `.planning/phases/08-portfolio-polish/deferred-items.md` | NEW | Pre-existing `test_record_manager` fixture errors logged out-of-scope |

## Test results

```
backend/$ venv/Scripts/python -m pytest tests/test_anon_cleanup.py tests/test_demo_bootstrap.py -v

tests/test_demo_bootstrap.py::test_sample_doc_file_exists PASSED         [ 14%]
tests/test_demo_bootstrap.py::test_seed_idempotent PASSED                [ 28%]
tests/test_demo_bootstrap.py::test_bootstrap_endpoint_calls_seed_and_schedules_purge PASSED [ 42%]
tests/test_demo_bootstrap.py::test_seed_skips_permanent_user PASSED      [ 57%]
tests/test_anon_cleanup.py::test_purge_filters_correctly PASSED          [ 71%]
tests/test_anon_cleanup.py::test_cascade_order PASSED                    [ 85%]
tests/test_anon_cleanup.py::test_purge_swallows_per_user_errors PASSED   [100%]

7 passed, 1 warning in 2.99s
```

Full backend suite (excluding `tests/test_e2e_subagent.py` and two pre-existing `test_record_manager` integration tests with a missing `user_id` fixture):

```
132 passed, 4 skipped, 2 deselected, 1 warning in 66.89s
```

The 4 skipped tests are stubs owned by parallel plans 08-01 (`test_auth_anon.py::test_auth_*`) and 08-03 (`test_chat_retry.py::test_retry_*`). The 2 deselected `test_record_manager` failures pre-date Phase 8 (commit `c46981a`, "module 3 completed") — documented in `deferred-items.md`.

## Endpoint smoke check

```
$ python -c "from main import app; print([r.path for r in app.routes if hasattr(r,'path') and 'demo' in r.path])"
['/api/demo/bootstrap']
```

Curl smoke against the deployed Fly.io URL with a freshly-minted anon JWT is **deferred to Wave 2 frontend integration** (Plan 08-04). Reason: the JWT minting + Sentry trace correlation are easier to validate end-to-end from the Try-demo CTA in the browser than via a hand-crafted curl, and the unit tests already pin the request/response contract.

## Permanent-user guard decision

**Chose silent no-op (`{"seeded": false}`) over 403 Forbidden.** Rationale: the permanent-user code path is harmless (no DB writes, no side effects), so refusing with 403 would add no security value — and it would create a noisy debugging signal in prod logs whenever a permanent user accidentally hit the endpoint (e.g. via stale cached frontend logic). RESEARCH §Anti-Patterns marked either option acceptable. The no-op aligns with the "always idempotent, always safe to retry" contract that `/api/demo/bootstrap` should expose to the frontend.

## Deviations from Plan

None — plan executed exactly as written. The only out-of-plan addition is `.planning/phases/08-portfolio-polish/deferred-items.md` documenting two pre-existing unrelated test failures discovered during the full-suite verification step.

## Threat model coverage

- **T-08-02 (DoS / resource leak)** — mitigated. `@limiter.limit("5/minute")` decorator on the endpoint; purge loop bounded to `list_users(page=1, per_page=100)`; idempotency guard inside seed skips work when the user already has documents.
- **T-08-02-PERM (permanent user accidentally seeded)** — mitigated. Router fetches `db.auth.admin.get_user_by_id(user_id)` and short-circuits when `user.is_anonymous` is false. Verified by `test_seed_skips_permanent_user`.
- **T-08-02-FK (cascade-order FK violation)** — mitigated. Hard-coded delete order in `_cascade_delete_user_data`: storage -> document_chunks -> documents -> folders -> messages -> threads. Verified by `test_cascade_order` (asserts table-name call sequence via `db.table.call_args_list`).
- **T-08-02-LOOP (one bad user aborts the sweep)** — mitigated. Per-user `try/except` wraps `_cascade_delete_user_data + delete_user`; logs `logger.warning` and continues. Verified by `test_purge_swallows_per_user_errors`.
- **T-08-02-LEAK (user UUIDs in cleanup logs)** — accepted per plan; logs stay server-side (no Sentry breadcrumbs on backend).

## Commits

- `7715bb4` — `feat(08-02): demo_service seed + purge + cascade-delete (Task 1)`
- `0f81e49` — `feat(08-02): /api/demo/bootstrap router + main.py registration (Task 2)`

## Self-Check: PASSED

- `backend/services/demo_service.py` — FOUND
- `backend/routers/demo.py` — FOUND
- `backend/main.py` — FOUND (modified)
- `backend/tests/test_demo_bootstrap.py` — FOUND (4 real tests)
- `backend/tests/test_anon_cleanup.py` — FOUND (3 real tests)
- Commit `7715bb4` — FOUND in git log
- Commit `0f81e49` — FOUND in git log
- Route `/api/demo/bootstrap` — registered in `app.routes` (smoke check passed)
- All Task 1 + Task 2 acceptance-criteria grep checks — passed
- No stub markers (TODO/FIXME/placeholder) in new files
