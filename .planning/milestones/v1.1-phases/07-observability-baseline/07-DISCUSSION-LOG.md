# Phase 07 Discussion Log

Date: 2026-05-15
Mode: discuss (default)
Areas discussed: 4 of 4

## Area 1: Sentry scope + PII

**Q1: Sentry coverage scope?**
- Options: Frontend only | Frontend + Backend (separate projects) | Frontend + Backend (same project)
- Selected: **Frontend only**
- Rationale: ROADMAP OBS-01 explicitly frontend; backend covered by LangSmith (OBS-02). Avoid extra Fly dep weight.

**Q2: PII scrubbing scope (multi-select)?**
- Options: chat content | user email + UUID | JWTs | document file names + folder paths
- Selected: **JWTs + user email + UUID**
- Implication: chat content and file paths ALLOWED in Sentry payloads. No `Sentry.setUser()` calls — events fully anonymous.

**Q3: Sentry tier + release tagging?**
- Options: Free Developer + git SHA | Free + semver | Paid Team
- Selected: **Free Developer tier + git SHA release tag**
- Rationale: 5k errors/mo sufficient; `CF_PAGES_COMMIT_SHA` auto-available; vite-plugin handles upload.

## Area 2: /api/health DB-check shape

**Q1: DB probe approach?**
- Options: `select 1` | count on documents table | match_document_chunks RPC
- Selected: **`select 1` via supabase-py**
- Rationale: Lightest probe; verifies Postgres reachability + auth without coupling to schema.

**Q2: Failure response shape?**
- Options: 503 + degraded JSON | 200 + status field | 500 + raw exception
- Selected: **503 + `{status:"degraded", db:"unreachable"}`**
- Rationale: Non-2xx so UptimeRobot fires; explicit degraded signal.

**Q3: Auth + rate-limit?**
- Options: Public unauthed unlimited | Public unauthed rate-limited | API-key gated
- Selected: **Public, unauthenticated, NOT rate-limited (excluded from slowapi)**
- Rationale: UptimeRobot pings from rotating IPs without auth; `select 1` is cheap so DoS amplification is negligible.

## Area 3: LangSmith env routing

**Q1: dev↔prod separation strategy?**
- Options: Single key + project env var | Separate keys per env | Disable in local
- Selected: **Single API key, project routed via `LANGSMITH_PROJECT` env var**
- Rationale: Standard SDK pattern; minimal secret management; matches existing `backend/services/tracing.py`.

**Q2: Verification approach for OBS-02 success criterion?**
- Options: Manual smoke (inspect dashboard) | Automated check via SDK list_runs
- Selected: **Automated check via LangSmith API**
- Rationale: User opted for tighter verification despite extra script weight.

## Area 4: UptimeRobot config + alerts

**Q1: Account tier + monitor count?**
- Options: Free 2 monitors | Free 3 monitors (with keyword check) | Paid Solo (1-min)
- Selected: **Free tier, 2 monitors at 5-min interval (`/api/health` + CF Pages root)**
- Rationale: Matches OBS-03 literal; sufficient signal for portfolio.

**Q2: Alert routing?**
- Options: Email only | Email + public status page | Email + SMS
- Selected: **Email-only to owner; no public status page**
- Rationale: OBS-03 wording ("owner gets email"); avoids exposing uptime numbers publicly.

## Carried forward decisions (from prior phases)

- Free-tier first (matches Phase 4/5 cost ceiling)
- CF Pages env vars Production scope only, Preview disabled (Phase 5)
- Fly secrets pattern for backend env (Phase 4)
- No new heavy backend deps (Phase 4 image-size discipline)

## Scope-creep deferred

- Backend Sentry integration (deferred — future enhancement)
- Public status page (rejected — Phase 8 may revisit)
- LangSmith cost digest (out of scope)
- Log shipping (Fly logs sufficient at this scale)
- SLO / error budgets (premature)
