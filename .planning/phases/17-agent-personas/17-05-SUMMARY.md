---
phase: 17-agent-personas
plan: 05
subsystem: api
tags: [pydantic, schemas, fastapi, response-model, supabase, migration, personas, ddl]

# Dependency graph
requires:
  - phase: 17-agent-personas (17-02)
    provides: "the persona API RED baseline (test_thread_persona_patch.py / test_personas_api.py / test_preferences_api.py default_persona block) that names the ThreadModelUpdate->ThreadUpdate rename + persona/default_persona fields this plan declares"
  - phase: v1.2 (Phase 13)
    provides: "migration 032's additive-nullable ADD COLUMN pattern (threads.model) + the ThreadModelUpdate/ThreadResponse/PreferencesResponse/PreferencesUpdate schema shapes this clones"
provides:
  - "PersonaResponse (id/label/is_default ONLY; voice_block absent, A5) for GET /api/personas (PERS-01/D-07)"
  - "ThreadResponse.persona declared so it survives response_model on every thread read (PERS-05/Pitfall 1)"
  - "ThreadUpdate (renamed from ThreadModelUpdate) with model + persona, both None-default for exclude_unset partial PATCH (PERS-01/PERS-05)"
  - "default_persona on PreferencesResponse + PreferencesUpdate for the settings default (PERS-04)"
  - "migration 035 FILE: additive nullable threads.persona + user_preferences.default_persona, no backfill/constraint/FK/DEFAULT/RLS (D-08/D-10) — authored only, applied by 17-08"
