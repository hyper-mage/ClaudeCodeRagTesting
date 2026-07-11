---
phase: 15-options-ui-capstone-demo-gating
plan: 03
subsystem: ui
tags: [react, oauth, pkce, sessionstorage, vitest, testing-library, openrouter]

# Dependency graph
requires:
  - phase: 10-oauth-pkce-backend-exchange-frontend-connect
    provides: OAuthCallbackPage exchange flow, startOpenRouterConnect PKCE helper, sessionStorage verifier/state contract
  - phase: 13-preferences-per-thread-model
    provides: PATCH /api/threads/{id} {model} and PUT /api/preferences {default_model} apply endpoints
  - phase: 12-model-cache-catalog
    provides: GET /api/models catalog (display-name resolution for the toast label)
provides:
  - One-shot or_pending_selection resume in OAuthCallbackPage (D-02) — thread PATCH / prefs PUT after a successful exchange
  - Locked combined/warning toast wiring (UI-SPEC copywriting, ${label} only interpolation)
  - returnTo allowlist navigation guard ({'/', '/settings'}, SPA navigate only) — T-15-10
  - Back-to-settings stash clear on abandon; Retry preserves the stash
  - OAuthCallbackPage.test.tsx — 9-case resume lifecycle matrix (RESEARCH Wave-0 gap closed)
affects: [15-05 (useKeyGate stash writer — shares only the string contract), 15-08 (phase verification)]

# Tech tracking
tech-stack:
  added: []
  patterns: [one-shot sessionStorage stash (removeItem-before-apply), returnTo allowlist at read time, mocked useNavigate via vi.hoisted for imperative-navigation page tests]

key-files:
  created:
    - frontend/src/pages/OAuthCallbackPage.test.tsx
  modified:
    - frontend/src/pages/OAuthCallbackPage.tsx

key-decisions:
  - "Stash consumed inside the existing ranRef-guarded effect: removeItem FIRST, then parse, then apply — one-shot holds even when JSON.parse or the apply throws"
  - "Toast label resolved best-effort from GET /api/models (name ?? id); ANY catalog failure silently falls back to the raw modelId — no error surfaced (SEC-01)"
  - "Apply failure degrades to the locked warning toast + navigation; the failure screen is reserved for exchange errors only (connection succeeded)"
  - "Navigation target derived through RETURN_TO_ALLOWLIST ['/', '/settings'] — non-allowlisted returnTo (absolute URLs, other paths) forced to /settings via SPA navigate()"
  - "useNavigate mocked via vi.hoisted + partial react-router-dom mock (ChatPage.test.tsx has no navigation-assert precedent — plan-sanctioned fallback)"

patterns-established:
  - "One-shot stash: sessionStorage.removeItem before the consuming action so replays are impossible (Pitfall 6)"
  - "Page tests for window.location.search readers: seed the jsdom URL via history.replaceState beside MemoryRouter initialEntries"

requirements-completed: [KEY-05]

# Metrics
duration: 16min
completed: 2026-07-06
---

# Phase 15 Plan 03: OAuthCallbackPage Pending-Selection Resume Summary

**One-shot `or_pending_selection` resume in OAuthCallbackPage: after a successful OpenRouter exchange the pre-OAuth model pick auto-applies (thread PATCH / prefs PUT) with the locked combined toast and allowlisted returnTo navigation — 9 lifecycle tests, full FE suite 65/65 green.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-07-06T01:21:52Z
- **Completed:** 2026-07-06T01:38:00Z
- **Tasks:** 2 (TDD RED → GREEN)
- **Files modified:** 2 source files (+ deferred-items.md, SUMMARY.md)

## Accomplishments

- D-02 resume shipped: the user's original pick (the model chosen before being sent to OAuth) completes without re-picking — `kind:'thread'` → `PATCH /api/threads/{threadId} {model}`, otherwise `PUT /api/preferences {default_model}`, each with its locked success toast (`Connected — ${label} …`), label = catalog display name with silent raw-id fallback
- One-shot guarantee: `removeItem('or_pending_selection')` runs BEFORE parse/apply, so a throw anywhere in the resume can never replay it; apply failure fires the locked warning toast and STILL navigates — the failure screen never renders for an apply error
- T-15-10 mitigation: `returnTo` constrained to `['/', '/settings']` at read time, consumed only via SPA `navigate()` — stash-injected absolute URLs / arbitrary paths land on `/settings`
- Failure-screen lifecycle locked in: "Back to settings" now clears the stash (abandon); Retry left untouched so the stash survives naturally (startOpenRouterConnect rewrites only verifier/state)
- Legacy no-stash and malformed-stash paths byte-identical to Phase 10 behavior (`OpenRouter connected.` → `/settings`)
- New `OAuthCallbackPage.test.tsx` (252 lines, 9 cases) closes the RESEARCH Wave-0 coverage gap: both apply surfaces, removal-before-apply ordering (asserted from inside the rejecting PATCH mock), label fallback, allowlist (`https://evil.example`, `/other`), legacy/malformed paths, Back-clears/Retry-preserves

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — resume lifecycle test matrix** - `329ce87` (test)
2. **Task 2: GREEN — one-shot resume implementation** - `58dc4a4` (feat)

