---
phase: 14-usage-cost-display-settings-key-state-ux
plan: 05
subsystem: ui
tags: [react, typescript, settings, byok, balance, theme, cost, tailwind]

# Dependency graph
requires:
  - phase: 14-02
    provides: "useKeyStatus exposes balance ({connected, limit_remaining, is_low}) + isLow + balanceLoading + balanceError; composed loading/failed states via `&& balance === null`"
  - phase: 13-theme-default-model
    provides: "DefaultModelSelector (self-PUT + own heading) and ThemeToggle (self-PUT) as relocatable components; the temporary ChatPage inline mounts (D-04 temp spot)"
provides:
  - "SettingsPage: full PREF-01 3-section theme-aware page (OpenRouter + 4-state balance line + amber low-balance warning, Default model, Theme)"
  - "Two live tri-state key states ('Your key: connected', 'No key — connect to chat'); Demo state structurally reserved for Phase 15 (not built)"
  - "ChatPage: D-06 relocation complete — temp prefsControls cluster removed, footer prop dropped from ThreadSidebar + ThreadListContent with no dangling empty wrapper"
affects: [frontend-settings, frontend-key-state-ux, frontend-balance-indicator, phase-15-demo-mode]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Four-state balance line composed from the Plan-02 hook contract: balanceLoading && balance===null → 'Checking balance…'; balanceError && balance===null → 'Balance unavailable right now.'; limit_remaining===null → 'Pay-as-you-go — no limit set'; else → 'Balance: \$X' (as reported, never recomputed)"
    - "Amber low-balance warning gated on the SERVER-computed balance.is_low (no FE threshold re-derivation); lucide AlertTriangle is the warning mark (no literal ⚠ glyph)"
    - "Theme-aware surface tokens copied from ChatContainer (page bg-white dark:bg-gray-950, card bg-gray-50 dark:bg-gray-900 + border gray-200 dark:gray-800) applied to a previously dark-only page"
    - "Relocated self-contained controls mount directly (DefaultModelSelector owns its heading) — no duplicate heading added by the host page"

key-files:
  created: []
  modified:
    - frontend/src/pages/SettingsPage.tsx
    - frontend/src/pages/ChatPage.tsx

key-decisions:
  - "Bound the balance line to the verbatim Plan-02 contract names (balance.limit_remaining / balanceLoading / balanceError); used the `&& balance === null` composition so an in-flight refetch never masks an already-resolved value"
  - "Rendered limit_remaining directly in the template (`Balance: $${balance.limit_remaining}`) — as reported by OpenRouter, no client-side toFixed/arithmetic (ROADMAP SC#1 / Phase 11 D-04 'never recomputed')"
  - "SettingsPage now owns defaultModel + models state, seeded via its own mount fetches (/api/preferences for the default, /api/models for the catalog), mirroring ChatPage's silent-on-failure, array-guarded pattern; the theme reconcile stayed in ChatPage as a global concern"
  - "Demo tri-state NOT built (D-08 / SC#4): demo_fallback is OFF and CONTEXT locks demo enablement to Phase 15, so mode=='demo' is unreachable — wired only connected/no-key from status.connected, no dead Demo UI"
  - "Made the connected status label + green text theme-aware (text-green-600 dark:text-green-400) and added the locked 'No key — connect to chat' status line above the existing no-key helper"

patterns-established:
  - "Tri-state nested ternary that narrows TypeScript correctly for the balance line (balance===null guard before the limit_remaining===null check so the final branch sees a non-null number)"
  - "Clean footer-prop removal: ThreadSidebar/ThreadListContent render the footer wrapper only when truthy, so dropping the prop entirely leaves no empty box (Pitfall 6)"

requirements-completed: [COST-02, COST-03, PREF-01]

# Metrics
duration: ~25min
completed: 2026-06-29
---

# Phase 14 Plan 05: Settings/Account Page (PREF-01) + D-06 Relocation Summary

