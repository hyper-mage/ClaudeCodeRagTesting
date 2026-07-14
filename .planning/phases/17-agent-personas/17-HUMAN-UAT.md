---
status: complete
phase: 17-agent-personas
source: [17-VERIFICATION.md]
started: 2026-07-14T09:05:00Z
updated: 2026-07-14T10:30:00Z
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
  status: failed
  reason: "User reported: concurrent two-chat setup is very laggy; running turns together breaks with an error+retry; after several attempts both ran tool calls but produced no output (timed out/errored). No wrong-persona-voice leak was observed — both turns simply failed to complete, so persona no-bleed is unconfirmed rather than falsified."
  severity: major
  test: 5
  artifacts: []
  missing: []

- truth: "After switching the chat model, clicking Retry on an interrupted/failed turn successfully re-sends and produces a fresh answer (Gap 2 scope: 'fails e.g. model switch mid-turn')."
  status: failed
  reason: "User reported: same-model Retry works, but Retry AFTER switching the model does not succeed. Core interrupt→Retry passed; the model-switch retry path is the gap."
  severity: major
  test: 6
  artifacts: []
  missing: []