## TDD Gate Compliance

RED gate: `329ce87` — 7 resume tests failed (exit 1), 2 legacy-behavior tests passed, failures confined to resume behavior per acceptance criteria. GREEN gate: `58dc4a4` — 9/9 pass. No refactor commit needed.

## Files Created/Modified

- `frontend/src/pages/OAuthCallbackPage.test.tsx` - 9-case resume lifecycle matrix (MemoryRouter + mocked useNavigate/api/pkce, jsdom URL seeded via history.replaceState, locked toast strings asserted byte-exact incl. em-dash)
- `frontend/src/pages/OAuthCallbackPage.tsx` - `PendingSelection` interface, `RETURN_TO_ALLOWLIST`, `parsePendingSelection` helper, one-shot resume block replacing the fixed toast+navigate, stash clear on Back-to-settings

## Decisions Made

- Stash parse isolated in a module-level `parsePendingSelection` helper returning `PendingSelection | null` — keeps TS narrowing intact inside the `models.find` closure (a `let` + inline try/catch loses narrowing in callbacks)
- `expect.anything()`-style negative assertion used for the allowlist test (`mockNavigate` never called with the evil returnTo) in addition to the positive `/settings` assertion

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed frontend dependencies in the fresh worktree**
- **Found during:** Task 1 (RED verify)
- **Issue:** parallel-executor worktree had no `frontend/node_modules` (gitignored, not shared with the main checkout) — vitest could not start
- **Fix:** `npm ci` in `frontend/` (lockfile-pinned, no repo file changes)
- **Files modified:** none (environment only)
- **Verification:** vitest runs; full suite 65/65 after GREEN
- **Committed in:** n/a (no tracked-file change)

---

**Total deviations:** 1 auto-fixed (1 blocking, environment-only)
**Impact on plan:** None — no scope creep, no tracked-file changes outside the plan's two files.

## Deferred Issues

- **Full-repo `npm run lint` exits 1 with 5 pre-existing errors** — all in files untouched by this plan (`FileUpload.tsx`, `AuthContext.tsx`, `ToastContext.tsx`, `ChatPage.tsx` (= known D-13-06-A), `themeBootstrap.test.ts`). The plan's own files lint clean (`npx eslint` on both exits 0). Logged as **D-15-03-A** in `deferred-items.md`; out of scope per the scope boundary. The Task 2 acceptance criterion "npm run lint exit 0" is met for the plan's surface but not for the whole repo due to this pre-existing debt.

## Issues Encountered

None beyond the deferred pre-existing lint debt above.

## Known Stubs

None — no placeholder text, no hardcoded empty data flowing to UI. The stash-WRITER (`useKeyGate`, plan 15-05) does not exist yet by design; the two plans share only the locked `or_pending_selection` string contract, and the resume is fully exercised by tests seeding the stash directly.

## Requirements Note

`requirements-completed` lists KEY-05 per this plan's frontmatter, but KEY-05 ("selecting a model with no connected key triggers the OAuth connect flow") spans plans 15-03 (resume half, done) AND 15-05 (gate + stash-writer half). The orchestrator should mark KEY-05 complete only once 15-05 also lands. REQUIREMENTS.md intentionally not modified here (worktree mode — orchestrator owns shared-file writes).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The consume side of the locked stash contract is live and fully tested; plan 15-05's `useKeyGate` can write `{kind, modelId, threadId?, returnTo}` and get the D-02 auto-apply for free
- Verification (15-08) can assert the full connect→resume loop once 15-05 merges
- No blockers introduced; pre-existing lint debt tracked in D-15-03-A

## Self-Check: PASSED

- `frontend/src/pages/OAuthCallbackPage.test.tsx` — FOUND
- `frontend/src/pages/OAuthCallbackPage.tsx` (contains `or_pending_selection`, removeItem-before-apply, allowlist) — FOUND
- Commit `329ce87` (test) — FOUND
- Commit `58dc4a4` (feat) — FOUND
- Targeted vitest exit 0 (9/9), full suite 65/65, `npm run build` exit 0 — VERIFIED

---
*Phase: 15-options-ui-capstone-demo-gating*
*Completed: 2026-07-06*
