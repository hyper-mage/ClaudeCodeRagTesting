---
quick_id: 260717-j1d
type: quick
subsystem: api
tags: [fastapi, supabase, gzip, sse, react, react-memo, swr-cache, threadpool, performance]

provides:
  - Single DB round-trip on thread GET/PATCH/DELETE (embedded select + scoped write)
  - Pure-CRUD FastAPI endpoints run in the threadpool (concurrent ChatPage mount fan-out)
  - Cached service-role Supabase client (one instance, not per-request)
  - GZip compression on fat JSON GETs (SSE chat still streams incrementally)
  - Module-scoped Supabase session cache in api.ts (no per-request getSession lock)
  - Stale-while-revalidate caches for chat messages + folder contents
  - Conditional post-send thread reload + memoized MessageBubble
affects: [chat, threads, documents, folders, preferences, frontend-hooks]

tech-stack:
  added: []   # no new dependencies
  patterns:
    - "Ownership-via-scoped-write: a single .eq(id).eq(user_id) UPDATE/DELETE returning 0 rows IS the IDOR 404 gate (no separate ownership SELECT)"
    - "PostgREST resource embedding (*, messages(*)) collapses parent+children into one round-trip"
    - "Sync path operations as plain def so FastAPI runs them in the threadpool"
    - "Module-level Map SWR cache: render cached instantly, revalidate in background, invalidate on mutation"
    - "React.memo on list-row components so per-token SSE deltas re-render only the changed bubble"

key-files:
  created: []
  modified:
    - backend/routers/threads.py
    - backend/database.py
    - backend/routers/documents.py
    - backend/routers/folders.py
    - backend/routers/preferences.py
    - backend/main.py
    - backend/tests/test_thread_model_patch.py
    - backend/tests/test_thread_persona_patch.py
    - backend/tests/test_thread_usage_exposed.py
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useChat.ts
    - frontend/src/hooks/useFolderTree.ts
    - frontend/src/pages/ChatPage.tsx
    - frontend/src/components/MessageBubble.tsx

key-decisions:
  - "get_thread uses a single embedded select (*, messages(*)) ordered on the foreign table; update/delete drop the ownership SELECT and let a scoped write's 0-row result be the 404"
  - "GZipMiddleware(minimum_size=1000) applied globally (primary approach); documented SSE path-exclusion fallback if live smoke shows batched chat delivery"
  - "api.ts caches the session via onAuthStateChange + a near-expiry (60s) getSession fallback so it never sends an expired bearer"
  - "SWR message/folder caches invalidate the whole map on every mutation (freshness > a stale hit; navigation is the hot path)"

requirements-completed: []

duration: ~15min
completed: 2026-07-17
---

# Quick 260717-j1d: Optimize UI Responsiveness & Backend Latency Summary

**Nine behavior-preserving perf fixes across 5 atomic tasks: single-round-trip thread endpoints + threadpool offload + GZip on the backend; session cache, SWR message/folder caches, conditional thread reload, and a memoized MessageBubble on the frontend — no new deps, all invariants preserved.**

## Performance

- **Duration:** ~15 min (first task commit 19:01Z → last task commit 19:09Z; incl. verification)
- **Started:** 2026-07-17T18:55:00Z (approx)
- **Completed:** 2026-07-17T19:10:14Z
- **Tasks:** 5 / 5
- **Files modified:** 14

