---
status: partial
phase: 11-per-request-key-model-resolution-chat-loop-seam
source: [11-VERIFICATION.md]
started: 2026-06-22
updated: 2026-06-22
---

## Current Test

[awaiting human testing — 2 MANDATORY SEC-01 gates]

## Tests

### 1. SEC-01 (a) — prod-LangSmith zero-user-key-run

**Requirement:** SEC-01 · **Why manual:** needs a real OAuth-provisioned OpenRouter key + the live prod LangSmith project; no automated test can observe the prod trace sink.

**Steps:**
1. Connect a real OpenRouter account (BYOK) so a per-user key is stored.
2. Send a chat turn that runs on that user key.
3. Open the prod LangSmith project and confirm **zero runs** appear for that turn (the `wrap_openai` wrapper is gated off when `trace=False` / user key).

**Pass:** no run for the BYOK turn appears in prod LangSmith. **Highest-blast-radius gate (A5/D-10).**

### 2. SEC-01 (b) — live exc_info traceback redaction at the log sink

**Requirement:** SEC-01 · **Why manual:** the unit test covers the `_ScrubFilter` end-to-end through `routers.chat`, but a live confirm needs a real logged exception carrying an `sk-or-` token at the actual log sink.

**Steps:**
1. Force a logged exception whose locals/str carry an `sk-or-v1-…` token on the chat path (e.g. a transient failure during a BYOK turn).
2. Inspect the live log sink output for that `logger.error(..., exc_info=True)` line.

**Pass:** the traceback shows `[redacted-key]`, not the raw `sk-or-` token.

---

When both pass, re-run verification (or mark the phase `passed`) — the automated 4/4 must-haves are already green.
