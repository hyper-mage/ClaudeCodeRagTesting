---
phase: 07-observability-baseline
plan: "01"
subsystem: observability
tags: [sentry, vite, react, source-maps, pii-scrub, cloudflare-pages, frontend]

# Dependency graph
requires:
  - phase: 05-deploy-frontend-to-cloudflare-pages
    provides: Vite build pipeline + CF Pages deploy with CF_PAGES_COMMIT_SHA env var
  - phase: 06-prod-wiring-auth-cors-rate-limiting-cost-caps
    provides: Supabase auth flow (the JWT/email/UUID surface that beforeSend now scrubs)
provides:
  - "@sentry/react ^10.53.1 installed (dependencies) — client error capture SDK"
  - "@sentry/vite-plugin ^5.3.0 installed (devDependencies) — build-time source-map upload + release tagging"
  - "frontend/src/lib/sentry.ts — Sentry init singleton with DSN-guarded no-op + beforeSend/beforeBreadcrumb PII scrub + no Sentry.setUser"
  - "frontend/vite.config.ts — sentryVitePlugin LAST in plugins[]; release.name from CF_PAGES_COMMIT_SHA; sourcemaps deleted after upload; disabled outside CF Pages; build.sourcemap=true"
  - "frontend/src/main.tsx — side-effect import './lib/sentry' before createRoot"
affects:
  - 07-02 (backend Sentry SDK — mirrors PII scrub contract)
  - 07-03 (LangSmith trace correlation — may want to attach Sentry event_id)
  - 07-04 (Sentry dashboard provisioning + deployed smoke; will reuse VITE_SENTRY_DSN / SENTRY_ORG / SENTRY_PROJECT / SENTRY_AUTH_TOKEN / CF_PAGES_COMMIT_SHA env keys)
  - 07-05 (env-var documentation pass)

# Tech tracking
tech-stack:
  added:
    - "@sentry/react@^10.53.1"
    - "@sentry/vite-plugin@^5.3.0"
  patterns:
    - "DSN-guarded no-op init (mirrors backend/services/tracing.py:9-10 early-return)"
    - "Build-time release tagging via process.env.CF_PAGES_COMMIT_SHA (not import.meta.env — vite.config.ts runs in Node)"
    - "PII scrub via beforeSend + beforeBreadcrumb at SDK boundary, before events leave the browser"
    - "Vite plugin ordering: instrumentation plugins LAST so they see the final emitted bundle (Pitfall 1)"
    - "Source-map upload-then-delete (filesToDeleteAfterUpload) — maps to Sentry, never to CDN (Pitfall 2)"

key-files:
  created:
    - "frontend/src/lib/sentry.ts (70 lines)"
  modified:
    - "frontend/src/main.tsx (+1 line — side-effect import)"
    - "frontend/vite.config.ts (+19 / -1 — plugin import, plugin call, build.sourcemap)"
    - "frontend/package.json (+2 lines — @sentry/react, @sentry/vite-plugin)"
    - "frontend/package-lock.json (+529 lines — npm-managed)"

key-decisions:
  - "Side-effect import of './lib/sentry' from main.tsx (not a function call) — matches RESEARCH §Code Example §1 module-top init"
  - "No release.name in Sentry.init options — let vite-plugin's release.inject:true (default) inject CF_PAGES_COMMIT_SHA at build time"
  - "Explicit release.name: process.env.CF_PAGES_COMMIT_SHA in vite-plugin options — auto-detect does NOT cover CF Pages (RESEARCH OQ1)"
  - "disable: !process.env.CF_PAGES — plugin never runs on local builds (Pitfall 9), keeps SENTRY_AUTH_TOKEN out of dev surface"
  - "No replay integration; tracesSampleRate 0.1 — Sentry free-tier 5k-error quota envelope (Pitfall 8)"
  - "Sentry.setUser is forbidden everywhere in frontend — anonymity per CONTEXT D-1; grep-verified zero matches"

patterns-established:
  - "PII scrub at SDK boundary: any third-party observability SDK that ships events to a SaaS provider gets a beforeSend/beforeBreadcrumb (or equivalent) scrub before init; never relies on dashboard-side rules"
  - "Build secret discipline: any build-time secret (SENTRY_AUTH_TOKEN) reads from process.env in vite.config.ts (Node-side); never from import.meta.env (would inline into bundle)"
  - "DSN-guarded no-op pattern: an observability init module is a top-level no-op when its DSN env var is unset — matches backend/services/tracing.py"

requirements-completed: [OBS-01]

# Metrics
duration: 14min
completed: 2026-05-16
---

# Phase 07 Plan 01: Sentry Frontend Integration Summary

**`@sentry/react` initialized before React mount with DSN-guarded no-op, JWT/email/UUID scrub in `beforeSend`+`beforeBreadcrumb`, and `@sentry/vite-plugin` configured to upload then delete source maps tagged by CF Pages commit SHA.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-05-16T05:19:26Z
- **Completed:** 2026-05-16T05:33:02Z
- **Tasks:** 3 / 3
- **Files modified:** 5 (2 created/new, 3 modified)

