---
phase: 08-portfolio-polish
plan: "03"
subsystem: api
tags: [fastapi, sse, supabase, postgrest, retry, chat, dedup, tdd]

# Dependency graph
requires:
  - phase: 08-portfolio-polish
    provides: "Plan 08-00 — conftest fixtures (mock_stream_chat_completion, mock_user_id) + test_chat_retry.py skip stubs"
provides:
  - "Retry-aware POST /api/threads/{thread_id}/messages?retry=true contract"
  - "Backend dedup hook that deletes the orphan empty assistant row + skips duplicate user-row insert on retry"
  - "3-test regression suite for retry path (test_chat_retry.py)"
affects:
  - 08-04 (frontend useChat.retryLastUserMessage — consumes ?retry=true contract)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SELECT-then-DELETE-by-id fallback for supabase-py 2.13.0 (postgrest delete chain lacks order/limit)"
    - "FastAPI Query() bool param injected ahead of Depends() — OpenAPI exposes ?retry on the route"
    - "TestClient + monkeypatched routers.chat.get_supabase + mock_stream_chat_completion fixture pattern (mirrors test_chat_cap.py)"

key-files:
  created: []
  modified:
    - backend/routers/chat.py
    - backend/tests/test_chat_retry.py

key-decisions:
  - "Strategy A (backend cleanup before retry) per RESEARCH §Pitfall 3 — one query-param + guarded delete; no new endpoint, no extra round-trip"
  - "SELECT-then-DELETE-by-id (NOT chained .delete().order().limit()) — verified via dir() that postgrest SyncFilterRequestBuilder lacks order/limit on the delete path in supabase-py 2.13.0"
  - "Delete most-recent assistant row regardless of content (covers empty-placeholder, '[An error occurred...]', and '[Response interrupted]' variants) — more robust than content-equality match"
  - "User-message insert guarded by `if not retry:` — original user row preserved from prior failed send; re-inserting would duplicate the user turn"

patterns-established:
  - "Retry-aware mutation handlers: accept ?retry=true Query param; on retry, perform inverse-of-failure cleanup BEFORE re-running the success path"
  - "Scope-guarded delete: thread_id + user_id + role filter triple — survives JWT tampering even with service-role client"

requirements-completed: [PORT-02]

# Metrics
duration: ~25min
completed: 2026-05-17
---

# Phase 8 Plan 03: Backend retry-dedup hook for POST /threads/{id}/messages

**`POST /api/threads/{thread_id}/messages?retry=true` now deletes the orphan empty assistant row from the prior failed turn AND skips re-inserting the user message — chat retry is now data-layer-idempotent (one user + one final assistant per logical send).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-17T (post-Wave-0 sync)
- **Completed:** 2026-05-17
- **Tasks:** 1 (TDD with explicit RED → GREEN gate commits)
- **Files modified:** 2

## Accomplishments

- Added `retry: bool = Query(False)` parameter to `send_message` — OpenAPI now exposes `?retry=true|false` on the route (acceptance criterion verified: `'retry' in str(spec['paths']['/api/threads/{thread_id}/messages']['post']['parameters'])` → `True`).
- Retry branch performs SELECT-then-DELETE on the most-recent assistant row for `(thread_id, user_id, role='assistant')`, gated by the same thread-ownership check that protects the rest of the handler.
- User-message insert wrapped in `if not retry:` — preserves the original user turn instead of duplicating it.
- Default path (no `?retry` or `?retry=false`) is byte-identical to the pre-08-03 handler — all 4 chat_cap regression tests still pass.

## Task Commits

This task was TDD per `tdd="true"` on the single PLAN.md task. RED → GREEN gates committed separately to satisfy the plan-level TDD gate enforcement:

1. **RED — Failing retry-dedup tests** — `1e63e95` (test)
2. **GREEN — Retry-aware send_message impl** — `b338632` (feat)

Plan metadata commit follows the SUMMARY/STATE update (see final_commit below).

## Files Created/Modified

- `backend/routers/chat.py` — added `Query` import; extended `send_message` signature with `retry: bool = Query(False)`; inserted retry-cleanup block (SELECT-then-DELETE prior assistant row by id, scoped by thread_id + user_id + role); wrapped user-row insert in `if not retry:` guard. +43 / -7 lines.
- `backend/tests/test_chat_retry.py` — un-skipped Plan 08-00 stubs and added the third test (`test_retry_skips_user_message_insert`); 3 passing tests using `mock_stream_chat_completion` + monkeypatched `routers.chat.get_supabase`. +254 / -10 lines.

## Decisions Made

- **SELECT-then-DELETE-by-id instead of chained `.delete()...order().limit()`** — empirically verified with `dir(SyncFilterRequestBuilder)` that the chain isn't supported in supabase-py 2.13.0; PLAN.md explicitly endorses the fallback. The SELECT pulls only `id` (cheap), then DELETE-by-id is a primary-key lookup. Two queries, both indexed.
- **Delete most-recent assistant row regardless of content** — PATTERNS.md line 539 proposed `.eq("content", "")`, but the handler's `except` branch (line 866) sets content to `"[An error occurred while generating the response]"` and the `finally` branch (line 879) sets `"[Response interrupted]"`. Filtering by `content=""` would miss both. The most-recent-assistant-row-per-thread is unambiguous (the prior failed turn) and matches PLAN.md §behavior intent exactly.
- **Query() param placed BEFORE `user_id: Depends(get_user_id)`** — FastAPI accepts either ordering, but Query-params-before-Depends is the conventional shape and matches the rest of the file.

