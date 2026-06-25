---
phase: 14
slug: usage-cost-display-settings-key-state-ux
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-25
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend); frontend has no test framework — browser-verified per CLAUDE.md |
| **Config file** | `backend/` (pytest discovered via `backend/tests/`) |
| **Quick run command** | `backend/venv/Scripts/python -m pytest backend/tests/<test_file> -q` |
| **Full suite command** | `backend/venv/Scripts/python -m pytest backend/tests -q` |
| **Estimated runtime** | ~30 seconds (backend unit) |

---

## Sampling Rate

- **After every task commit:** Run the relevant quick `pytest` file
- **After every plan wave:** Run the full backend suite
- **Before `/gsd-verify-work`:** Full backend suite must be green; frontend surfaces browser-verified
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| (filled by planner from RESEARCH.md §Validation Architecture) | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_keys_balance.py` — stubs for COST-02/COST-03 (balance proxy + server-side `is_low` + null-limit tolerance)
- [ ] `backend/tests/test_thread_usage_exposed.py` — stubs for COST-01/COST-04 (`MessageResponse.usage` survives `GET /api/threads/{id}` history load)
- [ ] extend `backend/tests/test_error_surfacing.py` — `forbidden` (403) code branch for PREF-01 mid-chat recovery
- [ ] frontend: no framework — per-message cost line, thread total, settings sections, recovery bubble browser-verified

*Backend pytest infrastructure already exists; frontend has none by project convention.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Per-message cost line + thread `Σ` total render correctly | COST-01, COST-04 | No frontend test framework | Send a turn, reload thread, confirm cost line + header total persist |
| Settings page sections (key tri-state, balance, default model, theme) | PREF-01 | No frontend test framework | Open `/settings`, verify all sections + tri-state copy |
| Mid-chat 401/402/403 in-thread recovery buttons | PREF-01 | Requires live key-failure state | Trigger key failure, confirm typed bubble + action buttons |
| Amber low-balance indicator | COST-03 | Requires low-balance account state | Configure threshold above balance, confirm amber dot + settings warning |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