## Accomplishments
- **Backend round-trip collapse:** `get_thread` now issues ONE embedded select (`*, messages(*)` asc by created_at); `update_thread`/`delete_thread` dropped the ownership SELECT — a single scoped `.eq(id).eq(user_id)` UPDATE/DELETE returning 0 rows is the IDOR 404 gate. `delete_thread` additionally gained the `user_id` scope the old delete lacked (strictly safer).
- **Threadpool offload:** all 5 threads endpoints + 7 documents CRUD endpoints + all folders CRUD + both preferences endpoints converted `async def → def` (bodies are fully synchronous), so FastAPI runs them in its threadpool. `upload_document` (awaits `file.read()`), chat, keys, demo, models, personas left untouched.
- **DB client singleton:** `get_supabase()` is now a lazy module-level singleton (one shared service-role client) instead of `create_client()` per request.
- **GZip:** `GZipMiddleware(minimum_size=1000)` compresses the fat JSON GETs; the SSE chat route must still stream incrementally (see the flagged manual smoke + fallback below).
- **Frontend session cache:** `api.ts` reads the token from a module-scoped cache kept fresh by `onAuthStateChange`, with a 60s near-expiry `getSession()` fallback — no per-request LockManager lock.
- **SWR caches:** `useChat` (per-thread messages) and `useFolderTree` (root-private + per-folder contents) render cached data instantly then revalidate; folder cache is fully cleared on every mutation.
- **ChatPage/MessageBubble:** `loadThreads()` fires only for the first message of an untitled thread; `MessageBubble` is wrapped in `React.memo` so an SSE delta re-renders only the streaming bubble.

## Task Commits

Each task committed atomically (disjoint file ownership — any one is revertible alone):

1. **Task 1: threads.py single round-trips + threadpool offload** - `f2cc954` (perf) — includes the `test_thread_usage_exposed.py` mechanism update (deviation, folded in via amend to keep the get_thread revert atomic)
2. **Task 2: DB singleton + threadpool offload (docs/folders/prefs) + GZip** - `21492d1` (perf)
3. **Task 3: cache the Supabase session in api.ts** - `0e47f14` (perf)
4. **Task 4: SWR caches for chat + folder navigation** - `6a312ac` (perf)
5. **Task 5: conditional thread reload + memoized MessageBubble** - `b148f3f` (perf)

_Plan metadata (SUMMARY/STATE) committed separately by the orchestrator._

## Files Created/Modified
- `backend/routers/threads.py` - collapsed get/patch/delete to one round-trip each; all 5 endpoints `def`
- `backend/database.py` - `get_supabase()` lazy module-level singleton
- `backend/routers/documents.py` - 7 CRUD endpoints `async def → def` (upload stays async)
- `backend/routers/folders.py` - 6 CRUD endpoints `async def → def`
- `backend/routers/preferences.py` - both endpoints `async def → def`
- `backend/main.py` - `GZipMiddleware(minimum_size=1000)` after CORS
- `backend/tests/test_thread_model_patch.py` - `_mock_db` + 404 test to the single-UPDATE mechanism (contract intact)
- `backend/tests/test_thread_persona_patch.py` - same mechanism update (no-clobber/explicit-null/404 intact)
- `backend/tests/test_thread_usage_exposed.py` - mock rewired to the embedded `*, messages(*)` select (usage contract intact)
- `frontend/src/lib/api.ts` - module-scoped session cache + near-expiry fallback
- `frontend/src/hooks/useChat.ts` - `messageCache` Map SWR + post-turn refresh effect
- `frontend/src/hooks/useFolderTree.ts` - `contentsCache` Map SWR + clear-on-mutation
- `frontend/src/pages/ChatPage.tsx` - `wasUntitled`-gated `loadThreads()`
- `frontend/src/components/MessageBubble.tsx` - `export default memo(MessageBubble)`

