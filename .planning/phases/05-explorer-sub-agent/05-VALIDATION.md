---
phase: 5
slug: explorer-sub-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest/RTL (frontend if added) |
| **Config file** | backend/pytest.ini / backend/pyproject.toml (Wave 0 adds if missing) |
| **Quick run command** | `cd backend && venv/Scripts/python -m pytest tests/test_explorer_service.py -q` |
| **Full suite command** | `cd backend && venv/Scripts/python -m pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-XX-XX | TBD | TBD | EXPL-01..EXPL-06 | unit/integration | TBD at planning | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner MUST fill this table — one row per task — linking each task to its automated verify command and requirement.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_explorer_service.py` — unit tests for explorer tool loop, budget enforcement, structured output parsing (EXPL-01, EXPL-05, EXPL-06)
- [ ] `backend/tests/test_explorer_tools.py` — explorer-facing wrappers over KB tools (EXPL-02)
- [ ] `backend/tests/test_explorer_integration.py` — end-to-end: parent chat → explorer tool call → SSE events → summary returned (EXPL-03, EXPL-04)
- [ ] `backend/tests/fixtures/explorer_fixtures.py` — seeded KB hierarchy + golden queries
- [ ] `backend/tests/conftest.py` — shared Supabase test client, user scoping fixture (if not present)
- [ ] pytest + pytest-asyncio installed in `backend/requirements.txt` if missing

*Planner MUST produce Wave 0 plan tasks that stand up these files before other waves run.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Explorer progress UI rendering | EXPL-04 | Visual SSE stream in browser | Start dev server, ask a multi-step KB question, observe indigo-styled nested tool calls updating in real time |
| "Games similar to X" reasoning quality | EXPL-03 | LLM output quality judgement | Seed KB with 3 strategy games, ask "what's similar to Catan", confirm at least 2 cross-references with plausible reasoning |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
