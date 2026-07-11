---
phase: 15-options-ui-capstone-demo-gating
plan: 10
subsystem: ui
tags: [react, vitest, model-selector, combobox, render-gating, byok]

# Dependency graph
requires:
  - phase: 15-options-ui-capstone-demo-gating
    provides: "ModelSelector sectioned+searchable picker (15-04), SettingsPage default-model + catalog wiring (15-05/13-xx), late-prop timing gap surfaced by 15-VERIFICATION CR-02"
provides:
  - "effectiveState render-gating so a post-mount `models` prop unlocks the ModelSelector panel on the Settings surface"
  - "Late-arrival regression test proving the sectioned panel renders from a catalog prop supplied after mount, with no lazy /api/models fetch"
affects: [settings-surface model picking, MODEL-01 search, MODEL-08 starring, KEY-05 gating, phase-15 verification re-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Render-gate off a DERIVED effective state (suppliedModels ? 'loaded' : state) instead of the once-seeded useState — decouples panel render from mount-time prop timing"

key-files:
  created: []
  modified:
    - frontend/src/components/ModelSelector.tsx
    - frontend/src/components/ModelSelector.test.tsx

key-decisions:
  - "Derived `effectiveState: LoadState = suppliedModels ? 'loaded' : state` rather than adding a setState-in-effect to sync a late prop — avoids an extra render pass and keeps the lazy-fetch state machine (idle→loading→loaded/error) as the single source of truth when no catalog is supplied"
  - "Retargeted ONLY the four panel render gates to effectiveState; openMenu/loadModels/setState left untouched so the empty-[]-prop lazy-fetch regression and chat prop-at-mount path stay byte-behaviorally identical"

patterns-established:
  - "Effective-state render gating: when a component both lazy-fetches AND accepts a possibly-late prop for the same data, gate render off `suppliedProp ? 'ready' : internalState` so late props flip the view without mutating the fetch state machine"

requirements-completed: [KEY-05, MODEL-08, MODEL-01, MODEL-03]

# Metrics
duration: 12min
completed: 2026-07-08
---

# Phase 15 Plan 10: Close CR-02 — ModelSelector late-catalog render gating Summary

**ModelSelector now render-gates off a derived `effectiveState` so a `models` prop that arrives after mount (the Settings surface's post-mount `/api/models` fetch) immediately unlocks the sectioned panel — closing CR-02 without a lazy fetch or any change to the lazy-fetch/chat paths.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-08
- **Tasks:** 1 (TDD: RED → GREEN, no refactor needed)
- **Files modified:** 2

## Accomplishments
- Root-caused CR-02: `ModelSelector` seeds `state` once at mount via `useState`; on the Settings surface (`models=undefined` at mount, `setModels` after the post-mount `/api/models` fetch) `state` stays stuck at `'idle'`, so none of the four `state ===` render gates fire and the open panel shows only the search input.
- Fix: derived `const effectiveState: LoadState = suppliedModels ? 'loaded' : state` next to the existing `rows` derivation, and retargeted the four panel render gates (`loading` / `error` / `loaded-empty` / `loaded-list`) from `state` to `effectiveState`. A late non-empty catalog prop now flips the panel to `'loaded'` immediately.
- Added a late-arrival regression test that renders with `models` undefined, drains mount microtasks, rerenders with a non-empty catalog, opens, and asserts the sectioned panel (Favorites → Popular → All models, one seeded favorite) renders with `SECTIONED_COUNT + 1` option rows and that `/api/models` was NOT lazily fetched.
- Re-enabled the settings-surface requirements gated behind the broken panel: search (MODEL-01), starring (MODEL-08), and keyless gating (KEY-05); Popular chip (MODEL-03) renders inside the now-visible rows.

## Task Commits

Each task was committed atomically (TDD):

1. **Task 1 (RED): late-arrival failing test** - `2222950` (test)
2. **Task 1 (GREEN): effectiveState render gating** - `8da66f6` (feat)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

## Files Created/Modified
- `frontend/src/components/ModelSelector.tsx` - Added `effectiveState` derivation; retargeted the four panel render gates (~421/425/435/443) from `state` to `effectiveState`. No change to `openMenu`, `loadModels`, `setState`, section-build, favorites, search, or a11y wiring.
- `frontend/src/components/ModelSelector.test.tsx` - Added the late-arrival render test (render `models=undefined` → rerender with catalog → open → sectioned panel, no `/api/models` fetch).

## Decisions Made
- Chose a derived `effectiveState` over a `useEffect` that syncs a late prop into `setState`: no extra render pass, and the lazy-fetch state machine remains the single writer of `state`. When `suppliedModels` is undefined (no catalog or empty `[]`), `effectiveState === state`, so the lazy path and the empty-`[]` regression are provably untouched.
- Retargeted exactly the four render gates and nothing else (per plan constraint) — the `loading`/`error` gates only ever matter on the lazy path where `effectiveState === state`, so their behavior is unchanged.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. RED failed cleanly at `findByRole('listbox')` (panel stuck on the `'idle'` seed), then went green with the two-line derivation + four gate retargets. Full ModelSelector suite: 30/30 passing. `npm run build` (tsc + vite) passes — no type error from the `effectiveState: LoadState` derivation (the pre-existing >500 kB chunk-size advisory is unrelated).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CR-02 closed: the 15-04 #2 sections truth and the 15-05 #1 "both surfaces" truth now hold on the Settings surface under real fetch timing.
- Ready for a phase-15 verification re-run against gaps[1] + gaps[2].
- No new threat surface: the change flips a display gate on already-fetched, already-trusted catalog data — no new fetch, no cross-user state (T-15-35 accept, register unchanged).

## Self-Check: PASSED

- FOUND: `.planning/phases/15-options-ui-capstone-demo-gating/15-10-SUMMARY.md`
- FOUND: `frontend/src/components/ModelSelector.tsx`
- FOUND: `frontend/src/components/ModelSelector.test.tsx`
- FOUND commit: `2222950` (test — RED)
- FOUND commit: `8da66f6` (feat — GREEN)

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-08*
