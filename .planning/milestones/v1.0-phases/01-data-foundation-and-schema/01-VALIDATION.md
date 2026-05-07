---
phase: 01
slug: data-foundation-and-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/tests/ (existing directory) |
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
| 01-01-01 | 01 | 1 | DATA-01 | migration | `supabase db push --dry-run` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | DATA-05 | migration | `supabase db push --dry-run` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | DATA-03 | integration | `cd backend && python -m pytest tests/test_rls.py -v` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | DATA-06 | integration | `cd backend && python -m pytest tests/test_rls.py -v` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | DATA-07 | integration | `cd backend && python -m pytest tests/test_rls.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_rls.py` — stubs for DATA-03, DATA-06, DATA-07 RLS verification
- [ ] `backend/tests/conftest.py` — shared fixtures for Supabase test client
- [ ] pytest installed in venv — verify with `pip show pytest`

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Supabase dashboard shows ltree extension enabled | DATA-05 | Requires Supabase dashboard or psql | Run `SELECT * FROM pg_extension WHERE extname = 'ltree'` via SQL editor |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
