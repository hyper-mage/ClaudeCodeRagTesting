---
phase: 10-oauth-pkce-backend-exchange-frontend-connect
plan: 04
subsystem: ui
tags: [react, oauth, pkce, byok, routing, nav, react-router]

# Dependency graph
requires:
  - phase: 10-oauth-pkce-backend-exchange-frontend-connect
    plan: 03
    provides: "default export SettingsPage, default export OAuthCallbackPage, useKeyStatus() -> { status, loading, refresh }"
provides:
  - "frontend/src/App.tsx — /settings (Protected+AuthenticatedLayout) + /settings/openrouter/callback (Protected, bare no-layout) routes wired to the Plan 03 pages"
  - "frontend/src/components/IconSidebar.tsx — Settings gear nav entry (desktop rail + mobile IconNavRow) -> /settings + always-visible desktop connection-status dot beside DemoPill"
  - "frontend/src/components/MobileTopBar.tsx — mobile connection-status dot left of DemoPill"
affects: [Phase 13/14 (/settings grows into the full settings/account page; the dot evolves into the full Demo/Your-key/No-key state machine in Phase 14)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Route mirroring: /settings copies the /documents Protected+AuthenticatedLayout block; the callback route is deliberately bare (Protected, NO AuthenticatedLayout) per UI-SPEC Surface 4 so the OAuth return renders sidebar-free while keeping the Supabase bearer for the exchange POST"
    - "Nav-entry mirroring: the Settings gear is added identically to BOTH the desktop rail (with mb-2) and IconNavRow (without mb-2, matching its siblings), after Documents, before the flex-1 spacer; active state bg-gray-800 (never blue)"
    - "Display-only status dot: h-2 w-2 rounded-full, bg-green-500/bg-gray-500 driven by useKeyStatus().status?.connected, role=status + connected/not aria-label, no onClick, no setInterval (fetch-once-on-mount via the shared hook)"

key-files:
  created: []
  modified:
    - frontend/src/App.tsx
    - frontend/src/components/IconSidebar.tsx
    - frontend/src/components/MobileTopBar.tsx

key-decisions:
  - "The desktop connection dot lives in IconSidebar (not a new ChatContainer header bar and not a new file) — IconSidebar renders on the chat route via AuthenticatedLayout, so the dot is always visible there; placed after the flex-1 spacer, just above DemoPill, mirroring the mobile placement (dot adjacent to DemoPill)"
  - "useKeyStatus is consumed independently by IconSidebar (desktop) and MobileTopBar (mobile) — the two render at mutually-exclusive breakpoints (md:flex vs md:hidden), so there is no double-fetch on a single viewport; the hook fetches once on mount and does not poll"
  - "Verify gate scoped per the plan caveat: success = `npm run build` exit 0 AND `npx eslint` clean on this plan's touched files (App.tsx, IconSidebar.tsx, MobileTopBar.tsx). Repo-wide `npm run lint` still fails on 4 pre-existing ChatPage.tsx errors (D-10-A) — out of scope, this plan does not touch ChatPage"
  - "Task 3 (prod round-trip on the Cloudflare Pages origin) is a blocking human-verify checkpoint — NOT auto-approved and NOT fabricated; the automated backend regression (pytest -q) was run, the 8 prod browser steps are returned to the human"

requirements-completed: [KEY-01, KEY-03]
requirements-pending-human-verify: []
human-verify-result: "Task 3 verified 8/8 on prod (boardgame-rag-prod.pages.dev) 2026-06-22 — connect round-trip, key never returned, forged-state rejected, hard-refresh succeeds, masked status, disconnect/reconnect, no key leak. Step 7 surfaced a stale connection-dot defect (per-instance useKeyStatus didn't refresh the persistent sidebar/top-bar dots on in-SPA disconnect); fixed in cf7d749 (window-event broadcast) and re-verified — dots now flip green/gray live."

# Metrics
duration: 6min
completed: 2026-06-19
---

# Phase 10 Plan 04: Route + Nav + Header-Dot Wiring Summary

**The final BYOK wiring plan: registers `/settings` (Protected + AuthenticatedLayout) and the bare-but-Protected `/settings/openrouter/callback` routes against the Plan 03 pages, adds the `Settings` gear nav entry to both the desktop IconSidebar rail and the mobile IconNavRow drawer cluster, and renders the always-visible connection-status dot on the chat route in two places — the mobile `MobileTopBar` (left of `DemoPill`) and the desktop `IconSidebar` rail (beside `DemoPill`). Both dots are 8px display-only `h-2 w-2 rounded-full`, green-when-connected / gray-when-not, `role="status"` + connected/not `aria-label`, consuming the shared `useKeyStatus` hook with no polling. `npm run build` green; the three touched files are lint-clean. Task 3 — the prod Cloudflare Pages round-trip — is a BLOCKING human-verify checkpoint and is returned to the user (not fabricated); the backend `pytest -q` regression portion ran with no plan-attributable failures.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-19
- **Completed:** 2026-06-19
- **Tasks:** 3 total (2 `type=auto` executed + committed; 1 `type=checkpoint:human-verify gate="blocking"` returned to the human)
- **Files:** 0 created, 3 modified

## Accomplishments

- **Task 1 — routes + IconSidebar gear (`58e22bb`):** `App.tsx` now imports `SettingsPage` + `OAuthCallbackPage` (mirroring the existing page imports) and registers two routes: `/settings` wrapped `<ProtectedRoute><AuthenticatedLayout><SettingsPage /></AuthenticatedLayout></ProtectedRoute>` (mirrors the `/documents` block) and `/settings/openrouter/callback` wrapped `<ProtectedRoute><OAuthCallbackPage /></ProtectedRoute>` (bare — no `AuthenticatedLayout`/sidebar per UI-SPEC Surface 4; Protected so the session survives the round-trip for the bearer'd exchange POST). `IconSidebar.tsx` adds `Settings` to the lucide import and renders a gear button in BOTH the desktop rail (`p-2 rounded mb-2`, active `bg-gray-800`, `title="Settings"`, glyph `size={20}`, `navigate('/settings')`) and `IconNavRow` (same, minus `mb-2`, via `handleNavigate('/settings')`), immediately after Documents and before the `flex-1` spacer. `isSettings = location.pathname === '/settings'` computed in both. The desktop connection dot also shipped in this commit (same file — see Task 2).
- **Task 2 — connection-status dot (`2b550c9` + the desktop dot in `58e22bb`):** `MobileTopBar.tsx` consumes `useKeyStatus()` and renders an 8px display-only dot (`h-2 w-2 rounded-full`, `bg-green-500` when `status?.connected` else `bg-gray-500`, `role="status"` + a connected/not `aria-label`) positioned to the LEFT of the `<DemoPill />` right-slot so demo-identity and key-state read as two distinct signals. The matching desktop dot is rendered in `IconSidebar.tsx`'s rail bottom region — after the `<div className="flex-1" />` spacer, just above `DemoPill` — consuming the same `useKeyStatus()`. No `setInterval`, no polling; no new file; no `ChatContainer` header bar introduced.
- **Task 3 — PENDING HUMAN VERIFICATION (blocking checkpoint):** the prod Cloudflare Pages round-trip cannot be executed by the agent (requires the real user, the OpenRouter auth screen, the deployed prod origin, and browser/Sentry inspection). The 8 prod verification steps are recorded below for the human. The automated regression portion (`pytest -q`) ran: see Verification Evidence.

## Task Commits

1. **Task 1: routes + IconSidebar gear (+ desktop dot)** — `58e22bb` (feat)
2. **Task 2: MobileTopBar connection dot** — `2b550c9` (feat)

**Plan metadata** (this SUMMARY + STATE/ROADMAP) committed separately.

## Files Modified

- `frontend/src/App.tsx` (modified) — imports `SettingsPage` + `OAuthCallbackPage`; adds `/settings` (Protected + AuthenticatedLayout) and `/settings/openrouter/callback` (Protected, bare) routes. `_redirects` unchanged (SPA catch-all already serves the callback path in prod).
- `frontend/src/components/IconSidebar.tsx` (modified) — `Settings` lucide import; `isSettings` in both the rail and `IconNavRow`; gear button after Documents in both; `useKeyStatus()` consumed in the desktop component; desktop connection dot beside `DemoPill`.
- `frontend/src/components/MobileTopBar.tsx` (modified) — `useKeyStatus()` consumed; 8px display-only connection dot left of `DemoPill`.

## Verification Evidence

- **Build:** `cd frontend && npm run build` (tsc -b strict + vite) → **exit 0** after Task 1 and after Task 2 (the chunk-size >500 kB warning is pre-existing and unrelated).
- **Lint (this plan's touched files):** `npx eslint src/App.tsx src/components/IconSidebar.tsx src/components/MobileTopBar.tsx` → **exit 0** (zero errors). tsc strict (`noUnusedLocals`/`noUnusedParameters`) clean.
- **Routes:** `App.tsx` greps positive for `path="/settings"`, `path="/settings/openrouter/callback"`, `SettingsPage`, `OAuthCallbackPage`; the callback route is `ProtectedRoute`-wrapped WITHOUT `AuthenticatedLayout`.
- **Gear:** `IconSidebar.tsx` greps positive for `Settings` (lucide import + glyph), `title="Settings"`, `navigate('/settings')` (rail) and `handleNavigate('/settings')` (IconNavRow), active `bg-gray-800`; no `bg-blue-` on the gear.
- **Dots:** both `IconSidebar.tsx` and `MobileTopBar.tsx` grep positive for `useKeyStatus`, `h-2 w-2 rounded-full`, `bg-green-500`, `bg-gray-500`, `role="status"`, and a connected/not `aria-label`; no `setInterval` in either file.
- **`_redirects` unchanged:** still `/* /index.html 200` (no edit).
- **Backend regression (`pytest -q`):** **156 passed, 2 errors** in 12.48s. The 2 errors are the pre-existing `user_id` fixture issue in `test_record_manager.py::test_check_duplicate_integration` / `test_find_previous_version_integration` — documented in STATE.md "Pending Todos" as pre-dating v1.1, in a file this plan does not touch. No plan-attributable failure; the keys/SEC-02 lockdown suite is green. (This plan modifies zero backend files.)

## Decisions Made

- **Desktop dot anchor = IconSidebar rail (not a new header bar):** UI-SPEC Surface 3 left the desktop chat anchor to planner discretion ("visible on the chat route, distinct from DemoPill"); the plan PINNED IconSidebar's bottom DemoPill region. IconSidebar renders on the chat route via `AuthenticatedLayout`, so the dot is always visible there. Chosen over a new `ChatContainer` header bar (avoids restructuring the title-less desktop chat shell) and over a new `KeyStatusDot.tsx` file (the plan's `files_modified` already scopes IconSidebar + MobileTopBar).
- **Two independent `useKeyStatus()` consumers (no shared parent):** IconSidebar (`md:flex`) and MobileTopBar (`md:hidden`) render at mutually-exclusive breakpoints, so a single viewport mounts only one — no duplicate `/api/keys/status` fetch on a given screen. The hook fetches once on mount and exposes `refresh()`; no polling per UI-SPEC Surface 3.
- **Bare callback route:** `/settings/openrouter/callback` is `ProtectedRoute`-wrapped but NOT inside `AuthenticatedLayout`, so the OAuth return renders a clean centered card with no sidebar (UI-SPEC Surface 4) while the Supabase session is preserved for the bearer'd exchange POST (RESEARCH Q2 / Pitfall 7).

## Deviations from Plan

None — plan executed exactly as written for Tasks 1 and 2.

The desktop IconSidebar connection dot (logically part of Task 2) was committed in the Task 1 commit (`58e22bb`) rather than the Task 2 commit, because both the gear (Task 1) and the desktop dot (Task 2) edit the same file `IconSidebar.tsx`; splitting one file across two commits via partial staging would have been fragile. The two edits are non-overlapping (gear in the top nav cluster; dot in the bottom DemoPill region), exactly as the plan's Task 2 action requires. The MobileTopBar dot — the other half of Task 2 — is the standalone Task 2 commit (`2b550c9`). Net effect on the tree is identical to the plan's intent; only the commit boundary for the in-file desktop dot shifted by one commit.

## Task 3 — Prod Round-Trip Verification (VERIFIED 8/8 — 2026-06-22)

Performed by the user on the deployed **prod Cloudflare Pages origin** (`https://boardgame-rag-prod.pages.dev`), signed in as a real user. Prerequisites done before the run: migration 028 applied to PROD (`supabase db push --linked`, ref `ybehhhduhynsdujmxdzx`, applied 025→028 in order; D-03 carry-forward closed) and `KEY_ENCRYPTION_SECRET` set as a distinct prod Fly secret (D-04); backend redeployed (`fly deploy`, `/api/health` 200).

1. [x] Gear → `/settings` loads → "Connect OpenRouter" (not-connected).
2. [x] Connect → OpenRouter `/auth` screen → authorized.
3. [x] Returned to `/settings/openrouter/callback` (no 404 — SPA fallback) → "Connecting…" spinner → auto-redirect to `/settings` (Connected) + "OpenRouter connected." toast.
4. [x] `/settings` shows the masked tail + "Connected since {date}"; chat-route dot green.
5. [x] Hard-refresh on the callback mid-flow → SUCCEEDS (D-07, sessionStorage).
6. [x] Forged callback (`?code=x&state=WRONG`) → generic "Couldn't connect…" inline error + Retry/Back, rejected (CSRF, ROADMAP #2).
7. [x] Disconnect → confirm dialog → not-connected + Connect CTA; **sidebar dot flips green→gray live**. Reconnect → re-stamps. *(Initially the persistent sidebar/top-bar dots did not refresh on in-SPA disconnect — per-instance `useKeyStatus` held stale state. Fixed in `cf7d749` via a `notifyKeyStatusChanged()` window-event broadcast every instance listens for; re-verified live.)*
8. [x] No `sk-or-v1-…` in browser console, network response bodies (exchange/status), or Sentry for the flow.

**Result:** all 8 steps pass. KEY-01 + KEY-03 satisfied on prod.

## Deferred Issues

- **Pre-existing `ChatPage.tsx` lint errors** (`react-hooks/set-state-in-effect`, 4 errors): repo-wide `npm run lint` still fails on these. Confirmed pre-existing (D-10-A in deferred-items.md), in a file this plan does not touch — out of scope per the SCOPE BOUNDARY rule. This plan's three touched files are individually lint-clean (`npx eslint` exit 0); the build (the hard gate) is green.
- **Pre-existing `test_record_manager.py` `user_id` fixture errors** (2 errors): surfaced by `pytest -q`. Documented in STATE.md "Pending Todos" as pre-dating v1.1; orthogonal to this plan (zero backend files touched). Not a regression.

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. This plan is pure frontend wiring (routes, nav entry, display-only dots) consuming already-shipped Plan 02/03 endpoints and pages. The three registered prod-origin threats (T-10-12 callback 404, T-10-13 forged-state, T-10-14 key-in-console/network/Sentry) are verified by Task 3 steps 3, 6, and 8 respectively — pending the human prod round-trip. No new endpoint, auth path, file-access pattern, or schema change introduced.

## Self-Check: PASSED

- `frontend/src/App.tsx` (modified; /settings + callback routes + page imports) — FOUND
- `frontend/src/components/IconSidebar.tsx` (modified; gear rail + IconNavRow + desktop dot) — FOUND
- `frontend/src/components/MobileTopBar.tsx` (modified; mobile dot) — FOUND
- Commit `58e22bb` (feat: routes + IconSidebar gear + desktop dot) — FOUND
- Commit `2b550c9` (feat: MobileTopBar dot) — FOUND
- `npm run build` — exit 0; the three touched files lint-clean (`npx eslint` exit 0)
- Backend `pytest -q` — 156 passed; 2 pre-existing out-of-scope fixture errors (not a regression)

---
*Phase: 10-oauth-pkce-backend-exchange-frontend-connect*
*Completed: 2026-06-19 (Tasks 1-2); Task 3 prod round-trip verified 8/8 on 2026-06-22 (+ dot-sync fix cf7d749).*
