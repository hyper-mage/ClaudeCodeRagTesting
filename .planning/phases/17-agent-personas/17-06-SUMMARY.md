---
phase: 17-agent-personas
plan: 06
subsystem: backend
tags: [personas, router, chat-resolver, per-turn-resolution, no-bleed, d-04, d-07, d-09, d-10, pers-01, pers-03, pers-06, tdd-green]

# Dependency graph
requires:
  - phase: 17-agent-personas
    plan: 04
    provides: "services.persona_service.{list_personas, resolve_persona_id, get_persona_voice, DEFAULT_PERSONA_ID, PERSONAS} + stream_chat_completion(persona_voice=...) composition seam"
  - phase: 17-agent-personas
    plan: 05
    provides: "models.schemas.PersonaResponse (id/label/is_default, voice_block withheld) — the GET /api/personas wire shape"
provides:
  - "GET /api/personas — auth-gated catalog endpoint returning [{id,label,is_default}] (PERS-01 backend core / D-07)"
  - "routers.chat._safe_thread_persona / _safe_user_default_persona / _resolve_persona — the per-turn (non-cached) persona VOICE resolver (D-09 tier chain + D-10 validate)"
  - "event_generator resolves persona_voice once per turn and threads it into stream_chat_completion(persona_voice=...) — the applied per-request voice (PERS-06 core)"
