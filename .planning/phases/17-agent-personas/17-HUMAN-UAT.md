---
status: partial
phase: 17-agent-personas
source: [17-VERIFICATION.md]
started: 2026-07-14T09:05:00Z
updated: 2026-07-14T09:05:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. SC-1 visual — new chat shows the effective persona + expert voice
expected: Open a brand-new chat as a user with no pinned persona and no settings default. The header persona picker shows 'Board-Game Expert' (not 'Select a persona'), and the agent answers a board-game question in the expert voice.
result: [pending]

### 2. SC-2 tool call under General Assistant (full tool access)
expected: Pin General Assistant, then ask something that forces a tool call (e.g. 'search my documents for …'). A transparent tool-call card appears AND the answer reads more vanilla than the expert — confirming General Assistant retains FULL tool access.
result: [pending]

### 3. SC-3 visual — settings default shows on a new chat
expected: Set the settings/account default persona to General Assistant, then open a new chat. The new-chat header picker reads 'General Assistant' and the reply is more vanilla.
result: [pending]

### 4. SC-4 reload persistence
expected: Pin a non-default persona on a thread, hard-reload the app, reopen that thread. The picker still shows the pinned persona after reload (persists across sessions).
result: [pending]

### 5. SC-5 cross-user / cross-thread no-bleed
expected: Two concurrent users (or two threads) with different personas issue turns at the same time. Each turn is answered in its OWN persona voice; no leakage of one user's/thread's persona into the other.
result: [pending]

### 6. Gap 2 live — interrupt → Retry
expected: Interrupt a streaming response (or reload onto a persisted '[Response interrupted]' turn), then click Retry. A single Retry click re-sends the last user message with no copy/paste, the interrupted card disappears, and a fresh answer streams in.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
