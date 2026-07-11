---
phase: 15-options-ui-capstone-demo-gating
plan: 01
subsystem: api
tags: [fastapi, pydantic, supabase, migration, preferences, demo-gating, byok]

# Dependency graph
requires:
  - phase: 13-preferences-per-thread-model
    provides: "user_preferences table + own-row RLS (migration 032), GET/PUT /api/preferences partial upsert (exclude_unset), PreferencesResponse/PreferencesUpdate models"
  - phase: 11-byok-usage-capture
    provides: "demo_fallback_enabled config flag (env-driven, default OFF, fail-closed shape)"
  - phase: 10-byok-key-exchange
    provides: "GET /api/keys/status handler + KeyStatusResponse"
provides:
  - "migration 033: user_preferences.favorite_models TEXT[] NOT NULL DEFAULT '{}' — authored AND applied LIVE to dev (ntkkmljbariflblldmha)"
  - "MessageCreate.use_demo (bool, default False) — POST message bodies accept the D-11 [Use demo] retry override without 422"
  - "KeyStatusResponse.demo_enabled + demo_enabled set EXPLICITLY in BOTH /api/keys/status branches (keyless early return included — T-15-01)"
  - "PreferencesResponse.favorite_models (default []) + PreferencesUpdate.favorite_models (None default, max_length=200) — GET/PUT roundtrip with bidirectional no-clobber"