## Accomplishments

- Frontend bundle now initializes Sentry (browser tracing only — no replay) before any React rendering can throw, so unhandled errors and unhandled promise rejections are captured from the very first frame.
- PII scrub is enforced at the SDK boundary inside the browser: `Authorization` headers (which carry full Supabase JWTs embedding user UUID + email + role) are replaced with `[redacted]` in both error events and fetch/xhr breadcrumbs; console breadcrumbs that mention the Supabase `sb-<ref>-auth-token` localStorage key are dropped entirely; any auto-attached `event.user` is stripped.
- Build-time source-map upload is wired through `@sentry/vite-plugin` configured to run LAST in the plugin array, only when `CF_PAGES` is set, with release tagged by `CF_PAGES_COMMIT_SHA` and `dist/**/*.map` files deleted after upload — so production stack traces will symbolicate in the Sentry dashboard without leaking maps to the public CDN.
- Threat surface T-07-05 (`SENTRY_AUTH_TOKEN` leak into runtime bundle) is closed by Node-side `process.env` reads in `vite.config.ts`; defense-in-depth `grep -r "SENTRY_AUTH_TOKEN" dist/` returns zero matches on the local build.

## Task Commits

Each task was committed atomically:

1. **Task 1: Install @sentry/react and @sentry/vite-plugin** — `a4f0000` (chore)
2. **Task 2: Author frontend/src/lib/sentry.ts init singleton with PII scrub** — `8b5b563` (feat)
3. **Task 3: Wire sentry init into main.tsx and configure vite.config.ts source-map upload** — `cc777e4` (feat)

## Files Created/Modified

- `frontend/src/lib/sentry.ts` (NEW, 70 lines) — Sentry init singleton; reads `VITE_SENTRY_DSN` at module top; no-op when unset; `beforeSend` redacts case-insensitive `authorization` headers and strips `event.user`; `beforeBreadcrumb` scrubs fetch/xhr `request_headers.authorization` and drops console breadcrumbs matching `/sb-[^-]+-auth-token/`; re-exports `Sentry`.
- `frontend/src/main.tsx` (MODIFIED, +1 line) — Side-effect import `'./lib/sentry'` inserted between `react-dom/client` import and `./index.css` import, so init runs before `createRoot`.
- `frontend/vite.config.ts` (MODIFIED, +19 / -1) — Imports `sentryVitePlugin`; appends it LAST in `plugins[]` (after `react()` + `tailwindcss()`); reads `SENTRY_ORG` / `SENTRY_PROJECT` / `SENTRY_AUTH_TOKEN` / `CF_PAGES_COMMIT_SHA` from `process.env`; `sourcemaps.filesToDeleteAfterUpload: ['./dist/**/*.map']`; `disable: !process.env.CF_PAGES`; adds `build: { sourcemap: true }` so the plugin has maps to upload.
- `frontend/package.json` (MODIFIED, +2 lines) — Adds `"@sentry/react": "^10.53.1"` to `dependencies`, `"@sentry/vite-plugin": "^5.3.0"` to `devDependencies`. No unrelated bumps.
- `frontend/package-lock.json` (MODIFIED, +529 lines) — npm-managed; regenerated to record the resolved trees of both new packages.

## Decisions Made

- **Side-effect import (no exported `initSentry()` function).** The plan's PATTERNS.md sketched a function-wrapped init; final shape per RESEARCH §Code Example §1 is a module-top `if (dsn) { Sentry.init(...) }`. Consumer (`main.tsx`) just imports the module for side effects. Rationale: matches the existing `frontend/src/lib/supabase.ts` analog (module-top side effect, no exported initializer), and lets Sentry's global error handlers register before any user code runs.
- **`release.name` lives in the vite-plugin options, NOT in `Sentry.init`.** The vite-plugin's `release.inject: true` default injects the release at build time. Declaring `release` in `Sentry.init` would override the plugin-injected value. (Decision documented as an inline comment in `sentry.ts`.)
- **`build.sourcemap: true` is a separate, independently-required key.** Without it, Vite emits no `.map` files for the plugin to upload, so the plugin silently produces a release with no symbols. Vite-plugin alone is not enough (RESEARCH Pitfall 1).
- **Plugin order: `sentryVitePlugin` is index 2 (LAST) after `react()` (0) and `tailwindcss()` (1).** Verified by line-number comparison in acceptance criteria — instrumentation plugins must see the final emitted bundle, otherwise source maps are produced from an intermediate stage and don't match what's served (RESEARCH Pitfall 1 / PATTERNS Pattern 2).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Comment in `sentry.ts` accidentally tripped the `Sentry.setUser` anonymity grep**

