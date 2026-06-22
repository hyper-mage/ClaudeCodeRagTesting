---
phase: 11
slug: per-request-key-model-resolution-chat-loop-seam
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-22
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing `backend/tests/`) |
| **Config file** | none detected — uses `backend/tests/conftest.py` fixtures |
| **Quick run command** | `cd backend && venv/Scripts/python -m pytest tests/ -q` |
| **Full suite command** | `cd backend && venv/Scripts/python -m pytest tests/` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner from PLAN.md tasks. One row per task mapping to a requirement + automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | SEC-04 | T-11-01 / — | concurrent requests never share key/model | unit | `pytest tests/ -q -k resolution` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> RESEARCH.md specifies new/extended test files. Planner finalizes the exact list.

- [ ] `backend/tests/` test stubs for SEC-04 (per-request key/model isolation), SEC-01 (sk-or scrub + wrap_openai gate), DEMO-03 (fail-closed resolution)
- [ ] `backend/tests/conftest.py` — shared fixtures (extend existing)

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `wrap_openai` gate verified against prod LangSmith project (zero user-key runs post-gate) | SEC-01 | Requires live prod LangSmith project + a real OAuth-provisioned key | Send a BYOK chat turn; confirm no run appears in prod LangSmith for that turn |
| OpenRouter 402 (payment) vs 429 (rate-limit) surface distinctly | DEMO-03 / SEC-01 | Requires tripping a live free-model rate cap / negative-balance owner key | Drive a free-model turn past the per-minute cap; confirm distinct structured SSE error |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
