---
phase: 17-agent-personas
plan: 02
subsystem: testing
tags: [pytest, personas, api, red-scaffold, tdd, idor, no-clobber, exclude-unset, preferences]

# Dependency graph
requires:
  - phase: 13 (v1.2)
    provides: "the model-pin API analogs (routers/models.py, routers/threads.py PATCH, preferences.py favorite_models block) + test_models_api.py / test_thread_model_patch.py / test_preferences_api.py harnesses this clones"
  - phase: 17-agent-personas (17-01)
    provides: "the persona RED resolver/prompt baseline + 17-PATTERNS.md pattern map for the API surface"
provides:
  - "RED baseline for GET /api/personas catalog (PERS-01/D-07): auth-gated, [{id,label,is_default}], voice_block withheld (A5)"
  - "RED baseline for PATCH /api/threads/{id} {persona} (PERS-01/PERS-05): persona-set scoped by id+user_id (T-17-04 IDOR) + persona-only no-clobber-model (T-17-05)"
  - "RED baseline for PUT/GET /api/preferences default_persona roundtrip (PERS-04) + theme/sibling no-clobber (T-17-05)"
affects: [17-06-personas-router, 17-07-threads-preferences-routes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auth-gate probe: exercise the REAL get_user_id (no dependency_overrides) → assert 401/403 for the gated GET"
    - "No-clobber pin via exclude_unset: assert the absent sibling key is NOT in the upsert/update patch dict (both clobber directions)"
    - "Catalog-shape lockdown: assert set(item.keys()) == {id,label,is_default} so a leaked voice_block FAILS (A5)"

key-files:
  created:
    - backend/tests/test_personas_api.py
    - backend/tests/test_thread_persona_patch.py
  modified:
    - backend/tests/test_preferences_api.py

key-decisions:
  - "Auth-gate test exercises the real get_user_id (no override) and asserts 401/403 — in RED it currently returns 404 (route unregistered), which is the correct RED signal; it becomes a true 401 gate once 17-06 registers the router"
  - "default_persona tests named with 'persona' substring so `pytest -k persona` selects EXACTLY the 4 new tests (no existing prefs test carries that substring)"

patterns-established:
  - "Persona API RED tests clone the shipped v1.2 model-pin harnesses (test_models_api / test_thread_model_patch / test_preferences_api favorite_models block) s/model/persona/"
  - "No-clobber assertions run BOTH directions (persona-only must not carry sibling; sibling-only must not carry persona) mirroring the favorite_models Pitfall-12 pins"

requirements-completed: []  # RED scaffold only — PERS-01/04/05 traceability stays Pending until 17-06/17-07 turn these GREEN

# Metrics
duration: 9min
completed: 2026-07-13
---

# Phase 17 Plan 02: Persona API RED Test Scaffolds Summary

**Wave 0 RED baseline for the persona HTTP surface — 2 new backend test files + an appended default_persona block (11 new tests, 9 failing RED for the correct reason) pinning the auth-gated GET /api/personas catalog with voice_block withheld, the PATCH /api/threads persona write with IDOR re-check + no-clobber-model, and the PUT/GET /api/preferences default_persona roundtrip, with zero production code touched.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-07-13T14:09:00Z
- **Completed:** 2026-07-13T14:18:31Z
- **Tasks:** 3
- **Files modified:** 3 (2 created, 1 appended)

## Accomplishments
- `test_personas_api.py` — 3 tests pinning GET /api/personas (PERS-01/D-07): the auth-gated catalog returns a length-2 `[{id,label,is_default}]` list, `set(keys) == {id,label,is_default}` (so a leaked `voice_block` FAILS, A5), exactly one `is_default` that is `board_game_expert` (PERS-03/D-05), and the auth gate (real `get_user_id`, no override). All 3 fail RED — the route is unregistered until 17-06 (→ 404).
- `test_thread_persona_patch.py` — 4 tests cloning `test_thread_model_patch.py`'s `_mock_db(owned)` chain: persona-set scoped by `id`+`user_id` (T-17-04 IDOR), persona-only body does NOT clobber `model` (T-17-05 — the test that forces the switch off the hardcoded `{"model": body.model}`), plus the model-only + 404-non-owned regression pins. 2 fail RED (persona-set, no-clobber-model); 2 regression pins already GREEN.
- `test_preferences_api.py` — +4 appended `default_persona` tests (PERS-04): new-user GET resolves `default_persona` to `None`, PUT→GET roundtrip persists it (payload carries `default_persona` + `user_id` + `updated_at`), and both no-clobber directions (theme-only must not carry `default_persona`; persona-only must not carry `default_model`/`theme`). 2 fail RED (new-user key, roundtrip); 2 no-clobber pins already GREEN. The 8 pre-existing prefs tests are untouched and still pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED scaffold — GET /api/personas** - `014bb67` (test)
2. **Task 2: RED scaffold — PATCH persona pin** - `1dfd66c` (test)
3. **Task 3: Extend test_preferences_api.py — default_persona** - `9612f34` (test)

**Plan metadata:** _(final docs commit — see git log)_

## Files Created/Modified
- `backend/tests/test_personas_api.py` - 3-test RED scaffold for the auth-gated GET /api/personas catalog (mirrors `test_models_api.py`; no DB patch — the catalog is a code constant); locks the wire shape to `{id,label,is_default}` and withholds `voice_block` (A5).
- `backend/tests/test_thread_persona_patch.py` - 4-test RED scaffold for PATCH /api/threads persona (clones `test_thread_model_patch.py`'s `_mock_db(owned)` + `eq_calls` ownership-scope assertion); pins persona-set, no-clobber-model, model-only regression, and 404-non-owned IDOR.
- `backend/tests/test_preferences_api.py` - +4 `default_persona` tests appended (clone the `favorite_models` block + reuse `_mock_db_with_pref_row`/`_upsert_payload`); existing tests unmodified.

## Decisions Made
- **Auth-gate test asserts 401/403 against the real dependency:** `test_personas_requires_auth` runs with NO `dependency_overrides[get_user_id]`, so the genuine gate (`auth.get_user_id` → `HTTPException(401)` on a missing Bearer header) is exercised. In the RED state the route is unregistered so it returns 404 (still a failure → correct RED signal); once 17-06 registers `routers.personas` it becomes a true 401 gate. This mirrors how the model-pin routers are all `Depends(get_user_id)`.
- **`-k persona` precision:** all four new prefs tests carry the `persona` substring and no pre-existing prefs test does, so `pytest tests/test_preferences_api.py -k persona` selects exactly the new four (verified: 4 selected, 8 deselected).
- **Clean-assertion over KeyError for missing keys:** the RED assertions check `"key" in body`/`in payload` first (rather than indexing straight to a KeyError), so RED surfaces as a readable AssertionError and flips cleanly GREEN when 17-07 adds the field.

## Deviations from Plan

None - plan executed exactly as written. All three tasks produced test-only files matching the plan's acceptance criteria (3 / 4 / 4 test functions respectively) and the specified RED reasons.

## Issues Encountered
- **Test runner:** the system Python's global pytest loads a stray `dash` testing plugin that `INTERNALERROR`s on collect. Resolved by running the project venv interpreter directly (`backend/venv/Scripts/python.exe -m pytest ... -p no:dash`). This is a local-env quirk, not a code issue — no files changed.

Otherwise all verifications behaved exactly as specified:
- `pytest tests/test_personas_api.py tests/test_thread_persona_patch.py` → 5 failed RED, 2 passed (the model-only + 404 regression pins).
- `pytest tests/test_preferences_api.py -k persona` → 2 failed RED, 2 passed, 8 deselected — the filter selects exactly the 4 new tests.
- `pytest tests/test_preferences_api.py -k "favorite or theme or default_model"` → 8 passed (existing regression intact).

## Threat Surface
No new runtime surface — test-only plan. The 3 STRIDE register entries are encoded as RED tests that 17-06/17-07 must satisfy:
- **T-17-04** (EoP / IDOR, PATCH persona on a non-owned thread) → `test_patch_persona_404_non_owned` (already GREEN — ownership re-check pre-exists) + the `eq_calls` id+user_id scope pin in `test_patch_sets_persona`.
- **T-17-05** (Tampering / field clobber) → `test_patch_persona_only_does_not_clobber_model` + `test_preferences_put_theme_only_preserves_default_persona` + `test_preferences_put_default_persona_only_no_clobber`.
- **T-17-06** (Info Disclosure, prompt text leak) → `test_get_personas_returns_catalog` asserts `voice_block` is never in the response (A5).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- **17-06 (personas router)** must ship `GET /api/personas` returning `services.persona_service.list_personas()` (`[{id,label,is_default}]`, voice_block withheld) and register it in `main.py` — turns all 3 `test_personas_api.py` tests GREEN (the 404→200 + 404→401 flips).
- **17-07 (threads/preferences routes)** must (a) rename `ThreadModelUpdate`→`ThreadUpdate` with a `persona` field and switch the PATCH to `body.model_dump(exclude_unset=True)` — turns the 2 RED thread-persona tests GREEN while keeping the model-only + 404 pins; and (b) thread `default_persona` through `PreferencesUpdate`/`PreferencesResponse` + the GET/PUT `.select`/return dicts — turns the 2 RED prefs tests GREEN.
- **Traceability:** PERS-01/04/05 stay Pending until 17-06/17-07 turn these GREEN (RED scaffold only).

## Self-Check: PASSED

- FOUND: backend/tests/test_personas_api.py
- FOUND: backend/tests/test_thread_persona_patch.py
- FOUND: backend/tests/test_preferences_api.py
- FOUND: .planning/phases/17-agent-personas/17-02-SUMMARY.md
- FOUND commits: 014bb67 (Task 1), 1dfd66c (Task 2), 9612f34 (Task 3)

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
