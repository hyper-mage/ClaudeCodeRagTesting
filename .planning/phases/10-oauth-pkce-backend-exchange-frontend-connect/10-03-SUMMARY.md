---
phase: 10-oauth-pkce-backend-exchange-frontend-connect
plan: 03
subsystem: ui
tags: [react, oauth, pkce, byok, sentry, csrf, web-crypto, sse-unrelated]

# Dependency graph
requires:
  - phase: 10-oauth-pkce-backend-exchange-frontend-connect
    plan: 02
    provides: "POST /api/keys/openrouter/exchange {code,code_verifier}->{connected}, GET /api/keys/status->{connected,masked_label,connected_at}, DELETE /api/keys (204)"
provides:
  - "frontend/src/lib/pkce.ts — Web Crypto code_verifier + S256 code_challenge + CSRF state + startOpenRouterConnect() redirect helper (the only genuinely-new logic in the phase)"
  - "frontend/src/lib/sentry.ts — sk-or-v1-… scrub in beforeSend (message/exception/request.url) AND beforeBreadcrumb (message/data), the frontend half of SEC-01"
  - "frontend/src/hooks/useKeyStatus.ts — shared GET /api/keys/status fetch-into-state with refresh()"
  - "frontend/src/pages/SettingsPage.tsx — /settings stub (connect / status / disconnect)"
  - "frontend/src/pages/OAuthCallbackPage.tsx — callback state machine (spinner -> redirect+toast / inline error)"
