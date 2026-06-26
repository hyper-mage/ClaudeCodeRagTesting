---
phase: 14
slug: usage-cost-display-settings-key-state-ux
status: approved
nyquist_compliant: true
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
| 14-01-01 | 01 | 1 | COST-01/02/03/04, PREF-01 | T-14 balance | RED stubs: no `sk-or-` in `/balance` response; mid-stream 401→`no_api_key`, 403→`forbidden` | unit (RED) | `pytest test_keys_balance.py test_thread_usage_exposed.py "test_error_surfacing.py::test_unauthorized_code_on_401" "test_error_surfacing.py::test_forbidden_code_on_403" -q` | ❌ W0 (authored here) | ⬜ pending |
| 14-01-02 | 01 | 1 | COST-01/04, PREF-01 | T-14 leak | `MessageResponse.usage` survives history load; chat.py 401→`no_api_key`/403→`forbidden` before `else` | unit (GREEN) | `pytest test_thread_usage_exposed.py test_error_surfacing.py -q` | ✅ | ⬜ pending |
| 14-01-03 | 01 | 1 | COST-02/03 | T-14 balance | `/api/keys/balance` decrypt in-memory, `scrub_secrets`, fixed 502, no `exc_info`, server-computed `is_low`, returns only `{connected,limit_remaining,is_low}` | unit (GREEN) | `pytest test_keys_balance.py -q` | ✅ | ⬜ pending |
| 14-02-01 | 02 | 2 | COST-01/04, PREF-01 | — | `useChat` captures `done.usage` + typed `errorType` (no toast on key path) | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-02-02 | 02 | 2 | COST-02/03 | — | `useKeyStatus` exposes balance + `isLow` + loading/error; no polling | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-03-01 | 03 | 3 | COST-01 | — | per-message cost caption `$0.0021 · 1.2k tok`; omit when `usage.cost` null | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-03-02 | 03 | 3 | PREF-01 | T-14 recovery | typed recovery bubble keyed on `errorType` (401/403→`[Reconnect]`, 402→`[Add credits ⇗]`+`[Reconnect]`) | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-03-03 | 03 | 3 | COST-04 | — | per-thread `Σ` total summed from persisted `messages.usage`; hidden when sum=0 | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-04-01 | 04 | 3 | COST-03 | — | IconSidebar key dot tri-state (green/amber/gray); amber on `isLow` | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-04-02 | 04 | 3 | COST-03 | — | MobileTopBar key dot mirrors tri-state | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-05-01 | 05 | 3 | COST-02/03, PREF-01 | — | Settings 3 sections; tri-state copy (2 live: connected, no-key; Demo reserved→P15); balance line + amber warning; no `mode==='demo'` UI | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |
| 14-05-02 | 05 | 3 | PREF-01 | — | ChatPage temp mounts removed (`:176` DefaultModelSelector, `:179` ThemeToggle) | build/lint + browser | `cd frontend && npm run build && npm run lint` | N/A (no FE test fw) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · File Exists ❌ W0 = authored by the Wave 0 RED task (14-01-01)*

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (14-01-01 authors the 3 backend test files RED before 14-01-02/03 turn them green)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-25
