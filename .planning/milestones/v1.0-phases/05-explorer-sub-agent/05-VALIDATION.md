---
phase: 5
slug: explorer-sub-agent
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-15
last_updated: 2026-04-16
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + TypeScript+Vite (frontend type/lint check; no test runner) |
| **Config file** | backend/pytest.ini (created in 05-01 Task 1) |
| **Quick run command** | `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_tools.py -q` |
| **Full suite command** | `cd backend && venv/Scripts/python -m pytest tests/ -q --ignore=tests/test_e2e_subagent.py` |
| **Frontend gate** | `cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run lint && npm run build` |
| **Estimated runtime** | ~60 seconds backend + ~30 seconds frontend |

---

## Sampling Rate

- **After every task commit:** Run quick run command (or frontend gate for Plan 04 tasks)
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full backend suite + frontend gate must be green; manual UAT (Plan 04 Task 3) approved
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-T1 | 05-01 | 1 | EXPL-05, EXPL-06 | contract (Pydantic + Settings) | `cd backend && venv/Scripts/python -c "from models.schemas import ExplorerResult, ExplorerFinding; from pydantic import ValidationError; r=ExplorerResult(mode='summarize', query='q', synthesis='s'); assert r.findings==[]; assert r.iterations==0; print('OK')"` | ❌ creates models | ⬜ pending |
| 05-01-T2 | 05-01 | 1 | EXPL-01, EXPL-02, EXPL-05 | unit (contract) | `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q -k "rejects or mode_pattern or output_size_cap"` | ❌ creates tests | ⬜ pending |
| 05-02-T1 | 05-02 | 2 | EXPL-01, EXPL-05, EXPL-06 | structural | `cd backend && venv/Scripts/python -c "from services.explorer_service import run_exploration, _execute_explorer_tool, _summarize_findings; import inspect; assert inspect.isgeneratorfunction(run_exploration); print('OK')"` | ❌ creates service | ⬜ pending |
| 05-02-T2 | 05-02 | 2 | EXPL-01, EXPL-05 | unit (behavior) | `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_tools.py -q -k "not find_similar and not recommendation_seed"` | ✅ from 05-01 | ⬜ pending |
| 05-03-T1 | 05-03 | 3 | EXPL-01, EXPL-06 | structural + regression | `cd backend && venv/Scripts/python -c "from routers.chat import EXPLORE_KB_TOOL, KB_LS_TOOL; assert EXPLORE_KB_TOOL['function']['name']=='explore_kb'; assert sorted(EXPLORE_KB_TOOL['function']['parameters']['properties']['mode']['enum'])==['deep_search','find_similar','summarize']; from services.explorer_service import run_exploration; print('OK')" && cd backend && venv/Scripts/python -m pytest tests/test_folders_api.py -q` | ✅ existing | ⬜ pending |
| 05-03-T2 | 05-03 | 3 | EXPL-02, EXPL-03, EXPL-04, EXPL-06 | unit + integration (SSE) | `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py tests/test_explorer_integration.py -q` | ✅ from 05-01 | ⬜ pending |
| 05-04-T1 | 05-04 | 4 | EXPL-06 | TS typecheck + lint | `cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run lint` | ✅ existing | ⬜ pending |
| 05-04-T2 | 05-04 | 4 | EXPL-04, EXPL-06 | TS typecheck + lint + build | `cd frontend && npx tsc --noEmit -p tsconfig.app.json && npm run lint && npm run build` | ✅ existing | ⬜ pending |
| 05-04-T3 | 05-04 | 4 | EXPL-01, EXPL-02, EXPL-03, EXPL-04, EXPL-05 | manual UAT | golden queries via live UI (see Manual-Only Verifications) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Coverage check:**
- EXPL-01: 05-01-T2, 05-02-T1, 05-02-T2, 05-03-T1, 05-04-T3
- EXPL-02: 05-01-T2, 05-02-T2, 05-03-T2, 05-04-T3
- EXPL-03: 05-03-T2, 05-04-T3
- EXPL-04: 05-03-T2, 05-04-T2, 05-04-T3
- EXPL-05: 05-01-T1, 05-01-T2, 05-02-T1, 05-02-T2, 05-04-T3
- EXPL-06: 05-01-T1, 05-02-T1, 05-03-T1, 05-03-T2, 05-04-T1, 05-04-T2

**Sampling continuity check:** No 3 consecutive tasks without an automated verify command. ✅

---

## Wave 0 Requirements

- [x] **Owned by 05-01-T2:** `backend/tests/test_explorer_service.py` — unit tests for explorer tool loop, budget enforcement, structured output parsing (EXPL-01, EXPL-05, EXPL-06)
- [x] **Owned by 05-01-T2:** `backend/tests/test_explorer_tools.py` — explorer-facing wrappers over KB tools (EXPL-02)
- [x] **Owned by 05-01-T2:** `backend/tests/test_explorer_integration.py` — end-to-end: parent chat → explorer tool call → SSE events → summary returned (EXPL-03, EXPL-04, EXPL-06)
- [x] **Owned by 05-01-T2:** `backend/tests/fixtures/explorer_fixtures.py` — seeded LLM scenarios, mock_llm_client, make_tool_call/make_response helpers
- [x] **Owned by 05-01-T2:** `backend/tests/conftest.py` — shared fixtures re-exported from explorer_fixtures
- [x] **Owned by 05-01-T1:** pytest-asyncio added to `backend/requirements.txt`; `backend/pytest.ini` created

*All Wave 0 files created in Plan 05-01 (Wave 1 of execution). Subsequent plans REMOVE skip markers and replace `pass` bodies — they do not need to create new test files.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Owned By |
|----------|-------------|------------|-------------------|----------|
| Explorer progress UI rendering | EXPL-04, EXPL-06 | Visual SSE stream in browser | Plan 04 Task 3 — golden query 1 (`Summarize the Catan folder.`) | 05-04-T3 |
| "Games similar to X" reasoning quality | EXPL-03 | LLM output quality judgement | Plan 04 Task 3 — golden query 2 (`What games are like Azul?`) | 05-04-T3 |
| Multi-step deep search | EXPL-01 | LLM strategy quality | Plan 04 Task 3 — golden query 3 (`Find all games with tile placement mechanics.`) | 05-04-T3 |
| Conversation-context recommendation | EXPL-04 | LLM seed-resolution quality | Plan 04 Task 3 — golden query 4 (follow-up after Catan) | 05-04-T3 |
| Budget cap graceful degradation | EXPL-05 | Requires env var swap + restart | Plan 04 Task 3 — golden query 5 (set EXPLORER_MAX_ITERATIONS=2) | 05-04-T3 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (all owned by 05-01-T2)
- [x] No watch-mode flags
- [x] Feedback latency < 90s (longest single command estimate: 60s for full backend suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-approved 2026-04-16
