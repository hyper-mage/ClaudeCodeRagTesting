---
phase: 15-options-ui-capstone-demo-gating
plan: 07
subsystem: ui
tags: [react, vitest, testing-library, sse, demo-mode, useChat, banner, tdd]

# Dependency graph
requires:
  - phase: 15-options-ui-capstone-demo-gating (plan 15-01)
    provides: demo_enabled on GET /api/keys/status (backend half of the smallest-seam flag exposure)
  - phase: 15-options-ui-capstone-demo-gating (plan 15-02)
    provides: POST message body {use_demo:true} honored server-side only when demo_fallback_enabled; mode:"demo" on demo done events
  - phase: 15-options-ui-capstone-demo-gating (plan 15-05)
    provides: KeyStatus.demo_enabled?: boolean FE interface + ChatPage gate plumbing (left byte-identical)
  - phase: 11-per-request-key-model-resolution-chat-loop-seam
    provides: mode:"demo" done-event emission (unread until this plan) + LOCKED banner copy (D-08)
  - phase: 14-usage-cost-display-settings-key-state-ux
    provides: typed ErrorMessageBubble with dead demoEligible/onUseDemo props + [Use demo] button on forbidden
provides:
  - useChat.lastTurnWasDemo — first FE read of the Phase-11 mode:"demo" SSE signal (latch, thread-scoped reset)
  - useChat.sendMessage useDemo option — use_demo:true key present ONLY on demo retries, ABSENT on normal sends
  - useChat.retryWithDemo — [Use demo] 403 recovery mirroring retryLastUserMessage with the demo override
  - ChatContainer demo banner (DEMO-02, D-10) — non-dismissible, locked copy, first shrink-0 child, both themes
  - Live demoEligible/onUseDemo wiring at the ErrorMessageBubble call site (D-11) — dead props gone
affects: [15-08 (phase verification + deploy flag flip reads this banner live)]

