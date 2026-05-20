# Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `06-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 06-prod-wiring-auth-cors-rate-limiting-cost-caps
**Areas discussed:** Rate limiter design, Max-iter cap on main chat loop, Supabase Auth redirect URLs, OpenRouter cost controls

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Rate limiter design | Library, storage, scope, key, cap value, 429 shape | ✓ |
| Max-iter cap on main chat loop | Value, on-cap behavior, settings field, telemetry | ✓ |
| Supabase Auth redirect URLs | Site URL, redirect allowlist, email templates, verification | ✓ |
| OpenRouter cost controls | Cap mechanism, threshold, alert-test, documentation | ✓ |

CORS rejection-path verification dropped from gray-area menu (4-option cap on AskUserQuestion) — folded as small task (`06-CONTEXT.md` D-21/D-22).

---

## Rate Limiter Design

### Library + storage backend

| Option | Description | Selected |
|--------|-------------|----------|
| slowapi + in-memory | FastAPI-native; counter resets on machine suspend; no Redis | ✓ |
| Custom dependency | Hand-rolled dict + asyncio.Lock; zero new deps; more code | |
| slowapi + Upstash Redis | Persistent across restarts; new account + secret; overkill | |

**User's choice:** slowapi + in-memory
**Notes:** Counter reset on Fly machine resume is acceptable for free-tier portfolio (single machine, suspends).

### Cap value for /api/chat per authenticated user

| Option | Description | Selected |
|--------|-------------|----------|
| 20/min | Generous for legit chat; blocks scripted bursts | ✓ |
| 10/min | Tighter; may interrupt back-and-forth debugging | |
| 30/min | Loose; demo-friendly | |

**User's choice:** 20/minute

### Scope — which routes

| Option | Description | Selected |
|--------|-------------|----------|
| /api/chat only | Only LLM-cost route; smallest surface | ✓ |
| /api/chat + document upload | Adds upload to cap | |
| All authenticated routes | Global cap; pollutes UX | |

**User's choice:** /api/chat only

### 429 response shape

| Option | Description | Selected |
|--------|-------------|----------|
| JSON + Retry-After | `{"error":"rate_limited","detail":...,"retry_after_seconds":N}` + header | ✓ |
| slowapi default | Plain-text default; less polished | |
| Generic 429 no body | Status only | |

**User's choice:** JSON + Retry-After

---

## Max-Iter Cap on Main Chat Loop

### Iteration cap value

| Option | Description | Selected |
|--------|-------------|----------|
| 15 | Higher than explorer's 6 because main loop has ~10 tools | ✓ |
| 10 | Conservative; may cut off legit chains | |
| 6 (mirror explorer) | Roadmap literal read; likely too tight for main loop | |
| 20 | Loose; bigger blast radius | |

**User's choice:** 15
**Notes:** Mirrors explorer's PATTERN (counter + graceful stop), not its exact numeric value. Document rationale in PLAN.

### Behavior when cap hit

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful assistant message | Persist final assistant content with cap-note suffix; stream ends cleanly | ✓ |
| SSE error event + 200 | Emits SSE `error` event; UI renders error bubble | |
| HTTP 500 abort | Worst UX; broken chat | |

**User's choice:** Graceful assistant message

### Settings field name + placement

| Option | Description | Selected |
|--------|-------------|----------|
| chat_max_iterations | Mirrors `explorer_max_iterations` naming | ✓ |
| main_loop_max_iterations | More literal; breaks naming pattern | |
| agent_max_iterations | Generic; ambiguous given multiple agents | |

**User's choice:** chat_max_iterations

### Telemetry on cap-hit

| Option | Description | Selected |
|--------|-------------|----------|
| Logger.warning + LangSmith tag | Local log + trace metadata `iteration_cap_hit=true` | ✓ |
| Logger.warning only | Local only | |
| No telemetry | Silent | |

**User's choice:** Logger.warning + LangSmith tag

---

## Supabase Auth Redirect URLs

### Site URL

| Option | Description | Selected |
|--------|-------------|----------|
| https://boardgame-rag-prod.pages.dev | Prod CF Pages origin; default token expansion target | ✓ |
| Leave default localhost | Breaks prod email links | |

**User's choice:** https://boardgame-rag-prod.pages.dev

### Redirect URLs allowlist

