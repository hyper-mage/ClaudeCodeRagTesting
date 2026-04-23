# Feature Research

**Domain:** Public portfolio deployment of a feature-complete agentic RAG app (solo, free-tier hosts)
**Researched:** 2026-04-22
**Confidence:** MEDIUM (training data + widely-documented community norms; host specifics verified against PROJECT.md: Fly.io backend, Vercel frontend, Supabase prod)

## Scope Note

This milestone (v1.1) deploys an already feature-complete app. "Features" here means **deployment-layer features** — things a portfolio RAG needs beyond "the code runs on a server." App features (chat, ingestion, agent tools, hybrid search, sub-agents) are already shipped in v1.0 and are treated as dependencies, not new work.

Primary consumer of this doc: roadmap phase planning for v1.1. Categories reflect realistic solo portfolio scope, not SaaS production scope.

## Feature Landscape

### Table Stakes (Users Expect These)

Features a visitor to a portfolio AI app assumes exist. Missing any of these makes the portfolio piece feel broken, unsafe to demo, or financially reckless.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Public HTTPS URL with custom-ish domain | "Live demo" link in README must resolve over TLS. `*.vercel.app` / `*.fly.dev` is acceptable for portfolio; custom domain is a nice-to-have. | LOW | Vercel + Fly both give free TLS on their subdomains. |
| Demo credentials in README | Reviewers will not sign up. A working `demo@ / demo123` (or one-click demo login button) is the single biggest conversion lever for portfolio pieces. | LOW | Dependency: existing Supabase Auth. Seed user via migration/script. Optionally wire a "Login as demo" button on `/login`. |
| Deployed URL + screenshots in README | GitHub-first reviewers scan README before clicking. Needs hero screenshot, live URL badge, short architecture note. | LOW | Pure docs. Add badges for Vercel/Fly deploy status if available. |
| Sentry (or equivalent) on frontend | When a recruiter hits a blank screen, you need to know. Free tier covers portfolio traffic easily. | LOW | Dependency: React app. `@sentry/react` + DSN env var. Source maps upload in Vite build. |
| LangSmith prod project separate from dev | Mixing dev + prod traces pollutes both. Every trace from the deployed app should be tagged prod. | LOW | Dependency: existing LangSmith integration in `backend/services/tracing.py`. Add `LANGSMITH_PROJECT` env for prod host. |
| Per-user rate limiting on chat endpoint | One curious visitor with a loop can burn your OpenRouter budget in minutes. This is the single most important cost-control feature. | MEDIUM | Dependency: FastAPI middleware + Supabase user_id. Simple in-memory or Supabase-table counter (requests/minute, tokens/day). SlowAPI lib works for FastAPI. |
| Hard monthly spend cap alerts | OpenRouter, OpenAI, and Tavily all support usage alerts. Missing this has burned portfolio devs publicly. | LOW | Provider dashboard config, not code. Set alerts at 50% / 80% / 100% of a chosen monthly cap. |
| CORS + auth redirect URLs locked to prod origin | Wildcard CORS or localhost-only redirect URLs are both visible footguns in a portfolio. | LOW | Dependency: existing FastAPI CORS middleware + Supabase Auth URL allowlist. Config change only. |
| Secrets in host secret stores (not `.env` committed) | `.env` in repo disqualifies a portfolio piece instantly for any reviewer who checks. | LOW | Fly secrets, Vercel env vars, Supabase dashboard. Already signaled in PROJECT.md. |
| Graceful error UI when LLM/provider fails | 502s, 429s, and timeouts are normal on free tiers. A blank chat box is a portfolio killer; a toast saying "Model provider rate-limited, try again" is not. | LOW-MEDIUM | Dependency: existing SSE stream handler. Catch `httpx` errors in `llm_service.py`, surface as SSE `error` event with friendly text. |
| Basic uptime / health check endpoint | Fly.io will kill and restart containers; it needs `/health` to know if a boot succeeded. Without it you get silent 5-minute cold starts. | LOW | FastAPI route returning `{"status": "ok"}`. Fly `http_checks` config. |

### Differentiators (Competitive Advantage)

