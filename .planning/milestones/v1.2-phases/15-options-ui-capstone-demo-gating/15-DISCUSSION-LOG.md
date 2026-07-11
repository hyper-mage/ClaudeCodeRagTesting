# Phase 15: Options UI Capstone + Demo Gating - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-02
**Phase:** 15-options-ui-capstone-demo-gating
**Areas discussed:** Key-gated selection flow, Picker upgrade (favorites+popular+search), Demo rollout & banner

---

## Key-gated selection flow (KEY-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm modal → OAuth | Dialog "Paid models need your OpenRouter key" + [Connect] launches startOpenRouterConnect(), [Cancel] keeps current model | ✓ |
| Instant OAuth redirect | Selection immediately launches PKCE — fewest clicks, jarring | |
| Lock paid rows | Paid rows disabled + lock icon until connected | |

**User's choice:** Confirm modal → OAuth (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-apply picked model | Stash pending selection in sessionStorage beside PKCE verifier; apply after exchange + toast | ✓ |
| No resume — re-pick manually | Callback lands as today; user re-picks | |
| Reopen picker, not applied | Restore picker state, user confirms again | |

**User's choice:** Auto-apply picked model (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Demo ON: free choice unlocked | Free models selectable keylessly via ?free_only=true; demo turns run picked free model; paid → modal; demo OFF → all gated | ✓ |
| Stay pinned to demo_fallback_model | Keyless users get zero model choice | |
| Free selectable even when demo OFF | Selection that can't run (fail-closed) — broken promise | |

**User's choice:** Demo ON: free choice unlocked (recommended)
**Notes:** Server-side free-model validation against model_cache mandatory; fallback to pinned slug on non-free/unknown.

| Option | Description | Selected |
|--------|-------------|----------|
| Both surfaces, shared gate | One gate hook wraps thread ModelSelector + settings DefaultModelSelector | ✓ |
| Thread selector only | Settings default stays pickable keylessly — inconsistent | |

**User's choice:** Both surfaces, shared gate (recommended)

---

## Picker upgrade (MODEL-08 + B-1 + W-1)

*(Answered via plain-text batch after AskUserQuestion timeouts: "all recommended except 4 (i pick b for that one)")*

| # | Question | Options | Selected |
|---|----------|---------|----------|
| 1 | Favorites storage | **user_preferences column (rec)** / new favorites table / localStorage | user_preferences column |
| 2 | Picker ordering | **Sections: Favorites → Popular → All alphabetical (rec)** / flat list with badges / favorites section + flat rest | Sections |
| 3 | Popular marking render | **Badge chip + Popular section (rec)** / ★ icon only / sort-boost only | Badge chip + section |
| 4 | Search behavior | client-side substring (rec) / **fuzzy match** / backend ?q= | **Fuzzy match (user override)** |

**Notes:** Q4 was the single deviation from recommendations — user explicitly picked fuzzy (typo tolerance) over substring. Implementation (hand-rolled scorer vs micro-dep) left to Claude's discretion, biased hand-rolled.

---

## Demo rollout & banner (DEMO-01/02 + SEC-03)

| # | Question | Options | Selected |
|---|----------|---------|----------|
| 5 | Flip demo_fallback_enabled in prod this phase? | **Yes — enable at deploy step (rec)** / ship dark / dev-only soak first | Yes — enable at deploy step |
| 6 | Banner placement | **Slim non-dismissible strip top of chat pane (rec)** / extend DemoPill / header-bar banner | Slim strip top of chat pane |
| 7 | [Use demo] on 403 bubble | **Yes when flag ON (rec)** — wire dead demoEligible/onUseDemo / no, [Reconnect] only | Yes when flag ON |

**Notes:** SEC-03 gate evidence accepted (999.2 finding PASS — $0.1026 403 block, kill switch green, no email). Banner copy locked from Phase 11 D-08.

---

## Claude's Discretion

- Fuzzy-match implementation (hand-rolled vs micro-dep)
- Modal/toast copy, section-header styling, badge color token, sessionStorage key names, gate hook naming
- How FE learns demo-flag state (smallest seam)
- Migration 033 shape (TEXT[] vs JSONB)
- Favorites empty-state treatment

## Deferred Ideas

- W-3 notice dedup + live visibility (separate fix)
- FU-A/FU-B/FU-D Phase-14 follow-ups (own track)
- Aux/utility-model override UI (no requirement)
- MODEL-F1 "New" badge, MODEL-F2 keyboard-heavy nav (post-v1.2)
- SEC-01 human gates + prod migration catch-up (audit track, alongside deploy)
