---
status: partial
phase: 14-usage-cost-display-settings-key-state-ux
source: [14-VERIFICATION.md]
started: 2026-06-30T02:33:27Z
updated: 2026-06-30T02:33:27Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live OpenRouter balance fetch (COST-02 / SC#2)
expected: With a real OAuth-connected OpenRouter key, opening /settings shows a real balance line — "Balance: $X" for a capped account or "Pay-as-you-go — no limit set" for an uncapped one. Automated tests mock httpx.get, so the real proxy against GET /api/v1/key has not been exercised end-to-end.
result: [pending]

### 2. Amber low-balance indicator (COST-03, surface #1 + #2)
expected: Set LOW_BALANCE_THRESHOLD_USD above a test account's remaining credit, connect that key: both the IconSidebar rail dot and the MobileTopBar dot turn amber (aria-label "OpenRouter balance low"), and /settings shows the amber "Balance low: $X — add credits" warning line. A null-limit (pay-as-you-go) key shows green / no warning; disconnect shows gray. Confirm in light AND dark.
result: [pending]

### 3. Balance freshness after a chat turn (SC#2 "after a turn" trigger)
expected: After a chat turn consumes credit, the always-visible header dot reflects an updated balance. NOTE: balance is currently fetched on hook mount + on the disconnect broadcast only — there is no post-turn re-fetch wired. Confirm whether the as-shipped freshness (re-checks on settings open / navigation) is acceptable, or whether a post-turn refresh is desired (CONTEXT D-03 granted executor discretion).
result: [pending]

### 4. Mid-chat 401/402/403 typed recovery bubble (PREF-01 / SC#4 / D-09)
expected: A mid-stream 401 renders "Connect your OpenRouter account to keep chatting." + [Reconnect]; a 402 renders "Your key is out of credit (402)." + [Add credits ⇗] (opens openrouter.ai credits in a new tab) + [Reconnect]; a 403 renders "Your key was rejected (403)." + [Reconnect] alone (Use demo hidden). No error toast on these typed paths; a generic stream failure still shows toast + Retry.
result: [pending]

### 5. Cost surfaces + Σ total visual + reload persistence (COST-01 / COST-04)
expected: A paid assistant turn shows a muted "$0.00XX · N tok" caption under the bubble (assistant only, never user); a free turn shows "N tok" (no $, no ·); the thread header shows "Σ $X.XXXX" when > 0; reloading the thread reconstructs the same per-message captions and Σ total from persisted usage. Light + dark coherent.
result: [pending]

### 6. Settings page light/dark coherence + D-06 relocation (PREF-01 / D-06)
expected: /settings reads coherently in BOTH themes (no orphan dark panel in light mode) across all three sections (OpenRouter, Default model, Theme). The ChatPage sidebar/drawer no longer show the default-model/theme cluster and have NO empty footer box; the per-thread model selector still works in the chat header.
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
