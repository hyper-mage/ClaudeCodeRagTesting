---
phase: 5
slug: deploy-frontend-to-cloudflare-pages
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — frontend has no test framework (per CLAUDE.md / package.json). Verification is build + manual browser checklist. |
| **Config file** | none |
| **Quick run command** | `cd frontend && npm run build` (TypeScript check + Vite build) |
| **Full suite command** | Manual browser checklist (CONTEXT.md D-13, 5 steps) |
| **Lint** | `cd frontend && npm run lint` |
| **Estimated runtime** | ~30s for build; ~5min for manual D-13 checklist |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm run build` — confirms TS strict + Vite build still pass and `_redirects` lands in `dist/`.
- **After every plan wave:** Push to `main`; CF Pages auto-builds; verify green status in CF dashboard "Deployments" tab.
- **Before `/gsd:verify-work`:** Manual D-13 5-step browser checklist passes + CORS update digest confirmed via `flyctl secrets list` + post-deploy bundle leak grep returns zero hits.
- **Max feedback latency:** ~30s for local build; ~2min for CF deploy round-trip.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | DEPLOY-05 | smoke | `test -f frontend/public/_redirects && grep -q '^/\* /index.html 200$' frontend/public/_redirects` | ❌ W0 | ⬜ pending |
| 5-01-02 | 01 | 1 | DEPLOY-05 | smoke | `cd frontend && npm run build && test -f dist/_redirects` | ❌ W0 | ⬜ pending |
| 5-01-03 | 01 | 1 | DEPLOY-05 | manual-only | CF Pages dashboard: project created, GitHub connected, build settings + env vars + Production-only branch deploy configured | ✅ | ⬜ pending |
| 5-01-04 | 01 | 1 | DEPLOY-05 | manual-only | CF Pages dashboard: latest deployment from `main` shows green status | ✅ | ⬜ pending |
| 5-01-05 | 01 | 1 | DEPLOY-05 | smoke | `curl -fsS https://boardgame-rag-prod.pages.dev/_redirects` returns `/* /index.html 200` | ✅ (post-deploy) | ⬜ pending |
| 5-01-06 | 01 | 1 | DEPLOY-05 | smoke | `curl -fsSI https://boardgame-rag-prod.pages.dev/documents \| grep -i 'content-type: text/html'` (proves SPA fallback for deep route) | ✅ (post-deploy) | ⬜ pending |
| 5-01-07 | 01 | 1 | DEPLOY-05 | smoke | `flyctl secrets list -a boardgame-rag-prod \| grep CORS_ALLOWED_ORIGINS` shows updated digest after `flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod` | ✅ | ⬜ pending |
| 5-01-08 | 01 | 1 | DEPLOY-05 / SEC-07 | smoke | `curl -s https://boardgame-rag-prod.pages.dev/assets/index-*.js \| grep -Ei 'service_role\|sk-proj\|sk-or-\|sb_secret_'` returns no match (re-run Phase 1 leak guard against prod bundle) | ✅ (post-deploy) | ⬜ pending |
| 5-01-09 | 01 | 1 | DEPLOY-05 | manual-only | D-13 browser checklist: login renders, Network tab shows absolute Fly URL, hard-refresh `/documents` renders SPA, send chat → SSE streams without CORS error | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Plan/task IDs are placeholders — gsd-planner finalizes exact numbering. Mapping survives renumbering because every row is keyed to a verifiable command.*

---

## Wave 0 Requirements

- [ ] `frontend/public/_redirects` — single line `/* /index.html 200`. Covers DEPLOY-05 deep-link refresh and tasks 5-01-01 / 5-01-02 / 5-01-05 / 5-01-06.
- [ ] (Optional, Claude's discretion per CONTEXT.md) `frontend/.nvmrc` — Node 20 for local-dev consistency. Not required by phase success criteria.
- [ ] No test framework install — frontend has none; adding one is out of scope per phase boundary.

*Wave 0 is intentionally tiny: only one mandatory file create. CF Pages dashboard + Fly secret are out-of-repo configuration captured in plan tasks 5-01-03 / 5-01-04 / 5-01-07.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CF Pages project + GitHub integration created | DEPLOY-05 | Out-of-repo dashboard configuration; no API automation in this phase per D-01 | Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git → select repo → set production branch `main`, root dir `frontend`, build cmd `npm run build`, output `dist`, env var `NODE_VERSION=20`, plus three `VITE_*` vars (Production scope) → Save and Deploy |
| First green CF deploy from `main` | DEPLOY-05 success criterion #1 | CF dashboard shows the build log; pass = "Success" status visible in Deployments tab | After Save and Deploy: wait for build to complete; verify status = "Success" in CF Pages dashboard Deployments tab |
| Preview deploys disabled | CONTEXT D-07 | CF dashboard setting; verifies non-production branches don't auto-deploy | Settings → Builds & deployments → Configure Preview deployments → "None" |
| Browser end-to-end (D-13 5 steps) | DEPLOY-05 success criteria #4 + cross-validates CORS update | Requires real browser DevTools (Network tab inspection, console error check, SSE stream observation) — no headless equivalent in scope this phase | (1) Load `https://boardgame-rag-prod.pages.dev` — login renders, no console errors. (2) DevTools Network → confirm requests target `https://boardgame-rag-prod.fly.dev/api/...`. (3) Log in as `ragtest1@gmail.com` / `testpass123`. (4) Navigate to `/documents`, hard-refresh — SPA renders, not CF 404. (5) Send chat — SSE streams without CORS error in console. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (manual-only tasks documented above with explicit "why manual" rationale)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (5-01-03 / 5-01-04 are consecutive manual-only — both are CF dashboard config; bracketed by automated 5-01-02 before and 5-01-05 after)
- [ ] Wave 0 covers all MISSING references (`_redirects` is the only file create)
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter (after gsd-plan-checker pass)

**Approval:** pending
