---
phase: 13-preferences-per-thread-model
plan: 03
subsystem: api
tags: [fastapi, preferences, threads, supabase, upsert, rls, pydantic]

# Dependency graph
requires:
  - phase: 13-01
    provides: PreferencesResponse/PreferencesUpdate/ThreadModelUpdate schemas + Wave 0 RED tests
  - phase: 13-02
    provides: live migration 000032 (user_preferences + RLS, threads.model, messages role 'notice')
provides:
  - GET /api/preferences (resolved default_model + theme, new-user defaults)
  - PUT /api/preferences (partial upsert keyed on user_id, JWT-bound)
  - PATCH /api/threads/{id} (set/clear per-thread model with ownership re-check)
  - preferences router wired into main.py
affects: [13-04, 14, 15, frontend-options-ui, model-selector, theme-toggle]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Partial upsert via body.model_dump(exclude_unset=True) + JWT-bound user_id (write side mirrors keys.py)"
    - "Explicit-null write for clear-to-default (PATCH model: None is written, NOT skipped) — inverse of the prefs PUT"
    - "Ownership re-check (.eq id + .eq user_id) before mutate as IDOR defense-in-depth atop RLS"

key-files:
  created:
    - backend/routers/preferences.py
    - .planning/phases/13-preferences-per-thread-model/deferred-items.md
  modified:
    - backend/routers/threads.py
    - backend/main.py
    - backend/models/schemas.py

key-decisions:
  - "Preferences write side mirrors keys.py: service-role client, user_id from Depends(get_user_id) never the body, updated_at set explicitly (ON CONFLICT skips defaults)"
  - "PATCH returns the row from .update().execute() directly (model rides along) — no extra re-select round-trip"
  - "ThreadResponse.created_at/updated_at made Optional so the PATCH echo row validates; real list/create/get rows always carry both, so no real-world contract weakens"
  - "main.py preferences wiring committed in Task 1 (it is the blocking dependency that makes Task 1's route reachable for its own test)"

patterns-established:
  - "Partial-upsert (exclude_unset) for prefs vs explicit-null write for thread-model clear — opposite intents, documented inline in both handlers"
  - "Ownership re-check returning 404 on a non-owned id before any write (IDOR mitigation, T-13-IDOR)"

requirements-completed: [MODEL-05, MODEL-06, PREF-02]

# Metrics
duration: 6min
completed: 2026-06-24
---

# Phase 13 Plan 03: Preference Write/Read Endpoints Summary

**GET/PUT /api/preferences (partial upsert, JWT-bound user_id, new-user defaults) and PATCH /api/threads/{id} (set/clear per-thread model with a 404 ownership re-check), wired into main.py — turning 6 of the Plan 13-01 Wave 0 RED scaffolds GREEN.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-24T23:28:19Z
- **Completed:** 2026-06-24T23:34:59Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `GET /api/preferences` resolves a brand-new user to `{default_model: null, theme: "dark"}` (maybe_single guard, never a 406) and an existing row to its stored values.
- `PUT /api/preferences` partial-upserts (exclude_unset) so a theme-only PUT never clobbers `default_model` and vice-versa; `user_id` is bound from the JWT (never the body, T-13-02) and `updated_at` is stamped explicitly.
- `PATCH /api/threads/{id}` sets `threads.model`, writes `{model: null}` EXPLICITLY to clear back to default (D-05), and returns 404 via an ownership re-check on a non-owned thread (T-13-IDOR).
- Preferences router wired into `main.py`; the three-tier resolution (chat.py, UNCHANGED) now reads the real `user_preferences.default_model` + `threads.model`.

## Task Commits

Each task was committed atomically:

1. **Task 1: preferences router — GET + PUT /api/preferences** - `1a24f71` (feat)
2. **Task 2: PATCH /api/threads/{thread_id} — set/clear per-thread model** - `8ade05c` (feat)
3. **Task 3: wire preferences router + wave-merge gate** - `d35cbfd` (docs; the main.py wiring itself rode in `1a24f71` as a blocking dependency)

_The 13-01 `test(...)` RED scaffolds (`df052d4`) supply the failing tests; these `feat(...)` commits are the GREEN gate of the plan-level TDD cycle._

## Files Created/Modified
- `backend/routers/preferences.py` (created) - GET + PUT /api/preferences; partial upsert keyed on user_id, new-user defaults, JWT-bound user_id.
- `backend/routers/threads.py` (modified) - added `update_thread_model` PATCH handler (ownership re-check + explicit-null clear); existing list/create/get/delete untouched.
- `backend/main.py` (modified) - import + `app.include_router(preferences.router)`.
- `backend/models/schemas.py` (modified) - `ThreadResponse.created_at/updated_at` made Optional so the PATCH echo row validates.
- `.planning/phases/13-preferences-per-thread-model/deferred-items.md` (created) - logs the 2 Plan-13-04 RED scaffolds + 2 pre-existing record_manager errors as out-of-scope.