## Decisions Made
- **Ownership as a scoped write:** rather than SELECT-then-write, the single `.eq(id).eq(user_id)` UPDATE/DELETE's 0-row result is the 404. This preserves the exact IDOR contract (T-13-IDOR/T-17-04) while halving round-trips; the `exclude_unset` patch dict is byte-for-byte unchanged (no-clobber + explicit-null contract T-17-05/D-05/D-10 preserved).
- **GZip global-first:** applied `GZipMiddleware` globally per the plan's primary approach. The SSE incremental-delivery guarantee cannot be verified without a browser, so the path-exclusion fallback is documented and flagged below.
- **SWR full-clear on mutation:** folder cache is cleared entirely on any mutation (cheap; mutations are rare, navigation is the hot path) so `refreshTree`/create/rename/delete/move always show fresh contents.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_thread_usage_exposed.py to the collapsed get_thread mechanism**
- **Found during:** Task 2 (full-suite verify surfaced it; root cause is the Task 1 `get_thread` collapse)
- **Issue:** `test_thread_usage_exposed.py::test_get_thread_returns_usage` mocked the OLD two-query mechanism (`threads.select('*')...` + `messages.select('*')...`). After `get_thread` collapsed to one embedded `select('*, messages(*)')...maybe_single()`, the mock returned a bare `MagicMock` for `.data`, so response-model validation failed with 4 `string_type` errors.
- **Fix:** Rewired `_thread_db()` to return a single thread row carrying an embedded `messages` array (assistant row keeps its `usage` dict). The test body and its usage-contract assertions are unchanged — only the mock mechanism changed.
- **Files modified:** `backend/tests/test_thread_usage_exposed.py`
- **Verification:** `pytest` — test passes; full suite 314 passed (was 313).
- **Committed in:** `f2cc954` (folded into the Task 1 commit via amend, so reverting the get_thread change reverts its test together)

---

**Total deviations:** 1 auto-fixed (1 bug — a regression test that encoded the changed mechanism).
**Impact on plan:** Necessary for correctness; the get_thread usage contract is preserved. No scope creep — this test verifies the exact endpoint Task 1 changed.

## Issues Encountered
- **Pre-existing test failures (NOT caused by this work, left as-is per scope boundary):**
  - `test_config.py::test_key_encryption_secret_default` — asserts the empty-string default; the dev `.env` sets `KEY_ENCRYPTION_SECRET` (per project memory: prod BYOK secrets applied), so `Settings()` reads the real value. This test only imports `config.Settings` + `services.log_scrub`, neither of which this task touched. Environmental.
  - `test_record_manager.py::{test_check_duplicate_integration,test_find_previous_version_integration}` — collection-time `fixture 'user_id' not found`. This is the exact STATE.md deferred item ("test_record_manager.py missing user_id fixture (pre-v1.1)"). Unrelated to the DB singleton.
- **Pre-existing frontend lint errors (NOT caused by this work):** 5 errors in `FileUpload.tsx` (5:56 `no-explicit-any`), `AuthContext.tsx` (48:17 `react-refresh/only-export-components`), `ToastContext.tsx` (96:17 same), `ChatPage.tsx` (70:5 `set-state-in-effect` — the pre-existing `loadThreads` mount effect, NOT the `handleSend` change), `themeBootstrap.test.ts` (24:17 unused `_query`). None are in the 4 frontend files this task modified; `api.ts`, `useChat.ts`, `useFolderTree.ts`, and my `MessageBubble`/`handleSend` edits added zero new lint errors.

## Verification Results

### Automated (run and reported honestly)
- **Task 1 backend tests** — `pytest test_thread_model_patch.py test_thread_persona_patch.py -p no:dash -q` → **7 passed** (3 model + 4 persona; 404-on-non-owned, explicit-null clear, model-only no-persona, persona-only no-clobber-model all green).
- **Task 2 full backend suite** — `pytest backend/tests -p no:dash -q` → **314 passed, 1 failed, 2 errors**. The 1 failure + 2 errors are the pre-existing environmental/deferred items above; every test related to this task's changes (threads patch/usage, health, rate-limit, chat, docs, folders, prefs) is green. No regression introduced by the DB singleton or `async→sync` flips.
- **Frontend build** — `npm run build` (tsc -b + vite) → **clean** after Tasks 3, 4, 5 (only the pre-existing >500kB chunk-size advisory).
- **Frontend lint** — `npm run lint` → **5 pre-existing errors, 0 new** (see Issues above); none in the files this task changed.
- **No new dependencies** — `git diff` of `requirements.txt` / `package.json` / `package-lock.json` since base is empty. No LangChain/LangGraph.

### REMAINING-MANUAL live browser smokes (no browser MCP available to this executor)
Run logged in as `ragtest1@gmail.com` / `testpass123` with backend + frontend dev servers up:

