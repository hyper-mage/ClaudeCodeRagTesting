---
phase: 15-options-ui-capstone-demo-gating
plan: 05
subsystem: ui
tags: [react, vitest, testing-library, openrouter, pkce, sessionstorage, key-gate, confirm-dialog]

# Dependency graph
requires:
  - phase: 15-options-ui-capstone-demo-gating (plan 15-01)
    provides: GET /api/keys/status returns demo_enabled (backend half of the smallest-seam flag exposure)
  - phase: 10-oauth-pkce-backend-exchange-frontend-connect
    provides: startOpenRouterConnect() PKCE helper + sessionStorage or_* semantics the stash rides beside
  - phase: 12-model-cache-catalog
    provides: server-computed is_free on ModelResponse rows (rendered verbatim, drives the gate branch)
  - phase: 14-usage-cost-display-settings-key-state-ux
    provides: useKeyStatus shared no-poll store, ConfirmDialog call sites, ErrorMessageBubble Reconnect
provides:
  - useKeyGate shared gate hook (D-04, locked name) — one decision table + one modal for BOTH selection surfaces
  - ConfirmDialog variant 'danger'|'primary' + light shell tokens (dark output byte-identical)
  - KeyStatus.demo_enabled?: boolean on the FE status type (undefined-while-loading -> treated false)
  - or_pending_selection stash WRITER (locked JSON contract consumed by 15-03's resume)
  - Stale-stash clears at the two non-gate connect launchers (Settings CTA, error-bubble Reconnect)
affects: [15-06 (banner reads demo_enabled), 15-07 (Use-demo wiring reads demo_enabled), 15-08 (phase verification)]

# Tech tracking
tech-stack:
  added: []
  patterns: [caller-side gate wrapping (guardedSelect replaces the raw onSelect; onApply holds the old body), vi.hoisted mutable key-status mock for gate-branch driving, single-writer sessionStorage stash with removeItem at non-writer launchers]

key-files:
  created:
    - frontend/src/hooks/useKeyGate.tsx
    - frontend/src/hooks/useKeyGate.test.tsx
  modified:
    - frontend/src/components/ConfirmDialog.tsx
    - frontend/src/hooks/useKeyStatus.ts
    - frontend/src/pages/ChatPage.tsx
    - frontend/src/components/DefaultModelSelector.tsx
    - frontend/src/components/DefaultModelSelector.test.tsx
    - frontend/src/pages/SettingsPage.tsx
    - frontend/src/components/ErrorMessageBubble.tsx

key-decisions:
  - "Gate branch (paid vs demo-OFF body) and display name (name ?? id) frozen at decision time in pending state — modal copy cannot shift if status refreshes while open"
  - "Unknown modelId (absent from the caller's catalog) treated as paid -> gated (unknown != free, mirrors the server guard's posture)"
  - "Callers pass models ?? [] — an unhydrated catalog degrades to gating keyless picks (conservative), never to recomputing is_free client-side"
  - "DefaultModelSelector's former handleSelect body moved verbatim into the gate's onApply — PUT/onChange structurally unreachable except via apply (Pitfall 7)"
  - "DefaultModelSelector.test mocks the useKeyStatus boundary (not AuthContext) — cuts the supabase-env import chain AND gives tests a switchable gate branch"

patterns-established:
  - "useKeyGate({ kind, threadId?, models, onApply }) -> { guardedSelect, gateModal }: wrap the apply path, render the modal, never touch the child selector's onSelect contract"
  - "sessionStorage single-writer rule: useKeyGate is the ONLY or_pending_selection writer; every non-gate startOpenRouterConnect() call site clears first (callback Retry preserves — 15-03-owned)"

requirements-completed: [KEY-05]

# Metrics
duration: 18min
completed: 2026-07-06
---

# Phase 15 Plan 05: Shared Key Gate (useKeyGate) Summary

**One `useKeyGate` hook now gates BOTH selection surfaces (thread header + settings default) with the locked KEY-05 decision table — keyless paid picks open a primary-variant ConfirmDialog whose [Connect] stashes `or_pending_selection` then launches PKCE; free rows fast-path under demo ON; 22 tests green across the three touched suites.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-06T18:12:38Z
- **Completed:** 2026-07-06T18:31:00Z
- **Tasks:** 3 (Task 2 as TDD RED → GREEN)
- **Files modified:** 9 (2 created, 7 modified)

## Accomplishments

- KEY-05 trigger path complete: keyless paid pick → `Connect OpenRouter?` modal (locked copy, `${model}` = name ?? id the ONLY interpolation) → [Connect] writes the locked stash JSON (`{kind, modelId, threadId?, returnTo}`) → `startOpenRouterConnect()` — 15-03's resume consumes it for the D-02 auto-apply
- Full locked decision table implemented and test-covered (10 hook tests): connected / status-null (A3 no flash-gate) / null clear row (Open Q1) apply immediately; keyless + demo ON free rows fast-path (D-03); paid or catalog-unknown ids gate with the paid body; demo OFF gates every pick with the demo-OFF body
- D-04 satisfied: identical gate on both surfaces via one hook — ChatPage wraps `handleThreadModelChange`, DefaultModelSelector wraps its onChange+PUT body; ChatContainer pass-through untouched
- Pitfall 7 closed and regression-tested: a keyless settings pick opens the modal BEFORE `onChange`/PUT — Cancel leaves the trigger on the prior model, zero PUT, zero stash
- Pitfall 6 / T-15-18 closed: `removeItem('or_pending_selection')` prepended at SettingsPage.handleConnect and the error-bubble [Reconnect]; the OAuthCallbackPage Retry untouched (preserves, 15-03-owned)
- ConfirmDialog `primary` variant (KeyRound 24 text-blue-600, bg-blue-600 confirm) + light shell tokens with `dark:` prefixes — dark output of the existing disconnect dialog byte-identical, default `'danger'` means zero call-site changes
- `KeyStatus.demo_enabled?: boolean` added — the FE half of the Pattern-5 smallest seam; store machinery (silent-on-error, dedup, broadcast) untouched

## Task Commits

Each task was committed atomically:

1. **Task 1: ConfirmDialog primary variant + light shell; KeyStatus.demo_enabled** - `6dd55c9` (feat)
2. **Task 2 RED: failing decision-table + stash tests** - `3e40f92` (test)
3. **Task 2 GREEN: useKeyGate implementation** - `adda3bf` (feat)
4. **Task 3: wire both surfaces + stale-stash clears** - `af51e1f` (feat)

## TDD Gate Compliance

RED gate: `3e40f92` — suite failed (exit 1, unresolvable `./useKeyGate` import; hook intentionally absent). GREEN gate: `adda3bf` — 10/10 pass. No refactor commit needed. Gate sequence verified in git log (test → feat).

## Files Created/Modified

- `frontend/src/hooks/useKeyGate.tsx` - shared gate hook: locked decision table, frozen-at-decision modal copy, stash-then-launch [Connect], side-effect-free [Cancel]
- `frontend/src/hooks/useKeyGate.test.tsx` - 10 tests: all 9 behavior rows + write-before-launch ordering asserted from inside the mocked `startOpenRouterConnect`
- `frontend/src/components/ConfirmDialog.tsx` - `variant?: 'danger' | 'primary'` (default danger), KeyRound/blue primary treatment, light shell tokens with dark: prefixes
- `frontend/src/hooks/useKeyStatus.ts` - `demo_enabled?: boolean` on the KeyStatus interface only; loadStatus/store byte-identical
- `frontend/src/pages/ChatPage.tsx` - gate instantiation (`kind:'thread'`, onApply = existing PATCH handler), `guardedSelect` passed to ChatContainer, `{gateModal}` rendered
- `frontend/src/components/DefaultModelSelector.tsx` - handleSelect body relocated into the gate's onApply; `guardedSelect` on ModelSelector; `{gateModal}` rendered
- `frontend/src/components/DefaultModelSelector.test.tsx` - useKeyStatus boundary mock (vi.hoisted, per-test switchable) + new Pitfall-7 gate test
- `frontend/src/pages/SettingsPage.tsx` - stale-stash clear in handleConnect
- `frontend/src/components/ErrorMessageBubble.tsx` - stale-stash clear in the [Reconnect] onClick (demoEligible/onUseDemo untouched — 15-07 owns them)

## Decisions Made

- Gate body + display name frozen in pending state at decision time (deterministic modal, no live-status drift while open)
- Catalog-unknown modelId gated as paid — mirrors the server free-guard's "unknown ≠ free" posture
- Test host exposes the hook via a ref assigned inside `useEffect` (react-hooks/refs forbids render-time ref mutation); `act()` flushes so the ref is always live before driving `guardedSelect`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree lacked frontend/node_modules — created a directory junction**
- **Found during:** Pre-task environment check
- **Issue:** parallel-executor worktree has no `frontend/node_modules` (gitignored); build/test tooling could not run
- **Fix:** Windows directory junction `frontend/node_modules` → main checkout's `frontend/node_modules` (environment only, gitignored, nothing committed)
- **Files modified:** none (environment only)
- **Verification:** build, lint, and vitest all run inside the worktree against worktree sources

**2. [Rule 3 - Blocking] DefaultModelSelector.test.tsx failed at import once the gate was wired**
- **Found during:** Task 3 (focused verify)
- **Issue:** the gate's import chain (useKeyGate → useKeyStatus → AuthContext → supabase client) throws at import in tests (missing VITE_SUPABASE_* env; file not in the plan's files_modified list)
- **Fix:** mocked the `useKeyStatus` boundary via `vi.hoisted` mutable state (default connected:true keeps the pre-existing tests' behavior); also added a Pitfall-7 gate test (Rule 2: keyless pick → modal, no onChange/PUT/stash, Cancel unchanged)
- **Files modified:** `frontend/src/components/DefaultModelSelector.test.tsx`
- **Commit:** `af51e1f`

**3. [Rule 1 - Bug] react-hooks lint errors in the new test host (immutability/refs)**
- **Found during:** Task 2 (GREEN verify)
- **Issue:** `api.current = gate` in the Host render body tripped `react-hooks/immutability` then `react-hooks/refs`
- **Fix:** renamed to `apiRef` and moved the assignment into a `useEffect`
- **Files modified:** `frontend/src/hooks/useKeyGate.test.tsx`
- **Commit:** `adda3bf`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug). **Impact on plan:** one file touched outside the frontmatter list (`DefaultModelSelector.test.tsx`) — required for the mandated focused-suite green; no scope creep otherwise.

