---
phase: 3
slug: kb-navigation-tools
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | TOOL-01 | unit | `pytest tests/test_kb_tools.py -k ls` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | TOOL-02 | unit | `pytest tests/test_kb_tools.py -k tree` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | TOOL-03 | unit | `pytest tests/test_kb_tools.py -k grep` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | TOOL-04 | unit | `pytest tests/test_kb_tools.py -k glob` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | TOOL-05 | unit | `pytest tests/test_kb_tools.py -k read` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | TOOL-06 | integration | `pytest tests/test_tool_dispatch.py` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | TOOL-07 | integration | `pytest tests/test_tool_dispatch.py -k scope` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | TOOL-08 | e2e | `pytest tests/test_tool_ui.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_kb_tools.py` — stubs for TOOL-01 through TOOL-05
- [ ] `backend/tests/test_tool_dispatch.py` — stubs for TOOL-06, TOOL-07
- [ ] `backend/tests/test_tool_ui.py` — stubs for TOOL-08
- [ ] `backend/tests/conftest.py` — shared fixtures (mock Supabase client)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tool call card UI rendering | TOOL-08 | Visual UI component | Open chat, ask agent to list files, verify ToolCallCard shows tool name, args, collapsible output |
| SSE tool_event streaming | TOOL-08 | Real-time streaming behavior | Send chat message triggering tool use, verify tool events stream before final response |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
