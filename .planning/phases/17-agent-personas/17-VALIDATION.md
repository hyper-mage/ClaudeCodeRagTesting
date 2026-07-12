---
phase: 17
slug: agent-personas
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-12
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 8.4.2 + pytest-asyncio 0.23.8 (`asyncio_mode = auto`) |
| **Framework (frontend)** | vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom |
| **Config file** | `backend/pytest.ini` ; `frontend/vitest.config.ts` (setup `src/test/setup.ts`) |
| **Quick run (backend)** | `cd backend && python -m pytest tests/test_persona_resolution.py -x` |
| **Quick run (frontend)** | `cd frontend && npx vitest run src/components/PersonaSelector.test.tsx` |
| **Full suite (backend)** | `cd backend && python -m pytest` |
| **Full suite (frontend)** | `cd frontend && npm test` |
| **Estimated runtime** | backend ~30s, frontend ~20s |

---

## Sampling Rate

- **After every task commit:** Run the task's quick-run command (see the per-task map).
- **After every plan wave:** `cd backend && python -m pytest` + `cd frontend && npm test`.
- **Before `/gsd-verify-work`:** Both full suites green AND `test_web_search.py::test_system_prompt_citation_guidance` still GREEN (citation guidance stays in the operational base — D-02).
- **Max feedback latency:** < 60 seconds (targeted quick-run per task).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | PERS-03/06 | T-17-01/02 | Unknown pin → default; no cross-thread bleed | unit (RED) | `cd backend && python -m pytest tests/test_persona_resolution.py -x` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | PERS-02 | T-17-03 | General has no board-game framing; tools identical | unit (RED) | `cd backend && python -m pytest tests/test_persona_prompt.py -x` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | PERS-02 (D-02) | — | Base keeps citation, drops KB-first bias | unit (RED) | `cd backend && python -m pytest tests/test_config.py -k operational_base` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 1 | PERS-01 (D-07) | T-17-06 | GET /api/personas auth-gated; voice_block withheld | unit (RED) | `cd backend && python -m pytest tests/test_personas_api.py -x` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 1 | PERS-01/05 | T-17-04/05 | PATCH scoped id+user_id; no-clobber; 404 non-owned | unit (RED) | `cd backend && python -m pytest tests/test_thread_persona_patch.py -x` | ❌ W0 | ⬜ pending |
| 17-02-03 | 02 | 1 | PERS-04 | T-17-05 | default_persona roundtrip; theme-only no-clobber | unit (RED) | `cd backend && python -m pytest tests/test_preferences_api.py -k persona` | ⚠️ extend | ⬜ pending |
| 17-03-01 | 03 | 1 | PERS-01 | T-17-07 | Picker onSelect(id); no key gate | unit (RED) | `cd frontend && npx vitest run src/components/PersonaSelector.test.tsx` | ❌ W0 | ⬜ pending |
| 17-03-02 | 03 | 1 | PERS-04 | T-17-07 | Picker PUT {default_persona}; no key gate | unit (RED) | `cd frontend && npx vitest run src/components/DefaultPersonaSelector.test.tsx` | ❌ W0 | ⬜ pending |
| 17-04-01 | 04 | 2 | PERS-02/03 | T-17-09/10 | Registry 2 personas; unknown→default; no voice_block leak | unit | `cd backend && python -m pytest tests/test_persona_resolution.py -k "registry or unknown"` | ✅ (17-01) | ⬜ pending |
| 17-04-02 | 04 | 2 | PERS-02 (D-02) | — | Base citation kept; KB-first/opener dropped | unit | `cd backend && python -m pytest tests/test_config.py -k operational_base tests/test_web_search.py::test_system_prompt_citation_guidance` | ✅ (17-01) | ⬜ pending |
| 17-04-03 | 04 | 2 | PERS-02 (D-01/D-04) | T-17-11 | Voice-first compose; tool_guide for all personas | unit | `cd backend && python -m pytest tests/test_persona_prompt.py -x` | ✅ (17-01) | ⬜ pending |
| 17-05-01 | 05 | 2 | PERS-01/04/05 | T-17-14 | Schema fields declared (Pitfall 1); PersonaResponse withholds voice_block | unit | `cd backend && python -c "import routers.threads; from models.schemas import PersonaResponse, ThreadUpdate; assert set(PersonaResponse.model_fields)=={'id','label','is_default'}"` | n/a (assertion) | ⬜ pending |
| 17-05-02 | 05 | 2 | PERS-05 (D-08) | T-17-12/13 | Additive nullable columns; no CHECK/FK/RLS | file gate | `grep -qi "ADD COLUMN persona" supabase/migrations/20240301000035_add_persona_columns.sql` | ❌ new | ⬜ pending |
| 17-06-01 | 06 | 3 | PERS-01 (D-07) | T-17-15/16 | GET /api/personas live + registered | unit | `cd backend && python -m pytest tests/test_personas_api.py -x` | ✅ (17-02) | ⬜ pending |
| 17-06-02 | 06 | 3 | PERS-03/06 | T-17-16/17 | Tier chain; unknown→default; non-cached no-bleed | unit | `cd backend && python -m pytest tests/test_persona_resolution.py -x` | ✅ (17-01) | ⬜ pending |
| 17-06-03 | 06 | 3 | PERS-06 (D-04) | T-17-17/18 | persona_voice threaded per-turn; tools untouched | unit | `cd backend && python -m pytest tests/test_persona_resolution.py tests/test_persona_prompt.py tests/test_key_model_resolution.py -x` | ✅ | ⬜ pending |
| 17-07-01 | 07 | 3 | PERS-01/05 | T-17-19/20 | exclude_unset PATCH; no-clobber; IDOR 404 | unit | `cd backend && python -m pytest tests/test_thread_persona_patch.py tests/test_thread_model_patch.py -x` | ✅ (17-02) | ⬜ pending |
| 17-07-02 | 07 | 3 | PERS-04 | T-17-20/21 | default_persona GET/PUT; JWT-bound user_id | unit | `cd backend && python -m pytest tests/test_preferences_api.py -x` | ✅ (17-02) | ⬜ pending |
| 17-08-01 | 08 | 3 | (Pitfall 6) | — | No SYSTEM_PROMPT env-shadow of the new base | cli gate | `! grep -qE "^SYSTEM_PROMPT=" .env && echo NO_SYSTEM_PROMPT_OVERRIDE` | n/a | ⬜ pending |
| 17-08-02 | 08 | 3 | PERS-05 (D-08) | T-17-23/24 | Migration 035 applied to dev (columns exist) | cli gate | `cd backend && python -c "from database import get_supabase; db=get_supabase(); db.table('threads').select('persona').limit(1).execute(); db.table('user_preferences').select('default_persona').limit(1).execute(); print('COLUMNS_EXIST')"` | n/a | ⬜ pending |
| 17-08-03 | 08 | 3 | PERS-05 | T-17-25 | Dev columns confirmed; prod deferred | **manual** | Supabase Table Editor (dev) | n/a | ⬜ pending |
| 17-09-01 | 09 | 4 | PERS-01 | T-17-26/27 | Chat picker renders fetched list; onSelect; no gate | unit | `cd frontend && npx vitest run src/components/PersonaSelector.test.tsx` | ✅ (17-03) | ⬜ pending |
| 17-09-02 | 09 | 4 | PERS-04 | T-17-26/27 | Settings picker self-PUT default_persona; no gate | unit | `cd frontend && npx vitest run src/components/DefaultPersonaSelector.test.tsx` | ✅ (17-03) | ⬜ pending |
| 17-10-01 | 10 | 5 | PERS-01/05 | T-17-29 | ChatPage persona state + optimistic PATCH (no gate) | build | `cd frontend && npm run build` | n/a | ⬜ pending |
| 17-10-02 | 10 | 5 | PERS-01 | T-17-29 | ChatContainer renders PersonaSelector | build+unit | `cd frontend && npm run build && npx vitest run src/components/PersonaSelector.test.tsx src/components/DefaultPersonaSelector.test.tsx` | n/a | ⬜ pending |
| 17-10-03 | 10 | 5 | PERS-04 | T-17-30 | SettingsPage renders DefaultPersonaSelector seeded | build | `cd frontend && npm run build` | n/a | ⬜ pending |
| 17-11-01 | 11 | 6 | PERS-01..06 | T-17-32/33 | Persona voice audible; General keeps tools; persistence; next-turn switch | **manual** | Running dev app (5 ROADMAP criteria) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_persona_resolution.py` — PERS-03/06/D-10 (mirror `test_key_model_resolution.py`) — plan 17-01
- [ ] `backend/tests/test_persona_prompt.py` — PERS-02 (composition + tools-independence) — plan 17-01
- [ ] `backend/tests/test_config.py` (extend) — base keeps citation, drops KB-first bias — plan 17-01
- [ ] `backend/tests/test_personas_api.py` — GET /api/personas (mirror `test_models_api.py`) — plan 17-02
- [ ] `backend/tests/test_thread_persona_patch.py` — PATCH persona (mirror `test_thread_model_patch.py`) — plan 17-02
- [ ] `backend/tests/test_preferences_api.py` (extend) — default_persona roundtrip + no-clobber — plan 17-02
- [ ] `frontend/src/components/PersonaSelector.test.tsx` — chat picker (mirror `DefaultModelSelector.test.tsx` minus gate) — plan 17-03
- [ ] `frontend/src/components/DefaultPersonaSelector.test.tsx` — settings picker — plan 17-03

*Existing harness covers the framework — no install needed. Wave 0 = plans 17-01, 17-02, 17-03.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dev Supabase columns present after `db push` | PERS-05 | Live DB state — build/unit checks pass without the push (false positive) | Supabase Dashboard → Table Editor (dev): confirm nullable `threads.persona` + `user_preferences.default_persona`, existing rows NULL (17-08 Task 3) |
| Agent audibly responds in the selected persona; General Assistant keeps tool access | PERS-01/02/03/05/06 | The LLM "sounds like" a persona — automation pins the composed prompt/tools but not the qualitative voice | Run dev app, sign in (ragtest1@gmail.com), walk the 5 ROADMAP criteria (17-11 Task 1) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency (2 manual checkpoints justified above)
- [x] Sampling continuity: no 3 consecutive code-producing tasks without an automated verify
- [x] Wave 0 covers all MISSING references (8 new/extended test targets across 17-01/02/03)
- [x] No watch-mode flags (all `vitest run` / `pytest`, non-interactive)
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-12
