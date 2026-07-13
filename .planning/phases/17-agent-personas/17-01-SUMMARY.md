---
phase: 17-agent-personas
plan: 01
subsystem: testing
tags: [pytest, personas, system-prompt, tdd, red-scaffold, resolver, prompt-composition]

# Dependency graph
requires:
  - phase: 16-web-search
    provides: "citation guidance in system_prompt (D-02 base) + SYSTEM_PROMPT env-shadow pitfall + test_web_search citation-guidance regression guard"
  - phase: 13 (v1.2)
    provides: "the model-pin resolver analog (_safe_thread_model/_safe_user_default_model/_resolve_key_and_model) + test_key_model_resolution.py MagicMock harness this clones"
provides:
  - "RED baseline for the persona resolver + registry (PERS-03/06, D-09, D-10, 42P01 tolerance)"
  - "RED baseline for base+voice prompt composition (D-01/D-02/D-03/D-04) + PERS-02 tools-independence"
  - "3 RED assertions pinning the config system_prompt base/voice split (D-02 keep citation, D-03 drop KB-first bias, A1 drop opener)"
affects: [17-04-prompt-core, 17-06-chat-resolver]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 RED scaffold: in-function imports so pytest COLLECTS clean and RED is a per-TEST import/assertion failure"
    - "Generator composition probe: drive stream_chat_completion to its first system_content event (patched get_llm_client, no network)"
    - "Env-isolated config assertion: monkeypatch.delenv(SYSTEM_PROMPT) so a local .env override cannot mask the shipped base"

key-files:
  created:
    - backend/tests/test_persona_resolution.py
    - backend/tests/test_persona_prompt.py
  modified:
    - backend/tests/test_config.py

key-decisions:
  - "Task 2 composition helper env-isolates settings.system_prompt (delenv SYSTEM_PROMPT + fresh config.Settings) and patches get_settings so the base is deterministic once 17-04 lands — beyond the plan's minimum, guards Pitfall 6 for GREEN robustness"
  - "test_tools_are_persona_independent uses the STRONGER direct observation (drain generator, assert create() tools kwarg identical across personas) rather than the tool_guide fallback"

patterns-established:
  - "Persona resolver tests clone the test_key_model_resolution.py _db_with_*_row MagicMock chain, stripped to a single default_persona select"
  - "Composition tests assert voice-leads-base via content.find(voice) < content.find('Sources:') rather than hardcoding voice wording (voice text is 17-04 discretion)"

requirements-completed: []  # RED scaffold only — PERS-02/03/06 traceability stays Pending until 17-04/17-06 turn these GREEN

# Metrics
duration: 13min
completed: 2026-07-13
---

# Phase 17 Plan 01: Persona RED Test Scaffolds Summary

**Wave 0 RED baseline — 15 failing tests pinning the persona resolver/registry (PERS-03/06, D-10, tier order, 42P01 tolerance), the base+voice prompt-composition contract (D-01/D-02/D-03/D-04 + PERS-02 tools-independence), and the config system_prompt base/voice split — all failing for the correct reason (missing 17-04/17-06 implementation), zero production code touched.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-07-13T13:53:27Z
- **Completed:** 2026-07-13T14:03:31Z
- **Tasks:** 3
- **Files modified:** 3 (2 created, 1 appended)

## Accomplishments
- `test_persona_resolution.py` — 7 tests pinning PERS-03 (Expert default), PERS-06 (no cross-thread bleed / T-17-02), D-10 (unknown-id fallback / T-17-01), D-09 tier order (thread pin → user default → system default), and 42P01 pre-migration tolerance. All fail RED at the in-function import of `services.persona_service` / `routers.chat._resolve_persona`.
- `test_persona_prompt.py` — 5 tests pinning the D-01/D-02/D-03/D-04 composition (voice FIRST, then operational base, then tool_guide), General Assistant vanilla framing (PERS-02/D-06), Expert KB-first bias (D-03), base rules for BOTH personas (D-02), and PERS-02/D-04 tools-independence (T-17-03) via direct `create()` tools-kwarg observation. All fail RED at the missing `get_persona_voice` / `persona_voice` kwarg.
- `test_config.py` — 3 appended `operational_base` assertions: citation guidance stays (D-02 regression guard, GREEN now), KB-first bias drops (D-03, RED), opener drops (A1, RED). Existing config tests untouched.
- Regression guard confirmed: `test_web_search.py::test_system_prompt_citation_guidance` still PASSES (no config.py touched).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED scaffold — persona resolver + registry** - `6889883` (test)
2. **Task 2: RED scaffold — base+voice composition + tools-independence** - `fff9680` (test)
3. **Task 3: Extend test_config.py — operational base keeps citation, drops KB-first bias** - `f768ead` (test)