## Deviations from Plan

None — plan executed exactly as written, including the documented SELECT-then-DELETE fallback when chained `.delete().order().limit()` is unsupported.

The PATTERNS.md line 539 example used `.eq("content", "")` as the delete filter, but PLAN.md §action explicitly says "the orphan identifier (likely 'latest row where content IS NULL or content = '') is in the PLAN — follow PLAN exactly" and PLAN.md §behavior says to use the SELECT-then-DELETE fallback. Both pointers converge on the most-recent-assistant-row approach, which is more robust against the error/interrupted placeholder variants the handler writes in its except/finally blocks. Documenting here for traceability — not a deviation, just choosing among PLAN-sanctioned shapes.

## Issues Encountered

- **Worktree behind master at agent spawn** — the per-agent worktree branch was attached to commit `b85e44c` (end of Phase 7), missing all Phase 8 prerequisites (planning docs, conftest fixtures, test stubs, sample doc). Resolved by `git merge master --ff-only` from the worktree — fast-forwarded the per-agent branch to pick up Wave 0 outputs without rewriting any history. Worktree branch name (`worktree-agent-a785faee58d5b6044`) preserved.
- **Worktree has no own `venv/`** — pytest invoked via the absolute path to the main repo's `backend/venv/Scripts/python.exe`. The test runner's `rootdir` resolves to the worktree (cwd-based), so pytest collects tests from the worktree files correctly while using the main repo's installed deps. No deps installation needed in the worktree.

## Verification

- `pytest tests/test_chat_retry.py -v` → 3 passed in ~9 s. ✅
- `pytest tests/test_chat_cap.py -v` → 4 passed in ~9 s (regression baseline preserved). ✅
- `pytest tests/ -q --ignore=tests/test_e2e_subagent.py --ignore=tests/test_record_manager.py` → **123 passed, 8 skipped** (skips are Wave-1 stubs for plans 08-01 + 08-02 running in parallel — not regressions). ✅
- OpenAPI introspection → `retry` parameter present on `POST /api/threads/{thread_id}/messages`. ✅
- `grep -E "retry:\s*bool\s*=\s*(False|Query\(False\))" backend/routers/chat.py` → match on line 474. ✅
- `grep -F "if not retry:" backend/routers/chat.py` → match on line 526. ✅
- `grep -E "delete\(\)\.eq\(.id." backend/routers/chat.py` → match on line 516 (SELECT-then-DELETE-by-id). ✅

## Deferred Issues

- `backend/tests/test_record_manager.py::test_check_duplicate_integration` — pre-existing fixture bug (function signature is `def test_check_duplicate_integration(user_id: str)` but no `user_id` fixture is defined; conftest only provides `test_user_id` and `mock_user_id`). NOT caused by this plan — visible on the worktree before any 08-03 changes. Per SCOPE BOUNDARY in deviation rules, out of scope for this plan. Logged here for visibility; surfacing to the orchestrator for a future plan-checker pass or dedicated cleanup ticket.

## Smoke Confirmation

Per PLAN.md §output, the curl smoke against a live Fly URL is deferred to Wave 3 prod-deploy (08-07). At that point the verification will be:

```bash
curl -X POST -G --data-urlencode "retry=true" \
  https://boardgame-rag-prod.fly.dev/api/threads/<TID>/messages \
  -H "Authorization: Bearer <ANON_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"content":"x"}'
```

Expected: SSE stream returns 200; prior orphan assistant row deleted; new assistant placeholder + answer streamed.

Unit-test coverage proves the contract at the handler level today; the curl smoke is a deployment-time confirmation.

## Next Phase Readiness

- Plan 08-04 (frontend `useChat.retryLastUserMessage`) can now wire `apiStream('/api/threads/{id}/messages?retry=true', ...)` against a stable backend contract.
- No blockers introduced. The `if not retry:` guard on the user insert is the contract handshake — 08-04 must NOT prepend the user message to local state on retry (or must re-use the existing message id) so the UI stays consistent with the database.

## TDD Gate Compliance

Plan-level TDD gate satisfied:
1. **RED** — `1e63e95 test(08-03): RED phase — failing retry-dedup tests`
2. **GREEN** — `b338632 feat(08-03): retry-aware POST /threads/{id}/messages dedupes orphan assistant row`
3. **REFACTOR** — none needed; impl is minimal-diff and matches PLAN.md §action verbatim.

RED was a true RED: 2 of the 3 new tests failed on first run (the retry-specific assertions). The third (`test_non_retry_path_unchanged`) passed on first run because today's handler already matches that contract — this is the correct fail-fast result, not a skipped RED gate. Documenting here for plan-checker / verifier transparency.

## Self-Check: PASSED

- File `backend/routers/chat.py` exists and contains `retry: bool = Query(False)`, `if not retry:`, and `delete().eq("id", prior.data[0]["id"])`. ✅
- File `backend/tests/test_chat_retry.py` exists with 3 non-skipped test functions matching PLAN.md `must_haves.artifacts.exports`. ✅
- Commit `1e63e95` (test) present in git log. ✅
- Commit `b338632` (feat) present in git log. ✅

---
*Phase: 08-portfolio-polish*
*Completed: 2026-05-17*
