---
phase: quick-260718-o4c
plan: 01
subsystem: backend-tests
tags: [integration-tests, postgrest, supabase, regression-guard, threads, folders, documents]
requires: []
provides:
  - "backend/tests/integration real-DB smoke suite (skip-guarded, marker-tagged, self-cleaning)"
  - "PostgREST-shape regression guard for GET/PATCH/DELETE /api/threads/{id}, GET /api/folders/{id}/contents, GET /api/documents"
affects:
  - backend/tests
tech-stack:
  added: []
  patterns:
    - "Real-DB integration tests: get_supabase NEVER mocked; auth overridden; system-user FK-satisfying seed rows; teardown-after-yield cleanup; sentinel-prefixed throwaway rows"
key-files:
  created:
    - backend/tests/integration/__init__.py
    - backend/tests/integration/conftest.py
    - backend/tests/integration/test_thread_shapes.py
    - backend/tests/integration/test_folder_doc_shapes.py
  modified: []
decisions:
  - "Real dev Supabase (.env) is the only DB available (dual-env setup has no separate test project) — mutation is the accepted approach, mitigated by sentinel prefix + system-user ownership + teardown-after-yield + skip guard."
  - "Upload/Storage flows (POST /api/documents/upload) left OUT OF SCOPE — direct row inserts are sufficient to guard READ-path shapes without Storage-object scaffolding."
metrics:
  duration: 4m9s
  completed: 2026-07-18
  tasks: 3
  files: 4
---

# Quick Task 260718-o4c: Real-DB Integration Smoke Tests for DB-Shape Endpoints Summary

A skip-guarded, self-cleaning `backend/tests/integration` suite (6 tests) that exercises REAL PostgREST round-trips (get_supabase NOT mocked) so shape regressions like the `get_thread` `maybe_single()`+`*, messages(*)` APIError-204 bug fail in pytest before deploy.

## What Was Built

Four new files under `backend/tests/integration/` (no product code touched):

- **`__init__.py`** — `SENTINEL = "__inttest_260718__"`, `SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"` (real `auth.users` row from migration 017, satisfies the `user_id` FK with no admin API), `HAS_SUPABASE` computed from `get_settings()`, and `requires_supabase = pytest.mark.skipif(...)`. The `integration` marker is already registered in `backend/pytest.ini` under `--strict-markers`, so no ini change was needed.
- **`conftest.py`** — autouse `override_auth` (runs requests as the system user, `get_supabase` stays REAL), `client`, `db`, and three seed fixtures (`seeded_thread` = thread + 2 messages inserted later-row-first with explicit 2020 timestamps; `seeded_folder`; `seeded_document`). Every fixture tears down after yield (idempotent delete-by-id), so a failed assertion still cleans up.
- **`test_thread_shapes.py`** (4 tests) — the canonical `test_get_thread_embeds_and_sorts_messages` (real `*, messages(*)` round-trip → 200 + 2 messages asc-ordered; would 500 on the pre-hotfix code), PATCH persist + no-clobber + null-clear, DELETE 204 + row-gone + cascade, and 404 on a nonexistent id.
- **`test_folder_doc_shapes.py`** (2 tests) — folder-contents shape (real `_get_folder_or_404` safe `maybe_single` + child selects) and documents-list raw row-shape (no `response_model`).

## Verification Results (run against dev Supabase)

| Command | Result |
|---------|--------|
| `pytest backend/tests/integration -p no:dash -q` | **6 passed** |
| `pytest backend/tests/integration/test_thread_shapes.py -p no:dash -q` | 4 passed |
| `pytest backend/tests/integration/test_folder_doc_shapes.py -p no:dash -q` | 2 passed |
| `pytest backend/tests/integration -p no:dash -q -m "not integration"` | 4 deselected (0 run, exit 0) — deselection works |
| Skip guard: creds cleared (`SUPABASE_URL="" VITE_SUPABASE_URL="" SUPABASE_SERVICE_ROLE_KEY=""`) | **6 skipped** (not errored), reason "integration: dev Supabase creds absent" |
| `pytest backend/tests -k thread -p no:dash -q` | 17 passed (mocked thread tests unaffected) |
| Mocked `test_thread_usage_exposed.py` + `test_thread_model_patch.py` | 4 passed (no product-code regression) |
| Orphan-row check (threads/folders/documents/messages for sentinel/system-user rows) | **0 orphans** — teardown ran cleanly |

The canonical GET test asserts 200 + both messages present + ordered asc by `created_at` (`messages[0]["content"] == "first"` even though the later "second" row was inserted first) — proving the real embedding + Python asc-sort contract end-to-end. That is the exact delta that 500s on the pre-hotfix `maybe_single()` + embedding code.

## Deviations from Plan

None — plan executed exactly as written. No product code was modified. No new real bugs surfaced.

## Authentication Gates

None.

## Known Stubs

None — the suite is fully wired to the real dev DB.

## Notes / Scope Boundaries

- The suite MUTATES the dev Supabase project (creates + deletes throwaway rows). Mitigations in place: sentinel prefix `__inttest_260718__`, fresh UUIDs per run, system-user ownership (never visible to real logged-in users), teardown-after-yield, and the skip guard. Post-run orphan grep confirmed zero leaked rows.
- `POST /api/documents/upload` (real Storage upload) is intentionally out of scope — direct row inserts guard the READ-path shapes without Storage-object scaffolding.
- Skip-guard proof required clearing creds via env vars (env overrides `.env` in pydantic-settings); with creds present all 6 run green.

## Self-Check: PASSED

- FOUND: backend/tests/integration/__init__.py
- FOUND: backend/tests/integration/conftest.py
- FOUND: backend/tests/integration/test_thread_shapes.py
- FOUND: backend/tests/integration/test_folder_doc_shapes.py
- FOUND commit d442331 (Task 1 harness)
- FOUND commit 747e3f5 (Task 2 thread shapes)
- FOUND commit 828b479 (Task 3 folder/doc shapes)
