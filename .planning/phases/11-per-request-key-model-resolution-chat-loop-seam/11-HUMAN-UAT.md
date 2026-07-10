---
status: partial
phase: 11-per-request-key-model-resolution-chat-loop-seam
source: [11-VERIFICATION.md]
started: 2026-06-22
updated: 2026-07-10
---

## Current Test

[awaiting human testing — gap-closure code (11-05/11-06) landed and re-verified 14/14 automated; both MANDATORY gates require the prod redeploy first]

## Tests

### 1. [MANDATORY] SEC-01 (a) re-run — prod-LangSmith zero-run for a BYOK turn (incl. tool turn)

**Requirement:** SEC-01 · **Why manual:** needs a real OAuth-provisioned OpenRouter key + the live prod LangSmith project; no automated test can observe the prod trace sink.

expected: After prod redeploy (with 11-05/11-06 + migration 034), a BYOK user turn — including an explore_kb tool turn — produces ZERO LangSmith runs at every layer (no chat_send_message parent, no subagent runs, no wrap_openai spans).
result: [pending]
history: FAILED 2026-07-09 pre-fix ("i see my message sent in langsmith. I am connected to openrouter and picked a free model to say hi") — root cause was the ungated endpoint @traceable + global LANGCHAIN_TRACING_V2; closed by plan 11-05 (run-layer tracing_context gate, decorator removed, resolution hoisted). See Gaps below.

### 2. [MANDATORY] SEC-01 (b) — live exc_info traceback redaction at the log sink

**Requirement:** SEC-01 · **Why manual:** the unit test covers the `_ScrubFilter` end-to-end through `routers.chat`, but a live confirm needs a real logged exception carrying an `sk-or-` token at the actual log sink (Fly/backend stdout, NOT LangSmith).

expected: A deliberately forced key-bearing exception logs [redacted-key] in the live sink traceback, never the raw sk-or-v1-... token.
result: [pending]
history: BLOCKED 2026-07-09 — no exception was forced, filter never exercised live.

### 3. Live 402 vs 429 distinct SSE codes

**Requirement:** (non-blocking) · **Why manual:** requires tripping a live free-model rate cap or a real negative-balance owner key.

expected: Free-model demo turn past the per-minute cap yields code rate_limit; negative-balance owner key yields payment_required — distinct structured SSE codes.
result: [pending]

### 4. Prod SQL-flip smoke of the LangSmith master toggle

**Requirement:** SEC-01 (non-blocking) · **Why manual:** requires migration 034 applied to prod (ships with the redeploy) and the live prod DB.

expected: UPDATE app_settings SET value='false' stops LangSmith runs for ALL turns within ~15s (TTL); flipping back to 'true' resumes owner/demo tracing.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps

- truth: "A BYOK user-key chat turn produces zero runs in the owner's prod LangSmith project"
  status: resolved
  reason: "Code fix landed 2026-07-10: plan 11-05 removed the endpoint @traceable, hoisted key resolution above the traced region, and gated the whole turn under tracing_context(enabled=langsmith_on and not is_user_key); plan 11-06 added the runtime master toggle (migration 034 applied to dev, flip smoke passed). Regression test test_langsmith_run_gate.py (RED-first, commit d4a3fbd) drives a full user-key tool turn and asserts zero runs. Live prod confirmation pending Test 1 after redeploy."
  severity: blocker
  test: 1
  root_cause: "Phase 11 originally gated only the inner wrap_openai LLM-client spans (get_llm_client(trace=False)); the pre-existing outer @traceable(name='chat_send_message') on the endpoint (chat.py:734) plus global LANGCHAIN_TRACING_V2=true opened an ungated LangSmith run for every turn — including BYOK user-key turns. test_langsmith_gate.py only asserted the client wrap, so the leak passed CI. Same defect at explorer_service.py:208 and subagent_service.py:53."
  debug_session: ""

## Notes

Re-verification 2026-07-10: 14/14 automated must-haves green (11-VERIFICATION.md). Both MANDATORY gates (Tests 1-2) block v1.2 sign-off and need the prod redeploy first — the same deploy should carry the CR-01 one-line fix from 11-REVIEW.md (gate = False if (is_user_key or not langsmith_on) else None — force off, never force on).