## Decisions Made
- **PATCH returns `.update().execute()` data directly** rather than a separate re-select: matches both the locked 13-01 mock (which wires the row onto the update chain) and real supabase-py (update echoes the modified rows), saving a round-trip.
- **main.py wiring landed in Task 1**, not Task 3: the preferences route must be mounted for Task 1's own test to be reachable (404 otherwise). Task 3 thereby became the pure full-suite wave-merge gate; its code action was already satisfied.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wired preferences router into main.py during Task 1**
- **Found during:** Task 1 (preferences router)
- **Issue:** Task 1's verify runs `test_preferences_api.py`, which imports `from main import app` and calls the live route. Without `app.include_router(preferences.router)` the PUT/GET 404'd, so Task 1 could not go green. The plan assigned wiring to Task 3.
- **Fix:** Added the `preferences` import + `app.include_router(preferences.router)` in Task 1's commit (`1a24f71`). Task 3's identical code action was then already done; Task 3 ran the full-suite gate.
- **Files modified:** backend/main.py
- **Verification:** `test_preferences_api.py` 3/3 green after wiring; wiring confirmed present in the committed tree.
- **Committed in:** `1a24f71`

**2. [Rule 1 - Bug] Made ThreadResponse timestamps Optional so the PATCH echo row validates**
- **Found during:** Task 2 (PATCH handler)
- **Issue:** The locked 13-01 mock returns the updated thread row WITHOUT `created_at`/`updated_at` and asserts a 200. With those fields required on `ThreadResponse`, FastAPI raised `ResponseValidationError` (500), so the PATCH could never return 200 against the contract.
- **Fix:** Changed `created_at`/`updated_at` to `datetime | None = None`. Real list/create/get rows always carry both, so no real-world response contract weakens — only the PATCH path tolerates the driver's partial echo.
- **Files modified:** backend/models/schemas.py
- **Verification:** `test_thread_model_patch.py` 3/3 green; resolution suite + all other suites that return ThreadResponse unregressed.
- **Committed in:** `8ade05c`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both were necessary to satisfy the locked Wave 0 test contracts; no scope creep. schemas.py was outside the plan's `files_modified` but the change was the minimal reconciliation required by the 13-01 RED mock and does not weaken any real-data response.

## Issues Encountered
- **Full-suite gate is not 100% green, by design.** `cd backend && pytest -q` → **201 passed, 2 failed, 2 errors**. The 4 non-green items are ALL out of scope for 13-03 and logged in `deferred-items.md`:
  - `test_deprecated_model_fallback.py` (2 failures) — Plan **13-04** RED scaffolds for the `notice`-role insertion + LLM-history-exclusion logic in `chat.py`. `git diff 1a24f71~1 HEAD` touches neither that test nor `chat.py`; both were already RED before 13-03 (the plan itself states "Plans 03/04 turn them green").
  - `test_record_manager.py` (2 errors) — documented pre-existing debt (missing `user_id` fixture), explicitly tolerated by the plan's Task 3 acceptance criteria and STATE.md Pending Todos.
- **All 6 plan-target tests + the resolution suite are green:** `pytest test_key_model_resolution.py test_preferences_api.py test_thread_model_patch.py` → **13 passed** (includes `test_thread_model_wins_when_set` against the now-real `threads.model` column).

## Known Stubs
None — the endpoints are fully wired to `user_preferences` / `threads` via the service-role client; no placeholder data or unwired surface.

## User Setup Required
None - no external service configuration required (migration 000032 already applied to dev in Plan 13-02).

## Next Phase Readiness
- **Plan 13-04** (notice-role / deprecated-model fallback) can proceed — its 2 RED scaffolds (`test_deprecated_model_fallback.py`) are the remaining open items; resolution + notice logic in `chat.py` is its surface.
- The frontend options UI (later phases) can now hydrate the model selector + theme from `GET /api/preferences` and persist via `PUT /api/preferences` + `PATCH /api/threads/{id}`.
- Carried debt: `test_record_manager.py` integration cases remain RED (pre-existing) — future plan-checker pass.

## Self-Check: PASSED

- FOUND: backend/routers/preferences.py
- FOUND: .planning/phases/13-preferences-per-thread-model/13-03-SUMMARY.md
- FOUND: .planning/phases/13-preferences-per-thread-model/deferred-items.md
- FOUND commit: 1a24f71 (Task 1 feat)
- FOUND commit: 8ade05c (Task 2 feat)
- FOUND commit: d35cbfd (Task 3 docs)

---
*Phase: 13-preferences-per-thread-model*
*Completed: 2026-06-24*
