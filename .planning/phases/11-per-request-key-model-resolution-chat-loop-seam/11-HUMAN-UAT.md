---
status: partial
phase: 11-per-request-key-model-resolution-chat-loop-seam
source: [11-VERIFICATION.md]
started: 2026-06-22
updated: 2026-07-09
---

## Current Test

[testing paused — 1 blocker gap (SEC-01 leak), 1 blocked gate (SEC-01 b not exercised)]

## Tests

### 1. SEC-01 (a) — prod-LangSmith zero-user-key-run

**Requirement:** SEC-01 · **Why manual:** needs a real OAuth-provisioned OpenRouter key + the live prod LangSmith project; no automated test can observe the prod trace sink.

expected: A BYOK user turn produces ZERO runs in prod LangSmith (the wrap_openai wrapper is gated off when the request runs on a user key).
result: issue
reported: "i see my message sent in langsmith. I am connected to openrouter and picked a free model to say hi"
severity: blocker
root_cause: >
  Phase 11 gated only the INNER wrap_openai LLM-client spans (get_llm_client(trace=False)),
  which is all test_langsmith_gate.py asserts — so the unit test passed. But the request
  handler carries a PRE-EXISTING outer decorator @traceable(name="chat_send_message")
  (backend/routers/chat.py:734, present since Module 1, 2026-03-19) plus a global
  LANGCHAIN_TRACING_V2=true from setup_tracing(). That decorator opens a LangSmith run for
  EVERY chat turn, ungated by is_user_key, so a BYOK turn's prompt/response still lands in
  the owner's prod LangSmith project. Two more @traceable sites leak the same way for tool
  turns: explorer_service.py:208 (subagent_explorer) and subagent_service.py:53
  (subagent_document_analysis). The gate was applied at the wrong layer and never closed.

### 2. SEC-01 (b) — live exc_info traceback redaction at the log sink

**Requirement:** SEC-01 · **Why manual:** the unit test covers the `_ScrubFilter` end-to-end through `routers.chat`, but a live confirm needs a real logged exception carrying an `sk-or-` token at the actual log sink.

expected: The logged traceback shows [redacted-key], not the raw sk-or- token.
result: blocked
blocked_by: other
reason: "User ran a normal successful turn (no exception logged) and inspected LangSmith rather than the backend log sink, so no sk- token was ever produced to redact — the filter was not exercised. In-process coverage (test_error_surfacing / _ScrubFilter through routers.chat) is green; a live confirm requires a deliberately forced key-bearing exception, checked in the Fly/backend stdout log (not LangSmith)."

## Summary

total: 2
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 1

## Gaps

- truth: "A BYOK user-key chat turn produces zero runs in the owner's prod LangSmith project"
  status: failed
  reason: "User reported: 'i see my message sent in langsmith. I am connected to openrouter and picked a free model to say hi'"
  severity: blocker
  test: 1
  root_cause: "Phase 11 gated only the inner wrap_openai LLM-client spans (get_llm_client(trace=False)); the pre-existing outer @traceable(name='chat_send_message') on the endpoint (chat.py:734) plus global LANGCHAIN_TRACING_V2=true opens an ungated LangSmith run for every turn — including BYOK user-key turns. test_langsmith_gate.py only asserts the client wrap, so the leak passed CI. Same defect at explorer_service.py:208 and subagent_service.py:53."
  artifacts:
    - path: "backend/routers/chat.py"
      issue: "@traceable(name='chat_send_message') at line 734 emits a LangSmith run for every turn, ungated by is_user_key"
    - path: "backend/services/explorer_service.py"
      issue: "@traceable(name='subagent_explorer') at line 208 leaks explore_kb tool turns for user keys"
    - path: "backend/services/subagent_service.py"
      issue: "@traceable(name='subagent_document_analysis') at line 53 leaks analyze_document tool turns for user keys"
    - path: "backend/services/tracing.py"
      issue: "setup_tracing() forces LANGCHAIN_TRACING_V2=true globally with no per-request gate"
    - path: "backend/tests/test_langsmith_gate.py"
      issue: "Only asserts the client-level wrap_openai gate; no coverage of the outer @traceable run for user keys — structurally cannot catch this leak"
  missing:
    - "Gate ALL @traceable runs on is_user_key so BYOK turns emit no LangSmith run (parent + subagent)"
    - "Resolve is_user_key BEFORE any @traceable run opens (currently resolved inside event_generator at chat.py:861, after the endpoint decorator has already opened the run)"
    - "Preferred approach: drop @traceable from the endpoint boundary; resolve key/is_user_key early; wrap the turn's work in langsmith.tracing_context(enabled=not is_user_key) around a @traceable inner worker — the contextvar suppresses the parent AND the subagent_explorer/subagent_document_analysis child runs in one place"
    - "Add a regression test that exercises a full user-key turn (incl. a tool call) and asserts zero LangSmith runs are created — not just that the client is unwrapped"
  debug_session: ""

## Notes

When Test 2 resolves, re-run verification (or mark the phase's automated 4/4 must-haves already green).
The Test 1 blocker re-opens SEC-01 and is the sole remaining v1.2 milestone gate.