| Option | Description | Selected |
|--------|-------------|----------|
| Prod + localhost dev | `https://boardgame-rag-prod.pages.dev/**` + `http://localhost:5173/**` | ✓ |
| Prod only | Tightest; blocks dev-against-prod-auth | |
| Prod + localhost + 127.0.0.1 | Adds `http://127.0.0.1:5173/**` | |

**User's choice:** Prod + localhost dev

### Email template handling

| Option | Description | Selected |
|--------|-------------|----------|
| Defaults | `{{ .SiteURL }}` token expansion; zero custom HTML | ✓ |
| Light branding | Edit confirm + reset templates with project name | |
| Full custom | Custom HTML/CSS for all 4 templates | |

**User's choice:** Defaults

### Verification flow for SC#1

| Option | Description | Selected |
|--------|-------------|----------|
| Manual signup E2E | Fresh throwaway email → confirm → land on prod → chat | ✓ |
| Existing test user only | Skips email-confirm path; doesn't satisfy SC#1 | |
| Scripted with admin API | Harder; no real value over manual | |

**User's choice:** Manual signup E2E

---

## OpenRouter Cost Controls

### Free portfolio interpretation

| Option | Description | Selected |
|--------|-------------|----------|
| Truly $0 — :free models only | Zero balance; OpenRouter's own rate limits cap | |
| Near-free — $5 prepaid safety net | Keep paid quality; $5 one-time | |
| Hybrid — :free default + paid fallback | Most code; defeats $0 promise | |
| **Other (custom)** | Truly $0 with toggle to allow paid models | ✓ |

**User's choice:** Truly $0 with a toggle to allow paid models
**Notes:** Forced 4 follow-up sub-questions to lock toggle mechanics. BYOK first considered, then deferred to v1.2+ (scope creep analysis: per-user encrypted key storage + UI + LLM-service refactor + Try-demo break).

### Toggle implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Single LLM_MODEL env, swap value | `flyctl secrets set LLM_MODEL=<paid-id>`; zero code | ✓ |
| Two env vars + USE_PAID flag | More config; same outcome | |
| fly.toml staging vs prod app split | Two Fly apps; overkill | |

**User's choice:** Single LLM_MODEL env, swap value

### Default :free model id

| Option | Description | Selected |
|--------|-------------|----------|
| Pick during research | Researcher verifies tool-use support, availability, context | ✓ |
| google/gemini-2.0-flash-exp:free | User-locked now without tool-use verification | |
| meta-llama/llama-3.3-70b-instruct:free | Same risk | |

**User's choice:** Pick during research
**Notes:** Hard gate — if no current `:free` model reliably supports tool-calling, planner must stop and surface before writing the plan.

### Cost cap config

| Option | Description | Selected |
|--------|-------------|----------|
| Zero balance + $0.01 test alert | Never load credit; verify alert via temp $1 paid swap | ✓ |
| Zero balance, skip alert test | Doesn't satisfy SC#5 verbatim | |
| Load $5 cap permanently | Defeats $0 promise | |

**User's choice:** Zero balance + $0.01 test alert

### Documentation

| Option | Description | Selected |
|--------|-------------|----------|
| PLAN checklist + .env.prod comment | Dashboard steps + dated screenshot + comment showing both LLM_MODEL ids | ✓ |
| PLAN only | No .env.prod comment | |
| Dedicated docs/cost-controls.md | New doc; overkill | |

**User's choice:** PLAN checklist + .env.prod comment

---

## Claude's Discretion

- Exact slowapi version pin
- `chat_rate_limit` env var format (string `"20/minute"` vs split int field)
- CORS rejection assertion location (extend `fly_smoke.sh` vs sibling script)
- Wording of cap-hit graceful message
- LangSmith trace metadata key spelling
- Whether `:free` revert is manual or scripted helper
- `chat_max_iterations` exact value tunable post-observation

## Deferred Ideas

- BYOK (per-user provider keys) — v1.2+ (scope creep documented in CONTEXT)
- Persistent rate-limit storage (Redis/Upstash)
- Document upload rate limit
- Global rate limit across all authenticated routes
- `allow_origin_regex` for CF Pages preview deploys
- Frontend 429 toast/banner UI (Phase 8 PORT-02)
- Custom email templates / branding
- Alert-test automation script
- `pip-tools` / lockfile
- Telemetry dashboard for cap-hits
