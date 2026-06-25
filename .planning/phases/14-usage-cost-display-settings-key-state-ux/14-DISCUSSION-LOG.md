# Phase 14: Usage/Cost Display + Settings/Key-State UX - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-25
**Phase:** 14-usage-cost-display-settings-key-state-ux
**Areas discussed:** Cost display placement, Low-balance warning, Settings page composition, Mid-chat key-failure recovery

---

## Cost display placement (COST-01, COST-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Always-visible line + header total | Per-msg muted cost line under each assistant bubble; per-thread total in thread header; total summed from persisted messages.usage (survives reload). | ✓ |
| Hover/expand only + header total | Per-msg cost hidden, shown on hover/expand; total still in header. | |
| Per-message only, total in settings | Per-msg line under bubbles; running total on settings page instead of header. | |

**User's choice:** Always-visible line + header total
**Notes:** Maximum transparency wins; total is source-of-truth summed from persisted usage, not session-only.

---

## Low-balance warning (COST-02, COST-03)

### Threshold + null-limit handling

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed $ remaining < threshold; skip null-limit | Warn under a hardcoded $ value; skip pay-as-you-go (null limit_remaining). | |
| Percent of limit < 10%; skip null-limit | Warn under ~10% of limit; skip null. | |
| Configurable threshold (env/setting) | Threshold in config, default ~$1.00; warn when remaining < threshold; null skipped. | ✓ |

**User's choice:** Configurable threshold (env/setting) — `LOW_BALANCE_THRESHOLD_USD` default 1.00
**Notes:** Null `limit_remaining` (uncapped pay-as-you-go) → no warning.

### Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Settings badge + header indicator color | Header key indicator goes amber + settings warning line near balance. Non-intrusive. | ✓ |
| Toast after a turn when low | Dismissible toast after each turn when low. | |
| Persistent banner above chat | Non-dismissible banner above thread. | |

**User's choice:** Settings badge + header indicator color
**Notes:** No toast spam, no blocking banner.

---

## Settings page composition (PREF-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Move both into Settings; remove temp spots | Default-model + theme relocate to Settings sections; remove P13 temp inline mounts. Per-thread selector stays in thread header. | ✓ |
| Move default model; keep theme toggle inline too | Default model → Settings; theme stays quick-access inline AND in Settings. | |
| Mirror all controls in both places | Both controls inline AND in Settings, synced. | |

**User's choice:** Move both into Settings; remove temp spots
**Notes:** Fulfills P13 D-04. Settings sections: OpenRouter (key state + masked label + balance + disconnect) · Default model · Theme. Per-thread model selector unaffected.

---

## Mid-chat key-failure recovery (PREF-01, SC#4)

| Option | Description | Selected |
|--------|-------------|----------|
| In-thread ErrorMessageBubble + action buttons | Typed copy + action buttons keyed to 401/402/403 (Reconnect / Add credits / Use demo). Persists in thread, reuses existing taxonomy + component. | ✓ |
| Toast + link to settings | Dismissible toast linking to settings. | |
| Blocking modal with actions | Modal interrupt with recovery actions. | |

**User's choice:** In-thread ErrorMessageBubble + action buttons
**Notes:** ErrorMessageBubble currently only has {onRetry, isStreaming} (ErrorMessageBubble.tsx:3-15) — must be extended for typed actions.

---

## Claude's Discretion

- Exact `LOW_BALANCE_THRESHOLD_USD` field name + default; `GET /api/keys/balance` response shape + hook surface; settings-section ordering/layout; precise copy; per-thread-total derivation location; amber color token; balance refresh debounce/cache.

## Deferred Ideas

- Rich model picker (favorites/pinning, key-gated selection, demo banner UI) — Phase 15.
- Enabling `demo_fallback_enabled` in prod — Phase 15, gated on SEC-03 / backlog 999.2.
- Richer profile editing (name/avatar) beyond key/model/theme/profile-status — deferred unless a later requirement asks.