affects: [10-04 (routing + nav gear + header dot wires these pages into App.tsx/IconSidebar/MobileTopBar), Phase 14 (/settings grows into the full settings page)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Web Crypto PKCE (no library): base64url over crypto.getRandomValues + crypto.subtle.digest('SHA-256')"
    - "sessionStorage (NOT localStorage) for code_verifier + CSRF state — survives same-tab hard refresh (D-07), tightens CSRF binding"
    - "One-shot callback effect guarded by a ranRef against React StrictMode double-run; verifier/state read from sessionStorage NOT React state"
    - "Locked generic failure copy: the caught error / HTTP status / sk-or- fragment is never interpolated into the DOM (D-06)"
    - "Additive Sentry scrub rule beside the existing Authorization/JWT rules (extend, never rewrite)"

key-files:
  created:
    - frontend/src/lib/pkce.ts
    - frontend/src/hooks/useKeyStatus.ts
    - frontend/src/pages/SettingsPage.tsx
    - frontend/src/pages/OAuthCallbackPage.tsx
  modified:
    - frontend/src/lib/sentry.ts

key-decisions:
  - "Extracted startOpenRouterConnect() into lib/pkce.ts so the SettingsPage Connect CTA and the OAuthCallbackPage Retry button run the identical PKCE init (planner-granted discretion; avoids duplicating the sessionStorage+redirect logic)"
  - "Connect/Disconnect/Retry/Back buttons use text-base font-semibold (not a Display/Label size) to stay inside the locked 4-size/2-weight scale; bg-blue-600 appears ONLY on the Connect CTA + Retry"
  - "connected_at formatted client-side via toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric'}) -> 'Jun 19, 2026' (no time-of-day), with a NaN guard"
  - "Pre-existing ChatPage.tsx react-hooks/set-state-in-effect lint errors are out of scope (SCOPE BOUNDARY) — logged to deferred-items.md; new files are lint-clean (npx eslint exits 0)"

patterns-established:
  - "PKCE Connect + Callback round-trip: SPA-owned state (randomString) stored in sessionStorage, validated on return before the bearer'd exchange POST"
  - "Sentry secret-scrub-by-extension: one regex rule added beside existing redaction in both hooks, applied to all stringy carriers (message, exception values, request.url, breadcrumb message/data)"

requirements-completed: [KEY-01, KEY-03, KEY-04]

# Metrics
duration: 5min
completed: 2026-06-19
---

# Phase 10 Plan 03: Frontend Connect + Callback Core Summary

**The BYOK frontend connect core: a ~30-line Web Crypto PKCE helper (verifier + S256 challenge + CSRF state), the `sk-or-v1-…` Sentry scrub that closes the frontend half of SEC-01, a shared `useKeyStatus` hook, the `/settings` connect/status/disconnect stub, and the `OAuthCallbackPage` state machine (spinner → redirect+toast / locked inline error) — sessionStorage-backed so a hard-refresh is the success path, CSRF state validated before the bearer'd exchange POST, and the caught error is never interpolated into the DOM. `npm run build` green; all new/modified files lint-clean.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-06-19T20:56Z
- **Completed:** 2026-06-19
- **Tasks:** 3 (all `type=auto`)
- **Files:** 4 created, 1 modified

## Accomplishments

- **Task 1 — `lib/pkce.ts` + `lib/sentry.ts` scrub (`f30b364`):** New `pkce.ts` with `randomString` (crypto.getRandomValues → base64url → slice) and `async challengeFromVerifier` (`crypto.subtle.digest('SHA-256', …)` → base64url); no default export, no React import. Extended `sentry.ts` with `const OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g` + a `scrub` helper, applied in `beforeSend` (message, each `exception.values[].value`, `request.url`) and `beforeBreadcrumb` (message + stringy data) — purely additive beside the existing Authorization redaction and `sb-…-auth-token` console drop (both verified intact).
- **Task 2 — `useKeyStatus` + `SettingsPage` (`c7ebb1a`):** `useKeyStatus()` mirrors `useDocuments.loadDocuments` (session-gated `useCallback`, `apiFetch('/api/keys/status')` into state, silent catch, `finally` clears loading, `useEffect` kickoff) — no poll, no Realtime. `SettingsPage` renders the loading spinner (no CTA flash), the not-connected Connect CTA (`bg-blue-600`, full-width) + explainer, and the connected state (green dot + "Connected", `font-mono` masked tail, "Connected since {short date}", red Disconnect via `ConfirmDialog` → `DELETE /api/keys` → `refresh()`). Added `startOpenRouterConnect()` to `pkce.ts` (stores verifier+state in sessionStorage, redirects to `openrouter.ai/auth` with the S256 challenge) so the CTA and the callback Retry share one init.
- **Task 3 — `OAuthCallbackPage` (`a2fa199`):** One-shot effect (`ranRef` StrictMode guard) reads `code`+`state` from the URL and `verifier`+`state` from sessionStorage (NOT React state), runs the CSRF check (`returnedState !== storedState` → failure), POSTs `{code, code_verifier}` to `/api/keys/openrouter/exchange`, then on success removes both sessionStorage keys, fires `showToast('OpenRouter connected.', 'success')`, and `navigate('/settings', { replace: true })`. Failure renders the locked sentence "Couldn't connect your OpenRouter account — please try again." with `AlertCircle` (`text-red-400`), a blue Retry (re-runs `startOpenRouterConnect`), and a neutral "Back to settings" — the caught error is never interpolated. `role="status"` (in-flight) / `role="alert"` (failure).

## Task Commits

1. **Task 1: lib/pkce.ts + lib/sentry.ts sk-or scrub** — `f30b364` (feat)
2. **Task 2: useKeyStatus hook + SettingsPage stub** — `c7ebb1a` (feat)
3. **Task 3: OAuthCallbackPage state machine** — `a2fa199` (feat)

**Plan metadata** (this SUMMARY + STATE/ROADMAP/REQUIREMENTS + deferred-items.md) committed separately.

## Files Created/Modified

- `frontend/src/lib/pkce.ts` (created) — `randomString`, `challengeFromVerifier`, `startOpenRouterConnect`; Web Crypto, named exports only, sessionStorage-backed.
- `frontend/src/lib/sentry.ts` (modified) — additive `/sk-or-v1-[A-Za-z0-9_-]+/g → '[redacted-key]'` scrub in both `beforeSend` and `beforeBreadcrumb`; existing rules untouched.
- `frontend/src/hooks/useKeyStatus.ts` (created) — `useKeyStatus()` → `{ status, loading, refresh }`; session-gated, silent catch, no poll/Realtime.
- `frontend/src/pages/SettingsPage.tsx` (created) — `/settings` stub: connect (PKCE init) / status (masked tail + connected-since) / disconnect (ConfirmDialog → DELETE → refresh).
- `frontend/src/pages/OAuthCallbackPage.tsx` (created) — callback state machine: spinner → CSRF-validated exchange → redirect+toast / locked inline failure + Retry/Back.

## Verification Evidence

- **Build:** `cd frontend && npm run build` (tsc -b strict + vite) → **exit 0** after each task (the chunk-size >500 kB warning is pre-existing and unrelated).
- **Lint (new/modified files):** `npx eslint src/lib/pkce.ts src/lib/sentry.ts src/hooks/useKeyStatus.ts src/pages/SettingsPage.tsx src/pages/OAuthCallbackPage.tsx` → **exit 0** (zero errors). tsc strict (`noUnusedLocals`/`noUnusedParameters`) clean.
- **Sentry scrub greps:** `sentry.ts` contains `/sk-or-v1-[A-Za-z0-9_-]+/g` + `[redacted-key]` applied in BOTH hooks; the Authorization redaction (lines 48/77) and the `sb-…-auth-token` console drop (line 86) are still present.
- **CSRF / sessionStorage:** `OAuthCallbackPage` greps positive for `sessionStorage.getItem('or_pkce_state')` + `sessionStorage.getItem('or_pkce_verifier')` + `returnedState !== storedState` before the exchange POST; zero `localStorage` usage in any new file (the only `localStorage` tokens are explanatory comments).
- **No leak in failure UI:** grep for `{err` / `error.message` / `String(e)` / `{e}` inside `OAuthCallbackPage.tsx` JSX → **none found**.
- **Typography/color locks:** `SettingsPage` has no `text-lg`/`text-xl`/`text-3xl`/`font-medium`/`font-extrabold`; `bg-blue-600` appears ONLY on the Connect CTA (and the callback Retry) — never on the dot, Disconnect, gear, or Back.

## Decisions Made

- **Shared `startOpenRouterConnect()` helper** — extracted into `lib/pkce.ts` (planner-granted discretion in the Task 3 action) so the SettingsPage Connect CTA and the callback Retry run byte-identical PKCE init (fresh verifier+state, sessionStorage, S256 redirect). This is where the two `sessionStorage.setItem` calls live; the SettingsPage Connect handler reaches them through the helper.
- **Button typography** — Connect/Disconnect/Retry/Back use `text-base font-semibold` (the Heading role) rather than introducing a 5th size, keeping the locked 4-size/2-weight scale; full-width `py-3` clears the 44px mobile touch target.
- **`connected_at` formatting** — `toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'})` → "Jun 19, 2026" (no time-of-day), guarded against a NaN date.
- **Em-dash + ellipsis are literal single characters** — the failure sentence uses a literal `—` and the spinner caption a literal `…` (matching the UI-SPEC's single-char ellipsis lock), not HTML entities, so the acceptance grep matches the locked copy.

## Deviations from Plan

None - plan executed exactly as written.

One in-scope structural choice within the planner's stated discretion: the PKCE connect init was extracted into a shared `startOpenRouterConnect()` exported from `lib/pkce.ts` (the Task 3 action explicitly permits "extract a shared helper if cleaner, planner discretion"). This keeps the SettingsPage Connect handler and the callback Retry on one code path; the sessionStorage writes therefore live in `pkce.ts` rather than inline in `SettingsPage.tsx`, which the Task 2 acceptance criterion anticipates (the connect handler "runs the PKCE init").

## Deferred Issues

- **Pre-existing `ChatPage.tsx` lint errors** (`react-hooks/set-state-in-effect`, 4 errors): surfaced by the Task 2/3 `npm run lint` verify step. Confirmed pre-existing on commit `f30b364` via `git stash` — in a file this plan does not touch, so out of scope per the SCOPE BOUNDARY rule. Logged to `.planning/phases/10-oauth-pkce-backend-exchange-frontend-connect/deferred-items.md` (D-10-A). The new plan files are lint-clean; the build (the plan's hard gate) is green.

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. All four registered threats are mitigated and verified:

- **T-10-08** (CSRF / callback session fixation): SPA generates `state` via `randomString(32)`, stores it in sessionStorage, and `OAuthCallbackPage` rejects when `returnedState !== storedState` before the exchange POST. Verified by grep (`!==` state check present; exchange is inside the post-check branch).
- **T-10-09** (sk-or-v1-… leaking to Sentry events/breadcrumbs/URL): `/sk-or-v1-[A-Za-z0-9_-]+/g → '[redacted-key]'` applied in `beforeSend` (message, exception values, request.url incl. the callback URL) + `beforeBreadcrumb` (message, data). Frontend half of SEC-01.
- **T-10-10** (raw exchange error / key rendered into the failure UI): failure copy is the hard-coded locked sentence; the caught error is never interpolated (grep confirms no `error.message`/`String(e)` in JSX).
- **T-10-11** (verifier/state in localStorage / lost on refresh): sessionStorage only — the callback reads from sessionStorage so a hard-refresh re-runs successfully (D-07). Zero `localStorage` usage in any new file.

## Issues Encountered

- The repo-wide `npm run lint` fails on 4 pre-existing `react-hooks/set-state-in-effect` errors in `ChatPage.tsx` (a rule promoted to error by a newer `eslint-plugin-react-hooks` after Phase 8). These are not caused by this plan (reproduced on the prior commit) and are out of scope — handled per the Deferred Issues section. The plan's hard verification gate (`npm run build`) is green, and the five files this plan created/modified are individually lint-clean.

## User Setup Required

None. The Connect flow redirects to `openrouter.ai/auth` at click time and consumes the already-live Plan 02 backend endpoints; no new env var or external config. (These pages are not yet reachable in the running app — routing, the IconSidebar gear, and the header dot are wired in Plan 04.)

## Next Phase Readiness

- The two new pages + the `useKeyStatus` hook are built and build-clean — Plan 04 wires them into `App.tsx` (`/settings` + `/settings/openrouter/callback` routes under `ProtectedRoute`), adds the IconSidebar/IconNavRow gear, and hosts the connection dot (consuming `useKeyStatus`) in the chat header / MobileTopBar.
- The OAuth round-trip is end-to-end ready to test once Plan 04 makes `/settings` reachable: Connect → OpenRouter auth screen → callback → exchange → redirect+toast.
- **Carry-forward for deploy:** unchanged from Plan 02 — migration 028 must be applied to PROD before the exchange endpoint runs there (D-03). No new frontend env var introduced.

## Self-Check: PASSED

- `frontend/src/lib/pkce.ts` — FOUND
- `frontend/src/lib/sentry.ts` — FOUND (modified; sk-or scrub + existing rules present)
- `frontend/src/hooks/useKeyStatus.ts` — FOUND
- `frontend/src/pages/SettingsPage.tsx` — FOUND
- `frontend/src/pages/OAuthCallbackPage.tsx` — FOUND
- Commit `f30b364` (feat: pkce + sentry scrub) — FOUND
- Commit `c7ebb1a` (feat: useKeyStatus + SettingsPage) — FOUND
- Commit `a2fa199` (feat: OAuthCallbackPage) — FOUND
- `npm run build` — exit 0; new/modified files lint-clean (npx eslint exit 0)

---
*Phase: 10-oauth-pkce-backend-exchange-frontend-connect*
*Completed: 2026-06-19*
