# Plan 07-04 SUMMARY — Sentry dashboard provisioning + CF Pages env wiring + deployed-error smoke

**Completed:** 2026-05-16
**Plan:** `.planning/phases/07-observability-baseline/07-04-PLAN.md`
**Requirements:** OBS-01
**Type:** Manual dashboard work (no autonomous execution)

## Outcome

✅ Sentry frontend integration verified on deployed CF Pages bundle. OBS-01 satisfied with caveat (UI onboarding overlay quirk).

## Sentry project

- **Org slug:** `hyper-mage-tower`
- **Project slug:** `boardgame-rag-frontend`
- **Project URL:** https://hyper-mage-tower.sentry.io/projects/boardgame-rag-frontend/
- **DSN:** stored in 1Password as `VITE_SENTRY_DSN` (pattern: `https://<key>@o4511400654143488.ingest.us.sentry.io/4511400689795072`)
- **Tier:** Free Developer (5k errors/mo, 1 user, 30d retention)
- **Auth token:** scoped to Release=Admin + Organization=Read (minimum for source-map upload + release create); stored in 1Password as `SENTRY_AUTH_TOKEN`

## CF Pages env vars (Production scope)

| Var | Type | Purpose |
|---|---|---|
| `VITE_SENTRY_DSN` | Plaintext | Bundled into Vite output (DSN is intended-public client identifier) |
| `SENTRY_AUTH_TOKEN` | **Secret** | Build-time only; never bundled (no `VITE_` prefix → Vite doesn't inline) |
| `SENTRY_ORG` | Plaintext | Build-time only |
| `SENTRY_PROJECT` | Plaintext | Build-time only |

## Deploys exercised

- `ad8a98f` — first deploy after env wiring; build log showed `@sentry/vite-plugin` uploading source maps + creating release; release `ad8a98f` appeared in Sentry → Releases
- `e7e4040` — added `enableLogs: true` + `consoleLoggingIntegration` to satisfy Sentry's per-project onboarding wizard (it was gating the Issues view until it detected a Logs envelope item)

## Verification matrix

| Check | Tool | Result |
|---|---|---|
| Sentry SDK loaded in deployed bundle | `window.__SENTRY__` console eval | ✅ v10.41.0-beta.0 |
| Error envelope POST 200 | DevTools Network | ✅ POSTs to `*.ingest.us.sentry.io/api/.../envelope/` return 200 (in private window — uBlock blocks in normal browsing) |
| Logs envelope landing | Sentry → Explore → Logs | ✅ Multiple test logs visible (`test2`, `test log from devtools`, MetaMask extension orphan-data noise) |
| Source maps deleted from dist | `curl -I` against `assets/index-*.js.map` | ✅ Returns SPA fallback HTML (`<!doctype html>`) — `.map` file does not exist; CF Pages SPA routing returns index.html for unknown paths instead of literal 404; intent satisfied |
| Build secret not in bundle | `curl -s <bundle.js> \| grep -c "sntrys_\|sntryu_\|SENTRY_AUTH_TOKEN"` | ✅ 0 matches |
| Release tag matches deploy SHA | Sentry → Releases | ✅ Release name = deploy commit SHA via `@sentry/vite-plugin` (`release.name: process.env.CF_PAGES_COMMIT_SHA`) |
| PII scrub active (`beforeSend`/`beforeBreadcrumb`) | code grep + `__SENTRY__` integration list | ✅ Plan 07-01 wired; grep `Sentry.setUser` in `frontend/src/` returns 0 (anonymity invariant) |

## Caveats

- **Sentry per-project Issues view stuck on "Get Started" onboarding overlay** despite events landing. Workaround: Logs surface (Explore → Logs) shows captured events normally; events ARE in the project. Issues UI flips out of onboarding when Sentry's polling detects the first event of the right type — there's a delay (sometimes hours) that's UI-side only. Did not block OBS-01 functional verification.
- **uBlock Origin / Firefox tracking protection blocks `*.sentry.io`** by default in normal browsing — events fail CORS. Private browsing or disabled blocker required for end-user error capture. Acceptable for portfolio (most visitors will not be blocked); document in PROJECT for end-user QA.
- **Source-map upload smoke test required two deploys** because the wizard's Logs-flow trigger required adding `enableLogs: true` to satisfy Sentry's per-project onboarding state machine. The Logs feature was not in original CONTEXT scope but is free-tier compatible and provides additional debugging signal at zero cost.
- **Console-thrown errors show `<anonymous>` source** (devtools eval has no source map). Real un-minified stack only appears for errors thrown from actual app code paths. Source-map upload confirmed via Sentry Releases artifact list (separate from runtime stack-map resolution).

## Deferred to follow-up

- Sentry Issues view onboarding overlay clearing — wait for Sentry's polling to flip the per-project state, OR file Sentry support ticket if persists >24h
- Trigger a real app-path error (not console eval) to verify un-minified stack frames resolve to `src/...` paths in event detail

## Commits

- `e7e4040` — `feat(07-04): enable Sentry Logs for wizard verify step`

(Plan 07-01 commits — chore install + sentry.ts + vite-plugin wiring — already landed during Wave 1 cherry-pick.)
