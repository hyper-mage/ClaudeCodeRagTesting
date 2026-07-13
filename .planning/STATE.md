---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Web Search & Agent Personas
status: executing
stopped_at: Completed 17-09-PLAN.md (persona picker components)
last_updated: "2026-07-13T22:15:27.561Z"
last_activity: 2026-07-13
progress:
  total_phases: 2
  completed_phases: 1
  total_plans: 15
  completed_plans: 14
  percent: 50
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-11 after v1.2 completion)

**Core value:** The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.
**Current focus:** Phase 17 — agent-personas

## Current Position

Phase: 17 (agent-personas) — EXECUTING
Plan: 11 of 11
Status: Ready to execute
Last activity: 2026-07-13

Progress: [█████████░] 93%

## Accumulated Context

### Decisions

v1.2 decisions promoted to PROJECT.md Key Decisions table at milestone close (2026-07-11). Full log there.

Recent decisions affecting v1.3 work:

- [v1.3 roadmap]: Phase 16 is a fix + prod-verify of the existing `web_search` tool (not greenfield) — likely Tavily Bearer-auth vs `api_key`-in-body and/or unset key.
- [v1.3 roadmap]: Phase 17 personas reuse the v1.2 model-pin infra — `user_preferences` default + per-thread column (migration 032 pattern), the per-request resolution seam in `chat.py`/`llm_service.stream_chat_completion`, and the `ModelSelector`/`DefaultModelSelector` UI. Predefined personas only.
- [Phase 16]: 16-01 is a Wave 0 RED test scaffold: WSRCH-01..04 pinned by failing tests (test_web_search.py + test_config.py); no production code touched — 16-02 turns them GREEN. Requirement traceability stays Pending until 16-02.
- [Phase ?]: [Phase 16]: 16-02 turned the 16-01 RED baseline GREEN — Tavily is header-only Bearer auth (body api_key deleted), search_depth is env-configurable (WEB_SEARCH_DEPTH), tool_result SSE carries is_error, scrub_secrets redacts tvly-.
- [Phase ?]: [Phase 16]: local .env SYSTEM_PROMPT override shadows the new citation-guidance default — must be removed from .env/.env.prod for D-01/D-02 guidance to reach the running app (flagged in 16-02 SUMMARY).
- [Phase 16]: [Phase 16]: 16-03 wired the frontend failed-state — ToolEvent.status gained 'error', the tool_result handler maps backend is_error, and ToolCallCard shows a red AlertTriangle + red border on failure (D-03/WSRCH-04).
- [Phase 16]: [Phase 16]: used 'as ToolEvent[status]' cast (not the plan's illegal 'as const' on a ternary, TS1355) for the is_error->status mapping; union widening is a two-file atomic pair verified by the full npm run build.
- [Phase 17]: 17-01 is the Wave 0 persona RED baseline — 15 failing tests pin PERS-03/06, D-10, D-09 tier order, 42P01 tolerance, the D-01/D-02/D-03/D-04 base+voice composition, and PERS-02/D-04 tools-independence; zero production code touched (17-04/17-06 turn GREEN). Traceability stays Pending until then.
- [Phase 17]: 17-02 is the Wave 0 persona API RED baseline: 11 tests (9 RED) pin the auth-gated GET /api/personas catalog with voice_block withheld (A5/T-17-06), PATCH /api/threads persona with id+user_id IDOR re-check (T-17-04) + no-clobber-model (T-17-05), and PUT/GET /api/preferences default_persona roundtrip (PERS-04); zero production code touched, PERS-01/04/05 traceability stays Pending until 17-06/17-07 turn GREEN
- [Phase 17]: 17-03 authored the Wave 0 persona-picker RED scaffolds — PersonaSelector.test.tsx (4 its, PERS-01 onSelect) + DefaultPersonaSelector.test.tsx (3 its, PERS-04 PUT default_persona); both DELIBERATELY drop the useKeyStatus/useKeyGate mock (persona has no key/cost surface) and assert a keyless pick is never gated; RED via cannot-resolve until 17-09 authors the components.
- [Phase ?]: [Phase 17]: 17-04 turned the persona composition RED baseline GREEN — settings.system_prompt is now the persona-agnostic operational base (D-02); opener (A1) + KB-first bias (D-03) moved into per-persona voice_blocks in services/persona_service.py; stream_chat_completion gained persona_voice and composes voice->base->tool_guide (Pitfall 2). PERS-02/03 composition-core GREEN; end-to-end closure awaits 17-06 resolver + 17-11 validation.
- [Phase ?]: [Phase 17]: Pitfall 6 confirmed live — SYSTEM_PROMPT (and KEY_ENCRYPTION_SECRET) are set in .env and shadow code defaults; operational-base unit tests delenv SYSTEM_PROMPT so they pass, but the running app needs SYSTEM_PROMPT removed from .env/.env.prod at deploy.
- [Phase ?]: [Phase 17]: 17-05 authored the persona DATA CONTRACT — PersonaResponse (id/label/is_default, voice_block withheld A5), ThreadResponse.persona (Pitfall 1), ThreadModelUpdate->ThreadUpdate + persona (exclude_unset partial PATCH), default_persona on both preferences models, and the additive-nullable migration 035 FILE (threads.persona + user_preferences.default_persona; no backfill/constraint/FK/DEFAULT/RLS, D-08/D-10). Migration authored NOT applied (17-08 owns db push). PERS-01/04/05 stay Pending until 17-06/17-07 wire endpoints, 17-08 applies, 17-09 ships pickers.
- [Phase ?]: [Phase 17]: 17-06 shipped the persona READ+RESOLUTION seam — auth-gated GET /api/personas (catalog code-constant, voice_block withheld A5) registered in main.py; chat.py gained the non-cached _resolve_persona sibling (D-09 thread-pin>user-default>Expert, D-10 validate-to-default, 42P01-tolerant) wired once per turn into stream_chat_completion(persona_voice=...). Model/key 4-tuple untouched (Pitfall 8); tools persona-independent (D-04). 17-01 resolver (6) + 17-02 personas_api (3) RED scaffolds GREEN. PERS-01/03/06 backend core live but stay Pending — 17-09 picker + 17-11 validation close them.
- [Phase ?]: [Phase 17]: 17-07 wired persona WRITE+PERSISTENCE — PATCH /api/threads/{id} now body.model_dump(exclude_unset=True) so persona/model never clobber (IDOR + explicit-null-clear intact); PUT/GET /api/preferences thread default_persona through both selects + all 4 return dicts (null for new users). 17-02 thread-persona-patch + prefs default_persona RED scaffolds GREEN. PERS-01/04/05 stay Pending (pickers=17-09, migration apply=17-08).
- [Phase 17]: 17-09 shipped the two gate-free persona pickers GREEN — PersonaSelector (chat header; onSelect(id), parent owns the PATCH) and DefaultPersonaSelector (settings; self-PUT /api/preferences {default_persona}). Both render the parent-supplied GET /api/personas catalog (never hardcoded, D-07), carry NO key gate (a keyless user can pick/set a persona, PERS-01/PERS-04), add no per-message badge (picker-only, D-12), and are fresh components (not a ModelSelector clone). 17-03 RED scaffolds GREEN (7/7).
- [Phase ?]: [Phase 17]: 17-10 wired the persona pickers into the running app (last implementation wave) — ChatPage fetches GET /api/personas once + owns an optimistic no-key-gate handleThreadPersonaChange (PATCH /api/threads/{id} {persona}, passed DIRECTLY not via useKeyGate) + Thread.persona seeded from the thread read on reopen (PERS-05); ChatContainer renders PersonaSelector beside ModelSelector (Sigma cost intact); SettingsPage renders DefaultPersonaSelector seeded from GET /api/preferences.default_persona. PERS-01/04/05 now live end-to-end; 17-11 is human UAT. FE build+133 tests green; required-prop addition to ChatContainer forced a Rule-1 test-props compile fix; 5 pre-existing lint errors confirmed baseline via git stash, deferred.

### Pending Todos

None yet.

### Blockers/Concerns (carried forward)

- [v1.2+]: Supabase free-tier `pg_cron` availability affects any future scheduled model-refresh upgrade (lazy TTL is the shipped baseline).
- [ops]: Supabase key migration deferred — legacy anon/service_role keys in use; new publishable/secret keys are a future-version task.
- [ops]: POST /api/demo/bootstrap failure (D-999.1-DEMO-A) — anon-session demo bootstrap; revisit if demo UX work returns.

## Deferred Items

Items acknowledged and deferred at v1.2 milestone close on 2026-07-11:

| Category | Item | Status |
|----------|------|--------|
| uat_gap | Phase 11 UAT test 3 — live 402 vs 429 distinct SSE codes | pending (non-blocking; unit coverage green) |
| uat_gap | Phase 11 UAT test 4 — prod SQL-flip smoke of LangSmith master toggle | pending (non-blocking; suppress-only post-CR-01, dev flip smoke passed) |
| tech_debt | W-1/W-2 (Phase 13) — dead-pin notice accumulates per send + not SSE-emitted | open |
| tech_debt | W-3 (Phase 15) — stale Demo-mode banner until thread switch after mid-thread connect | open |
| tech_debt | W-4/W-5 (Phase 11) — FE scrub regex narrower than backend; budget_service logger not directly filtered | open |
| tech_debt | W-6 (Phase 14) — no post-turn balance refresh | open |
| validation | Phase 13 Nyquist PARTIAL — `/gsd:validate-phase 13`; v1.1 phases 1, 3, 6, 6.1, 7, 8 unvalidated | open |
| test_debt | test_record_manager.py missing `user_id` fixture (pre-v1.1) | open |
| ops | Free-model provider 429s make live smokes flaky (D-999.1-LLM-A) | open |
| ops | execute_readonly_query 42501 SET LOCAL role quirk (D-09-A) | open |

## Session Continuity

Last session: 2026-07-13T22:14:53.130Z
Stopped at: Completed 17-09-PLAN.md (persona picker components)
Resume file: None
Next: Execute 17-03-PLAN.md (continue Phase 17 agent-personas)