## Deferred Issues

- **Full-repo `npm run lint` exits 1 with 5 pre-existing errors** — identical set already logged as **D-15-03-A** in `deferred-items.md` (FileUpload, AuthContext, ToastContext, ChatPage `loadThreads` false positive = D-13-06-A, themeBootstrap.test). All plan-touched files lint clean via focused `npx eslint` (exit 0). The only hit inside a plan file is the pre-existing ChatPage effect warning whose line number shifted by one added import — not introduced by this plan.

## Issues Encountered

None beyond the deferred pre-existing lint debt above.

## Known Stubs

None — the gate is fully wired end-to-end on both surfaces; `demo_enabled` is served live by the 15-01 backend. No placeholder copy, no hardcoded empty data flowing to UI.

## Requirements Note

`requirements-completed` lists KEY-05 per frontmatter. 15-03 (resume/consumer half) noted KEY-05 should be marked complete only once 15-05 lands — with this plan, both halves (gate + stash writer here; resume in 15-03) are done. REQUIREMENTS.md intentionally not modified here (worktree mode — orchestrator owns shared-file writes).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The full keyless connect loop is now closed: gate (15-05) → stash → PKCE → resume + auto-apply (15-03)
- 15-06/15-07 can read `status.demo_enabled` from the shared store with zero new fetches
- Wave-2 merge gate (full FE suite + build + lint) should run after the sibling 15-04 (ModelSelector upgrade) merges — this plan deliberately never touched ModelSelector.tsx or fuzzy.ts

## Self-Check: PASSED

- `frontend/src/hooks/useKeyGate.tsx` (contains 'Connect OpenRouter?' ×1, 'or_pending_selection' ×2) — FOUND
- `frontend/src/hooks/useKeyGate.test.tsx` — FOUND
- Commits `6dd55c9`, `3e40f92`, `adda3bf`, `af51e1f` — FOUND
- Targeted vitest exit 0 (22/22 across useKeyGate/ChatPage/DefaultModelSelector suites), `npm run build` exit 0, focused eslint on all plan files exit 0 — VERIFIED

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-06*