affects: [17-07-threads-preferences-routes, 17-08-apply-migration, 17-09-persona-pickers, 17-11-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sibling resolver clone: _resolve_persona mirrors _resolve_key_and_model's per-request, NOT-@lru_cache'd shape (PERS-06 no-bleed) without widening the key/model 4-tuple (Pitfall 8)"
    - "Thin catalog router: personas.py is a code-constant seam over list_personas() — no DB, no refresh (simpler than models.py which reads model_cache)"
    - "42P01 pre-migration tolerance: _safe_user_default_persona swallows the absent default_persona column so the resolver works before migration 035 is applied (17-08)"

key-files:
  created:
    - backend/routers/personas.py
  modified:
    - backend/main.py
    - backend/routers/chat.py
    - backend/tests/test_explorer_integration.py

key-decisions:
  - "PERS-01/03/06 left Pending (NOT marked complete): this plan ships their BACKEND core (catalog endpoint + per-turn resolver + stream wiring) but the phase discipline (17-04/17-05 both stated) defers requirement closure to 17-11 validation — PERS-01 additionally needs the 17-09 chat-UI picker per its requirement text."
  - "Did NOT widen _resolve_key_and_model's 4-tuple (Pitfall 8) — added _resolve_persona as an independent sibling so the ~18 key/model resolver tests stay byte-for-byte green."
  - "Explorer test mock signature (Rule 1 fix) updated to accept persona_voice — directly caused by the new call-site kwarg; mirrors the real stream_chat_completion signature (persona_voice slot after model, before trace, added in 17-04)."

requirements-completed: []  # PERS-01/03/06 backend core GREEN here but stay Pending — 17-09 picker (PERS-01) + 17-11 validation close them (mirrors 17-04/17-05)

# Metrics
duration: 6min
completed: 2026-07-13
---

# Phase 17 Plan 06: Persona READ + RESOLUTION Seam Summary

**Shipped the persona read + per-turn resolution seam: a new auth-gated `GET /api/personas` catalog endpoint (thin code-constant clone of models.py), its registration in main.py, and the non-cached `_resolve_persona` sibling in chat.py that resolves the persona voice (thread pin → user default → system default, D-09/D-10) once per turn and threads it into `stream_chat_completion(persona_voice=...)` — turning the 17-02 personas_api (3) and 17-01 resolver (6) RED scaffolds fully GREEN with the model/key resolver and its tests untouched (Pitfall 8 avoided).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-07-13T14:59Z
- **Completed:** 2026-07-13
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- **`personas.py` (NEW)** — `APIRouter(prefix="/api/personas")` with a single auth-gated `GET` (`Depends(get_user_id)`, `response_model=list[PersonaResponse]`) that returns `list_personas()`. No DB, no refresh — the catalog is a code constant (D-07), so this router is simpler than its `models.py` analog. The docstring flags that `voice_block` is never shipped (A5) and the route is auth-gated (T-17-15). Registered in `main.py` (import + `app.include_router(personas.router)` after `preferences.router`, exactly once).
- **`chat.py` persona resolver siblings** — three module-level functions added NEXT TO the model helpers, none of which touch `_resolve_key_and_model`: `_safe_thread_persona` (absent-key read of `thread_row["persona"]` off the SELECT * row); `_safe_user_default_persona` (clone of `_safe_user_default_model` selecting `default_persona`, wrapping the read in the 42P01 try/except so it tolerates the not-yet-applied migration 035); and `_resolve_persona` (D-09 tier chain `body.persona → thread pin → user default`, then `get_persona_voice(resolve_persona_id(pinned))` for the D-10 validate-to-default). The docstring documents that it is deliberately NOT `@lru_cache`'d (PERS-06 no-bleed).
- **`chat.py` wiring** — inside `event_generator`, immediately after the existing `_resolve_key_and_model(...)` call (same per-request try-block scope), `persona_voice = _resolve_persona(db, user_id, thread.data, body)`; and `persona_voice=persona_voice` added to the `stream_chat_completion(...)` kwargs alongside `api_key`/`model`/`trace`. The `tools=tools` assembly and the `TOOL_SELECTION_GUIDE if tools else None` append are untouched — tools stay persona-independent (D-04/PERS-02).

## Task Commits

Each task committed atomically:

1. **Task 1: GET /api/personas router + main.py registration** — `560d14a` (feat)
2. **Task 2: per-turn persona resolver siblings in chat.py** — `a976ff2` (feat)
3. **Task 3: wire resolver into event_generator + stream call (+ explorer mock fix)** — `5352840` (feat)

**Plan metadata:** _(final docs commit — see git log)_

## Files Created/Modified
- `backend/routers/personas.py` (NEW, 36 lines) — auth-gated `GET /api/personas` returning `list_personas()`; voice_block never shipped (A5).
- `backend/main.py` — added `personas` to the `from routers import ...` line and `app.include_router(personas.router)` after `preferences.router`.
- `backend/routers/chat.py` — imported `resolve_persona_id`/`get_persona_voice`; added `_safe_thread_persona`/`_safe_user_default_persona`/`_resolve_persona` siblings; resolved `persona_voice` per turn in `event_generator` and passed it into `stream_chat_completion`.
- `backend/tests/test_explorer_integration.py` — Rule 1 fix: the `_stream` mock signature now accepts `persona_voice=None` (see Deviations).

## Verification

- `test_personas_api.py` — **3/3 GREEN**: 200 + a 2-item catalog with exactly `{id,label,is_default}` (voice_block absent, A5), exactly one default == `board_game_expert`, and the auth gate (401/403 with no override).
- `test_persona_resolution.py` — **7/7 GREEN**: registry shape, null-pin → Expert default, thread pin wins over user default, user default when no pin, unknown-id → default (D-10, no raise), no cross-thread bleed (PERS-06), and 42P01 pre-migration tolerance.
- `test_key_model_resolution.py` — **still GREEN** (~18 tests): `_resolve_key_and_model` untouched, 4-tuple intact (Pitfall 8 avoided).
- `test_persona_prompt.py` — **GREEN**: composition seam unaffected.
- `grep -c "personas.router" main.py` == 1; `grep -c "def _resolve_persona" chat.py` == 1; `grep -c "persona_voice = _resolve_persona" chat.py` == 1; `grep -c "persona_voice=persona_voice" chat.py` == 1; `TOOL_SELECTION_GUIDE if tools else None` unchanged (D-04).
- Full backend suite: **310 passed**, 5 failed, 2 errors — every remaining red is pre-existing debt or a 17-07-owned RED scaffold (see Deferred), none caused by this plan's wiring.

## Decisions Made
- **PERS-01/03/06 left Pending, not marked complete.** This plan ships the backend core (catalog endpoint + per-turn resolver + applied voice), but the phase's stated discipline (17-04: "end-to-end closure awaits 17-06 resolver + 17-11 validation"; 17-05: "stay Pending until … 17-09 ships the pickers") defers requirement closure. PERS-01's own text mandates a chat-UI picker (17-09); PERS-03/PERS-06 are backend-live now but validated end-to-end in 17-11. Marking them complete here would break the phase's consistent traceability signal.
- **No widening of `_resolve_key_and_model`.** Added `_resolve_persona` as an independent sibling rather than extending the key/model resolver's 4-tuple, so the ~18 existing key/model tests unpack unchanged (Pitfall 8).
- **Resolver reads work pre-migration.** `_safe_thread_persona` is an absent-key read and `_safe_user_default_persona` swallows the 42P01, so every turn already resolves to the Expert default voice even though migration 035 is not applied until 17-08 — no runtime dependency on the live columns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Explorer test mock rejected the new `persona_voice` kwarg**
- **Found during:** Task 3 (full-suite verification)
- **Issue:** `test_explorer_integration.py`'s `_make_explore_tool_call_streams._stream()` mock hardcodes the exact kwarg list of the `stream_chat_completion` call site. Task 3 added `persona_voice=persona_voice` to that call, so the mock raised `TypeError: _stream() got an unexpected keyword argument 'persona_voice'`, failing all 3 explorer tests. This was directly caused by this task's change (in scope), not a pre-existing failure.
- **Fix:** Added `persona_voice=None` to the mock signature, in the same slot the real `stream_chat_completion` uses (after `model`, before `trace`; the param was added in 17-04). The mock now mirrors production and ignores the value.
- **Files modified:** `backend/tests/test_explorer_integration.py`
- **Commit:** `5352840` (Task 3 commit)

**Total deviations:** 1 auto-fixed (1 test-mock signature drift caused by this task's call-site kwarg). No production-code deviation; plan otherwise executed exactly as written.

## Deferred / Out-of-Scope (expected RED, owned by later plans or pre-existing)
The full backend suite's 5 remaining failures + 2 errors are NONE of them caused by this plan (my files: personas.py, main.py, chat.py, and the explorer mock — all green):
- `test_thread_persona_patch.py` (2) + `test_preferences_api.py::test_preferences_put_default_persona_roundtrip` (1) — 17-02 RED scaffolds owned by **17-07** (threads PATCH persona via `exclude_unset` + preferences GET/PUT `default_persona` wiring). This plan does not touch `threads.py`/`preferences.py`.
- `test_preferences_api.py::test_get_defaults_for_new_user` (1) — caused by **17-05**'s `PreferencesResponse.default_persona` schema field surfacing in the `response_model` output; **17-07** updates the preferences GET dict + this expectation.
- `test_config.py::test_key_encryption_secret_default` (1) — documented pre-existing `.env` env-shadow (`KEY_ENCRYPTION_SECRET`), STATE.md deferred items.
- `test_record_manager.py` (2 errors) — documented pre-existing missing `user_id` fixture (STATE.md test_debt).

## Threat Surface
- **T-17-15** (Spoofing/Auth on GET /api/personas) → mitigated: `Depends(get_user_id)` gates the route (test_personas_api asserts 401/403 with no override).
- **T-17-16** (Injection via pinned id → voice) → mitigated: `_resolve_persona` calls `resolve_persona_id` first; an unknown/crafted id collapses to the default voice (D-10, test asserts no-raise) — only registry `voice_block` strings reach the system message.
- **T-17-17** (cross-user/thread bleed) → mitigated: `_resolve_persona` is a plain per-turn function (NOT `@lru_cache`'d), called in `event_generator`'s per-request scope; the no-cross-thread-bleed test proves back-to-back different pins never cross.
- **T-17-18** (persona gating tools) → accept: `tools` + `TOOL_SELECTION_GUIDE` are untouched and persona-independent (D-04) — grep-confirmed the append still keys on `if tools`, not persona.

No threat flags — no new security surface beyond the planned auth-gated catalog read and the (already-mitigated) pinned-id → voice boundary.

## User Setup Required
None for this plan's code. **Carry-forward (unchanged from 17-04/17-05):** migration 035 is not yet applied — the resolver tolerates the absent `default_persona` column (42P01) and defaults to Expert; 17-08 applies the migration to dev (`.env`) and prod (`.env.prod`). The `SYSTEM_PROMPT` `.env` shadow (Pitfall 6) still needs removal at deploy so the operational base reaches the running app.

## Next Plan Readiness
- **17-07** can wire `threads.py` PATCH (`ThreadUpdate` + `exclude_unset`) and `preferences.py` GET/PUT `default_persona` — turning the 4 remaining persona RED scaffolds (thread PATCH + preferences default) GREEN. The resolver already reads `thread.persona`/`user_preferences.default_persona`, so once 17-07 persists them and 17-08 applies migration 035, per-thread/per-user pins take effect with no chat.py change.
- **17-09** ships the chat-UI picker over `GET /api/personas` (now live) → closes PERS-01.
- **17-11** validates the end-to-end persona chain → closes PERS-03/PERS-06 traceability.

## Self-Check: PASSED

- FOUND: backend/routers/personas.py
- FOUND: backend/main.py (personas.router registered)
- FOUND: backend/routers/chat.py (_resolve_persona + persona_voice wiring)
- FOUND commit: 560d14a (Task 1)
- FOUND commit: a976ff2 (Task 2)
- FOUND commit: 5352840 (Task 3)

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
