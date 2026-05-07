---
phase: 04
slug: file-manager-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-11
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) |
| **Config file** | none (default pytest discovery) |
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
| 04-01-XX | 01 | 0 | -- | unit | `pytest tests/test_folders_api.py -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 1 | FMGR-02 | unit (backend) | `pytest tests/test_folders_api.py::test_create_folder -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 1 | FMGR-03 | unit (backend) | `pytest tests/test_folders_api.py::test_rename_folder -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 1 | FMGR-04 | unit (backend) | `pytest tests/test_folders_api.py::test_delete_folder_cascade -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 1 | -- | unit (backend) | `pytest tests/test_folders_api.py::test_reject_public_mutation -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 1 | -- | unit (backend) | `pytest tests/test_folders_api.py::test_move_updates_paths -x` | Wave 0 | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-01 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-05 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-06 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-07 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-08 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-09 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | FMGR-10 | manual (UI) | N/A | N/A | ⬜ pending |
| 04-XX-XX | XX | 2 | DATA-02 | manual (UI) | N/A | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_folders_api.py` — stubs for folder CRUD, move, cascade delete, read-only enforcement
- [ ] `backend/routers/folders.py` — the router being tested
- [ ] `backend/models/folder_models.py` — Pydantic models for folder operations

*No frontend test framework detected — UI testing is manual via browser*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tree sidebar shows folder hierarchy | FMGR-01 | Visual UI component | Open /documents, verify tree sidebar renders with Board Games and My Documents roots |
| Drag-drop move files/folders | FMGR-05 | Browser interaction | Drag a file from one folder to another, verify it moves in tree and DB |
| Context menu operations | FMGR-06 | Browser interaction | Right-click file/folder, verify menu appears with correct actions |
| Bulk select and operate | FMGR-07 | Browser interaction | Shift-click multiple files, verify bulk actions available |
| Board Games read-only styling | FMGR-08 | Visual styling | Verify Board Games tree has distinct read-only appearance, mutations blocked |
| Upload by dropping onto folder | FMGR-09 | Browser + OS interaction | Drop OS file onto folder in tree, verify upload triggers |
| Breadcrumb navigation | FMGR-10 | Visual UI component | Click through folders, verify breadcrumbs update and are clickable |
| Hierarchical folder display | DATA-02 | Visual UI component | Verify nested folder structure renders correctly with expand/collapse |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
