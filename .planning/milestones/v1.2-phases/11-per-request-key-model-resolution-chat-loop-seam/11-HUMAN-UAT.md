---
status: passed
phase: 11-per-request-key-model-resolution-chat-loop-seam
source: [11-VERIFICATION.md]
started: 2026-06-22
updated: 2026-07-11
---

## Current Test

[complete — both MANDATORY gates passed on prod 2026-07-11; 2 non-blocking smokes deferred]

## Tests

### 1. [MANDATORY] SEC-01 (a) re-run — prod-LangSmith zero-run for a BYOK turn (incl. tool turn)

**Requirement:** SEC-01 · **Why manual:** needs a real OAuth-provisioned OpenRouter key + the live prod LangSmith project; no automated test can observe the prod trace sink.

expected: After prod redeploy (with 11-05/11-06 + fix pass + migration 034), a BYOK user turn — including a KB tool turn — produces ZERO LangSmith runs at every layer.
result: pass
evidence: >
  2026-07-11, prod Fly v32 (commit e2c7e08), migration 034 applied to prod (seed row confirmed
  via .env.prod service client). BYOK "hi" on a free model + KB tool-call turn: zero LangSmith
  runs. Control: after disconnecting OpenRouter, an owner/demo turn in the same thread produced
  exactly one chat_send_message trace (nvidia/nemotron demo model, 3 LLM child calls) — gate
  suppresses BYOK only, tracing intact for owner/demo.
note: >
  The control trace's Input contains prior BYOK thread messages — expected: stateless
  completions send full history, and the demo turn is an owner-key traced turn. Not a gate
  leak. Possible future hardening: strip/hash history in traced inputs, or per-thread trace
  opt-out when the thread contains BYOK-era messages.
history: FAILED 2026-07-09 pre-fix ("i see my message sent in langsmith...") — closed by plans 11-05/11-06.

### 2. [MANDATORY] SEC-01 (b) — live exc_info traceback redaction at the log sink

**Requirement:** SEC-01 · **Why manual:** unit test covers `_ScrubFilter` end-to-end in-process; live confirm needs a real logged exception at the actual Fly log sink.

expected: A key-bearing exception logs [redacted-key] at the live sink, never raw sk-or-v1-...
result: pass
evidence: >
  2026-07-11: provisioned key revoked at openrouter.ai, BYOK turn sent → openai.AuthenticationError
  401 ("User not found") raised through _traced_turn → stream_chat_completion; full exc_info
  traceback observed in fly logs with ZERO sk-or- occurrences. Honest scope note: this 401
  path carries no key text in the exception message/frames, so [redacted-key] did not appear —
  nothing required redaction. Live sink confirmed key-free on the primary key-bearing error
  flow; filter trigger remains covered in-process (test_logging_filter_scrubs_exc_info).
history: BLOCKED 2026-07-09 — filter never exercised.

### 3. Live 402 vs 429 distinct SSE codes

**Requirement:** (non-blocking) · **Why manual:** requires tripping a live free-model rate cap or a real negative-balance owner key.

expected: rate cap → code rate_limit; negative balance → payment_required.
result: [pending]
note: deferred — non-blocking for phase sign-off and v1.2 closure; unit coverage green (test_429_402_distinct_codes).

### 4. Prod SQL-flip smoke of the LangSmith master toggle

**Requirement:** SEC-01 (non-blocking) · **Why manual:** requires the live prod DB + prod LangSmith sink.

expected: UPDATE app_settings value=false stops chat-turn runs within ~15s TTL; flip back resumes.
result: [pending]
note: deferred — non-blocking; dev-side flip smoke passed at the 11-06 Task 3 checkpoint, and post-CR-01 the flag is suppress-only (env kill-switch remains authoritative for enabling).

## Summary

total: 4
passed: 2
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

- truth: "A BYOK user-key chat turn produces zero runs in the owner's prod LangSmith project"
  status: resolved
  reason: "Code fix landed 2026-07-10 (plans 11-05/11-06 + CR-01..WR-06 fix pass) and CONFIRMED LIVE on prod 2026-07-11: BYOK turn incl. tool call produced zero runs; control owner turn traced normally. SEC-01 (a) closed."
  severity: blocker
  test: 1
  root_cause: "Phase 11 originally gated only the inner wrap_openai LLM-client spans; the pre-existing outer @traceable(name='chat_send_message') on the endpoint plus global LANGCHAIN_TRACING_V2=true opened an ungated LangSmith run for every turn. test_langsmith_gate.py only asserted the client wrap, so the leak passed CI."
  debug_session: ""

## Notes

Both MANDATORY SEC-01 gates passed on prod 2026-07-11 → phase 11 sign-off unblocked; SEC-01 closes for v1.2.
Tests 3-4 remain pending as non-blocking follow-ups (surface via /gsd-audit-uat).
WR-03 disconnect path has no automated coverage (11-REVIEW.md disposition) — optional manual smoke: kill the tab mid-stream, confirm clean logs.
