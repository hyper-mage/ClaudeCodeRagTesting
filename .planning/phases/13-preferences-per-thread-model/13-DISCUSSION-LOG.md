# Phase 13: Preferences + Per-Thread Model - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 13-preferences-per-thread-model
**Areas discussed:** Theme scope, Model selector UX + placement, New-thread model inheritance, Deprecated-model fallback notice

---

## Theme scope (light mode)

| Option | Description | Selected |
|--------|-------------|----------|
| Core surfaces light palette | Wire theme mechanism + usable light palette on chat/sidebar/login/composer; defer polish on secondary UI | ✓ |
| Full app light theme | Refactor every hardcoded dark color across all components | |
| Persistence + mechanism only | Wire + persist toggle + flash-free paint, light visuals stay rough | |

**User's choice:** Core surfaces light palette (Recommended)
**Notes:** App is dark-only today (no `dark:` variants, hardcoded gray palette). SC#3 only mandates persistence + flash-free paint; full re-theming overlaps P14/P15. Chosen middle path delivers a toggle that looks right on the surfaces users actually use.

---

## Model selector UX + placement

| Option | Description | Selected |
|--------|-------------|----------|
| Thread header dropdown + temp default control | Compact dropdown in active thread header for per-thread model (reuse P12 catalog); default set via same minimal component in a temp spot until P14 | ✓ |
| Composer-area selector | Per-thread picker next to send button | |
| Menu/overlay only | Both selectors behind a small menu, nothing inline | |

**User's choice:** Thread header dropdown + temp default control (Recommended)
**Notes:** Minimal functional selector reusing Phase 12 `model_cache`; explicitly NOT the Phase 15 rich picker (no favorites/key-gating). Default-model control is temporary until the Phase 14 settings page absorbs it.

---

## New-thread model inheritance

| Option | Description | Selected |
|--------|-------------|----------|
| null → inherit live default at send | threads.model null on create; resolution falls to user_preferences.default_model; column written only on explicit per-thread pick | ✓ |
| Snapshot current default onto the row | Copy default_model into threads.model at create; thread pinned to default-at-creation | |

**User's choice:** null → inherit live default at send (Recommended)
**Notes:** Matches the existing tolerant resolution chain (`chat.py:174-175`). Thread tracks the user's current default; simpler and avoids stale snapshots.

---

## Deprecated-model fallback notice

| Option | Description | Selected |
|--------|-------------|----------|
| Inline thread notice message | Non-AI system/notice line in the thread; persists, visible on reload. Trigger: model absent from P12 model_cache at send | ✓ |
| Toast | Transient toast on send; disappears, not visible on reload | |
| Persistent banner on the thread | Sticky banner until user picks a new model | |

**User's choice:** Inline thread notice message (Recommended)
**Notes:** Persists in thread context and survives reload; ties the notice to the affected thread. Must not crash the thread (SC#4).

---

## Claude's Discretion

- Preferences API row shape (single upsert row per user)
- Migration split (combined vs `user_preferences` + `threads.model` separate)
- CSS-variable vs Tailwind `dark:`-class theming strategy
- Exact wording/styling of the deprecation notice line

## Deferred Ideas

- Rich model picker (favorites/pinning, key-gated selection, demo banner) — Phase 15
- Settings/account page (key status + default model + theme + profile) — Phase 14 (PREF-01)
- Usage/cost display (per-message cost, balance, low-balance warning, per-thread totals) — Phase 14 (COST-01..04)