affects: [15-04, 15-05, 15-06, 15-07, frontend-model-picker-favorites, frontend-demo-banner, 15-08-prod-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Env-driven flag surfaced read-only on an existing status endpoint: compute once at handler top, set explicitly in EVERY return branch (never rely on the Pydantic default for a branch)"
    - "Whole-array-replace field riding partial-upsert mechanics: None default on the Update model keeps exclude_unset semantics; Field(max_length=N) bounds abuse"

key-files:
  created:
    - supabase/migrations/20240301000033_add_favorite_models.sql
  modified:
    - backend/models/schemas.py
    - backend/routers/keys.py
    - backend/routers/preferences.py
    - backend/tests/test_keys_status.py
    - backend/tests/test_preferences_api.py

key-decisions:
  - "favorite_models is TEXT[] and deliberately NOT a FK to model_cache (same deprecation-tolerance rationale as default_model, D-06): a starred slug must persist when the model leaves the cache"
  - "Migration 033 adds NO policies — the own-row RLS from migration 032 covers the whole row, new column included"
  - "PreferencesUpdate.favorite_models bounded at max_length=200 (Open Q3 abuse bound, T-15-03)"
  - "demo_enabled computed once from get_settings().demo_fallback_enabled and set in BOTH status branches (RESEARCH Pitfall 3: keyless users are the demo audience; the Pydantic default would hide the flag from them)"
  - "GET/echo favorite_models uses the null-tolerant `row.data.get(...) or []` fallback mirroring the theme guard"
  - "MODEL-08 / DEMO-01 NOT marked complete: this plan lands the backend halves only; the FE star UI (15-06) and demo banner (15-07) complete them"

patterns-established:
  - "Flag-carrying status responses: every return branch carries the flag explicitly + a pinned test on the trap branch"

requirements-completed: []

# Metrics
duration: ~15min
completed: 2026-07-06
---

# Phase 15 Plan 01: Backend Seams — Favorites Column + demo_enabled Flag Exposure Summary

**Migration 033 (`favorite_models TEXT[]`) authored and pushed LIVE to dev, four additive Pydantic fields, `favorite_models` on the full preferences GET/PUT roundtrip, and `demo_enabled` set explicitly in BOTH `/api/keys/status` branches — every backend seam the Phase-15 frontend plans (15-04/05/06/07) consume.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-06T01:20:52Z
- **Completed:** 2026-07-06T01:36Z (approx)
- **Tasks:** 3/3 (Task 2 TDD: RED + GREEN commits; Task 3 is a DB-side ops action, no tracked-file commit)
- **Files:** 1 created, 5 modified

## Accomplishments

- `supabase/migrations/20240301000033_add_favorite_models.sql`: single additive DDL statement (`ALTER TABLE user_preferences ADD COLUMN favorite_models TEXT[] NOT NULL DEFAULT '{}'`), no policies, no backfill; header documents the non-FK deprecation-tolerance rationale and RLS coverage. **Applied to the LIVE dev database** — `supabase migration list` shows 033 remote-applied, and a live supabase-py probe of the column succeeded (validates RESEARCH Assumption A1: `list[str]` → TEXT[] through PostgREST).
- Four additive schema fields, each with the house phase + requirement-ID comment:
  - `MessageCreate.use_demo: bool = False` (D-11 retry override; server honors it only when the flag is ON — fail-closed preserved)
  - `KeyStatusResponse.demo_enabled: bool = False` (DEMO-01, read-only env-driven flag)
  - `PreferencesResponse.favorite_models: list[str] = Field(default_factory=list)` (no shared mutable default)
  - `PreferencesUpdate.favorite_models: list[str] | None = Field(default=None, max_length=200)` (exclude_unset partial-upsert semantics intact; 201 entries → 422)
- `keys.py status()`: `demo_enabled` computed once at the top, included in both the keyless early return AND the connected return (T-15-01 mitigated; pinned by a keyless-branch test).
- `preferences.py`: `favorite_models` at all 4 touch points (GET select + no-row default + return dict; PUT echo select + echo dict). Upsert path unchanged — `model_dump(exclude_unset=True)` already carries `favorite_models` only when the client sent it.
- 8 new tests + 1 updated, all green (13/13 across the two files); bidirectional no-clobber (Pitfall 12) proven in both directions on the captured upsert payload.

## Task Commits

1. **Task 1: Author migration 033 + four additive schema fields** — `495ed90` (feat)
2. **Task 2 (TDD RED): failing tests for demo_enabled + favorites roundtrip** — `08cef7d` (test)
3. **Task 2 (TDD GREEN): demo_enabled both branches + favorite_models roundtrip** — `50786ea` (feat)
4. **Task 3: Push migration 033 to LIVE dev + column probe** — no commit (DB-side operation; the migration file landed in `495ed90`)

## TDD Gate Compliance

- RED gate: `08cef7d` (`test(15-01): …`) — 4 behavior-driving tests failed before implementation (both flag-ON branch tests, stored-favorites GET echo, PUT echo).
- GREEN gate: `50786ea` (`feat(15-01): …`) after RED — 13/13 green.
- No REFACTOR commit — implementation was minimal on the first pass.
- Note: 4 of the 8 new tests passed during RED (flag-OFF default, favorites-default-[], both exclude_unset no-clobber pins). Investigated per the fail-fast rule: expected — they pin behavior whose enforcing mechanism (Pydantic defaults / exclude_unset) landed in Task 1's schema commit. They are regression pins, not behavior drivers; the drivers were genuinely RED.

## Files Created/Modified

- `supabase/migrations/20240301000033_add_favorite_models.sql` — the single additive ALTER, applied to dev.
- `backend/models/schemas.py` — four additive fields on MessageCreate / KeyStatusResponse / PreferencesResponse / PreferencesUpdate.
- `backend/routers/keys.py` — `demo_enabled` in both `status()` branches + docstring note.
- `backend/routers/preferences.py` — `favorite_models` in both selects and both response dicts; module docstring updated.
- `backend/tests/test_keys_status.py` — 3 new tests (keyless-branch pin, connected-branch, flag-OFF both branches) + `_status_db` helper.
- `backend/tests/test_preferences_api.py` — 5 new tests (default [], stored echo, favorites-only no-clobber, theme-only no-clobber, PUT echo) + `_upsert_payload` helper; existing strict-equality default-shape assert extended with `favorite_models: []`.

## Interfaces Delivered (consumed by 15-04/05/06/07 — do not deviate)

- `GET /api/keys/status` → `{ connected, masked_label?, connected_at?, demo_enabled }`
- `GET /api/preferences` → `{ default_model, theme, favorite_models }`
- `PUT /api/preferences {favorite_models: string[]}` → partial upsert, whole-array replace, echo includes `favorite_models`
- `POST /api/threads/{id}/messages` body accepts `{ content, use_demo? }` (default `False`)

## Decisions Made

- Did NOT mark MODEL-08/DEMO-01 complete in REQUIREMENTS.md: this plan delivers only the backend halves; the FE star UI and demo banner (plans 15-06/15-07) complete those requirements. Premature marking would misreport phase state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated the existing strict-equality assert in `test_get_defaults_for_new_user`**
- **Found during:** Task 2 (RED)
- **Issue:** Task 1's `PreferencesResponse.favorite_models` addition changed the GET wire shape, so the pre-existing `body == {"default_model": None, "theme": "dark"}` assert failed.
- **Fix:** Extended the expected dict with `"favorite_models": []` (the plan's own behavior list mandates this default).
- **Files modified:** `backend/tests/test_preferences_api.py`
- **Commit:** `08cef7d`

**2. [Rule 3 - Blocking] Worktree lacked gitignored runtime files (venv, .env, supabase link)**
- **Found during:** Task 1 verification / Task 3
- **Issue:** The parallel-executor worktree has no `backend/venv`, no repo-root `.env`, and no `supabase/.temp` link state (all gitignored), blocking test runs and the live push/probe.
- **Fix:** Ran the main checkout's venv Python against the worktree source (verified modules load from the worktree path); copied `.env` and `supabase/.temp` from the main checkout into the worktree (both confirmed gitignored — never committed).
- **Files modified:** none tracked
- **Commit:** n/a

## Issues Encountered

- `supabase db push` prompts for confirmation; the global `--yes` flag suppressed it cleanly (no migration-repair contingency needed — dev history was clean through 032, and the dry-run confirmed 033 was the only pending migration).

## Test Results

- `tests/test_keys_status.py` + `tests/test_preferences_api.py`: **13 passed** (5 pre-existing + 8 new).
- Schema asserts: `MessageCreate(content='x').use_demo is False`; `use_demo=True` accepted (no 422 path); `KeyStatusResponse(connected=False).demo_enabled is False`; `PreferencesResponse().favorite_models == []`; `PreferencesUpdate().model_dump(exclude_unset=True) == {}`; 200 favorites accepted, 201 rejected (ValidationError).
- Grep gates: `demo_enabled` non-comment count in keys.py = 4 (>= 3); `favorite_models` count in preferences.py = 10 (>= 4).
- Live: `supabase migration list` shows `20240301000033 | 20240301000033`; column probe printed `column live`.
- Full backend suite deliberately NOT run in-task (wave-1 merge gate owns it, per plan).

## Security (threat model verification)

- T-15-01 (info disclosure, keyless branch): mitigated — `demo_enabled` set explicitly in the keyless early return; pinned by `test_status_keyless_carries_demo_enabled_true`.
- T-15-02 (tampering, upsert): existing mitigation intact — `user_id` bound from the JWT sub (`Depends(get_user_id)`), never the body; own-row RLS from migration 032 backstops (covers the new column).
- T-15-03 (DoS, favorites array): mitigated — `Field(max_length=200)`, 201 entries → 422 (verified).
- T-15-04 (EoP, demo_enabled): accepted per plan — output-only field computed from env settings; never parsed from any request.
- No new threat surface beyond the plan's register (no new endpoints, no new auth paths, no schema change outside migration 033).

## Known Stubs

None — all new fields are wired to real data end-to-end (DB column live, routers roundtrip, flag reads the real env-driven setting).

## Next Phase Readiness

- All four FE-consumed contracts are live and pinned by tests; plans 15-04/05/06/07 can build against them immediately.
- Prod migration push (029-033) remains EXCLUSIVELY plan 15-08's concern (dev-only here, per plan and project memory).
- STATE.md / ROADMAP.md / REQUIREMENTS.md intentionally NOT modified (worktree mode — orchestrator owns shared-file writes after the wave).

## Self-Check: PASSED

All created/modified files exist on disk and all task commits are reachable (495ed90, 08cef7d, 50786ea). Working tree clean apart from this SUMMARY.
