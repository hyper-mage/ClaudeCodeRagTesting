---
phase: 02
slug: default-kb-and-ingestion-extensions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (not installed — Wave 0 installs) |
| **Config file** | none — Wave 0 creates |
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
| 02-01-01 | 01 | 1 | DATA-04 | integration | `python -m pytest tests/test_seed_default_kb.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | DATA-08 | unit | `python -m pytest tests/test_parsing_formats.py::test_image_ocr -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | DATA-09 | unit | `python -m pytest tests/test_parsing_formats.py::test_xlsx_parse -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | DATA-10 | unit | `python -m pytest tests/test_upload_folder.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pip install pytest` and add to `backend/requirements.txt`
- [ ] `backend/tests/test_parsing_formats.py` — stubs for DATA-08, DATA-09
- [ ] `backend/tests/test_seed_default_kb.py` — stubs for DATA-04
- [ ] `backend/tests/test_upload_folder.py` — stubs for DATA-10

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OCR quality on photographed rule cards | DATA-08 | Visual quality assessment | Upload a JPG photo of a game rule card, verify extracted text is readable |
| First-login browse experience | DATA-04 | UI interaction | Log in as new user, verify 10 games visible without uploading |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