- **Found during:** Task 2 verification — `grep -rn "Sentry.setUser" frontend/src/` returned `1` match (required: `0`).
- **Issue:** A documentation comment at the top of `sentry.ts` literally said `(we never call Sentry.setUser)`, which made the substring-grep treat the file as a violation of CONTEXT D-1 even though no real call existed. The grep is the threat-model T-07-06 invariant; it must remain a clean zero across `frontend/src/`.
- **Fix:** Rephrased the comment to `(identity attachment is forbidden — D-1)` so the forbidden token never appears in the source tree, even in comments.
- **Files modified:** `frontend/src/lib/sentry.ts`
- **Verification:** Re-ran `grep -rn "Sentry.setUser" frontend/src/ | wc -l` → `0`. tsc/lint/build remained clean.
- **Committed in:** `8b5b563` (Task 2 commit, applied before the commit was created).

---

**Total deviations:** 1 auto-fixed (1 bug — grep invariant compliance).
**Impact on plan:** Cosmetic comment rewrite; the implementation behavior was already correct. Zero scope creep.

## Issues Encountered

- **Worktree was branched from a commit predating Phase 07 planning artifacts.** The `worktree-agent-a9f9f4c6b7933a53f` branch was created from a commit before `7899216 docs(07): create 5 plans + ROADMAP update`, so the `.planning/phases/07-observability-baseline/` directory and the updated `STATE.md` / `ROADMAP.md` were absent in the worktree. Resolved by `git checkout master -- .planning/phases/07-observability-baseline/ .planning/STATE.md .planning/ROADMAP.md` to materialize the plan files into the worktree's working tree (no commit yet — those will reconcile when the worktree merges back). No impact on execution.
- **4 pre-existing ESLint errors surfaced on `npm run lint`** in `FileUpload.tsx`, `AuthContext.tsx`, `ToastContext.tsx`, `ChatPage.tsx`. All four are tracked in `.planning/phases/06.1-mobile-responsive-chat-layout/deferred-items.md` and live in files this plan does not modify. Out of scope per execute-plan SCOPE BOUNDARY rule; no new lint errors introduced by this plan.

## Verification Outcomes

| Check | Result |
|------|--------|
| `cd frontend && npx tsc --noEmit --project tsconfig.app.json` | 0 errors |
| `cd frontend && npm run build` | succeeded (6.71s, dist + sourcemaps emitted; plugin disabled outside CF Pages, expected) |
| `cd frontend && npm run lint` | 4 errors — ALL pre-existing in phase 06.1 deferred-items.md (no new errors introduced) |
| `cd frontend && npm ls @sentry/react @sentry/vite-plugin` | both present at expected versions |
| `grep -rn "Sentry.setUser" frontend/src/` | 0 matches (CONTEXT D-1 anonymity invariant) |
| `grep -rn "replaysSessionSampleRate\|replayIntegration\|replayCanvasIntegration" frontend/src/` | 0 matches (Pitfall 8 — no replay) |
| `grep -c "sentryVitePlugin\|sourcemap: true" frontend/vite.config.ts` | 4 (≥ 2 required) |
| `grep -r "SENTRY_AUTH_TOKEN" frontend/dist/` | 0 matches (T-07-05 build-secret leak guard) |
| `git diff --stat HEAD~3 HEAD -- frontend/` | exactly the 5 expected files; no others |
| Plugin order: `sentryVitePlugin` line > `react()` AND `tailwindcss()` lines | line 13 > line 8 and line 9 — OK |
| main.tsx: `'./lib/sentry'` line < `createRoot(` line | line 3 < line 7 — OK |

## User Setup Required

None for this plan — all in-repo code changes. The four CF Pages **Build**-scope env vars (`VITE_SENTRY_DSN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN`) and the deployed-bundle smoke test are scope of Plan 07-04 (Sentry dashboard provisioning + deployed-error verification).

## Next Phase Readiness

- **07-02 (backend Sentry SDK):** Can now compose against the same `VITE_SENTRY_DSN` → `SENTRY_DSN` env pattern and replicate the same PII scrub contract (`Authorization` → `[redacted]`, no `set_user`).
- **07-04 (dashboard + deployed smoke):** Frontend code half of OBS-01 is complete. 07-04 needs to (a) create the Sentry project, (b) set the four Build-scope env vars in CF Pages, (c) trigger a CF Pages rebuild, (d) `curl -I https://<app>.pages.dev/assets/<hash>.js.map` must return 404 (T-07-04 regression), and (e) intentionally throw a frontend error and confirm it lands in the Sentry dashboard with the JWT scrubbed.
- **No blockers** for downstream Phase 07 plans.

## Self-Check: PASSED

- `frontend/src/lib/sentry.ts` exists — FOUND
- `frontend/src/main.tsx` updated with sentry import — FOUND
- `frontend/vite.config.ts` updated with plugin — FOUND
- `frontend/package.json` has both packages — FOUND
- Commit `a4f0000` (Task 1) — FOUND in git log
- Commit `8b5b563` (Task 2) — FOUND in git log
- Commit `cc777e4` (Task 3) — FOUND in git log

---
*Phase: 07-observability-baseline*
*Plan: 07-01*
*Completed: 2026-05-16*