**Plan metadata:** _(final docs commit — see below)_

## Files Created/Modified
- `backend/tests/test_persona_resolution.py` - 7-test RED scaffold for the persona resolver + registry (clones `test_key_model_resolution.py`'s `_db_with_*_row` MagicMock chain, stripped to a `default_persona` select).
- `backend/tests/test_persona_prompt.py` - 5-test RED scaffold for base+voice composition + tools-independence (drives `stream_chat_completion` to its first `system_content` event with `get_llm_client` patched).
- `backend/tests/test_config.py` - +3 `operational_base` assertions (env-isolated via `delenv("SYSTEM_PROMPT")`) pinning the D-02/D-03/A1 base/voice split.

## Decisions Made
- **Env-isolated composition helper (beyond plan minimum):** Task 2's `_drive` helper patches `llm_service.get_settings` with a fresh `config.Settings()` built after `delenv("SYSTEM_PROMPT")`, so the operational base is deterministic once 17-04 lands regardless of any local `.env` SYSTEM_PROMPT override (Pitfall 6). This keeps the tests robustly GREEN after implementation, not just RED now.
- **Stronger tools-independence assertion:** used the plan's primary path (drain the generator with an empty stream so `create()` is invoked, assert the `tools` kwarg is identical across personas) plus an assertion that the two composed system messages DIFFER — directly pinning "persona changes ONLY the system message, never the tools list" (PERS-02/D-04, T-17-03). The tool_guide fallback was not needed.
- **Voice-leads-base assertion is wording-agnostic:** asserts `content.find(voice) < content.find("Sources:")` using the whole returned voice string rather than hardcoding voice prose, because the voice_block wording is 17-04's discretion.

## Deviations from Plan

None - plan executed exactly as written. (The env-isolation and stronger tools assertion in Task 2 are within the plan's explicitly-offered latitude — the plan calls for patching `get_llm_client` and offers a tools-passthrough-or-fallback choice; both were satisfied without altering scope.)

## Issues Encountered
None. All three verifications behaved exactly as specified:
- `pytest tests/test_persona_resolution.py tests/test_persona_prompt.py` → 12 failed RED (ModuleNotFoundError `services.persona_service` / ImportError `_resolve_persona`), 0 collection errors.
- `pytest tests/test_config.py -k operational_base` → 2 failed (drops_kb_first_bias, drops_opener), 1 passed (keeps_citation), 17 deselected — the `-k` filter selects exactly the 3 new tests.
- `pytest tests/test_web_search.py::test_system_prompt_citation_guidance` → 1 passed (regression guard intact).

## Threat Surface
No new runtime surface — test-only plan. The 3 STRIDE register entries are all encoded as RED tests that 17-06 must satisfy:
- **T-17-01** (Tampering, crafted/stale persona id) → `test_unknown_pinned_id_falls_back_to_default`.
- **T-17-02** (Info Disclosure, cross-thread bleed) → `test_no_cross_thread_bleed`.
- **T-17-03** (EoP, persona gating tools) → `test_tools_are_persona_independent`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- **17-04 (prompt core)** and **17-06 (chat resolver)** now have a complete automated RED baseline to turn GREEN. Contracts imported by these tests: `services.persona_service.{DEFAULT_PERSONA_ID, PERSONAS, list_personas, resolve_persona_id, get_persona_voice}`, `routers.chat._resolve_persona`, and the `persona_voice` kwarg on `stream_chat_completion`.
- **Carry-forward for 17-04 (Pitfall 6):** a `SYSTEM_PROMPT` value in `.env`/`.env.prod` shadows the config default via pydantic-settings. The composition tests are env-isolated so they pass regardless, but the RUNNING app needs the `.env` override removed for the refactored base to reach it (flagged in the 16-02 SUMMARY / STATE decisions). These tests do NOT cover the running-app env — that remains a deploy-time follow-up.

## Self-Check: PASSED

- FOUND: backend/tests/test_persona_resolution.py
- FOUND: backend/tests/test_persona_prompt.py
- FOUND: .planning/phases/17-agent-personas/17-01-SUMMARY.md
- FOUND commits: 6889883 (Task 1), fff9680 (Task 2), f768ead (Task 3)

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
