---
status: complete
phase: 17-agent-personas
source: [17-VERIFICATION.md]
started: 2026-07-14T09:05:00Z
updated: 2026-07-14T10:50:00Z
resolution: "5/6 pass. Both gaps diagnosed as ENVIRONMENT/pre-existing (not persona defects) and DEFERRED to backlog per user decision 2026-07-14: D-17-CONC-A (backend event-loop concurrency) + D-17-MODCAT-A (model catalog hardening). Phase 17 marked complete."
---

## Current Test

[testing complete]

## Tests

### 1. SC-1 visual — new chat shows the effective persona + expert voice
expected: Open a brand-new chat as a user with no pinned persona and no settings default. The header persona picker shows 'Board-Game Expert' (not 'Select a persona'), and the agent answers a board-game question in the expert voice.
result: pass

### 2. SC-2 tool call under General Assistant (full tool access)
expected: Pin General Assistant, then ask something that forces a tool call (e.g. 'search my documents for …'). A transparent tool-call card appears AND the answer reads more vanilla than the expert — confirming General Assistant retains FULL tool access.
result: pass

### 3. SC-3 visual — settings default shows on a new chat
expected: Set the settings/account default persona to General Assistant, then open a new chat. The new-chat header picker reads 'General Assistant' and the reply is more vanilla.
result: pass

### 4. SC-4 reload persistence
expected: Pin a non-default persona on a thread, hard-reload the app, reopen that thread. The picker still shows the pinned persona after reload (persists across sessions).
result: pass

### 5. SC-5 cross-user / cross-thread no-bleed
expected: Two concurrent users (or two threads) with different personas issue turns at the same time. Each turn is answered in its OWN persona voice; no leakage of one user's/thread's persona into the other.
result: issue
reported: "broken. Very laggy setting up two new chats. When run together they break — I get an error and retry. After several attempts both ran tool calls but still gave no output; assumed they timed out or errored out."
severity: major
note: "Symptom is a concurrency/streaming failure (errors + no output under parallel turns), NOT an observed persona bleed — no wrong-voice leakage was reported because neither turn produced output. Persona no-bleed remains unconfirmed (untestable while concurrent turns fail). Possible causes: free-tier OpenRouter model rate-limiting/timeout under concurrent streams, single-worker uvicorn/SSE contention, or a backend concurrency defect. To be pinned by diagnosis."

### 6. Gap 2 live — interrupt → Retry
expected: Interrupt a streaming response (or reload onto a persisted '[Response interrupted]' turn), then click Retry. A single Retry click re-sends the last user message with no copy/paste, the interrupted card disappears, and a fresh answer streams in.
result: pass
reported: "pass, but I did try switching the model as well and that did not pass. If I keep the same model it retries successfully."
note: "Core interrupt→Retry (same model) PASSES. Sub-case: Retry AFTER switching the chat model does NOT succeed. This is inside Gap 2's original scope (VERIFICATION Gap 2: 'fails e.g. model switch mid-turn'). Tracked as a separate gap for closure."

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0
blocked: 0
gaps: 2

## Gaps

- truth: "Two concurrent users/threads with different personas each get their own persona voice with no cross-bleed, and both turns complete."
  status: diagnosed
  reason: "User reported: concurrent two-chat setup is very laggy; running turns together breaks with an error+retry; after several attempts both ran tool calls but produced no output (timed out/errored). No wrong-persona-voice leak was observed — both turns simply failed to complete, so persona no-bleed is unconfirmed rather than falsified."
  severity: major
  test: 5
  classification: "ENVIRONMENT (primary) + PRE-EXISTING CODE defect (amplifier) — NOT a Phase-17 persona defect. Persona per-request isolation was confirmed correct (fresh OpenAI() per call, local persona_voice, no shared buffer)."
  root_cause: "Free-tier ':free' OpenRouter chat model caps ~1 concurrent request/key, so the 2nd simultaneous stream is 429/5xx (primary visible error). Amplified by a pre-existing backend defect: the chat hot path iterates a BLOCKING synchronous OpenAI client directly on the asyncio event loop (no asyncio.to_thread) under a single uvicorn worker — turn A blocks the loop while waiting on the slow free model's first token, starving turn B into lag + APITimeoutError -> [Response interrupted]. Already tracked (CONCERNS.md single-process limit; STATE.md deferred D-999.1-LLM-A). The subagent paths (chat.py:1216/1291) already offload correctly; the main token stream (chat.py:1134) never did."
  artifacts:
    - path: "backend/services/llm_service.py"
      issue: "sync `from openai import OpenAI` + blocking sync generator `stream_chat_completion` (no AsyncOpenAI, no await)"
    - path: "backend/routers/chat.py:1134"
      issue: "main token stream iterated on the event loop with no asyncio.to_thread offload (unlike subagent branches 1216/1291)"
    - path: "Dockerfile"
      issue: "single uvicorn worker (no --workers) — one event loop, no parallelism to mask blocking"
    - path: ".env (LLM_MODEL)"
      issue: "free-tier ':free' OpenRouter chat model with ~1 concurrent-request cap"
  missing:
    - "ENV: point LLM_MODEL at a paid/credited, tool-capable OpenRouter (or OpenAI) model with real concurrency for the concurrency test"
    - "CODE (pre-existing, cross-cutting — arguably its own backend-concurrency task, NOT persona scope): offload the chat hot path off the event loop (asyncio.to_thread + queue.Queue mirroring the subagent paths, OR switch to AsyncOpenAI + async for) and/or run uvicorn with multiple workers"
  debug_session: .planning/debug/concurrent-turns-no-output.md

- truth: "After switching the chat model, clicking Retry on an interrupted/failed turn successfully re-sends and produces a fresh answer (Gap 2 scope: 'fails e.g. model switch mid-turn')."
  status: diagnosed
  reason: "User reported: same-model Retry works, but Retry AFTER switching the model does not succeed. Core interrupt→Retry passed; the model-switch retry path is the gap."
  severity: major
  test: 6
  classification: "ENVIRONMENT (model availability) — NOT a CODE defect. The retry mechanism satisfies Gap 2 ('re-send under the new model')."
  root_cause: "The interrupt→Retry path is model-agnostic and correct: the FE send body carries no model (useChat.ts:170); the server resolves body.model(none) -> freshly-reloaded thread_row.model -> user_default -> settings (chat.py:301-306), and retry differs from a normal send only by deleting the last assistant row + skipping the user-insert (chat.py:895-923). Model switch DOES persist to the thread via PATCH before retry, so retry uses exactly the new model. The agent loop ALWAYS sends tools (chat.py:1136), so a switched-to model with no tool endpoint / unfunded / keyless returns 400/402/404/500 -> model_unavailable. Same-model retry works because that model is proven tool-capable + funded; an arbitrary switched-to model may not be. Race ruled out (a non-persisted switch would make retry SUCCEED on the old model)."
  artifacts: []
  missing:
    - "ENV: re-test model-switch retry using a known tool-capable, funded model (e.g. openai/gpt-4o-mini, anthropic/claude-sonnet-4.5) — expected to close the gap with no code change"
    - "OPTIONAL product hardening (not required): filter the ModelSelector catalog to tool-capable models, and/or confirm the existing `model_unavailable` bubble ('Pick a different model') renders on the retried turn"
  debug_session: .planning/debug/retry-model-switch-fails.md