1. **Task 1 — embedded-select order:** open a thread with history → messages render in `created_at` order.
2. **Task 1 — no-clobber through the collapsed UPDATE:** change Model then Persona in the header → reopen the thread → BOTH pins persist.
3. **Task 1 — DELETE 204:** delete a thread → sidebar removes it, Network shows 204.
4. **Task 1 — IDOR 404:** DevTools replay `GET`/`PATCH /api/threads/<random-uuid>` with your bearer → 404.
5. **Task 2 — SSE incremental under GZip (CRITICAL, see flag below):** send "Compare Catan vs Wingspan" → assistant text must appear PROGRESSIVELY and tool cards must appear DURING the turn (not all-at-once).
6. **Task 2 — GZip active on JSON:** DevTools → a large GET (e.g. `/api/models`) response carries `content-encoding: gzip`, while the chat request still shows an incrementally-growing stream.
7. **Task 3 — valid bearer / logout no-header / refresh freshness:** logged-in `GET /api/threads` carries a `Bearer` whose `exp` is in the future; logout → next request sends no `Authorization`; after a token refresh the next fetch still 200s.
8. **Task 4 — chat cache:** A→B→A renders A instantly with no B-linger; a completed turn in A is present after switch-away-and-back; example-prompt fresh-thread path still streams the optimistic bubble (CR-01).
9. **Task 4 — folder cache:** X→Y→X renders X instantly (no spinner flash); upload/rename/move/delete shows FRESH contents; BOARD GAMES + MY DOCUMENTS roots still populate.
10. **Task 5 — auto-title + no redundant refetch + live memo bubble:** first message of an untitled thread updates the sidebar title; a second message in the same titled thread fires NO `GET /api/threads`; the streaming bubble + tool cards still update live while historical bubbles don't re-parse.

### FLAG — GZip + SSE (Task 2 fix 4)
The PRIMARY approach (global `GZipMiddleware(minimum_size=1000)`) is implemented. **This executor could NOT run the live SSE smoke (no browser).** If the user observes **batched (non-incremental) chat delivery**, apply the plan's documented fallback: a `GZipMiddleware` subclass that, for an `http` scope where `scope["path"].endswith("/messages")` and `scope["method"] == "POST"`, delegates straight to `self.app(scope, receive, send)` (skipping gzip) and otherwise `await super().__call__(...)`, registered in place of the plain middleware in `backend/main.py`. A guiding comment is already in `main.py` at the `add_middleware` call.

## Invariants Preserved (verified by automated tests where possible)
- WR-01, CR-01/skipNextLoad, abort-on-switch — untouched in `useChat` (early-return branch and ref logic unchanged; SWR render inserted only in the genuine-switch branch after the resets).
- exclude_unset no-clobber (T-17-05) + explicit-null clear (D-05/D-10) — patch dict unchanged; asserted green by `test_thread_model_patch` / `test_thread_persona_patch`.
- IDOR 404 (T-13-IDOR/T-17-04) — now enforced by the scoped write's 0-row result; asserted green (both patch test files still assert id+user_id scoping).
- DELETE 204, auto-title, live streaming bubble + tool cards, refreshTree freshness — preserved (auto-title + streaming/folder-freshness require the manual smokes above).

## Next Steps
- Run the 10 REMAINING-MANUAL live smokes above, prioritizing #5 (SSE incremental under GZip).
- If #5 shows batched delivery, apply the GZip SSE-exclusion fallback documented in `main.py`.
- Optionally file the pre-existing `test_config` env-default and `test_record_manager` fixture failures as separate cleanup (already tracked in STATE.md deferred items).

## Self-Check: PASSED

- SUMMARY.md present at the expected path.
- All 5 task commit hashes exist in git history: `f2cc954`, `21492d1`, `0e47f14`, `6a312ac`, `b148f3f`.
- All 14 modified files present in the working tree and staged into their task commits.

---
*Quick task: 260717-j1d*
*Completed: 2026-07-17*