For a portfolio piece, "competitive advantage" means **things that make a reviewer remember the project**. These go beyond "it runs" and signal production-minded engineering.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| One-click demo login button | Removes the single biggest friction point. Recruiter clicks → chat in 3 seconds. Outperforms "here are credentials, copy-paste." | LOW | Frontend-only: button on `/login` that calls `supabase.auth.signInWithPassword` with hardcoded demo creds. |
| Nightly demo-data reset (cron) | Prevents demo account from being polluted with junk uploads by prior visitors. Visitor N+1 sees a clean slate. Also bounds storage costs. | MEDIUM | Fly.io cron or Supabase scheduled function (pg_cron). Deletes `documents` + `document_chunks` + storage objects for `user_id = demo_user_id`. Preserves default KB (visibility='public'). |
| Public status page / health badge in README | Shields.io badge pinging `/health`. Tiny touch, signals ops awareness. | LOW | Shields.io endpoint badge or UptimeRobot public status page (free tier). |
| Uptime monitoring (UptimeRobot / BetterStack free tier) | Catches Fly.io cold starts failing, Supabase outages, expired keys. Free tiers give 5-min interval + email alerts. | LOW | External service. Point at `/health`. Email to owner. |
| Keep-warm ping to avoid cold starts | Fly.io free machines auto-stop after idle. First-visitor cold start is ~10-30s on a Python+Docling image. A cron-pinged `/health` every 4 minutes keeps it warm. | LOW | Trade-off: burns free-tier machine-hours. Acceptable for portfolio traffic. Alternative: Fly `auto_stop_machines = false` + `min_machines_running = 1`. |
| Landing page / about route | Most portfolio RAGs drop visitors straight into chat. A 1-screen landing with "what this is / try demo / how it works / tech stack" converts better and gives context before the chat UI confuses non-technical viewers. | MEDIUM | New route `/` → landing, existing chat moves to `/chat`. Content-only page, no backend. |
| Token/cost usage dashboard for owner | Private `/admin` route showing requests, tokens, cost-to-date per user. Answers "is the demo being abused right now?" at a glance. | MEDIUM | Dependency: LangSmith traces already capture this. Either link to LangSmith dashboard (free) or build a thin admin page reading from a `usage_events` table. LangSmith link is the 10x cheaper option. |
| Abuse protection on signup (email verify + hCaptcha) | Public Supabase signup without verification = spam account farm. Supabase has built-in email confirmation and captcha hooks. | LOW-MEDIUM | Supabase Auth setting: require email confirmation. hCaptcha integration via Supabase Auth is config-only (dashboard) + anon key flow. |
| Per-IP rate limit on unauthenticated routes | `/signup`, `/login`, `/api/health` need IP-level throttling (auth'd rate limits don't apply). Prevents credential stuffing and signup floods. | MEDIUM | SlowAPI or custom middleware keyed on `X-Forwarded-For` (Fly passes real IP in this header). |
| README architecture diagram | A simple mermaid diagram (Vercel → Fly → Supabase → OpenRouter) in README signals systems thinking. Takes 20 minutes. | LOW | Mermaid renders in GitHub natively. |
| Graceful degradation when web search / rerank unavailable | Tavily, Cohere rerank, OpenRouter each have independent outages. App should fall back (skip rerank, skip web search tool) rather than 500. | LOW-MEDIUM | Dependency: existing `retrieval_service.py`, `rerank_service.py`, `web_search_service.py`. Wrap each external call in try/except and omit from tool list or fall back to vector-only. |
| Structured logs (JSON) with request IDs | Fly.io log viewer is 10x more useful with JSON logs and a request ID to correlate frontend → backend → LangSmith. | LOW | Python `logging` + JSON formatter (e.g., `python-json-logger`). Frontend sends `X-Request-Id`. |

### Anti-Features (Commonly Requested, Often Problematic)

