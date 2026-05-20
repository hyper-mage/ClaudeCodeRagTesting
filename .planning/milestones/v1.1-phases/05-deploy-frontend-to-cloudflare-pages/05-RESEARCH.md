# Phase 5: Deploy Frontend to Cloudflare Pages — Research

**Researched:** 2026-05-05
**Domain:** Static SPA hosting on Cloudflare Pages (Vite 6 / React 19 / Tailwind 4) + cross-origin wiring to Fly backend
**Confidence:** HIGH

## Summary

Phase 5 ships the existing Vite SPA to `https://boardgame-rag-prod.pages.dev` via Cloudflare Pages' GitHub git integration, points it at the Phase 4 Fly backend (`https://boardgame-rag-prod.fly.dev`) by injecting `VITE_API_BASE_URL` at build time, and overwrites Fly's `CORS_ALLOWED_ORIGINS` placeholder with the CF origin so cross-origin SSE chat actually works in a browser. All decisions are locked in `05-CONTEXT.md` — research here is **prescriptive** (how to execute the locked decisions correctly), not exploratory.

The phase is small in code surface (one new file: `frontend/public/_redirects`; optional `frontend/.nvmrc`) but has a few pieces of out-of-repo configuration (CF Pages dashboard + one `flyctl secrets set` call) that are easy to misconfigure silently. The biggest verification gotchas are: (a) confirming the Network tab shows absolute Fly URLs (not same-origin `/api`, which would mean `VITE_API_BASE_URL` didn't get baked in), and (b) confirming a hard-refresh on `/documents` returns the SPA, not a 404.

**Primary recommendation:** Pin `NODE_VERSION=20` on CF Pages (matches the local `node v20.14.0` that produced `package-lock.json`), commit `frontend/public/_redirects` with `/* /index.html 200` (Vite copies it verbatim to `dist/_redirects`), and run `flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod` only **after** the first green CF deploy confirms the URL.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Git auto-deploy via Cloudflare Pages GitHub integration on push to `main`. Build settings + env vars configured once in CF dashboard. No `wrangler` CLI auth on the developer laptop.
- **D-02:** Production branch = `main`. Preview/PR deploys disabled (D-07). Only `main` produces a public deployment.
- **D-03:** CF Pages project slug = `boardgame-rag-prod`. Public URL = `https://boardgame-rag-prod.pages.dev`. Naming consistent with Fly + Supabase + LangSmith.
- **D-04:** No custom domain in this phase. Default `*.pages.dev` is sufficient.
- **D-05:** CF Pages build config: root directory = `frontend/`, build command = `npm run build`, output directory = `dist`.
- **D-06:** Node version pinned via env var `NODE_VERSION` on CF Pages. Planner verifies the lockfile-compatible Node version before pinning.
- **D-07:** Preview deploys (PR + non-`main` branch) disabled in CF Pages settings.
- **D-08:** Three env vars set in CF Pages dashboard, scoped to **Production** environment only:
  - `VITE_API_BASE_URL = https://boardgame-rag-prod.fly.dev` (no trailing slash)
  - `VITE_SUPABASE_URL = <prod Supabase URL>` (from `.env.prod`)
  - `VITE_SUPABASE_ANON_KEY = <prod Supabase anon key>` (from `.env.prod`)
- **D-09:** Anon key is fine to ship in the bundle (public, RLS-bound). Service-role key is NOT set anywhere in CF Pages.
- **D-10:** Commit `frontend/public/_redirects` with the single line `/* /index.html 200`. Vite copies `public/` to `dist/` at build time.
- **D-11:** Phase 5 owns the CORS update from Phase 4's placeholder. After the first green CF deploy: `flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod`.
- **D-12:** Single-origin CORS string only — no `localhost:5173` fallback in the prod allowlist.
- **D-13:** Manual browser verification, documented as a PLAN checklist (5 steps in CONTEXT).
- **D-14:** No scripted CF smoke harness this phase.

### Claude's Discretion

- Exact Node version pin in D-06 (planner reads lockfile + Vite/React reqs → picks LTS major).
- Whether to add `frontend/.nvmrc` alongside the CF Pages env var.
- Order of operations: connect repo first vs set env vars first.
- Whether to pre-create CF Pages project via Wrangler API or do it entirely in the dashboard.

### Deferred Ideas (OUT OF SCOPE)

- Custom domain on CF Pages — defer to v1.2+.
- Preview deploys with backend `allow_origin_regex` for CORS — deferred indefinitely.
- Scripted CF Pages smoke (`cf_smoke.sh`) — deferred. Phase 7 may add UptimeRobot pings instead.
- CORS rejection-path test (Phase 6 SEC-02).
- Wildcard / regex CORS for preview deploys — Phase 6 if previews ever re-enabled.
- `frontend/.nvmrc` — Claude's discretion at plan time.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-05 | Developer can push the frontend build to Cloudflare Pages and reach a public URL that loads the SPA with correct deep-link refresh behavior (`_redirects`). | CF Pages GitHub integration (§Standard Stack); `_redirects` syntax verified (§Code Examples); Node version pinning (§Standard Stack); CORS hand-off (§Architecture Patterns); manual browser verification flow (§Common Pitfalls). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **No LangChain/LangGraph** — out of scope here (frontend deploy only, no agent code).
- **No admin UI for config** — env vars only, set via CF Pages dashboard.
- **GSD workflow enforced** — file changes route through GSD commands.
- **Tech stack frozen** — React 19 + Vite 6 + Tailwind 4 + shadcn/ui; no swap.

## Standard Stack

### Core

| Library / Service | Version | Purpose | Why Standard |
|---|---|---|---|
| **Cloudflare Pages** | current (v3 build system) | Static SPA host | Unlimited bandwidth on free tier vs Vercel 100GB cap; native GitHub integration; built-in SPA fallback; supports `_redirects`. Locked by D-01. |
| **Cloudflare Pages v3 build image** | default | Build runner | Default Node 22.16.0; supports any Node via `NODE_VERSION` env var or `.nvmrc`. |
| **Vite** | `^6.4.1` (locked in `package.json`) | Build tool | Already used; produces `dist/` with `public/` contents copied verbatim. |
| **Node.js** | `20.14.0` (local) → pin **`NODE_VERSION=20`** on CF | Build runtime | `package-lock.json` lockfileVersion 3 was generated with Node 20 locally. Vite 6 supports Node 18.18+/20+/22+. React 19 has no separate Node requirement. Node 20 LTS is safe + matches local. CF default is Node 22, which would also work, but pinning prevents future drift. |

### Supporting

| Tool | Version | Purpose | When to Use |
|---|---|---|---|
| `flyctl` | latest (already installed Phase 4) | One-shot CORS secret update (D-11) | After first green CF deploy lands. |
| Browser DevTools | n/a | Manual verification (D-13) | Step in PLAN — Network tab + console + hard-refresh checks. |

### Alternatives Considered

| Instead of | Could Use | Why Not |
|---|---|---|
| CF Pages | Vercel | Locked out by `research/SUMMARY.md` — bandwidth cap and SSE-rewrite buffer concerns. |
| `_redirects` | CF Pages auto-SPA fallback (no top-level `404.html`) | CF Pages already auto-handles SPA routing when no `404.html` exists, so `_redirects` is technically redundant. **However**, D-10 locks it in as belt-and-suspenders insurance. Keep `_redirects`. |
| `NODE_VERSION` env var | `.nvmrc` file | Either works equivalently per CF docs. Plan uses env var (D-06). `.nvmrc` is Claude's discretion as a nice-to-have for local-dev consistency. |
| Wrangler CLI / API | Dashboard | Dashboard is fine for one-time setup. Wrangler would re-introduce CLI auth that D-01 explicitly avoids. |

**No installation step:** Phase 5 adds zero npm packages. Frontend bundle stays as-is.

**Version verification (locked tools):**
- `node --version` on local (build environment parity proxy): **`v20.14.0`** (verified 2026-05-05).
- CF Pages default Node: **22.16.0** (per CF docs, v3 build system, 2026).
- Vite 6 supported Node range: **18.18+ / 20+ / 22+** (Vite 6 docs).
- Recommendation: **`NODE_VERSION=20`** — matches lockfile-generating environment exactly. `22` is the CF default and also works; pick `20` for least drift risk.

## Architecture Patterns

### Recommended Project Structure

```
repo-root/
├── frontend/
│   ├── public/
│   │   ├── _redirects            ← CREATE (D-10): "/* /index.html 200"
│   │   ├── favicon.svg           (existing)
│   │   └── icons.svg             (existing)
│   ├── src/                      (no changes — Phase 1 already wired apiFetch/apiStream)
│   ├── package.json              (no changes)
│   ├── package-lock.json         (no changes)
│   ├── vite.config.ts            (no changes — envDir: '..' is dev-only)
│   └── .nvmrc                    ← OPTIONAL (Claude's discretion): "20"
└── (CF Pages dashboard config — out-of-repo)
```

### Pattern 1: GitHub Git Integration (Push-to-Deploy)

**What:** CF Pages connects to the GitHub repo, watches the production branch, runs `npm run build` on push, deploys output to `*.pages.dev`.
**When to use:** D-01 locks this in. No CLI / wrangler auth on dev laptop.
**Steps (dashboard, one-time):**
1. CF Dashboard → Workers & Pages → Create application → Pages → **Connect to Git** → authorize GitHub → select repo.
2. Set **Production branch** = `main`.
3. **Framework preset:** Vite (or "None" — both work; Vite preset just pre-fills the build command).
4. **Build command:** `npm run build`
5. **Build output directory:** `dist`
6. **Root directory (advanced):** `frontend` ← critical for D-05; without this CF runs `npm` at repo root and fails.
7. **Environment variables (Production scope only):** add three from D-08 + `NODE_VERSION=20` (D-06).
8. **Settings → Builds & deployments → Configure Production deployments → Preview branch control:** select **"None"** to disable preview deploys (D-07).
9. Save → first deploy auto-triggers from latest `main` commit.

### Pattern 2: `_redirects` for SPA Fallback (Belt-and-Suspenders)

**What:** A one-line file in `frontend/public/_redirects`:
```
/* /index.html 200
```
Vite's documented behavior: "Assets in [public/] are copied to the root of the dist directory as-is." So this lands at `dist/_redirects`, where CF Pages picks it up and serves `index.html` (200, not a redirect) for any unmatched path.

**Note (verified):** CF Pages' v3 build system **automatically** treats projects without a top-level `404.html` as SPAs and serves `index.html` for unknown routes. So `_redirects` is technically redundant for this app. **However**, D-10 explicitly commits the file as defensive insurance — if a future plan adds a `404.html`, the explicit `_redirects` rule keeps deep-link refresh working. Keep the file.

**When to use:** Always for an SPA on CF Pages. Locked by D-10.

### Pattern 3: CORS Hand-off (Phase 4 → Phase 5)

**What:** Phase 4 set `CORS_ALLOWED_ORIGINS=http://localhost:5173` as a placeholder. After Phase 5's first green CF deploy reveals the URL, overwrite:
```bash
flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod
```
**Behavior verified against Fly docs:**
- `flyctl secrets set` overwrites the existing key (no `unset` needed first).
- Triggers a single Fly machine restart with the new env.
- `flyctl secrets list` shows only key names + digests (not values) — verify by checking the digest changed vs the Phase 4 baseline, OR by running a CORS smoke from the new origin.

**Order matters:** Run this **after** the CF Pages deploy is live, not before. If you run it first and the CF deploy fails, the Fly backend will reject the only valid prod origin (localhost no longer in the list per D-12) — but since D-12 confirms backend has a `["http://localhost:5173"]` fallback only when `CORS_ALLOWED_ORIGINS` is unset (not when set to a non-matching value), there's no harm beyond a temporary mismatch. Still, "deploy first, then update CORS" is the correct sequence.

### Anti-Patterns to Avoid

- **Hardcoding Fly URL in source.** Phase 1 D-05/D-08 already wired `VITE_API_BASE_URL` through `apiFetch`/`apiStream`. Don't reintroduce literal URLs.
- **Forgetting root directory = `frontend/`.** Without this, CF runs `npm install` from repo root, hits no `package.json`, build fails with confusing logs. Most common Phase 5 failure mode for monorepos.
- **Setting env vars at "Preview" scope only.** D-08 locks "Production" scope. Preview is disabled (D-07) anyway, so values would never be read.
- **Trailing slash on `VITE_API_BASE_URL`.** `apiFetch` does `${API_BASE}${path}` where `path` starts with `/api/...`. Trailing slash on base = `//api/...` = 404. D-08 calls this out.
- **Setting `CORS_ALLOWED_ORIGINS` to a comma list with localhost.** D-12 forbids it. Backend's dev fallback (Phase 1 D-02) covers local dev when the var is unset on the laptop; it's not needed in the Fly secret.
- **Renaming `_redirects` to `_redirects.txt` or putting it in `frontend/_redirects` (outside `public/`).** Vite only copies files inside `public/`. The exact filename `_redirects` (no extension) is what CF expects.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| SPA deep-link routing | Custom 404.html with JS redirect, Cloudflare Workers script | `_redirects` file (D-10) | Native CF Pages support; one line; zero runtime cost. |
| Build pipeline / CI | GitHub Actions for frontend, Wrangler CLI deploy | CF Pages GitHub git integration (D-01) | Push-to-deploy is built in; no auth tokens on laptop. |
| Cross-origin URL config | Build-time string replacement, runtime fetch of a config endpoint | `VITE_API_BASE_URL` env var (D-08) baked at build time | Already wired in Phase 1; standard Vite pattern. |
| CORS allowlist | Wildcard `*` with credentials hack | Explicit single origin in Fly secret (D-11) | Wildcard + credentials is spec-invalid (PITFALLS Pitfall 7). |

**Key insight:** This phase is **all dashboard configuration + one git commit + one Fly secret update**. There is no application code to write. Resist the urge to add tooling.

## Runtime State Inventory

This is a deploy-only phase, but a small inventory is worth completing:

| Category | Items Found | Action Required |
|---|---|---|
| Stored data | None — CF Pages serves static assets only; no DB writes; Supabase data unchanged. | None. |
| Live service config | (1) **CF Pages project** `boardgame-rag-prod` — created in CF dashboard, config lives in CF (not git). (2) **Fly secret** `CORS_ALLOWED_ORIGINS` — currently `http://localhost:5173`, must be overwritten via `flyctl secrets set`. | (1) Document config in PLAN as out-of-repo manual steps. (2) `flyctl secrets set` post-deploy (D-11). |
| OS-registered state | None — no local processes / scheduled tasks involved. | None. |
| Secrets/env vars | (1) `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` set in CF dashboard (Production scope). (2) `NODE_VERSION` env var on CF. (3) `CORS_ALLOWED_ORIGINS` Fly secret overwrite. | All set via dashboards / CLI per locked decisions. |
| Build artifacts / installed packages | `dist/` is built fresh by CF on each push — no stale artifact concern. Local `frontend/dist/` (if any) is gitignored and irrelevant. | None. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| `node` | Local Vite build sanity-check (optional) | ✓ | v20.14.0 | — |
| `git` | Push to `main` (triggers CF deploy) | ✓ (assumed — Phase 4 confirmed) | — | — |
| `flyctl` | D-11 CORS update | ✓ (Phase 4 confirmed authenticated) | — | — |
| GitHub repo access for CF Pages | D-01 git integration | Assumed (developer is repo owner per git config `hyper-mage`) | — | — |
| Cloudflare account | CF Pages project creation | Assumed (D-01 explicitly chooses CF) | — | If missing → blocking; create free account first. |
| Browser | D-13 manual verification | ✓ (any modern browser) | — | — |

**Missing dependencies with no fallback:** None known. Plan should include a preflight check that the developer is logged into Cloudflare's dashboard before starting.

**Missing dependencies with fallback:** None.

## Common Pitfalls

### Pitfall 1: CF Pages Root Directory Misconfiguration

**What goes wrong:** CF runs `npm install` and `npm run build` at repo root, sees no `package.json` (or sees the wrong one), build fails with `ENOENT package.json` or `Missing script: "build"`.
**Why it happens:** CF Pages' default root is the repo root. For a monorepo / two-app layout (this repo has `frontend/` + `backend/`), root must be set explicitly to `frontend`.
**How to avoid:** During CF dashboard setup, set **Build configuration → Root directory** = `frontend`. With root set, build command stays `npm run build` and output stays `dist` (relative to root, so the actual deploy artifact is `frontend/dist/`).
**Warning signs:** Build log shows `npm error code ENOENT` or `npm error path /opt/buildhome/repo/package.json`.

### Pitfall 2: `_redirects` In Wrong Location

**What goes wrong:** Deep-link refresh on `/documents` returns CF's 404 page instead of the SPA.
**Why it happens:** File at `frontend/_redirects` (not in `public/`) is ignored by Vite — never copied to `dist/`. Or filename has an extension (`_redirects.txt`).
**How to avoid:** Exact path `frontend/public/_redirects`, exact filename, exact contents `/* /index.html 200` (one line, three space-separated tokens).
**Warning signs:** After deploy, `curl https://boardgame-rag-prod.pages.dev/_redirects` returns 200 with the rule contents (proves Vite copied it correctly). If it 404s, the file didn't make it into `dist/`.

### Pitfall 3: `VITE_API_BASE_URL` Not Baked Into Bundle

**What goes wrong:** Browser Network tab shows requests going to `https://boardgame-rag-prod.pages.dev/api/...` (same-origin) instead of the absolute Fly URL. Frontend appears to load but every API call 404s.
**Why it happens:** (a) Env var was set at Preview scope, not Production. (b) Env var was added after the build ran — needs a re-deploy. (c) Typo in var name (`VITE_API_BASE` instead of `VITE_API_BASE_URL`). Vite only inlines `VITE_*` vars that exist at build time.
**How to avoid:** Set env vars **before** the first build (or trigger a manual redeploy after setting). Confirm scope is "Production." Match var name exactly.
**Warning signs:** `view-source:` of deployed page → search built JS for the literal string `boardgame-rag-prod.fly.dev` — if absent, the env var didn't bake in. Network tab shows requests to same-origin paths.

### Pitfall 4: CORS Mismatch After Phase 5 Deploy

**What goes wrong:** CF deploy is green, login page renders, but chat/documents API calls fail with `Access-Control-Allow-Origin` errors. Browser console: `from origin 'https://boardgame-rag-prod.pages.dev' has been blocked by CORS policy`.
**Why it happens:** D-11 step skipped — `CORS_ALLOWED_ORIGINS` Fly secret still holds Phase 4's `http://localhost:5173` placeholder.
**How to avoid:** PLAN must include `flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod` as an explicit task **after** verifying CF deploy is green. Wait ~30s for Fly machine restart. Refresh CF page and retry.
**Warning signs:** Login page renders (static asset served by CF, no API call), but any button that hits `/api/...` fails silently or with a CORS error in console.

### Pitfall 5: Trailing Slash on `VITE_API_BASE_URL`

**What goes wrong:** All API calls return 404. Network tab shows requests to `https://boardgame-rag-prod.fly.dev//api/threads` (double slash).
**Why it happens:** D-08 says "no trailing slash" — but it's easy to add one in the dashboard. `apiFetch` does `${API_BASE}${path}` where path is `/api/threads`.
**How to avoid:** Set `VITE_API_BASE_URL` to exactly `https://boardgame-rag-prod.fly.dev` (no trailing `/`).
**Warning signs:** Network tab shows `//api/...` in URLs.

### Pitfall 6: Anon Key Confusion

**What goes wrong:** Login fails with cryptic Supabase auth errors, OR (much worse) RLS bypass because someone shipped the service-role key.
**Why it happens:** D-09 calls this out. Anon key in bundle is fine (public, RLS-bound). Service-role key in `VITE_*` would be a critical leak (PITFALLS #1, #2). Phase 1 D-12 / SEC-07 grep guard on prod bundle covers this — verify it's still passing after CF Pages deploy.
**How to avoid:** Set only `VITE_SUPABASE_ANON_KEY` (not service-role). Run a one-shot grep on the deployed bundle: `curl -s https://boardgame-rag-prod.pages.dev/assets/index-*.js | grep -Ei 'service_role|sk-|sb_secret_'` — must return zero matches.
**Warning signs:** Network tab shows requests to Supabase with `Authorization: Bearer <very-long-static-jwt>` (service-role JWT decodes with role: service_role at jwt.io).

### Pitfall 7: Browser Cache Hides New Deploy

**What goes wrong:** Verification clicks the URL, sees old version (or 404), thinks deploy failed.
**Why it happens:** CF Pages aggressively caches HTML at the edge for the apex; built-asset filenames are content-hashed (cache-safe), but `index.html` itself can be served stale briefly.
**How to avoid:** During verification, hard-refresh (Ctrl+Shift+R / Cmd+Shift+R) or open in an incognito window.
**Warning signs:** Network tab shows `200 (from disk cache)` on `index.html` while CF dashboard says deploy is fresh.

## Code Examples

### `frontend/public/_redirects` (CREATE — sole new file)

```
/* /index.html 200
```

(One line, no trailing whitespace, no extension on the filename.)

Verified syntax per [Cloudflare Pages Redirects docs](https://developers.cloudflare.com/pages/configuration/redirects/) — format is `[source] [destination] [status]`, splat `*` matches anything, status `200` rewrites (vs `301/302` which redirect).

### Optional `frontend/.nvmrc` (Claude's discretion)

```
20
```

Mirrors the `NODE_VERSION=20` env var on CF Pages; helps anyone using `nvm` locally pick the matching version. Does not affect CF build (env var is the canonical source there).

### `flyctl secrets set` invocation (D-11, post-deploy)

```bash
flyctl secrets set CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev -a boardgame-rag-prod
```

Verification (digest changes, value never shown):

```bash
flyctl secrets list -a boardgame-rag-prod | grep CORS_ALLOWED_ORIGINS
# Compare digest to the Phase 4 baseline (recorded in 04-VERIFICATION.md if available)
```

End-to-end CORS smoke (browser console, on the CF Pages tab after Fly restart finishes):

```js
// Should succeed once CORS is updated:
fetch('https://boardgame-rag-prod.fly.dev/api/health').then(r => r.text()).then(console.log)
```

### Browser Verification Sequence (D-13 — five PLAN tasks)

```
1. Hard-load https://boardgame-rag-prod.pages.dev — login page renders, no console errors.
2. DevTools → Network → confirm any /api/* request URL begins with https://boardgame-rag-prod.fly.dev/api/...
3. Log in as ragtest1@gmail.com / testpass123.
4. Navigate to /documents (in-app). Hard-refresh (Ctrl+Shift+R). SPA renders (not CF 404).
5. Send a chat message. SSE streams chunks (Network tab: Type=eventsource, content arriving incrementally).
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Vercel for frontend | Cloudflare Pages | research/SUMMARY.md decision | Unlimited bandwidth; simpler SPA story; locked by Phase 5 D-01. |
| Manual `_redirects` rule for SPA | CF Pages auto-SPA fallback (no `404.html`) | CF Pages v3 build system | Both work; D-10 keeps explicit `_redirects` for safety. |
| `wrangler` CLI deploy | GitHub git integration | CF Pages 2022+ | Push-to-deploy; no laptop auth tokens. D-01 chooses this path. |
| Node 18 default | Node 22.16.0 default (CF v3) | CF Pages 2025+ | Pin via `NODE_VERSION` to control drift. |

**Deprecated/outdated:**
- Vercel rewrites to proxy `/api/*` to backend — research/PITFALLS Pitfall 8 documents this is unsafe for SSE. We avoid by calling Fly directly via `VITE_API_BASE_URL` (D-08).

## Open Questions

1. **Does CF Pages strip `Authorization` headers from upstream `_redirects` proxy rules?** *Not relevant here — we don't use `_redirects` as a proxy. Browser hits Fly directly. Flag dismissed.*
2. **Will CF Pages ever auto-detect Vite and skip the framework preset?** Mostly yes; framework preset prefills the same build command we'd type manually. Either path works.
3. **Does committing `_redirects` need a `.gitignore` audit?** No — `_redirects` is a source file in `public/`, intentionally tracked. `frontend/dist/` should remain gitignored (verify in PLAN preflight).

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | None (frontend has no test framework per CLAUDE.md / package.json) |
| Config file | none |
| Quick run command | `cd frontend && npm run build` (TypeScript check + Vite build) |
| Full suite command | Manual browser checklist (D-13) — no automated suite this phase |
| Lint | `cd frontend && npm run lint` (ESLint flat config) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| DEPLOY-05 | CF Pages project deploys green from `main` | manual-only | (CF dashboard log) | ✅ (CF dashboard) |
| DEPLOY-05 | Three env vars set (Production scope) | manual-only | (CF dashboard) | ✅ |
| DEPLOY-05 | `_redirects` present in `dist/` after build | smoke | `cd frontend && npm run build && test -f dist/_redirects` | ❌ Wave 0 (file to create) |
| DEPLOY-05 | `_redirects` reachable on deployed site | smoke | `curl -fsS https://boardgame-rag-prod.pages.dev/_redirects` | ✅ (post-deploy) |
| DEPLOY-05 | Network tab shows absolute Fly URL | manual-only | (DevTools) | ✅ |
| DEPLOY-05 | Hard-refresh of `/documents` returns SPA | manual-only | `curl -I https://boardgame-rag-prod.pages.dev/documents` should return 200 with `content-type: text/html` | ✅ (post-deploy) |
| DEPLOY-05 | CORS-allowed cross-origin call succeeds from CF origin | manual-only (browser console fetch) | n/a | ✅ |
| DEPLOY-05 | Frontend bundle has no service-role / secret leak | smoke (re-run Phase 1 SEC-07 guard against prod bundle URL) | `curl -s https://boardgame-rag-prod.pages.dev/assets/index-*.js \| grep -Ei 'service_role\|sk-proj\|sk-or-\|sb_secret_'` (expect no match) | ✅ (post-deploy) |

### Sampling Rate

- **Per task commit:** `cd frontend && npm run build` (succeeds locally before pushing — CF build will use the same scripts). Confirms `_redirects` lands in `dist/`.
- **Per wave merge:** Push to `main`; CF auto-builds; check CF dashboard "Deployments" tab for green status; run the manual D-13 5-step browser checklist.
- **Phase gate:** All 5 D-13 steps pass + CORS update via `flyctl secrets set` confirmed by digest change + bundle leak grep returns zero hits.

### Wave 0 Gaps

- [ ] `frontend/public/_redirects` — covers DEPLOY-05 deep-link refresh.
- [ ] (Optional, Claude's discretion) `frontend/.nvmrc` — local-dev consistency.
- [ ] No test framework install needed — frontend has none and adding one is out of scope.

*(Note: this phase is intentionally manual-verification heavy per D-13 / D-14. Automating browser checks would be Phase 7 UptimeRobot work.)*

## Sources

### Primary (HIGH confidence)

- [Cloudflare Pages — Redirects](https://developers.cloudflare.com/pages/configuration/redirects/) — `_redirects` syntax (`[source] [destination] [code?]`).
- [Cloudflare Pages — Build image / Node version](https://developers.cloudflare.com/pages/configuration/build-image/) — `NODE_VERSION` env var, `.nvmrc` / `.node-version` file alternatives, default 22.16.0 in v3 build system.
- [Cloudflare Pages — Branch build controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/) — disable preview deploys via Settings → Builds & deployments → Configure Production deployments → "None".
- [Cloudflare Pages — Serving Pages](https://developers.cloudflare.com/pages/configuration/serving-pages/) — auto-SPA fallback when no top-level `404.html` exists.
- [Vite — Public directory](https://vite.dev/guide/assets.html) — `public/` files copied as-is to `dist/`.
- [Fly.io — Secrets](https://fly.io/docs/apps/secrets/) — `flyctl secrets set` overwrite + restart semantics; `flyctl secrets list` shows digests only.
- Repo files: `frontend/package.json`, `frontend/package-lock.json`, `frontend/vite.config.ts`, `frontend/src/lib/api.ts`, `frontend/public/`.
- Local environment: `node --version` = v20.14.0 (verified 2026-05-05).

### Secondary (MEDIUM confidence)

- [Codemzy blog — Cloudflare Pages SPA routing](https://www.codemzy.com/blog/cloudflare-reactjs-spa-routing) — confirms full-SPA auto-fallback works without `_redirects`; flags partial-SPA edge cases not relevant here.
- `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` — project-internal research (high-confidence on repo specifics, medium on CF platform specifics).

### Tertiary (LOW confidence)

- Cloudflare Community thread reporting "infinite loop" on `/* /index.html 200` — appears to be an isolated case with conflicting `_headers` rules, not the documented norm. D-10 explicit rule remains canonical.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — CF Pages docs verified for Node version pinning and build config; Vite `public/` behavior verified.
- Architecture: HIGH — All decisions locked; `apiFetch`/`apiStream` Phase 1 wiring already in place and inspected.
- Pitfalls: HIGH — All seven pitfalls reflect known CF Pages / Vite / monorepo failure modes documented in upstream sources or research/PITFALLS.md.
- Validation: HIGH for the smoke commands; the manual D-13 browser checklist is locked by user decision.

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (CF Pages v3 build system is stable; Node 20 LTS is supported through 2026; no fast-moving APIs in this surface).