**Grew the Phase-10 dark-only `/settings` stub into the full PREF-01 three-section theme-aware settings page — OpenRouter (two live tri-state key states + masked label + connected-since + four-state balance line + amber low-balance warning + disconnect), Default model, and Theme — and finished the D-06 relocation by removing the temporary default-model/theme cluster from ChatPage with no dangling footer wrapper.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-29
- **Completed:** 2026-06-29
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- **SettingsPage is now theme-aware** (was dark-only): page wrapper `bg-white text-gray-900 dark:bg-gray-950 dark:text-white`, card `bg-gray-50 border border-gray-200 dark:bg-gray-900 dark:border-gray-800`, captions `text-gray-600 dark:text-gray-400`. No orphan dark panel remains in light mode.
- **Two live tri-state key states (D-08):** connected branch shows the locked `Your key: connected` (green dot + theme-aware green label, masked label `font-mono text-sm`, `Connected since …`); no-key branch adds the locked `No key — connect to chat` status line above the existing helper + `Connect OpenRouter` CTA. The Demo state is structurally reserved (not built) — `mode=='demo'` is unreachable this phase, so the page wires only `status.connected`.
- **Four-state balance line (COST-02)** inside the connected branch, directly under `Connected since`: `Checking balance…` / `Balance unavailable right now.` / `Pay-as-you-go — no limit set` / `Balance: $X`. `limit_remaining` is rendered exactly as reported, never recomputed.
- **Amber low-balance warning line (COST-03 / D-05 surface #2)** immediately after the balance line, gated on the server-computed `balance.is_low`: a lucide `AlertTriangle` (14px, `amber-500`) + `Balance low: $X — add credits` in `amber-700` (light) / `amber-300` (dark). Inline caption — not a pill/toast/banner.
- **Relocated sections (D-06):** a `mt-6` Default model section mounting `<DefaultModelSelector value={defaultModel} onChange={setDefaultModel} models={models} />` (no duplicate heading — the component owns it), then a `Theme` heading + `<ThemeToggle />`. The page owns `defaultModel` + `models`, seeded via its own `/api/preferences` + `/api/models` mount fetches.
- **ChatPage relocation cleanup (D-06):** deleted the `prefsControls` cluster + the `DefaultModelSelector`/`ThemeToggle` imports; removed the `footer` prop entirely from both `<ThreadSidebar>` and `<ThreadListContent>` (no dangling empty wrapper); removed the now-unused `defaultModel` state and its `/api/preferences` hydrate line while keeping the post-login theme reconcile. Retained the `models` catalog, the `models={models}` ChatContainer prop, and `handleThreadModelChange` so the per-thread selector stays in the thread header (D-07).

## Task Commits

Each task was committed atomically:

1. **Task 1: Grow SettingsPage to 3 theme-aware sections + balance/warning + tri-state copy** — `8daf8b1` (feat)
2. **Task 2: Remove the temporary prefsControls mounts from ChatPage** — `2b6c97a` (feat)

## Files Created/Modified

- `frontend/src/pages/SettingsPage.tsx` — theme-aware surfaces; tri-state copy (`Your key: connected` / `No key — connect to chat`); four-state balance line bound to `balance`/`balanceLoading`/`balanceError`; amber `is_low` warning with `AlertTriangle`; new Default model + Theme sections; page now owns `defaultModel` + `models` with silent, array-guarded mount fetches.
- `frontend/src/pages/ChatPage.tsx` — removed `prefsControls` + the two relocated imports; dropped both `footer` props; removed the unused `defaultModel` state + its hydrate line (kept theme reconcile); retained the catalog + per-thread selector wiring.

## Verification

- `npm run build` (tsc strict `-b` + vite build) exits **0** after both tasks.
- `npm run lint` reports **5 errors, all pre-existing and out of scope** (the exact set recorded in 14-02-SUMMARY's deferred-items: `FileUpload.tsx`, `AuthContext.tsx`, `ToastContext.tsx`, `ChatPage.tsx` `loadThreads()` setState-in-effect, `themeBootstrap.test.ts`). The two files changed by this plan lint clean — no NEW errors. The `ChatPage.tsx` error shifted from `:52` to `:49` only because three lines were removed above the untouched `loadThreads()` effect.
- Source assertions (SettingsPage): `Your key: connected`, `No key — connect to chat`, `Pay-as-you-go — no limit set`, `Checking balance…`, `Balance unavailable right now.`, `Balance: $`, `Balance low:`, `— add credits` all present; page wrapper carries `bg-white` + `dark:bg-gray-950`; card carries `bg-gray-50` + `dark:bg-gray-900`; warning uses `amber-700`/`amber-300` + an `AlertTriangle` import; no `Demo mode` literal and no `mode === 'demo'` branch.
- Source assertions (ChatPage): `prefsControls`, `DefaultModelSelector`, `ThemeToggle`, `footer=`, and `defaultModel` all return **0**; `models` state, `models={models}` prop, and `handleThreadModelChange` retained.
- Build environment: node_modules junction created via PowerShell for the build/lint, then removed before writing this SUMMARY (`frontend/node_modules` confirmed gone; main checkout target intact).

## Deviations from Plan

None — plan executed exactly as written. The Plan-02 hook contract field names (`balance.limit_remaining`, `balanceLoading`, `balanceError`) matched, so the balance line bound with no rebind.

## Known Stubs

- **Demo tri-state (intentional, locked to Phase 15):** The D-08 third key state (`Demo mode`) is structurally reserved, not stubbed as dead UI. `demo_fallback_enabled` is OFF and CONTEXT Deferred Ideas locks demo enablement to Phase 15, so `mode=='demo'` is unreachable on any settings surface this phase. The page wires only the two live states from `status.connected`. This is the documented SCOPE decision (D-08 / SC#4) — the verifier must NOT false-flag the absent Demo state against D-08's literal three-state wording.
- `defaultModel` initializes to `null` and is seeded from `/api/preferences`; until the fetch resolves (or if it fails), `DefaultModelSelector` shows its own placeholder. This is the intended best-effort seeding pattern (mirrors the prior ChatPage behaviour), not a dead stub.

## Security (threat model verification)

- **T-14-16 (Information Disclosure, settings balance/key display):** Only the masked label + the secret-free balance fields (`limit_remaining`, `is_low`) are rendered; the full key never crosses. Balance failure shows the fixed `Balance unavailable right now.` (no provider error, no HTTP code). Mitigated.
- **T-14-17 (Information Disclosure, balance line copy):** House-style locked copy only — no caught error / provider message / `sk-or` fragment is interpolated into the balance or warning line. Mitigated.
- **T-14-18 (Tampering, low-balance warning trigger):** The warning is gated on the server-computed `balance.is_low`; the FE never re-derives low-ness from a client threshold. Mitigated.
- **T-14-19 (Spoofing, disconnect action):** The existing ConfirmDialog + bearer'd `DELETE /api/keys` flow + `notifyKeyStatusChanged()` broadcast are unchanged. Accepted per plan.
- No new network endpoints, auth paths, or schema changes were introduced.

## User Setup Required

None — no external service configuration required. (To exercise the amber low-balance warning in a manual smoke, set `LOW_BALANCE_THRESHOLD_USD` above a test balance per the plan's verification note.)

## Next Phase Readiness

- PREF-01 settings page complete with the two live key states + masked label + balance + relocated default-model/theme controls; D-06 relocation finished with no ChatPage footer regression.
- Phase 15 wires the reserved Demo branch when `demo_fallback_enabled` is enabled — the connected/no-key structure leaves a clean insertion point.
- STATE.md / ROADMAP.md intentionally NOT modified (worktree mode — the orchestrator owns those writes after the wave).

## Self-Check: PASSED

Both modified files exist on disk; both task commits are reachable (`8daf8b1`, `2b6c97a`); `npm run build` exits 0 and the two changed files lint clean. The node_modules junction was removed (worktree `frontend/node_modules` gone).

---
*Phase: 14-usage-cost-display-settings-key-state-ux*
*Completed: 2026-06-29*
