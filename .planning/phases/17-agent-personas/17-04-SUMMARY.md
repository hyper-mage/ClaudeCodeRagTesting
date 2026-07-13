---
phase: 17-agent-personas
plan: 04
subsystem: backend
tags: [personas, system-prompt, prompt-composition, registry, llm-service, tdd-green, d-01, d-02, d-03, d-04]

# Dependency graph
requires:
  - phase: 17-agent-personas
    plan: 01
    provides: "RED scaffolds test_persona_prompt.py (base+voice composition) + test_config.py operational_base assertions this plan turns GREEN"
  - phase: 16-web-search
    provides: "citation guidance in system_prompt (D-02 base) + the SYSTEM_PROMPT env-shadow pitfall + the test_web_search citation regression guard"
provides:
  - "services.persona_service registry (PERSONAS + DEFAULT_PERSONA_ID) + list_personas/resolve_persona_id/get_persona_voice (D-05/D-07/D-10)"
  - "settings.system_prompt repurposed to the persona-agnostic operational BASE (D-02) — opener + KB-first bias removed"
  - "stream_chat_completion persona_voice param + voice→base→tool_guide composition seam (D-01/D-04)"
affects: [17-06-chat-resolver, 17-07-persona-persistence, 17-11-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Definition-in-code persona registry (mirrors system_prompt/TOOL_SELECTION_GUIDE) — no DB, no cache, no seed (D-07)"
    - "Voice-first prompt composition: persona voice prepended before the operational base so exactly one 'You are…' opener leads (Pitfall 2)"
    - "voice_block withheld from list_personas (A5) + resolve_persona_id validates any pinned id to the default (D-10) — predefined-only injection surface"

key-files:
  created:
    - backend/services/persona_service.py
  modified:
    - backend/config.py
    - backend/services/llm_service.py

key-decisions:
  - "PERS-02/PERS-03 left Pending (NOT marked complete): both are multi-plan requirements also owned by 17-06 (chat resolver) and 17-11 (phase validation). This plan turns their prompt-composition CORE green; end-to-end closure (pin → resolve → picker) is not yet wired."
  - "Signature slot: persona_voice inserted AFTER model, BEFORE trace. Verified the sole production caller (chat.py:1077) and all test callers use kwargs, so no positional call breaks."
  - "Used the exact voice/base wording pinned in 17-RESEARCH.md Pattern 1 verbatim (Claude's-discretion wording was pre-committed by research)."

requirements-completed: []  # PERS-02/03 composition-core GREEN here but stay Pending — 17-06 resolver + 17-11 validation must land before closure

# Metrics
duration: 16min
completed: 2026-07-13
---

# Phase 17 Plan 04: Persona Base/Voice Split + Composition Summary

**The one genuinely-novel piece of Phase 17 — split the monolithic `settings.system_prompt` into a persona-agnostic operational BASE (config.py) plus a 2-entry per-persona VOICE registry (new persona_service.py), and compose them voice-first in `stream_chat_completion` — turning the 17-01 RED scaffolds (test_persona_prompt + test_config operational_base) GREEN with zero regressions.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-07-13T09:37Z (first task commit)
- **Completed:** 2026-07-13
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 edited)

## Accomplishments
- **`persona_service.py` (NEW)** — `DEFAULT_PERSONA_ID = "board_game_expert"` + a 2-entry `PERSONAS` registry (D-05). Board-Game Expert (default, PERS-03) carries the D-03 KB-first bias in its `voice_block`; General Assistant is board-game-agnostic (D-06). Three helpers: `list_personas()` withholds `voice_block` (A5), `resolve_persona_id()` collapses any unknown/stale id to the default without raising (D-10), `get_persona_voice()` falls back to the default voice on any miss.
- **`config.py` base strip** — dropped the "You are a helpful assistant" opener (A1) and the KB-first bias (D-03); kept the citation "Sources:"/inline, tool-error, markdown-tables, and analyze_document rules (D-02). Added a comment flagging the persona-agnostic role and the Pitfall 6 SYSTEM_PROMPT env-shadow. `subagent_system_prompt`/`explorer_system_prompt` untouched (out of scope, confirmed intact).
- **`llm_service.py` composition** — added `persona_voice: str | None = None` (slot after `model`, before `trace`), documented in the docstring. Composition now seeds the operational base, prepends the voice when set (`voice + "\n\n" + base`, Pitfall 2 — one opener leads), then appends `tool_guide` for every persona unchanged (D-04). The `source_hint`/`scope_hint` blocks are byte-for-byte intact (3 "## Source Routing" occurrences confirmed).

## Task Commits

Each task committed atomically:

1. **Task 1: persona_service.py registry + helpers** — `e8ab22b` (feat)
2. **Task 2: strip config.py system_prompt to the operational base** — `dbf90ea` (refactor)
3. **Task 3: persona_voice param + voice-first composition** — `fe1ad7b` (feat)

**Plan metadata:** _(final docs commit — see below)_

## Files Created/Modified
- `backend/services/persona_service.py` (NEW, 71 lines) — persona registry + `list_personas`/`resolve_persona_id`/`get_persona_voice`; module docstring documents the D-07 code-constant posture and the T-17-09/T-17-10 injection/disclosure mitigations.
- `backend/config.py` — `system_prompt` repurposed to the persona-agnostic operational base (D-02); opener + KB-first bias removed; Pitfall-6 comment added.
- `backend/services/llm_service.py` — `stream_chat_completion` gains `persona_voice` + voice→base→tool_guide composition; docstring updated.

