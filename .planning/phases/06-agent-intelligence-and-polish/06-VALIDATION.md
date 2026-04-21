---
phase: 6
slug: agent-intelligence-and-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-21
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2.2 |
| **Config file** | None (implicit, `backend/tests/` dir) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | AGNT-01 | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_source_routing -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | AGNT-02 | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_budget_truncation -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | AGNT-03 | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_budget_categories -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 0 | AGNT-04 | unit | `cd backend && python -m pytest tests/test_budget_service.py::test_scope_parsing -x` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 0 | AGNT-05 | unit | `cd backend && python -m pytest tests/test_subagent_alignment.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_budget_service.py` — stubs for AGNT-01, AGNT-02, AGNT-03, AGNT-04
- [ ] `tests/test_subagent_alignment.py` — stubs for AGNT-05
- [ ] Install tiktoken: `pip install tiktoken==0.12.0`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Source scope indicator visible in tool cards | AGNT-01 (D-03) | Visual UI check | 1. Send "What are Catan rules?" 2. Verify tool card shows scope indicator in args_preview |
| Natural language scope narrowing works in chat | AGNT-04 | End-to-end chat flow | 1. Send "Only search Catan rules" 2. Verify tool calls are scoped to matching content |
| analyze_document shows progress like explore_kb | AGNT-05 | SSE event visual alignment | 1. Trigger analyze_document tool 2. Verify sub-events render in tool card same as explore_kb |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