Things that feel obvious for a "deployed app" but that are traps for a solo portfolio piece on free tiers.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Fully anonymous guest mode (no login at all) | "Lowest friction for reviewers." | Every unauthenticated request is unattributable to a Supabase user → RLS breaks, rate limits can only key on IP (easy to rotate), and your OpenRouter budget has no owner to blame. Anonymous public LLM endpoints have been abused into four-figure bills repeatedly. | Shared demo login with hard rate limits + nightly reset. Same friction, real attribution. |
| Full custom admin UI for usage/costs | "Founder needs visibility." | 2-3 days of work for something LangSmith + OpenRouter + Supabase dashboards already give you for free. | Link to LangSmith dashboard from README. Owner-only. |
| Multi-region deploy | "Global audience." | Free-tier portfolio traffic is 5 reviewers in one region. Multi-region on Fly doubles cold-start headaches and complicates Supabase connection pooling. | Single region closest to you. Add regions only if latency becomes a real complaint. |
| Dedicated CI/CD pipeline with staging env | "Real deploys have staging." | Staging + prod on free tiers = 2x secrets to rotate, 2x cold starts, 2x points of divergence. For a one-person portfolio, `main` → prod with manual rollback is enough. | Vercel preview deploys (automatic per-PR, free) cover the staging need for frontend. Fly deploys via `fly deploy` from local or GitHub Action. |
| Aggressive bot detection / WAF | "Protect from DDoS." | Cloudflare WAF / Turnstile is overkill for portfolio traffic. Adds latency and false positives for legit reviewers on VPNs. | Rate limiting per user + per IP is enough. Fly.io sits behind anycast already. |
| User-facing billing / usage meter | "Show users their quota." | Implies users care about quota. They don't — they're reviewers clicking once. Adds UI, backend counters, and expectation of accuracy. | Silent server-side rate limit. Return 429 with friendly message only when hit. |
| Feature flag system | "Toggle features per user." | Zero payoff at solo-portfolio scale. Env vars are fine. | `settings.WEB_SEARCH_ENABLED` etc. via pydantic-settings (already the pattern). |
| SSO / OAuth providers (Google, GitHub login) | "Reviewers want to log in with GitHub." | Every OAuth provider adds a new redirect URL to maintain, a new consent screen to test, and no reviewer will actually use it when `demo@ / demo123` is right there. Also complicates the demo-reset cron (can't delete a Google-linked account as easily). | Email/password only. Demo login button on login page. |
| Separate "production" reranker / embedding model | "Prod should use the best model." | Embeddings are content-addressed in `document_chunks`. Switching embedding models on deploy day invalidates the entire seeded KB. | Same model as dev. Pin it in config. Lock it until v1.2. |
| Aggressive caching layer (Redis in front of LLM) | "Save money on repeat queries." | Chat queries are highly unique; cache hit rate on free-form RAG queries is <5%. Redis adds a service, a connection string, a memory budget, and a cache-invalidation bug surface for negligible savings at portfolio volume. | Rate limiting is a 10x better cost lever than caching for this workload. |
| Real-time leaderboard / public activity feed | "Show the app is alive." | Exposes other visitors' queries/uploads; privacy/RLS nightmare. | Usage counter in owner-only admin view. |
| Custom auth flow replacing Supabase Auth | "More control." | Throws away email verification, captcha hooks, password reset, session management — all free from Supabase. | Use Supabase Auth. Every time. |

## Feature Dependencies

```
[Demo login button]
    └──requires──> [Demo user seeded in Supabase]
                       └──requires──> [Supabase prod project migrations+seed applied]

[Nightly demo reset cron]
    └──requires──> [Demo user seeded + stable user_id]
    └──requires──> [Fly.io scheduled job OR Supabase pg_cron]

[Per-user rate limiting]
    └──requires──> [Existing Supabase Auth user_id dependency (already in place)]
    └──enhances──> [Hard monthly spend cap] (defense in depth)

[LangSmith prod project]
    └──requires──> [LANGSMITH_PROJECT env var in Fly secrets]
    └──enables───> [Owner usage dashboard] (link-out, not build)

[Sentry frontend]
    └──requires──> [Vite source map upload in build step]

[Uptime monitor]
    └──requires──> [/health endpoint on backend]
    └──enables───> [Status badge in README]

[Keep-warm ping]
    └──requires──> [/health endpoint]
    └──conflicts─> [Fly auto_stop_machines=true] (pick one strategy)

[Graceful degradation (rerank/web/LLM)]
    └──requires──> [Existing service wrappers in backend/services/*]
    └──enhances──> [All chat flows]

[CAPTCHA on signup]
    └──requires──> [Supabase Auth captcha provider config]
    └──enhances──> [Per-IP rate limit] (belt-and-suspenders against bot signups)

[Landing page]
    └──requires──> [React Router restructure: / → landing, /chat → existing chat]
    └──enhances──> [Demo login button placement]
```

### Dependency Notes

- **Demo reset cron requires stable demo user_id:** Seed the demo user in a migration (or a one-shot script stored in `supabase/seed/`) so the cron deletes the right rows. Do NOT hardcode the uuid; read it from an env var `DEMO_USER_ID` set after seed.
- **Per-user rate limiting + hard spend cap are complementary, not redundant:** Rate limiting protects against one chatty user. Spend cap protects against a thousand of them, or against a bug in your own loop. Both are table stakes.
- **Keep-warm conflicts with auto-stop:** Pick one. For a portfolio, `min_machines_running = 1` on Fly is simpler than cron-pinging; it also uses less total compute than a 4-min ping loop.
- **Graceful degradation depends on existing service abstractions:** Already in place (`retrieval_service`, `rerank_service`, `web_search_service` are separate modules) — this is a wrap-in-try/except change, not an architecture change.
- **Landing page enhances demo login:** If `/` is the chat UI, the demo login button has nowhere to live except the login page. A landing page is where "Try the demo" naturally lives.

## MVP Definition

### Launch With (v1.1)

Must ship for the URL to be shareable as a portfolio piece without embarrassment or financial risk.

- [ ] Public HTTPS URL (Vercel + Fly defaults) — portfolio pointer
- [ ] Demo credentials in README + seeded demo user — reviewer conversion
- [ ] Per-user rate limit on chat endpoint — cost control
- [ ] Hard monthly spend cap alerts on OpenRouter + OpenAI + Tavily — cost control
- [ ] `/health` endpoint + Fly health checks — prevents silent cold-start death
- [ ] CORS + Supabase auth redirect URLs locked to prod origin — basic security
- [ ] Secrets in Fly/Vercel/Supabase secret stores (no `.env` in repo) — portfolio table stakes
- [ ] Sentry on frontend — error visibility
- [ ] LangSmith prod project separate from dev — trace hygiene
- [ ] Graceful error UI when LLM/provider fails — visible polish
- [ ] README with live URL, demo creds, screenshot, short architecture note — reviewer experience

### Add After Validation (v1.1.x / quickly after launch)

Add once the URL is up and traffic starts trickling in. Triggered by real observations.

- [ ] One-click demo login button — add if README creds copy-paste shows friction in session replay
- [ ] Nightly demo data reset cron — add as soon as the second visitor pollutes the demo account
- [ ] Uptime monitor (UptimeRobot free) — add once you notice you don't know when the app is down
- [ ] Keep-warm strategy (min_machines_running=1 OR cron ping) — add after first complaint about cold start
- [ ] Per-IP rate limit on unauthenticated routes — add if signup spam appears
- [ ] CAPTCHA + email verification on signup — add with per-IP limit (same trigger)
- [ ] Landing page — add once you want to share the URL in contexts beyond "recruiter reviewing resume"

### Future Consideration (v1.2+)

Nice to have, but each introduces complexity disproportionate to portfolio value today.

- [ ] Custom domain — defer until you have a personal brand domain to attach
- [ ] Owner admin dashboard (custom UI) — defer; LangSmith link covers it
- [ ] Structured JSON logs + request IDs — defer until you actually need to debug a prod incident
- [ ] Vercel preview deploys as implicit staging — free, but only add if you start doing meaningful PR work
- [ ] Multi-provider LLM failover (OpenRouter → direct OpenAI) — defer; graceful degradation is enough
- [ ] Public status page — defer; Shields.io badge is enough

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Public HTTPS URL | HIGH | LOW | P1 |
| Demo credentials + seeded user | HIGH | LOW | P1 |
| Per-user rate limit | HIGH (to owner, not visitor) | MEDIUM | P1 |
| Monthly spend cap alerts | HIGH (to owner) | LOW | P1 |
| `/health` endpoint + Fly checks | HIGH (ops) | LOW | P1 |
| CORS / auth redirect hardening | HIGH (security) | LOW | P1 |
| Secrets in host stores | HIGH (portfolio integrity) | LOW | P1 |
| Sentry frontend | MEDIUM | LOW | P1 |
| LangSmith prod project split | MEDIUM | LOW | P1 |
| Graceful LLM error UI | HIGH | LOW-MEDIUM | P1 |
| README with URL/creds/screenshot | HIGH | LOW | P1 |
| One-click demo login button | HIGH | LOW | P2 |
| Nightly demo reset cron | MEDIUM | MEDIUM | P2 |
| Uptime monitor | MEDIUM (owner) | LOW | P2 |
| Keep-warm (min_machines_running=1) | MEDIUM | LOW | P2 |
| Per-IP rate limit | MEDIUM | MEDIUM | P2 |
| CAPTCHA on signup | MEDIUM | LOW-MEDIUM | P2 |
| Email verification on signup | MEDIUM | LOW | P2 |
| Graceful degradation (rerank/web/LLM) | MEDIUM | LOW-MEDIUM | P2 |
| Landing page | MEDIUM | MEDIUM | P2 |
| Status badge in README | LOW | LOW | P2 |
| Structured JSON logs | LOW | LOW | P3 |
| Custom domain | LOW | LOW | P3 |
| Owner admin UI | LOW | MEDIUM-HIGH | P3 (anti-feature; use LangSmith) |

**Priority key:**
- P1: Must ship with v1.1 deployment or the portfolio piece is embarrassing/unsafe
- P2: Ship in v1.1 or shortly after; strong polish and risk mitigation
- P3: Defer to v1.2+ unless triggered by real signal

## Competitor Feature Analysis

"Competitors" here = other deployed portfolio AI/RAG apps a hiring manager might click before or after yours. Patterns observed across many public deployments (personal sites, Show HN posts, LangChain/LlamaIndex community showcases, Vercel AI SDK templates).

| Feature | Typical Portfolio RAG | Typical "Production-Lite" SaaS Demo | Our Approach |
|---------|----------------------|--------------------------------------|--------------|
| Login strategy | No auth (totally open) OR magic-link only | Email+password + OAuth + SSO | Email+password (existing) + demo login button |
| Cost control | None (hope for the best) | Per-tier quotas, Stripe metering | Per-user rate limit + monthly spend alert |
| Demo data | Polluted free-for-all | Per-session sandbox (ephemeral) | Shared demo user + nightly reset |
| Observability | console.log in browser devtools | Sentry + Datadog + PagerDuty | Sentry frontend + LangSmith prod project + UptimeRobot |
| Cold starts | Present, ignored | Kept warm via min instances | `min_machines_running=1` on Fly (or cron ping) |
| Error UX | White screen or raw stack trace | Toast + retry + status page | Toast on SSE error event + `/health` for monitor |
| Landing surface | Dropped directly into app UI | Marketing page + pricing + docs | Short landing (about/how/try) + demo button → chat |
| README | Single line + deploy badge | Full wiki, architecture docs, contributing guide | Live URL + demo creds + screenshot + mermaid diagram + tech stack |
| Abuse protection | None | WAF + CAPTCHA + fraud detection | CAPTCHA on signup + per-IP + per-user rate limit |
| Secrets handling | `.env` in repo (occasional) or host env vars | Vault / KMS / rotated secrets | Host secret stores (Fly/Vercel/Supabase) |

Our approach sits deliberately in the middle: more rigorous than "drop it on a VPS" portfolio norms (because this is a *public* LLM endpoint with real cost exposure), less ceremonial than SaaS-demo norms (because it's a solo project, not a business).

## Sources

- PROJECT.md v1.1 milestone definition (target features confirmed: containerized backend, Fly.io, Vercel, Supabase prod split, auth/CORS hardening, secret stores, observability baseline, demo creds + README)
- CLAUDE.md architecture context (existing services, auth, RLS, SSE, LangSmith integration already in place — feeds "dependencies on existing features" column)
- Fly.io documentation norms for free-tier machines (`auto_stop_machines`, `http_checks`, secrets) — MEDIUM confidence, training data
- Vercel documentation norms for env vars + preview deploys — MEDIUM confidence, training data
- Supabase Auth capabilities (email verification, captcha hooks, redirect URL allowlist) — MEDIUM confidence, training data
- LangSmith project-per-environment pattern — HIGH confidence, standard practice
- Community patterns from Show HN / Vercel AI SDK template deployments / LangChain community showcases (rate-limit-or-regret stories) — MEDIUM confidence, pattern-based not source-cited
- SlowAPI (FastAPI rate limiting) — MEDIUM confidence, known library

**Confidence caveats:**
- Host-specific config details (exact Fly.io flag names, Supabase dashboard UI paths) are LOW-MEDIUM confidence from training data and should be verified against current docs during phase planning.
- "Typical portfolio RAG" patterns are synthesized from community norms, not a formal survey.
- No Context7 lookups performed; this is ecosystem/pattern research, not library API research. Phase-specific plans (e.g., "add SlowAPI") should Context7-verify the library at plan time.

---
*Feature research for: portfolio deployment of feature-complete agentic RAG*
*Researched: 2026-04-22*