## Verification

- `test_persona_prompt.py` — **5/5 GREEN**: voice-leads-then-base, base-rules-present-for-both-personas, Expert-KB-first, General-no-board-game-framing, tools-identical-across-personas (T-17-03).
- `test_config.py` operational_base — **3/3 GREEN**: keeps citation (regression guard), drops KB-first bias (D-03), drops opener (A1).
- `test_persona_resolution.py::test_registry_has_exactly_two_with_one_default` — **GREEN** (the only resolver test in this plan's scope; it imports only `persona_service`).
- `test_web_search.py::test_system_prompt_citation_guidance` — **GREEN** (D-02 regression guard intact).
- Full backend suite: **301 passed**; no regression introduced by this plan (the 11 existing llm/chat tests — usage-capture, cap, retry, deprecated-model-fallback — all still pass).

## Decisions Made
- **PERS-02/PERS-03 left Pending, not marked complete.** Both requirements are also owned by 17-06 (chat resolver) and 17-11 (phase validation). This plan turns their prompt-composition CORE green (General is vanilla + full tools; Expert is the registry default), but the end-to-end pin→resolve→picker path is not wired until later plans. Marking them Complete now would falsely close them — consistent with 17-01 keeping them Pending.
- **`persona_voice` signature slot after `model`, before `trace`.** Verified the sole production caller (`chat.py:1077`) and every test caller use kwargs (`trace=(not is_user_key)`), so inserting a param before `trace` breaks no positional call. `None` path is unchanged for sub-agent/back-compat callers.
- **Verbatim research wording.** The voice/base strings were pinned in 17-RESEARCH.md Pattern 1 (Claude's-discretion wording pre-committed by research), so they were copied verbatim rather than re-authored.

## Deviations from Plan

None — plan executed exactly as written. Two clarifications, neither a scope change:
- The plan's Task-1/Task-2 acceptance oneliners specify "run with SYSTEM_PROMPT unset". The live `.env` sets `SYSTEM_PROMPT` (Pitfall 6, expected), so the raw oneliner shadows the code default; the env-isolated pytest tests (which `delenv("SYSTEM_PROMPT")`) are the authoritative gate and all pass. This is the documented deploy-time follow-up, not a defect.
- Task-1's `-k "registry or unknown"` verify: the `registry` test is GREEN, but `test_unknown_pinned_id_falls_back_to_default` imports `routers.chat._resolve_persona` (authored by 17-06) so it stays RED until that plan lands. The plan's load-bearing Task-1 acceptance (the `persona_service` python-c oneliner) passes.

## Deferred / Out-of-Scope (expected RED, owned by later plans)
The full backend suite still shows RED scaffolds authored by 17-02 that this plan does NOT own:
- 6 `test_persona_resolution.py` resolver tests (import `routers.chat._resolve_persona`) → **17-06**.
- 3 `test_personas_api.py` + 2 `test_thread_persona_patch.py` + 2 `test_preferences_api.py` (persona) → **17-06/17-07**.

Pre-existing failures unrelated to this plan (confirmed identical with the Task-3 edit stashed):
- `test_config.py::test_key_encryption_secret_default` — env-driven (`KEY_ENCRYPTION_SECRET` set in `.env`, same shadow mechanism as SYSTEM_PROMPT).
- `test_record_manager.py` 2 errors — documented pre-existing `user_id` fixture debt (STATE.md).

## Threat Surface
No new runtime surface — this plan only composes server-side strings into the LLM system message. The threat-model dispositions are satisfied by the registry design:
- **T-17-09** (Tampering/Injection via `get_persona_voice` input) → `resolve_persona_id` validates any pinned id to a registry entry (D-10); only server-defined `voice_block` strings can reach the system message.
- **T-17-10** (Info Disclosure via `list_personas`) → `list_personas` returns id/label/is_default only; `voice_block` never leaves the module.
- **T-17-11** (EoP via tool_guide) → accepted; `tool_guide` is appended for every persona unchanged (D-04); persona never gates the tools list.

No threat flags — no new endpoints, auth paths, or schema at trust boundaries in this plan.

## User Setup Required
None for this plan's code. **Deploy-time carry-forward (Pitfall 6):** remove `SYSTEM_PROMPT` from `.env` and `.env.prod` so the refactored operational base reaches the running app; the unit tests are env-isolated and do NOT cover the running-app env.

## Next Plan Readiness
- **17-06 (chat resolver)** can now import `services.persona_service.{DEFAULT_PERSONA_ID, PERSONAS, resolve_persona_id, get_persona_voice}` and thread the resolved voice into `stream_chat_completion(..., persona_voice=...)` (the kwarg exists). Turning the 6 remaining `test_persona_resolution.py` tests GREEN is its job.
- **17-07** wires `threads.persona`/`user_preferences.default_persona` persistence + `PersonaResponse`/`GET /api/personas` (which imports `list_personas`, already available).

## Self-Check: PASSED

- FOUND: backend/services/persona_service.py
- FOUND: backend/config.py (system_prompt = operational base)
- FOUND: backend/services/llm_service.py (persona_voice param)
- FOUND commits: e8ab22b (Task 1), dbf90ea (Task 2), fe1ad7b (Task 3)

---
*Phase: 17-agent-personas*
*Completed: 2026-07-13*
