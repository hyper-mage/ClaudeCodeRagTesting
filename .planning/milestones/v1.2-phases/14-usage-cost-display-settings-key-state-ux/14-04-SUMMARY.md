---
phase: 14-usage-cost-display-settings-key-state-ux
plan: 04
subsystem: ui
tags: [react, typescript, tailwind, byok, balance, status-indicator, accessibility]

# Dependency graph
requires:
  - phase: 14-02
    provides: "useKeyStatus exposes derived isLow (= balance?.is_low ?? false; false when balance unknown), alongside status"
provides:
  - "IconSidebar rail dot: tri-state gray/green/amber driven by useKeyStatus.isLow (fill + aria-label only)"
  - "MobileTopBar dot: identical tri-state logic (no mb-2, inline placement preserved)"
  - "COST-03 surface #1 (D-05): always-visible low-balance indicator without opening settings"
affects: [14-05, frontend-key-state-ux, frontend-balance-indicator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Tri-state status dot: a small `connected/isLow` lookup computes a single fill class + aria-label; only fill + label change, never shape/animation"
    - "Light/dark not-connected fill split (bg-gray-400 dark:bg-gray-500) per Phase-13 coherence bar; green/amber identical in both themes"

key-files:
  created:
    - .planning/phases/14-usage-cost-display-settings-key-state-ux/14-04-SUMMARY.md
  modified:
    - frontend/src/components/IconSidebar.tsx
    - frontend/src/components/MobileTopBar.tsx

key-decisions:
  - "Used a derived `dotFill` + `dotLabel` lookup (the RESEARCH/patterns-recommended `!connected ? … : isLow ? … : …` form) instead of an inline ternary on the JSX, keeping both components readable and identical"
  - "aria-label is bound to the `dotLabel` variable (not an inline string literal); the locked copy 'OpenRouter balance low' / 'OpenRouter connected' / 'OpenRouter not connected' lives verbatim in the lookup"
  - "Not-connected fill upgraded to light/dark split (bg-gray-400 dark:bg-gray-500); the prior single bg-gray-500 had no light variant — corrected to the UI-SPEC tri-state lock"

requirements-completed: [COST-03]

# Metrics
duration: ~12min
completed: 2026-06-29
---

# Phase 14 Plan 04: Tri-State OpenRouter Status Dot (IconSidebar + MobileTopBar) Summary

**Recolored the always-visible OpenRouter status dot in both the desktop rail (`IconSidebar`) and the mobile top bar (`MobileTopBar`) to a tri-state — gray when no key is connected, green when connected with OK/unknown balance, amber when connected and `isLow` — so a low balance is visible without opening settings (COST-03 / D-05 surface #1). Fill class + `aria-label` only; no new shape, no animation, no fetch.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-29 (approx)
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `IconSidebar`: reads `isLow` from `useKeyStatus()` alongside `status`; a `dotFill`/`dotLabel` lookup drives the rail dot tri-state. Not connected → `bg-gray-400 dark:bg-gray-500` + `aria-label="OpenRouter not connected"`; connected + `isLow` → `bg-amber-500` + `aria-label="OpenRouter balance low"`; connected + OK/unknown → `bg-green-500` + `aria-label="OpenRouter connected"`. The `h-2 w-2 rounded-full`, `role="status"`, and the rail `mb-2` are preserved; no `animate-` class.
- `MobileTopBar`: the SAME `isLow`-driven lookup and the SAME three fills/labels, mirroring `IconSidebar` exactly. The top-bar dot keeps its inline placement and deliberately has **no** `mb-2` (rail-only spacing not copied). Same `h-2 w-2 rounded-full role="status"`, no animation.
- Both dots now consume only the boolean `isLow` (server-computed, exposed by Plan 02) — the raw balance/threshold never reaches these display-only components.

## Tri-state contract (consumed)

From `useKeyStatus()` (Plan 02, locked names):
- `status?.connected` → `connected` boolean gate.
- `isLow` → `balance?.is_low ?? false`; `false` when balance is null/unknown, so the dot never falsely goes amber (D-03/D-04). amber is reachable only when connected AND server `is_low` is true.

Resulting fill/label table (identical in both components):

| State | Fill | aria-label |
|-------|------|------------|
| Not connected | `bg-gray-400 dark:bg-gray-500` | `OpenRouter not connected` |
| Connected + isLow | `bg-amber-500` | `OpenRouter balance low` |
| Connected + OK/unknown | `bg-green-500` | `OpenRouter connected` |

## Task Commits

Each task was committed atomically:

1. **Task 1: Tri-state dot in IconSidebar** - `87ed741` (feat)
2. **Task 2: Tri-state dot in MobileTopBar (identical logic)** - `0545090` (feat)

## Files Created/Modified
- `frontend/src/components/IconSidebar.tsx` - Added `isLow` to the `useKeyStatus` destructure; added `connected`/`dotFill`/`dotLabel` lookup; bound the rail dot's `className` fill and `aria-label` to it (kept `mb-2`).
- `frontend/src/components/MobileTopBar.tsx` - Same `isLow` destructure + identical `connected`/`dotFill`/`dotLabel` lookup; bound the inline dot's fill and `aria-label` to it (no `mb-2`).

## Decisions Made
- **Lookup over inline ternary.** Used the RESEARCH/patterns-recommended `!connected ? … : isLow ? … : …` form computed into `dotFill`/`dotLabel`, keeping the two components readable and byte-for-byte parallel (only the `mb-2` differs).
- **aria-label via variable.** The acceptance criteria reference the literal `aria-label="OpenRouter balance low"`; the locked string lives verbatim in the `dotLabel` lookup and is bound to the JSX `aria-label`. The patterns doc explicitly endorses the variable lookup, so this satisfies the intent (the exact copy is present and rendered).
- **Not-connected light variant.** The pre-existing dot was a single `bg-gray-500` with no light-mode variant; corrected to the UI-SPEC tri-state lock `bg-gray-400 dark:bg-gray-500` (light gray-400 / dark gray-500). Green and amber are identical in both themes per UI-SPEC § Color.

## Deviations from Plan

None - plan executed exactly as written. The not-connected fill gained its light-mode variant (`bg-gray-400 dark:bg-gray-500`) as the plan/UI-SPEC tri-state explicitly specifies; this is the documented lock, not a deviation.

## Security (threat model verification)
- **T-14-14 (Information Disclosure, low-balance dot):** mitigated. Both dots consume only the boolean `isLow`; the exact `limit_remaining` balance and the server threshold never reach `IconSidebar`/`MobileTopBar`.
- **T-14-15 (Tampering, dot state):** accepted per plan. Display-only indicator, no user input or action; an incorrect state is a bounded cosmetic risk only.

## Known Stubs
None. Both dots are wired to live `useKeyStatus().isLow`; no placeholder/empty data sources introduced.

## Build / Lint
- `npm run build` (tsc -b strict + vite build) → exit 0, clean.
- `npm run lint` → the two changed files (`IconSidebar.tsx`, `MobileTopBar.tsx`) lint clean. The 5 reported errors are ALL pre-existing in untouched files (`FileUpload.tsx:5:56`, `AuthContext.tsx:48:17`, `ToastContext.tsx:96:17`, `ChatPage.tsx:52:5`, `themeBootstrap.test.ts:24:17`) — out of scope (already logged in Plan 02's `deferred-items.md`).
- The worktree `frontend/` had no `node_modules`; created a Windows directory junction to the main checkout's `frontend/node_modules` to run the build/lint, then **removed the junction** (link only; main checkout target confirmed intact) before writing this SUMMARY so the orchestrator can cleanly remove the worktree. Note: `mklink /J` via the Bash tool mangled the target path (MSYS conversion left a dangling junction); recreated it successfully with PowerShell `New-Item -ItemType Junction`.

## Manual Verification (deferred to VALIDATION.md)
- Browser-observable (VALIDATION.md "Amber low-balance indicator"): configure `LOW_BALANCE_THRESHOLD_USD` above the test balance, connect that key → both the rail dot and the top-bar dot turn amber; connect a null/OK-balance key → green; disconnect → gray. Light + dark both coherent.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- COST-03 surface #1 (the always-visible header dot) is complete. Plan 05 owns surface #2 (the settings low-balance warning line) and the rest of the `/settings` OpenRouter section using `balance`, `balance.limit_remaining`, `balanceLoading`, `balanceError`.
- No blockers introduced. STATE.md / ROADMAP.md intentionally NOT modified (worktree mode — orchestrator owns those writes after the wave).

## Self-Check: PASSED

Both modified files exist on disk and contain the tri-state tokens (`bg-amber-500`, `OpenRouter balance low`, `bg-gray-400 dark:bg-gray-500`, `role="status"`, `h-2 w-2 rounded-full`, no `animate-`); MobileTopBar correctly omits `mb-2`. Both task commits are reachable (`87ed741`, `0545090`). `npm run build` exits 0; the two changed files lint clean. The `frontend/node_modules` junction was removed (working tree clean, main checkout target intact).

---
*Phase: 14-usage-cost-display-settings-key-state-ux*
*Completed: 2026-06-29*
