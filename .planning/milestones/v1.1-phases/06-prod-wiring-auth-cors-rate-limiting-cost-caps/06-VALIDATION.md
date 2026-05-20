---
phase: 6
slug: prod-wiring-auth-cors-rate-limiting-cost-caps
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `06-RESEARCH.md` §Validation Architecture (lines 697-743).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest==8.4.2` + `pytest-asyncio==0.23.8` (already in `backend/requirements.txt`) |
| **Config file** | None at repo root; tests live in `backend/tests/`. Pytest auto-discovers. |
| **Quick run command** | `cd backend && pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -x -q` |
| **Full suite command** | `cd backend && pytest tests/` |
| **Manual smoke command** | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |
| **Estimated runtime** | ~30s (quick subset), ~2-3min (full suite + smoke) |

---

## Sampling Rate

- **After every task commit:** Run quick command (subset of new tests, <30s)
- **After every plan wave:** Run full backend suite (`pytest tests/`)
- **Before `/gsd:verify-work`:** Full suite green + `fly_smoke.sh` exits 0 + manual D-15/D-19/D-20 checklists complete with screenshots
- **Max feedback latency:** 30 seconds (quick subset)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-00-01 | 00 (W0) | 0 | conftest fixture scaffolding | unit | `pytest tests/conftest.py --collect-only` | ❌ W0 creates | ⬜ pending |
| 06-00-02 | 00 (W0) | 0 | SEC-04 placeholders | unit | `pytest tests/test_rate_limit.py --collect-only -q` | ❌ W0 creates | ⬜ pending |
| 06-00-03 | 00 (W0) | 0 | SEC-05 placeholders | unit | `pytest tests/test_chat_cap.py --collect-only -q` | ❌ W0 creates | ⬜ pending |
| 06-00-04 | 00 (W0) | 0 | SEC-05 config defaults | unit | `pytest tests/test_config.py --collect-only -q` | ❌ W0 creates | ⬜ pending |
| 06-01-01 | 01 | 1 | SEC-04 (limiter module) | unit | `pytest tests/test_rate_limit.py::test_limiter_module_importable -x` | ❌ W0 placeholder | ⬜ pending |
| 06-01-02 | 01 | 1 | SEC-04 (key_func) | unit | `pytest tests/test_rate_limit.py::test_user_id_key_func -x` | ❌ W0 placeholder | ⬜ pending |
| 06-01-03 | 01 | 1 | SEC-04 (route decorated + Request param) | unit | `pytest tests/test_rate_limit.py::test_chat_route_decorated -x` | ❌ W0 placeholder | ⬜ pending |
| 06-01-04 | 01 | 1 | SEC-04 (429 JSON shape) | unit | `pytest tests/test_rate_limit.py::test_429_response_shape -x` | ❌ W0 placeholder | ⬜ pending |
| 06-01-05 | 01 | 1 | SEC-04 (auth-fail bypass) | unit | `pytest tests/test_rate_limit.py::test_auth_fail_does_not_tick -x` | ❌ W0 placeholder | ⬜ pending |
| 06-02-01 | 02 | 1 | SEC-05 (cap default value) | unit | `pytest tests/test_config.py::test_chat_max_iterations_default -x` | ❌ W0 placeholder | ⬜ pending |
| 06-02-02 | 02 | 1 | SEC-05 (cap-hit graceful) | integration | `pytest tests/test_chat_cap.py::test_cap_hit_graceful_exit -x` | ❌ W0 placeholder | ⬜ pending |
| 06-02-03 | 02 | 1 | SEC-05 (logger.warning) | unit | `pytest tests/test_chat_cap.py::test_cap_hit_logs_warning -x` | ❌ W0 placeholder | ⬜ pending |
| 06-02-04 | 02 | 1 | SEC-05 (LangSmith tag) | integration | `pytest tests/test_chat_cap.py::test_cap_hit_langsmith_tag -x` | ❌ W0 placeholder | ⬜ pending |
| 06-02-05 | 02 | 1 | SEC-05 (voluntary stop preserved) | unit | `pytest tests/test_chat_cap.py::test_voluntary_stop_preserved -x` | ❌ W0 placeholder | ⬜ pending |
| 06-03-01 | 03 | 2 | SEC-04 e2e burst | smoke | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` | ✅ extends existing | ⬜ pending |
| 06-03-02 | 03 | 2 | CORS rejection-path | smoke | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` | ✅ extends existing | ⬜ pending |
| 06-04-01 | 04 | 2 | SEC-01 manual signup E2E | manual | PLAN.md D-15 checklist (timestamps + screenshots) | n/a | ⬜ pending |
| 06-04-02 | 04 | 2 | SEC-06 alert configured | manual | PLAN.md D-19 checklist (screenshot) | n/a | ⬜ pending |
| 06-04-03 | 04 | 2 | SEC-06 alert delivered | manual | PLAN.md D-20 checklist (timestamp + screenshot) | n/a | ⬜ pending |
| 06-04-04 | 04 | 2 | SEC-06 :free model deployed | smoke | `flyctl secrets list -a boardgame-rag-prod \| grep LLM_MODEL` (digest) + chat smoke | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs are illustrative — final IDs assigned by gsd-planner.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_rate_limit.py` — placeholders for SEC-04 cases (decorated route, key_func, 429 shape, auth-fail bypass, limiter module import)
- [ ] `backend/tests/test_chat_cap.py` — placeholders for SEC-05 cases (cap-hit graceful exit, logger, LangSmith tag, voluntary stop preserved)
- [ ] `backend/tests/test_config.py` — placeholders for SEC-05 default value (or extend if file exists)
- [ ] `backend/tests/conftest.py` — extend with shared fixtures: `mock_jwt`, `mock_user_id`, `mock_stream_chat_completion` (drives inner generator deterministically — critical for cap-hit test)

*Framework already installed (`pytest==8.4.2` in `backend/requirements.txt`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prod signup → email confirm → land on prod CF URL → logged in → chat works | SEC-01 | Email delivery + Supabase dashboard config are out-of-repo; can't reliably script | D-15 checklist: fresh throwaway email; document each step pass/fail with timestamp + browser network-tab screenshot |
| OpenRouter $0.01 alert configured with developer email | SEC-06 | Out-of-repo dashboard config | D-19 checklist: screenshot of dashboard alert page with threshold + email visible |
| OpenRouter alert email delivery confirmed | SEC-06 | Requires temporary balance + paid model + email inbox | D-20 checklist: load $1 → swap LLM_MODEL=<paid> → 1 chat → screenshot inbox + timestamp → revert → drain |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (4 test files)
- [ ] No watch-mode flags (CI-friendly)
- [ ] Feedback latency < 30s (quick subset)
- [ ] `nyquist_compliant: true` set in frontmatter (after Wave 0 complete)

**Approval:** pending