# Tech tracking
tech-stack:
  added: []
  patterns: [vi.hoisted mutable useKeyStatus module mock for banner-matrix driving (mirrors 15-05's gate-branch mock), conditional-spread body key so absent-means-absent (never use_demo:false)]

key-files:
  created: []
  modified:
    - frontend/src/hooks/useChat.ts
    - frontend/src/hooks/useChat.test.tsx
    - frontend/src/components/ChatContainer.tsx
    - frontend/src/components/ChatContainer.test.tsx
    - frontend/src/pages/ChatPage.tsx

key-decisions:
  - "lastTurnWasDemo resets in the genuine-thread-switch branch of the [threadId] effect (after the skipNextLoad early-return) — the auto-created-thread handoff preserves the in-flight turn's latch exactly like it preserves the optimistic bubble (Open Q2, 999.1 no-clobber discipline untouched)"
  - "New ChatContainer props are optional (lastTurnWasDemo = false, onUseDemo?) — 11 pre-existing test call sites and any future consumer stay compiling; ChatPage always passes both, so the live path is fully wired"
  - "use_demo is added via conditional spread ({...(opts?.useDemo ? { use_demo: true } : {})}) — the key is structurally ABSENT on normal sends, pinned by a regression test that JSON.parses the mock call body"

patterns-established:
  - "Demo-turn signal read: done-event branch checks parsed.mode === 'demo' alongside (not instead of) the existing message_id/usage update"
  - "Banner render condition (!status?.connected && Boolean(status?.demo_enabled)) || lastTurnWasDemo — null status makes both terms false, so loading can never flash the banner"

requirements-completed: [DEMO-02]
# DEMO-01's remaining half is the 15-08 deploy step (DEMO_FALLBACK_ENABLED=true in prod);
# this plan shipped its full FE surface ([Use demo] + picked-signal rendering).

# Metrics
duration: 23min
completed: 2026-07-06
---

# Phase 15 Plan 07: Demo Banner + [Use demo] Recovery Summary

Phase-11's mode:"demo" SSE signal is finally read: useChat latches it into lastTurnWasDemo, ChatContainer renders the locked non-dismissible amber banner off `(!connected && demo_enabled) || lastTurnWasDemo`, and the 403 bubble's [Use demo] retries the turn with use_demo:true.

## Tasks Completed

| Task | Name | Commits | Files |
| ---- | ---- | ------- | ----- |
| 1 | useChat — lastTurnWasDemo signal, useDemo send option, demo retry (TDD) | 7c1782d (RED), b66d365 (GREEN) | useChat.ts, useChat.test.tsx |
| 2 | ChatContainer demo banner + demoEligible/onUseDemo wiring through ChatPage | 9357286 | ChatContainer.tsx, ChatContainer.test.tsx, ChatPage.tsx |

## What Was Built

**useChat (Task 1, TDD):**
- `lastTurnWasDemo` boolean state; the done-event branch now reads `parsed.mode === 'demo'` and latches true. Resets to false in the genuine-thread-switch branch of the `[threadId]` effect (skipNextLoad handoff preserves it, matching the optimistic-bubble no-clobber semantics).
- `sendMessage(content, { useDemo?: true })` — body becomes `{content, use_demo: true}` on demo retries only; normal sends carry NO `use_demo` key (asserted by JSON.parsing the apiStream mock body).
- `retryWithDemo()` — mirrors `retryLastUserMessage` exactly (isStreaming guard, last-user lookup, error-bubble strip, explicit threadId) plus `useDemo: true`.
- 8 new tests (Demo 1-8): latch set/absent/reset, body shape with and without the override, retry mechanics, no-op guards (no prior user message; mid-stream).

**ChatContainer + ChatPage (Task 2):**
- Banner is the FIRST shrink-0 child of the root flex column, above the thread-header row, full-bleed, present with or without an active thread. Locked element verbatim: `role="status"`, amber wash/border classes, `Info` 14px, and the LOCKED Phase-11 sentence. No close button, no interactive children (asserted in tests). DemoPill (anon-session badge, a DIFFERENT "demo" concept) untouched.
- ChatContainer calls `useKeyStatus()` locally (shared no-poll store — zero extra fetches) for `connected` + `demo_enabled`.
- Dead props wired: `demoEligible={Boolean(status?.demo_enabled)}` + `onUseDemo={onUseDemo}` (grep `demoEligible={false}` → 0 matches). ErrorMessageBubble itself untouched.
- ChatPage destructures `lastTurnWasDemo` + `retryWithDemo` from useChat and passes them through; the 15-05 gate code is byte-identical.
- 7 new tests: 4-row banner render matrix (keyless+flag → present; connected → absent; connected+latch → present; null status → absent), locked copy verbatim, role/non-dismissibility/DOM-order assertions, [Use demo] visibility + click for both flag states.

## Verification

- `npx vitest run src/hooks/useChat.test.tsx` — 15/15 green (7 pre-existing + 8 new)
- `npx vitest run src/components/ChatContainer.test.tsx src/pages/ChatPage.test.tsx` — 25/25 green
- Combined re-run of both plan test files — 32/32 green
- `npm run build` (tsc -b + vite) — exit 0
- `npx eslint` on all five modified files — clean (full-repo `npm run lint` fails only on the 5 pre-existing D-15-03-A errors in untouched files)
- Full FE suite + live dev spot-check deferred to the wave-3 merge gate / 15-08 per plan

## TDD Gate Compliance

Task 1 (`tdd="true"`): RED commit `7c1782d` (7 of 8 new tests failing — Demo 4 passes by design as a regression pin of the existing no-`use_demo` body) precedes GREEN commit `b66d365` (15/15 green). No refactor commit needed — implementation landed clean.

## Deviations from Plan

### Auto-fixed / environment

**1. [Rule 3 - Blocking] Worktree lacked frontend/node_modules**
- **Found during:** Task 1 setup
- **Issue:** gitignored node_modules absent in the fresh worktree; vitest cannot run
- **Fix:** `cmd /c mklink /J` junction to the main checkout's node_modules (same approach as 15-05)
- **Files modified:** none (filesystem junction only, ignored by git)

**2. [Out of scope — logged, not fixed] Pre-existing full-repo lint failures (D-15-03-A)**
- **Found during:** Task 1 verify (`npm run lint`)
- **Issue:** 5 errors in FileUpload.tsx, AuthContext.tsx, ToastContext.tsx, ChatPage.tsx (`react-hooks/set-state-in-effect` false positive on the pre-existing `loadThreads` effect — its reported line shifted 50→60 because this plan added lines above it), themeBootstrap.test.ts — all documented in `deferred-items.md` (D-15-03-A) since plan 15-03
- **Action:** verified all five plan files lint clean in isolation; no unrelated churn

### Implementation choices (within plan scope)

- ChatContainer's two new props are optional (`lastTurnWasDemo = false`, `onUseDemo?`) rather than required — avoids touching 11 pre-existing test call sites; ChatPage (the only consumer) always passes both, so the locked key_link is live end-to-end.

Otherwise: plan executed as written.

## Known Stubs

None — the banner reads live server signals, [Use demo] fires a real retry with `use_demo:true`, and no placeholder/empty-value wiring was introduced. (The server honors the override only when `demo_fallback_enabled` is ON — that flag stays OFF until the 15-08 deploy step by design, which is gating, not a stub.)

## Threat Flags

None — no security surface beyond the plan's threat model. T-15-24 (use_demo elevation) mitigated upstream per 15-02; T-15-25 (copy) satisfied — only LOCKED strings, zero interpolation; T-15-26 (repudiation) closed by the latch; T-15-27 (layout DoS) asserted by the shrink-0/DOM-order test.

## Self-Check: PASSED

- frontend/src/hooks/useChat.ts — FOUND (lastTurnWasDemo + retryWithDemo in return object)
- frontend/src/components/ChatContainer.tsx — FOUND (role="status" + locked sentence + demoEligible wired)
- Commits 7c1782d, b66d365, 9357286 — FOUND on worktree-agent-af7ba77bafa49323b
