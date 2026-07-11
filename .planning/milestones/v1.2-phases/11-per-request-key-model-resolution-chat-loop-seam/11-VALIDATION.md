---
phase: 11
slug: per-request-key-model-resolution-chat-loop-seam
status: planned
nyquist_compliant: true
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

- **After every task commit:** Run the task's `<verify>` command (sub-second; mocked LLM + DB)
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green + manual prod-LangSmith validation
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Populated by gsd-planner from PLAN.md tasks. One row per task mapping to a requirement + automated command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | SEC-01, DEMO-03 | T-11-01 / T-11-02 | scrub_secrets redacts sk-or-; demo_fallback_enabled default OFF | unit | `cd backend && venv/Scripts/python -m pytest tests/test_config.py -x -q -k "demo_fallback or scrub"` | ✅ (created here) | ⬜ pending |
| 11-01-02 | 01 | 1 | SEC-04, SEC-01, DEMO-03 | T-11-01 | Wave 0 stubs collected (incl. test_logging_filter_scrubs_exc_info); conftest usage event | unit | `cd backend && venv/Scripts/python -m pytest tests/test_key_model_resolution.py tests/test_langsmith_gate.py tests/test_error_surfacing.py tests/test_usage_capture.py -q` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | DEMO-03 | T-11-04 | additive nullable usage column, RLS untouched | source | `test -f supabase/migrations/20240301000029_add_usage_to_messages.sql && grep -qE "ADD COLUMN IF NOT EXISTS usage" supabase/migrations/20240301000029_add_usage_to_messages.sql` | ✅ (created here) | ⬜ pending |
| 11-02-02 | 02 | 1 | DEMO-03 | T-11-06 | migration applied to DEV only (prod deferred); resume requires literal `usage \| jsonb \| YES` probe row (not a bare "applied") | manual | MISSING — live dev push; information_schema probe (`usage \| jsonb \| YES`) IS the resume condition | n/a (live DB) | ⬜ pending |
| 11-03-01 | 03 | 2 | SEC-04, SEC-01 | T-11-08 | wrap_openai gated off for user keys; usage drained | unit | `cd backend && venv/Scripts/python -m pytest tests/test_langsmith_gate.py::test_user_key_client_not_wrapped tests/test_usage_capture.py::test_usage_summed_across_tool_loop -x -q` | ❌ W0 | ⬜ pending |
| 11-03-02 | 03 | 2 | SEC-04 | T-11-09 | all 4 aux call sites use resolved key/model (D-02 aux rides shared `model`; value source P13/P15) | unit | `cd backend && venv/Scripts/python -m pytest tests/test_key_model_resolution.py::test_user_key_threaded_to_all_call_sites -x -q` | ❌ W0 | ⬜ pending |
| 11-04-01 | 04 | 3 | SEC-04, DEMO-03 | T-11-10 / T-11-11 | fail-closed three-branch; no cross-user bleed; budget fifth read fixed | unit | `cd backend && venv/Scripts/python -m pytest tests/test_key_model_resolution.py -x -q` | ❌ W0 | ⬜ pending |
| 11-04-02 | 04 | 3 | SEC-01 | T-11-12 / T-11-12b | str(e) scrubbed; logging.Filter scrubs exc_info traceback (never-in-logs closure); 429/402 distinct codes | unit | `cd backend && venv/Scripts/python -m pytest tests/test_error_surfacing.py -x -q` | ❌ W0 | ⬜ pending |
| 11-04-03 | 04 | 3 | DEMO-03 | T-11-15 | usage summed + persisted to messages.usage; mode signal | unit | `cd backend && venv/Scripts/python -m pytest tests/test_usage_capture.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

> RESEARCH.md specifies new/extended test files. Planner finalizes the exact list.
> All created in plan 11-01 Task 2 as collected, skipped-until-implemented stubs; the
> named functions match the RESEARCH Test Map verbatim (plus test_logging_filter_scrubs_exc_info
> from the revision per RESEARCH Open Q2) so downstream `<verify>` commands resolve.

- [ ] `backend/tests/test_key_model_resolution.py` — SEC-04 + DEMO-03 + D-03 (6 functions: test_no_key_flag_off_refuses, test_demo_fallback_uses_free_model, test_user_key_threaded_to_all_call_sites, test_no_cross_user_bleed, test_fail_closed_no_or_fallback, test_model_fallthrough_absent_p13_schema)
- [ ] `backend/tests/test_langsmith_gate.py` — SEC-01 (test_user_key_client_not_wrapped)
- [ ] `backend/tests/test_error_surfacing.py` — SEC-01 + D-12 (test_sk_or_scrubbed_in_sse_error, test_429_402_distinct_codes, test_logging_filter_scrubs_exc_info — the exc_info/logging.Filter coverage that closes SEC-01 "never in logs"; un-skipped + implemented by plan 11-04 Task 2)
- [ ] `backend/tests/test_usage_capture.py` — D-04 (test_usage_summed_across_tool_loop, test_usage_persisted_to_messages)
- [ ] `backend/tests/conftest.py` — extend `mock_stream_chat_completion` to emit an optional trailing `{"type":"usage","usage":{…}}` event
- [ ] `backend/tests/test_config.py` — extend with demo_fallback_enabled/demo_fallback_model default + env-override pairs (+ scrub tests)

---

## Manual-Only Verifications

> **The two SEC-01 rows below marked [MANDATORY GATE] are BLOCKING phase sign-off** — no automated test substitutes for them; they are the load-bearing evidence for SEC-01 "keys never appear in traces/logs" and MUST be confirmed before Phase 11 is marked verified (checker re-check Warning 2).

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| **[MANDATORY GATE]** `wrap_openai` gate verified against prod LangSmith project (zero user-key runs post-gate) | SEC-01 | Requires live prod LangSmith project + a real OAuth-provisioned key | Send a BYOK chat turn; confirm no run appears in prod LangSmith for that turn (highest-blast-radius — A5/D-10). BLOCKS sign-off. |
| OpenRouter 402 (payment) vs 429 (rate-limit) surface distinctly | DEMO-03 / SEC-01 | Requires tripping a live free-model rate cap / negative-balance owner key | Drive a free-model demo turn past the per-minute cap; confirm distinct structured SSE error codes (rate_limit vs payment_required) |
| **[MANDATORY GATE]** `sk-or-` key scrubbed out of a logged exc_info traceback at the live log sink | SEC-01 | The unit test covers the filter end-to-end through `routers.chat`; a live confirm needs a real logged exception carrying a key | Force a logged exception whose locals/str carry an `sk-or-` token; confirm the log sink line shows `[redacted-key]` in the traceback, not the raw token. BLOCKS sign-off. |
| Migration 029 applied to DEV `messages.usage` column | DEMO-03 | Live dev Supabase push (non-TTY) | `information_schema.columns` probe returns `usage \| jsonb \| YES` (this literal row is the checkpoint resume condition); messages RLS intact; prod untouched |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (11-02-02 is a documented live-DB MISSING with an information_schema probe as the resume condition; manual prod-LangSmith + 402/429 + live exc_info scrub are listed manual-only)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (4 new test files + conftest + test_config, created in 11-01; incl. test_logging_filter_scrubs_exc_info)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planned