affects: [17-06-personas-router, 17-07-threads-preferences-routes, 17-08-apply-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "response_model field-declaration (Pitfall 1): a nullable persona field is declared on ThreadResponse/PreferencesResponse BEFORE any read/write wiring so FastAPI does not strip it from select('*') rows"
    - "Additive-nullable migration clone of 032: ADD COLUMN TEXT with no backfill/constraint/FK/DEFAULT/RLS — a removed persona id must persist and resolve to the system fallback, never raise (D-10)"

key-files:
  created:
    - supabase/migrations/20240301000035_add_persona_columns.sql
  modified:
    - backend/models/schemas.py
    - backend/routers/threads.py

key-decisions:
  - "requirements-completed left EMPTY: this is the data-contract layer only (schema fields + migration FILE). PERS-01/04/05 are user-facing (picker, settings default, cross-session persistence) and stay Pending until 17-06/17-07 wire the endpoints, 17-08 applies the migration, and 17-09 ships the pickers — mirrors the 17-01/02/04 Pending pattern"
  - "Migration 035 authored but DELIBERATELY not applied (per plan objective + [BLOCKING] 17-08 owns db push to dev/.env and prod/.env.prod)"
  - "PersonaResponse declares EXACTLY {id,label,is_default} — voice_block omitted so the serializer physically cannot ship persona prompt text to the client (A5/T-17-14)"

patterns-established:
  - "Pitfall 1 pre-emption: declare the persona/default_persona response fields in the schema before the read paths so they survive response_model stripping (same failure mode as the messages.usage field)"
  - "ThreadUpdate model+persona both default None → exclude_unset partial PATCH: a persona-only body cannot clobber model and vice-versa (adopted by 17-07)"

requirements-completed: []  # data contract only — PERS-01/04/05 traceability stays Pending until 17-06 (router) + 17-07 (wiring) turn the 17-02 RED tests GREEN, 17-08 applies migration 035, and 17-09 ships the pickers

# Metrics
duration: 6min
completed: 2026-07-13
---

# Phase 17 Plan 05: Persona Data Contract (schemas + migration 035) Summary

**The persona DATA CONTRACT: PersonaResponse (id/label/is_default, voice_block withheld) + ThreadResponse.persona + the ThreadModelUpdate->ThreadUpdate rename with a persona field + default_persona on both preferences models, plus the additive-nullable migration 035 FILE (threads.persona + user_preferences.default_persona, no backfill/constraint/FK/RLS) — declared BEFORE any read/write wiring so Pitfall 1 is pre-empted; migration authored but NOT applied (17-08 owns the db push).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-07-13T14:48:03Z
- **Completed:** 2026-07-13T14:53:39Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `PersonaResponse` added to `schemas.py` with EXACTLY `{id, label, is_default}` — `voice_block` deliberately absent so the GET /api/personas serializer cannot ship prompt text to the client (A5/T-17-14). This is the wire shape 17-06's router will return.
- `ThreadResponse.persona: str | None` declared beside `model` so persona survives `response_model` on every thread read even when `select('*')` returns it (Pitfall 1 — the exact failure mode documented on the `usage` field). Without this, PERS-05 cross-session restore is impossible.
- `ThreadModelUpdate` renamed to `ThreadUpdate` with `model` AND `persona` both `None`-defaulting, so 17-07's `model_dump(exclude_unset=True)` PATCH lets a persona-only body avoid clobbering `model` and vice-versa (T-17-05). `threads.py`'s import + the `update_thread_model` signature type-hint were updated so the module still loads.
- `default_persona: str | None` added to BOTH `PreferencesResponse` and `PreferencesUpdate` (mirrors `favorite_models`) — `None` default preserves the `exclude_unset` partial-upsert so a theme-only PUT cannot clobber it (PERS-04/T-17-05).
- Migration `20240301000035_add_persona_columns.sql` authored: two additive nullable `TEXT` columns (`threads.persona`, `user_preferences.default_persona`), no backfill, no constraint, no foreign key, no DEFAULT clause, no new RLS policy — a clone of migration 032's additive pattern (D-08/D-10). The own-row RLS from 032 covers the new columns automatically.

## Task Commits

Each task was committed atomically:

1. **Task 1: schemas.py — PersonaResponse + persona/default_persona field additions** - `81bf61c` (feat)
2. **Task 2: Author migration 035 — additive nullable persona pin columns** - `54c5870` (feat)

**Plan metadata:** _(final docs commit — see git log)_

## Files Created/Modified
- `backend/models/schemas.py` - Added `PersonaResponse` (id/label/is_default, voice_block withheld); added `ThreadResponse.persona` (Pitfall 1); renamed `ThreadModelUpdate` -> `ThreadUpdate` + added `persona` (both fields None-default for exclude_unset); added `default_persona` to `PreferencesResponse` and `PreferencesUpdate`.
- `backend/routers/threads.py` - Import `ThreadUpdate` (was `ThreadModelUpdate`) and updated the `update_thread_model` body type-hint to `ThreadUpdate` so the module still imports after the rename (17-07 rewrites the endpoint body).
- `supabase/migrations/20240301000035_add_persona_columns.sql` - NEW additive migration: `ALTER TABLE threads ADD COLUMN persona TEXT;` + `ALTER TABLE user_preferences ADD COLUMN default_persona TEXT;`. No RLS/constraint/FK/DEFAULT. Authored only — applied by the [BLOCKING] plan 17-08.

## Decisions Made
- **Migration authored, not applied:** per the plan objective, this plan writes the migration FILE only; the `db push` to dev (`.env`) and prod (`.env.prod`) is the [BLOCKING] plan 17-08. No Supabase call was made.
- **requirements-completed intentionally empty:** the schema contract + migration file are necessary preconditions but do not make PERS-01/04/05 user-observable. PERS-01 needs 17-06's router, PERS-04/05 need 17-07's wiring + 17-08's apply + 17-09's UI. Marking them complete now would be a false traceability signal, so they stay Pending (consistent with 17-01/02/04).
- **PersonaResponse = 3 fields only:** id/label/is_default with `voice_block` structurally excluded, so the info-disclosure threat (T-17-14, prompt-text leak) is impossible at the type level rather than by a runtime filter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2 verify grep gate false-positives on mandatory identifiers**
- **Found during:** Task 2 (author migration 035)
- **Issue:** The plan's literal verify gate `! grep -qiE "CREATE POLICY|CHECK|REFERENCES|DEFAULT"` is a naive substring match. It matches inside two identifiers that the contract MANDATES and cannot be renamed: `REFERENCES` matches "p-**references**" in the table name `user_preferences` (from migration 032), and `DEFAULT` matches "**default**_persona" in the required column name (which 17-07 will `.select("default_persona")`). So the plan's gate printed `GATE_FAILED` even though the artifact is correct.
- **Fix:** Fixed the GATE, not the artifact. Re-ran a clause-aware gate with word boundaries — `! grep -qiE "CREATE POLICY|\bCHECK\b|\bREFERENCES\b|\bDEFAULT\b"` — which correctly ignores the identifier substrings (word-boundary fails on "p|references" and "default|_") and verifies only real DDL clauses. It prints `MIGRATION_OK`. The migration file itself is unchanged and matches PATTERNS.md L226-227 exactly (two additive nullable columns; no CREATE POLICY, no CHECK constraint, no foreign-key REFERENCES clause, no DEFAULT clause).
- **Files modified:** none (artifact was already correct; only the verification command was corrected)
- **Verification:** `grep -qi "ALTER TABLE threads ADD COLUMN persona TEXT"` ✓, `grep -qi "ALTER TABLE user_preferences ADD COLUMN default_persona TEXT"` ✓, clause-aware negative gate → `MIGRATION_OK`.
- **Committed in:** `54c5870` (Task 2 commit — artifact only)

---

**Total deviations:** 1 auto-fixed (1 bug — in the plan's verification command, not the code).
**Impact on plan:** No scope creep. The migration artifact satisfies the acceptance-criteria intent verbatim (both columns, no policy/constraint/FK/DEFAULT clause); only the verify command needed word boundaries to avoid colliding with the mandatory `user_preferences`/`default_persona` identifiers.

## Issues Encountered
- **`test_config.py::test_key_encryption_secret_default` fails (pre-existing, out of scope):** the overall verification `pytest tests/test_config.py` returns 19 passed / 1 failed. The single failure asserts `Settings().key_encryption_secret == ""`, but the repo-root `.env` has `KEY_ENCRYPTION_SECRET` set, which pydantic-settings loads over the empty code default. This is the documented "Pitfall 6" env-shadowing (STATE.md Phase 17 note: "SYSTEM_PROMPT (and KEY_ENCRYPTION_SECRET) are set in .env and shadow code defaults"). It is env-driven and unrelated to this plan — my commits touch only `schemas.py`, `threads.py`, and the migration; none touch `config.py`. Per the scope boundary, left as-is (already tracked). The schema-relevant portion of the verification is green: the Task 1 import one-liner exits 0 and 19/20 config tests pass.
- **pytest runner quirk (from 17-02):** the system Python's global pytest loads a stray `dash` plugin that INTERNALERRORs on collect. Ran via the project venv with `-p no:dash` (`backend/venv/Scripts/python.exe -m pytest ... -p no:dash`). Local-env quirk, no files changed.

## User Setup Required
None - no external service configuration required. (Migration 035 is authored but NOT applied here; the `db push` to dev + prod is the [BLOCKING] plan 17-08.)

## Next Phase Readiness
- **17-06 (personas router)** can import `PersonaResponse` and return `list_personas()` — the wire shape `{id,label,is_default}` is now declared. Turns the 3 `test_personas_api.py` tests GREEN once the router registers in `main.py`.
- **17-07 (threads/preferences routes)** can switch the PATCH to `body.model_dump(exclude_unset=True)` over the `ThreadUpdate` body (model + persona both declared) and thread `default_persona` through the preferences GET/PUT — turns the 4 RED thread-persona + prefs `default_persona` tests GREEN.
- **17-08 (BLOCKING apply):** migration 035 is ready for `db push` to dev (`.env`) then prod (`.env.prod`). Per Pitfall 7 (MEMORY), run `supabase migration repair --status applied` on the prior range first if `db push` replays old migrations.
- **Traceability:** PERS-01/04/05 stay Pending until 17-06/17-07 turn the RED tests GREEN, 17-08 applies the migration, and 17-09 ships the pickers.

## Self-Check: PASSED

- FOUND: backend/models/schemas.py
- FOUND: backend/routers/threads.py
- FOUND: supabase/migrations/20240301000035_add_persona_columns.sql
- FOUND commit: 81bf61c (Task 1)
- FOUND commit: 54c5870 (Task 2)

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
