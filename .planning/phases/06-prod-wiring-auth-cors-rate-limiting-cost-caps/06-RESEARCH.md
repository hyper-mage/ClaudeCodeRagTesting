# Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps - Research

**Researched:** 2026-05-08
**Domain:** FastAPI rate limiting (slowapi), counter-bounded LLM tool loop, Supabase Auth URL config, OpenRouter free-tier + cost alerts, CORS rejection-path verification
**Confidence:** HIGH (slowapi pin, fly suspend semantics, free-model catalog, chat.py loop site verified) / MEDIUM (Site-URL-changes-invalidate-tokens — no authoritative answer found, mitigated by D-15 "fresh email" instruction)

## Summary

This phase wires four prod-readiness controls into the already-deployed Fly + CF Pages stack: per-user rate limiting on `/api/chat`, a max-iterations cap on the chat tool-use loop, Supabase Auth redirect URLs for the prod CF origin, and a $0.01 OpenRouter alert with `:free` model as the structural cost cap. The phase touches 6 backend files, the smoke script, and two out-of-repo dashboards (Supabase + OpenRouter). No frontend code changes — the 429 contract is published for Phase 8 to consume.

The HARD GATE (does a `:free` OpenRouter model reliably support tool-calling?) **passes**: as of May 2026 OpenRouter's free catalog includes ≥10 tool-capable models. Recommended pick: `openai/gpt-oss-120b:free` (131K context, native tool/function calling, generally available since 2025-08, model weights public on HuggingFace = stable provider). The free-tier rate limit (20 RPM / 50 RPD with $0 balance, 1000 RPD with ≥$10 lifetime credits) is a comfortable second backstop on top of slowapi's per-user app cap.

The most subtle planning issue surfaced by research is that **`backend/routers/chat.py:460` does NOT currently accept `request: Request`** — slowapi's `@limiter.limit(...)` decorator silently fails without that parameter. Plan must explicitly add it. The second is a custom 429 handler that wraps slowapi's `RateLimitExceeded` and returns the D-06 JSON shape with a `Retry-After` header (slowapi's default handler returns plain text, not JSON).

**Primary recommendation:** Pin `slowapi==0.1.9`, set `LLM_MODEL=openai/gpt-oss-120b:free`, register `Limiter(key_func=user_id_key, storage_uri="memory://")` on `app.state`, decorate the chat route with `@limiter.limit(settings.chat_rate_limit)` after adding `request: Request` to its signature, refactor the `while True` at chat.py:564 into a counter-bounded `for iteration in range(...)` loop with graceful cap-hit SSE emission, mirroring `explorer_service.py:232` (counter+voluntary-stop+exhausted-flag).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Rate Limiting — Library, Storage, Scope, Key**
- D-01: Use `slowapi` (FastAPI-native, decorator + dependency model). Add `slowapi==<latest>` to `backend/requirements.txt` (researcher picks pinned version per Phase 1 D-12 reproducibility convention). FastAPI-idiomatic, well-maintained, integrates with `Request` and dependency injection cleanly.
- D-02: **In-memory storage.** `Limiter(storage_uri="memory://")`. Single Fly machine + `auto_stop_machines="suspend"` (Phase 4 D-09) means counters reset on resume — acceptable for portfolio. No Redis/Upstash dependency, no new secret.
- D-03: **Scope: `/api/chat` only.** Threads/documents/folders/auth routes are NOT rate-limited.
- D-04: **Key: Supabase `user_id` from the JWT** (already extracted by `get_user_id()` dependency in `auth.py`). slowapi key function reads it from `request.state.user_id` (or equivalent). **Never key by IP.**
- D-05: **Cap value: `20/minute` per user.** Configurable via `Settings.chat_rate_limit: str = "20/minute"`.

**Rate Limiting — 429 Response Shape**
- D-06: Custom 429 handler returns JSON: `{"error": "rate_limited", "detail": "Too many chat requests — slow down.", "retry_after_seconds": <int>}` with HTTP `Retry-After: <int>` header. Status 429.
- D-07: Frontend handling NOT in scope (Phase 8 PORT-02). Backend just emits the contract.

**Max-Iter Cap**
- D-08: **Value: 15 iterations.** Mirrors explorer's pattern (counter+graceful-stop architecture), not the numeric value.
- D-09: **Field: `Settings.chat_max_iterations: int = 15`** in `backend/config.py`, adjacent to `explorer_max_iterations`.
- D-10: **On-cap behavior: graceful assistant message.** Replace `while True:` at chat.py:564 with counted loop. On cap-hit: emit final SSE `content_delta` with markdown-italic message, append to `full_content` so it persists, exit cleanly with normal `done` SSE event.
- D-11: **Telemetry on cap-hit:** `logger.warning(...)` + LangSmith trace metadata `iteration_cap_hit=true`.

**Supabase Auth**
- D-12: **Site URL = `https://boardgame-rag-prod.pages.dev`**.
- D-13: **Redirect URLs allowlist:** `https://boardgame-rag-prod.pages.dev/**` + `http://localhost:5173/**` (both with `/**` wildcard).
- D-14: **Email templates: Supabase defaults.** No custom HTML.
- D-15: **Verification: manual signup E2E with FRESH throwaway email**, document each step pass/fail.

**OpenRouter Cost Controls**
- D-16: **Default model = OpenRouter `:free` tier model**, picked by researcher with verified tool-calling support. **HARD GATE.**
- D-17: **Paid toggle = single `LLM_MODEL` env swap.**
- D-18: **Cost cap config: zero balance.**
- D-19: **Alert: $0.01 threshold** in OpenRouter dashboard.
- D-20: **Alert delivery test: load $1 → swap to paid → 1 chat → confirm email → revert → drain.**

**CORS Rejection-Path Verification**
- D-21: **No new wiring** — Phase 5 already set CORS allowlist.
- D-22: **Test mechanism: extend `backend/scripts/fly_smoke.sh`** with `curl -H "Origin: https://evil.example"` assertion checking absence of `Access-Control-Allow-Origin: https://evil.example` echo OR 400 status.

### Claude's Discretion

- Exact slowapi version pin (D-01) — researcher checks current stable; planner pins explicitly.
- `chat_rate_limit` shape: string env var (`"20/minute"`) vs split int — pick whichever slowapi consumes cleanest.
- CORS rejection assertion location: extend `fly_smoke.sh` vs sibling `cors_smoke.sh`.
- Italic vs plain text wording for cap-hit message (D-10).
- LangSmith trace metadata key spelling (D-11): `iteration_cap_hit` vs `chat.cap_hit`.
- D-20 step 5 revert: manual `flyctl secrets set` vs `revert_to_free.sh` helper. Manual fine.
- `chat_max_iterations` default 15 vs lower after observing usage — not blocking.

### Deferred Ideas (OUT OF SCOPE)

- BYOK (per-user provider keys) — v1.2+
- Persistent rate-limit storage (Redis/Upstash)
- Document upload rate limit
- Global rate limit across all authenticated routes
- `allow_origin_regex` for CF Pages preview deploys
- Frontend 429 toast/banner UI — Phase 8 PORT-02
- Custom email templates / branding
- Light alert-test automation script
- `pip-tools` / lockfile
- Telemetry dashboard for cap-hits — Phase 7 or later
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | User can log in from prod frontend with Supabase Auth redirect URLs correctly configured for CF Pages domain (no redirect loops, email verification lands on prod) | Supabase URL Configuration semantics + `/**` wildcard syntax (Architecture Pattern 4) + manual signup E2E procedure (Pitfall 7 + D-15 verbatim) |
| SEC-04 | `/api/chat` enforces a per-authenticated-user rate limit (configurable via env) capping requests/min to prevent LLM cost blowout | slowapi 0.1.9 integration pattern with custom `key_func` reading user_id from request (Architecture Pattern 1 + Code Examples 1, 2, 3); 429 JSON contract + `Retry-After` header (Pattern 2) |
| SEC-05 | Main chat tool-use loop has max-iterations cap (mirror explorer's pattern) so runaway agent can't drain budget | Counter-bounded loop refactor at chat.py:564, mirroring explorer_service.py:232 (Code Example 4); LangSmith metadata tag for observability (Pattern 5) |
| SEC-06 | OpenRouter account has monthly spend cap or alert configured so provider-level cost is bounded independent of app-level limits | `:free` model pick `openai/gpt-oss-120b:free` (HARD GATE pass); $0 balance structurally bounds cost; $0.01 alert + delivery test procedure (Architecture Pattern 6) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python backend MUST use `venv` virtual environment — `backend/venv/` already exists; new dep `slowapi` installs there before requirements.txt commit.
- No LangChain, no LangGraph — raw SDK calls only. slowapi is non-LLM infra; safe.
- Use Pydantic for structured LLM outputs — applies to `Settings` extension (`chat_max_iterations: int`, `chat_rate_limit: str`).
- All tables need RLS — not relevant this phase (no schema changes).
- Stream chat responses via SSE — preserved; cap-hit emits a final `content_delta` then normal `done` event, no SSE error event.
- Module 2+ uses stateless completions — preserved.
- Plans go to `.agent/plans/` per CLAUDE.md, BUT this project uses GSD's `.planning/phases/` flow; the GSD workflow enforcement clause in CLAUDE.md takes precedence.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `slowapi` | `0.1.9` | Rate limiting middleware for FastAPI | Only mature, FastAPI-aware option; `Limiter` integrates cleanly with dependency injection. Used in production handling millions of requests/month. Verified latest stable on PyPI 2026-05-08. |
| `openai` SDK | `1.74.0` (already pinned) | LLM calls to OpenRouter | Already in use; OpenRouter is OpenAI-protocol-compatible. No change. |
| `langsmith` | `0.3.42` (already pinned) | Trace metadata for cap-hit | Already wired via `services/tracing.py`; new tag piggybacks on existing tracer context. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `limits` | (transitive of slowapi) | Storage + parser backend | Auto-installed; `memory://` URI is built-in. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `slowapi` | `fastapi-limiter` | Requires Redis (new infra dependency) — violates D-02 in-memory locked decision. |
| `slowapi` | Custom middleware | Reinventing token-bucket / fixed-window with race conditions — D-01 forbids hand-rolling. |
| `openai/gpt-oss-120b:free` | `meta-llama/llama-3.3-70b-instruct:free` | 70B has only 66K context (smaller than 131K of gpt-oss-120b). Tool support listed but smaller community track record on OpenRouter for sustained tool loops. |
| `openai/gpt-oss-120b:free` | `google/gemini-2.0-flash-exp:free` | Marked **experimental** on OpenRouter (per the `:exp` suffix in the slug); spec says "experimental and frequently down" matches Phase context warning (b). Use as fallback only. |
| `openai/gpt-oss-120b:free` | `qwen/qwen3-coder:free` | 262K context attractive, but coder-tuned; chat-tuned `gpt-oss-120b` is a closer fit for the agentic chat use case. |

**Installation:**
```bash
# from backend/ directory with venv activated:
pip install slowapi==0.1.9
pip freeze | grep -i slowapi  # confirm: slowapi==0.1.9 (and limits transitive)
```

**Version verification (2026-05-08):**
- `slowapi==0.1.9` — verified via `pip index versions slowapi` against the project venv. Released 2024-02 per PyPI. Maintenance status: low activity, BUT the API surface used here (`Limiter`, `@limiter.limit`, `RateLimitExceeded`, `_rate_limit_exceeded_handler`) is stable and unchanged across the 0.1.x line. The "alpha quality" warning in the package metadata is conservative; production users report stability at scale.
- `openai/gpt-oss-120b:free` — verified at https://openrouter.ai/openai/gpt-oss-120b:free on 2026-05-08. Native tool/function-calling support, 131,072 context window, public model weights on HuggingFace (stable provider).

## Architecture Patterns

### Recommended Project Structure (additive — no new dirs)

```
backend/
├── main.py                 # MODIFY: add Limiter + 429 handler registration
├── auth.py                 # MODIFY (small): set request.state.user_id
├── config.py               # MODIFY: add chat_max_iterations, chat_rate_limit
├── requirements.txt        # MODIFY: pin slowapi==0.1.9
└── routers/
    └── chat.py             # MODIFY: add request: Request to signature; @limiter.limit; counter-bounded loop
└── scripts/
    └── fly_smoke.sh        # MODIFY: append CORS-rejection + rate-limit-burst assertions
```

### Pattern 1: slowapi Limiter on app.state with custom user-id key_func

**What:** Initialize `Limiter` once at module import in `main.py`, register on `app.state.limiter`, attach a custom `key_func` that reads `request.state.user_id` populated by the auth dependency.

**When to use:** This phase, exactly once. The route decorator pattern is the canonical slowapi approach.

**Critical quirk:** The decorated route function **MUST accept `request: Request` as a parameter**. Without it, slowapi cannot extract the request to invoke `key_func` and the rate limit silently no-ops. `backend/routers/chat.py:460` currently does NOT accept `request: Request` — the plan must add it.

**Example:**
```python
# backend/main.py
from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import get_settings

settings = get_settings()


def user_id_key(request: Request) -> str:
    """slowapi key_func: rate limit per Supabase user_id.

    Auth dependency (`get_user_id`) runs before this is read because
    slowapi invokes key_func AFTER the route's dependencies resolve.
    Falls back to "anonymous" so an unauthenticated request — which
    will 401 immediately at the auth dep anyway — can't crash the limiter.
    """
    return getattr(request.state, "user_id", None) or "anonymous"


limiter = Limiter(key_func=user_id_key, storage_uri="memory://")

app = FastAPI(title="Agentic RAG API")
app.state.limiter = limiter

# ... CORS middleware unchanged ...
```

### Pattern 2: Custom 429 JSON handler with Retry-After header

**What:** Override slowapi's default plaintext 429 with the D-06 JSON contract. slowapi's `RateLimitExceeded` exception carries `.detail` with limit metadata (e.g. `"20 per 1 minute"`); custom handler computes `retry_after_seconds` from the limit window and returns JSON.

**When to use:** Once in `main.py`, registered via `app.add_exception_handler(RateLimitExceeded, handler)`.

**Example:**
```python
# backend/main.py (continued)
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # exc.detail is e.g. "20 per 1 minute"; parse the window seconds.
    # Simpler: read from the exc.limit object (slowapi >=0.1.9 exposes .limit.GRANULARITY.seconds).
    retry_after = int(exc.limit.limit.GRANULARITY.seconds)
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "detail": "Too many chat requests — slow down.",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
```

> **Source:** slowapi `extension.py` exposes `exc.limit.limit.GRANULARITY` (the `limits` lib's `Granularity` namedtuple). If the attribute path proves brittle in 0.1.9, fallback parses `str(exc.detail)` with regex — but the documented attribute path is preferred.

### Pattern 3: Auth dependency populates request.state.user_id

**What:** `get_user_id()` in `backend/auth.py` already takes `request: Request`; one extra line sets `request.state.user_id = user_id` before returning. The slowapi `key_func` reads from there.

**Why:** slowapi's `key_func(request)` is called by the rate-limit decorator wrapper — it does NOT have access to FastAPI's dependency-injection context, so it cannot itself call `Depends(get_user_id)`. The bridge is `request.state`.

**Example:**
```python
# backend/auth.py — modify the existing function (3 lines added)
def get_user_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    auth_header = request.headers.get("Authorization")
    # ... existing JWT decode logic unchanged ...
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token: no sub claim")

    request.state.user_id = user_id  # NEW: bridge for slowapi key_func
    return user_id
```

> **Race-condition note:** slowapi runs the rate check INSIDE the route function (after FastAPI resolves deps). Order of operations: (1) request arrives, (2) FastAPI resolves `Depends(get_user_id)` → JWT verified, `request.state.user_id` set, (3) `@limiter.limit(...)` wrapper invokes `user_id_key(request)`, gets the right user_id, (4) actual route body runs. No race.

### Pattern 4: Supabase Auth URL configuration with `/**` wildcards

**What:** Two dashboard fields control where confirmation/reset emails land.

| Field | Value | Semantics |
|-------|-------|-----------|
| Site URL | `https://boardgame-rag-prod.pages.dev` | What `{{ .SiteURL }}` expands to in default email templates. Single value, no list. |
| Redirect URLs (allowlist) | `https://boardgame-rag-prod.pages.dev/**` AND `http://localhost:5173/**` | Allowed redirect destinations after magic-link / confirmation click. Wildcard `/**` matches any path (including `/auth/callback`, hash fragments, query strings). |

**Wildcard syntax (verified via Supabase docs):**
- `https://app.example.com/**` — matches any path. Use this.
- `https://app.example.com/*` — matches one path segment only. Don't use; breaks deep links.
- `https://*.example.com/auth/callback` — matches subdomain wildcard with fixed path. Not needed here (no preview deploys).

**Dashboard path:** Authentication → URL Configuration → Site URL / Redirect URLs

**Pitfall:** When Site URL changes, Supabase generates new confirmation links from the new value going forward. Whether **already-issued** confirmation tokens (sitting in someone's inbox) survive the change is **not authoritatively documented**. CONTEXT.md D-15 sidesteps this by requiring a FRESH throwaway email for the verification flow — don't depend on old tokens.

### Pattern 5: Counter-bounded LLM tool loop (mirroring explorer_service.py)

**What:** Replace `while True:` at `routers/chat.py:564` with a counter that increments per outer iteration and exits gracefully on cap-hit.

**Where exactly to test the cap:** At the **top of the outer loop**, BEFORE entering the inner `for event in stream_chat_completion(...)` block. This is where the explorer mirrors it (`while iteration < settings.explorer_max_iterations: iteration += 1`).

**Why top-of-loop, not after-tool-call:** A tool call mid-iteration is part of the SAME LLM turn that already consumed the iteration slot. Cutting in the middle of a tool execution would (a) abandon a half-streamed assistant message, (b) leave dangling `tool_calls` without `tool` results in `current_messages` (model-confusing on next call, but moot if we exit), (c) break the SSE contract (tool_start without tool_result). Top-of-loop = clean boundary.

**Cap-hit emission (mirrors explorer's voluntary-stop branch):**
1. Emit one final SSE `content_delta` with the markdown-italic notice.
2. Append same text to `full_content` so the post-loop `db.table("messages").update({"content": full_content, ...})` persists it.
3. `logger.warning(...)` with user_id + thread_id + cap value.
4. Tag LangSmith trace metadata `iteration_cap_hit=true`.
5. `break` the outer loop. The existing `done` SSE event fires normally afterward. No SSE `error` event.

**Important:** `chat.py` already has a voluntary-stop branch at line 794 (`if not tool_call_happened: break`). Keep both: voluntary stop is the main exit path; cap is the BACKSTOP for adversarial/buggy cases. The cap-hit branch is structurally a SECOND `break`, not a replacement.

### Pattern 6: OpenRouter `:free` model + $0 balance + $0.01 alert

**What:** Three-layer cost cap.

1. **Structural floor:** `LLM_MODEL` env var points to a `:free` model. With `$0` account balance, free models bypass the balance check; paid models would 402 immediately. So a paid request CANNOT fire while balance is $0.
2. **Alert:** $0.01 threshold in OpenRouter Account → Alerts. Email recipient = developer email of record. Fires the moment any non-zero spend appears (defense against accidental paid-model commits).
3. **Free-tier upstream limit:** OpenRouter caps `:free` models at **20 RPM / 50 RPD with $0 balance** (or 1000 RPD with ≥$10 lifetime credits purchased). This is a SECOND backstop on top of slowapi's per-user 20/min app cap.

**Alert delivery test procedure (D-20, verbatim):**
1. Load $1 USD into OpenRouter balance via dashboard.
2. `flyctl secrets set LLM_MODEL=openai/gpt-4o-mini -a boardgame-rag-prod` (researcher's `LLM_MODEL_PAID_OPTION`); `fly deploy` (or rely on auto-restart from secret change).
3. Send a single chat message ("hi") via prod UI. Burns ~$0.001.
4. Wait ≤5 min for alert email at developer inbox; capture screenshot with timestamp.
5. Revert: `flyctl secrets set LLM_MODEL=openai/gpt-oss-120b:free -a boardgame-rag-prod`.
6. Drain remaining ~$0.999: send a few more tiny test requests OR withdraw via the OpenRouter dashboard. Document final balance.

**Recommended `LLM_MODEL_PAID_OPTION`:** `openai/gpt-4o-mini` (cheap, tool-capable, OpenAI-protocol native). Alternative: `anthropic/claude-3.5-haiku`. Both burn well under $0.01 per "hi" request.

### Anti-Patterns to Avoid

- **Decorating an `async def` route without `request: Request` param:** slowapi silently no-ops. Always include the parameter explicitly. (See chat.py:460 — current signature is missing it.)
- **Using `IPLimiter` / `get_remote_address` as `key_func`:** Behind Cloudflare → Fly proxy chain, every user appears to share the same proxy IP. D-04 forbids this.
- **Reading `request.state.user_id` in `key_func` BEFORE the auth dep sets it:** Won't happen if dep order is correct, but if a future change moves rate-limit middleware ABOVE the route's auth dep (e.g. via `add_middleware`), the bridge breaks. Stick to the per-route decorator pattern.
- **Embedding the `:free` model id in code:** It's an env-driven swap (D-17). Code reads `settings.llm_model`; only the Fly secret value changes between free/paid.
- **Setting Site URL to a CF Pages preview/subdomain pattern:** Breaks email link expansion. Only `https://boardgame-rag-prod.pages.dev` (the prod alias) goes in Site URL. Wildcards belong in the Redirect URLs allowlist, not Site URL.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-user rate limiting | Custom decorator with dict + lock | `slowapi==0.1.9` | Token-bucket race conditions, sliding-window math, headers handling, and exception class are all already solved. |
| Tool-loop iteration capping | Custom retry/backoff library | Plain integer counter | The explorer pattern is 5 lines. Anything bigger is over-engineered. |
| Supabase JWT verification | Hand-decode JWT | Existing `auth.py` `get_user_id()` | Already wired with PyJWKClient + algorithm detection. Just add `request.state.user_id = user_id` line. |
| Cost capping | Custom usage tracker | `:free` model + $0 balance + dashboard alert | Provider-side enforcement is bulletproof. App-side tracking has consistency holes. |

**Key insight:** Every piece of infrastructure for this phase is already-solved. The phase is ~80% wiring (one-line additions, env config, dashboard clicks) and ~20% novel logic (the cap-hit graceful exit branch). Don't over-architect.

## Runtime State Inventory

> Phase 6 is a code+config wiring phase, not a rename/refactor. No data migrations needed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — verified by inspection of phase scope (no schema changes; no string-replace across DB columns). | None |
| Live service config | (1) Supabase Auth URL Configuration (Site URL + Redirect URLs) — must be set in prod project dashboard, NOT in git. (2) OpenRouter dashboard alert ($0.01) — also out-of-repo. (3) Fly secret `LLM_MODEL` — must be set to `openai/gpt-oss-120b:free` via `flyctl secrets set`. | Manual dashboard config (Supabase + OpenRouter); single `flyctl secrets set` command for `LLM_MODEL`. |
| OS-registered state | None — no Windows Task Scheduler / launchd / systemd registrations. Fly machines are container-restart-on-secret-change; no persistent OS state. | None |
| Secrets/env vars | New env vars introduced: `CHAT_MAX_ITERATIONS=15` (optional override, default in code), `CHAT_RATE_LIMIT="20/minute"` (optional override). `LLM_MODEL` value changes (already an existing secret). No new SOPS or vault keys. | Document in `.env.prod` comment block; optionally `flyctl secrets set CHAT_MAX_ITERATIONS=15` if non-default desired (planner's call). |
| Build artifacts / installed packages | New transitive: `limits` (slowapi dep) lands in `backend/venv/` and Docker image after `pip install`. No stale artifacts to clean. | Rebuild Docker image as part of `fly deploy`. Phase 2's Dockerfile pip-installs from requirements.txt — pin propagates automatically. |

## Common Pitfalls

### Pitfall 1: Route function missing `request: Request` parameter
**What goes wrong:** `@limiter.limit(...)` decorator silently no-ops. Burst tests pass (no 429), and you ship a phase that "looks" rate-limited but isn't.
**Why it happens:** slowapi's wrapper introspects the route's call signature for a `Request`. If absent, it falls through without invoking `key_func`. No exception, no warning.
**How to avoid:** `backend/routers/chat.py:460` currently is `async def send_message(thread_id: str, body: MessageCreate, user_id: str = Depends(get_user_id))`. **Plan task MUST explicitly add `request: Request` as the first parameter** (after `thread_id` is fine; FastAPI resolves by type+name).
**Warning signs:** Burst test in `fly_smoke.sh` issues 25 requests and gets 0 × 429 → assume signature is missing `Request` before assuming any other failure mode.

### Pitfall 2: slowapi default 429 is plaintext, not JSON
**What goes wrong:** Without a custom handler, 429 body is `"Rate limit exceeded: 20 per 1 minute"` (plain text, no JSON). Frontend (Phase 8) breaks when it tries to `.json()` it.
**Why it happens:** `_rate_limit_exceeded_handler` returns plaintext PlainTextResponse by default.
**How to avoid:** Register a custom handler per Pattern 2. Don't use `slowapi._rate_limit_exceeded_handler` — write your own.
**Warning signs:** `curl -i ... | grep -i content-type` on a 429 shows `text/plain` instead of `application/json`.

### Pitfall 3: Fly suspend/resume preserves slowapi's in-memory counter — but reset semantics still apply
**What goes wrong:** Question raised in Phase context: do in-memory slowapi counters survive `auto_stop_machines="suspend"`? Surprising answer: **YES, they do** — Fly's suspend uses Firecracker snapshots which preserve full memory contents (per Fly docs: "suspend lets you pause a running Fly Machine and save its complete state, including memory, to persistent storage. When resumed, the machine picks up exactly where it left off"). So a user who hit 20 requests at minute T, gets suspended at T+30s, resumed at T+45s, will resume with their counter intact and still see 429 until the limits-library window expires.
**Why this matters:** Counter-reset on resume is NOT a behavior to plan around for SEC-04. The window is wall-clock-based inside `limits` library, not process-uptime-based, so even if counters reset they'd typically be expired by the time of the next request. Either way, behavior is correct.
**Caveat:** If Fly is FORCEFULLY restarted (e.g. machine moves to a different host, or a rare crash), counters DO reset. Acceptable for portfolio. If scaling to >1 machine, counters become per-process (sharded) — flagged in CONTEXT.md as deferred.
**Warning signs:** None in normal operation. If multi-machine becomes a thing, switch to Redis-backed slowapi (deferred).

### Pitfall 4: `:free` model rate limit confusion (OpenRouter upstream vs slowapi app)
**What goes wrong:** Developer thinks slowapi's 20/min cap is what users hit. In reality, OpenRouter's `:free` upstream tier has its own 20 RPM / 50 RPD limit that fires from the LLM call, not the chat endpoint. A user hitting OpenRouter's limit sees a 429 from `openai.RateLimitError` deep in `stream_chat_completion`, NOT from slowapi.
**Why it happens:** Two layers, same numbers.
**How to avoid:** Document in PLAN that the slowapi limit is at-or-below upstream so users hit the friendly app contract first. Wrap the OpenRouter call in try/except for `RateLimitError` and surface a friendly SSE error event (Phase 8 PORT-02 owns the UI; backend can return the existing SSE `error` event shape). For SEC-04 verification (`fly_smoke.sh` burst test), this distinction matters: assert the 429 body is `{"error": "rate_limited", ...}` (slowapi shape), NOT a plaintext or OpenAI-error shape.
**Warning signs:** 429 body is plaintext or contains "OpenRouter" or "rate_limit_exceeded" without "rate_limited" → OpenRouter upstream fired before slowapi.

### Pitfall 5: LangSmith trace metadata across SSE generator yields
**What goes wrong:** Setting LangSmith metadata from inside an async generator after a `yield` runs after the `@traceable` decorator's tracer context may have closed. Tag silently doesn't appear on the trace.
**Why it happens:** `langsmith.traceable` opens a tracer context for the function call; SSE-style generators that yield mid-execution sometimes outlive the context if exceptions propagate.
**How to avoid:** Two options:
- Option A (preferred): Use `langsmith.run_helpers.get_current_run_tree()` to get the active run inside the generator, then `run.add_metadata({"iteration_cap_hit": True})`. This works as long as the generator is still inside the traced function's call stack.
- Option B (simpler): Add the tag to the input `metadata=` argument of `stream_chat_completion(...)` BEFORE the cap-hit yield, OR set an `os.environ["LANGSMITH_..."]`-style tag (not recommended; pollutes globals).
**Warning signs:** Trace appears in LangSmith but the `iteration_cap_hit` tag is missing on cap-hit cases. Quick smoke: write an explicit unit test that triggers cap-hit and queries the LangSmith API for the resulting run's metadata.

### Pitfall 6: CORS rejection-path test asserts the WRONG thing
**What goes wrong:** Test asserts `status code != 200`. FastAPI's `CORSMiddleware` returns 200 even for non-allowlisted origins on simple requests — it just OMITS the `Access-Control-Allow-Origin` header. For preflight (OPTIONS) requests, behavior depends on the spec issue: the middleware returns 400 if Origin doesn't match. So both 200-with-missing-header AND 400-on-OPTIONS are valid rejection signals.
**Why it happens:** CORS is browser-enforced via header echo, not server-enforced via status code (mostly). The browser checks `Access-Control-Allow-Origin` matches the request `Origin` and rejects the response if not. Server typically completes the request normally (for simple requests).
**How to avoid:** Use the assertion form D-22 already encodes:
```bash
# In fly_smoke.sh — CORS rejection assertion
RESP_HEADERS=$(curl -sI -X OPTIONS -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: POST" \
  "$FLY_URL/api/threads/dummy/messages")
echo "$RESP_HEADERS" | grep -qi "Access-Control-Allow-Origin: https://evil.example" \
  && fail "CORS allowed evil.example — rejection path broken" \
  || ok "CORS rejection path: Access-Control-Allow-Origin not echoed for evil.example"
```
The assertion is "the dangerous header echo is ABSENT". Use `grep -q` with negation. Don't rely on status code alone.
**Warning signs:** Test passes against a backend with `allow_origins=["*"]` (it shouldn't — Phase 1 D-03 forbids that combo).

### Pitfall 7: Site URL change MAY invalidate already-issued email tokens (unverified)
**What goes wrong:** A user with a pending confirmation email from BEFORE the Site URL change clicks the link AFTER the change; link goes to the old URL or fails verification.
**Why it happens:** Tokens are validated by Supabase server-side; the URL embedded in the link is what `{{ .SiteURL }}` expanded to at email-send time. If old URL is no longer on the redirect allowlist, click fails.
**How to avoid:** D-15 already requires a FRESH throwaway email for verification. Don't try to verify with an old test user's pending confirmation link. Send a NEW signup AFTER Site URL is updated, capture link from the new email.
**Warning signs:** Verification of "logging in for the first time" fails with 422 / "redirect_uri not allowed" → re-issued, fresh signup → works → diagnosis confirmed.

### Pitfall 8: JWT expiry mid-burst doesn't break key continuity
**What goes wrong (or doesn't):** Concern raised: if a user's JWT expires mid-burst, does slowapi see them as a NEW key (counter resets to 0)?
**Why it doesn't happen:** `request.state.user_id` is set from `payload.get("sub")` — the Supabase user UUID. `sub` is stable across token refreshes (the token itself rotates, the user identity doesn't). If the user gets a 401 mid-burst, they re-authenticate; new token still has same `sub`, slowapi sees same key, counter intact.
**Caveat:** A 401 followed by a fresh login DOES NOT consume a slowapi slot (auth dep raises before route body runs, so `@limiter.limit` doesn't tick — wait, this is wrong).

> **Correction needed (LOW confidence):** The order is dep-resolution then route-body, but `@limiter.limit` is route-decorator-level. If `Depends(get_user_id)` raises 401 BEFORE the rate-limit wrapper invokes `key_func`, the 401 bypasses the limiter and doesn't tick the counter. **Verify with a 4-line test in execution:** issue 1 valid request, then 5 invalid requests with bad token, then 19 valid requests; if the 20th valid request hits 429, dep-first-no-tick is confirmed. If the 20th passes (because invalids didn't tick), wonderful. If the burst limit fires earlier, planner needs a different approach.

**How to avoid in any case:** Plan a 4-line dependency-order verification in Wave 1 BEFORE the smoke test depends on it.
**Warning signs:** Mid-test counters behave non-monotonically.

## Code Examples

### Example 1: Full `main.py` with Limiter wired

```python
# backend/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from routers import threads, chat, documents, folders
from services.tracing import setup_tracing
from config import get_settings


setup_tracing()
settings = get_settings()


def user_id_key(request: Request) -> str:
    """Rate-limit key: Supabase user_id from JWT (set by auth dep on request.state)."""
    return getattr(request.state, "user_id", None) or "anonymous"


limiter = Limiter(key_func=user_id_key, storage_uri="memory://")

app = FastAPI(title="Agentic RAG API")
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # exc.limit.limit is a `limits` library RateLimitItem; .GRANULARITY.seconds is the window.
    try:
        retry_after = int(exc.limit.limit.GRANULARITY.seconds)
    except AttributeError:
        retry_after = 60  # fallback for the "20/minute" case
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limited",
            "detail": "Too many chat requests — slow down.",
            "retry_after_seconds": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(threads.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(folders.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```
**Source:** Composed from slowapi docs + FastAPI CORS docs + existing main.py.

### Example 2: chat.py route decorated with rate limit

```python
# backend/routers/chat.py — modify the existing send_message
from fastapi import APIRouter, Depends, HTTPException, Request
# ... other imports unchanged ...
from main import limiter  # circular-import risk; alternative: from limiter_module import limiter

# OR avoid circular import by exposing limiter via app.state at request time:
# def get_limiter(request: Request) -> Limiter:
#     return request.app.state.limiter
# Then: @get_limiter.limit(...) — but that doesn't work syntactically.
# Cleanest: factor `limiter` into a tiny `backend/limiter.py` module imported by both main.py and chat.py.

@router.post("/{thread_id}/messages")
@limiter.limit(get_settings().chat_rate_limit)  # "20/minute"
@traceable(name="chat_send_message")
async def send_message(
    request: Request,                     # NEW — required for slowapi
    thread_id: str,
    body: MessageCreate,
    user_id: str = Depends(get_user_id),  # populates request.state.user_id
):
    # ... existing body unchanged ...
```

> **Decorator order:** `@router.post` outermost, then `@limiter.limit`, then `@traceable`. Per slowapi docs: "the route decorator must be above the limit decorator." `@traceable` is innermost so it wraps the actual function, not the limiter wrapper.

> **Circular-import note:** `chat.py` imports `limiter` from `main.py`, which imports routers including `chat.py`. **Recommended fix:** create `backend/limiter.py`:
> ```python
> # backend/limiter.py
> from fastapi import Request
> from slowapi import Limiter
>
> def user_id_key(request: Request) -> str:
>     return getattr(request.state, "user_id", None) or "anonymous"
>
> limiter = Limiter(key_func=user_id_key, storage_uri="memory://")
> ```
> Then both `main.py` and `chat.py` import from `limiter.py`. Standard Python pattern.

**Source:** slowapi extension.py + FastAPI Request docs + existing chat.py structure.

### Example 3: auth.py one-line addition

```python
# backend/auth.py — modify get_user_id (only the bridge line is new)
def get_user_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization token")
    token = auth_header.split(" ", 1)[1]
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        if alg == "HS256":
            signing_key = settings.supabase_jwt_secret
        else:
            jwk_client = _get_jwk_client(settings)
            signing_key = jwk_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(token, signing_key, algorithms=[alg], audience="authenticated", leeway=30)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no sub claim")
        request.state.user_id = user_id   # NEW: bridge for slowapi key_func
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### Example 4: Counter-bounded chat loop refactor

```python
# backend/routers/chat.py — replace `while True:` at line 564
# BEFORE:
#     while True:
#         tool_call_happened = False
#         for event in stream_chat_completion(...):
#             ...
#         if not tool_call_happened:
#             break

# AFTER:
CAP_HIT_NOTICE = (
    "\n\n_I hit the tool-call limit ({n}) before finishing this answer. "
    "Try narrowing the question or breaking it into steps._"
)

iteration = 0
cap_hit = False
while iteration < settings.chat_max_iterations:
    iteration += 1
    tool_call_happened = False

    for event in stream_chat_completion(
        current_messages,
        tools=tools,
        tool_guide=TOOL_SELECTION_GUIDE if tools else None,
        source_hint=source_scope,
        scope_hint=scope_hint if scope_hint else None,
    ):
        # ... existing event handling unchanged (text_delta / tool_call dispatch) ...
        pass  # placeholder for the existing 200 lines

    if not tool_call_happened:
        break  # voluntary stop — main exit path

else:
    # while-else fires when the loop exhausts without breaking — i.e. cap hit.
    cap_hit = True

if cap_hit:
    notice = CAP_HIT_NOTICE.format(n=settings.chat_max_iterations)
    full_content += notice
    yield {
        "event": "content_delta",
        "data": json.dumps({"text": notice}),
    }
    logger.warning(
        f"Chat loop hit max_iterations cap "
        f"({settings.chat_max_iterations}) for user {user_id}, thread {thread_id}"
    )
    # LangSmith metadata tag — Pitfall 5 applies. Use run_helpers if @traceable is active.
    try:
        from langsmith.run_helpers import get_current_run_tree
        run = get_current_run_tree()
        if run is not None:
            run.add_metadata({"iteration_cap_hit": True, "cap_value": settings.chat_max_iterations})
    except Exception as e:
        logger.debug(f"LangSmith metadata tag failed (non-fatal): {e}")

# existing post-loop persistence logic continues unchanged:
db.table("messages").update({"content": full_content, ...}).eq(...).execute()
yield {"event": "done", ...}
```

> **Why `while-else`:** Pythonic way to detect "loop exited because counter exhausted" vs "loop exited because of `break`". Cleaner than a flag manually toggled before each `break`.

> **Edge case:** If the LAST iteration produces a `text_delta`-only response (no tool calls), `tool_call_happened` stays False, voluntary `break` fires, `cap_hit` stays False — correct behavior, no spurious cap notice.

**Source:** explorer_service.py:232 (counter pattern) + chat.py current structure (verified at lines 564-795).

### Example 5: fly_smoke.sh extensions for SEC-04 + CORS rejection

```bash
# Append to backend/scripts/fly_smoke.sh after the existing Step 5 SSE check.

# --- 6. Rate-limit burst (SEC-04) -------------------------------------
# Issue 25 rapid-fire chat requests; expect ≥1 × 429 with the slowapi JSON shape.
log "Burst: 25 rapid /api/chat requests, expect ≥1 × 429"
BURST_429=0
BURST_429_BODY=""
for i in $(seq 1 25); do
  CODE=$(curl -sS -o /tmp/burst_body_$i -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    "$FLY_URL/api/threads/$THREAD_ID/messages" \
    -d '{"content":"hi"}' 2>/dev/null)
  if [ "$CODE" = "429" ]; then
    BURST_429=$((BURST_429 + 1))
    [ -z "$BURST_429_BODY" ] && BURST_429_BODY=$(cat /tmp/burst_body_$i)
  fi
done
[ "$BURST_429" -ge 1 ] || fail "burst test got 0 × 429 (expected ≥1) — check @limiter.limit decorator + Request param (RESEARCH Pitfall 1)"
echo "$BURST_429_BODY" | jq -e '.error == "rate_limited"' >/dev/null \
  || fail "429 body wrong shape — expected {\"error\":\"rate_limited\",...}, got: $BURST_429_BODY"
ok "Rate limit fired $BURST_429 × 429 with correct JSON body"

# --- 7. CORS rejection (SEC-02 verification, D-22) --------------------
log "CORS: verify non-allowlisted origin gets no Access-Control-Allow-Origin echo"
CORS_RESP=$(curl -sI -X OPTIONS \
  -H "Origin: https://evil.example" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: authorization,content-type" \
  "$FLY_URL/api/threads/$THREAD_ID/messages" 2>&1 || true)
if echo "$CORS_RESP" | grep -qi "Access-Control-Allow-Origin: https://evil.example"; then
  fail "CORS allowed evil.example — rejection path broken (RESEARCH Pitfall 6)"
fi
ok "CORS rejection: Access-Control-Allow-Origin NOT echoed for evil.example"
```

**Source:** Pattern 5 + Pitfall 6, integrated into existing fly_smoke.sh structure (lines 73-111).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| IP-based rate limiting | User-id-based rate limiting (per Supabase JWT sub claim) | This phase | Behind reverse proxies (CF → Fly), IP is meaningless. user_id is the only fair identifier. |
| `while True:` agent loops | Counter-bounded loops with graceful cap exit | Industry shift since LLM agent loops became common (~2024) | Mandatory backstop against budget runaway. Numeric value (15 vs 6 vs 100) tunes per workload. |
| Loading credit balance for spend cap | $0 balance + `:free` model + alert at $0.01 | Convenient for $0-cost portfolios | Provider-side enforcement is bulletproof. But requires the `:free` model to support tools — historically NOT a given. |
| Plain CORS allowlist | CORS allowlist + rejection-path test | This phase (formalization) | Verifies the allowlist actually rejects, not just allows. Catches accidental `["*"]` regressions. |

**Deprecated/outdated:**
- `slowapi`'s default `_rate_limit_exceeded_handler` (returns plaintext) — superseded by custom JSON handler in 2024+ FastAPI projects.
- `allow_origins=["*"]` with `allow_credentials=True` — spec-invalid since CORS spec clarification ~2020. Already fixed in Phase 1.
- `gemini-2.0-flash-exp:free` as a primary `:free` choice — `:exp` suffix flags it experimental; gpt-oss-120b:free has surpassed it for reliable production use.

## Open Questions

1. **LangSmith trace metadata mid-generator**
   - What we know: `run_helpers.get_current_run_tree()` works inside `@traceable`-wrapped functions; SSE generator is INSIDE such a function.
   - What's unclear: Whether the run is still "current" after multiple `yield`s in an async generator. Documentation is thin.
   - Recommendation: Implement Option A (run_helpers); if smoke shows missing tags, fall back to Option B (set metadata on the LangSmith input args before cap-hit yield).

2. **JWT-expiry counter-tick semantics**
   - What we know: Auth dep raises 401 BEFORE route body runs.
   - What's unclear: Whether slowapi's `@limit` decorator runs auth dep first (FastAPI order) — so 401s do NOT tick the counter — or pre-empts. (Pitfall 8.)
   - Recommendation: 4-line verification test in Wave 1 before depending on it; document outcome.

3. **slowapi `exc.limit.limit.GRANULARITY.seconds` attribute path**
   - What we know: `limits` library exposes `Granularity` namedtuple.
   - What's unclear: Exact attribute path on slowapi's `RateLimitExceeded` exception in 0.1.9 vs 0.1.8.
   - Recommendation: Add a try/except fallback (Example 1 already has one — defaults to 60 seconds for "20/minute").

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `slowapi` (PyPI) | Rate limiting (D-01) | Will install | 0.1.9 | None — locked decision |
| `flyctl` CLI | Secret updates, deploy | ✓ (Phase 4 used it) | n/a | None — required |
| OpenRouter dashboard | Alert config (D-19), balance loading (D-20) | ✓ (account already exists per Phase 4 secrets) | n/a | None |
| Supabase prod project dashboard | URL Configuration (D-12, D-13) | ✓ (Phase 3 deliverable) | n/a | None |
| Throwaway email account for D-15 verification | Manual signup E2E | Developer-provided | n/a | Test alias (`+suffix@gmail.com`) on existing inbox |
| `curl` + `jq` | smoke script burst + CORS assertions | ✓ (Phase 4 already uses) | n/a | None |
| LangSmith project `boardgame-rag-prod` | Trace metadata tag (D-11) | ⚠️ Pending — Phase 7 deliverable | n/a | Tag still recorded; will appear in dev project until Phase 7 swaps the project name. **Non-blocking.** |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:**
- LangSmith prod project — Phase 7 owns; Phase 6 emits the tag regardless, it just lands in dev project. Document so Phase 7 verifies prod project sees the tag post-swap.

## Validation Architecture

> Nyquist gate enabled (workflow.nyquist_validation = true in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest==8.4.2` + `pytest-asyncio==0.23.8` (already in `backend/requirements.txt`) |
| Config file | None at repo root; tests live in `backend/tests/`. Sufficient — pytest auto-discovers. |
| Quick run command | `cd backend && pytest tests/ -x -q` (single test file or marker if narrowed) |
| Full suite command | `cd backend && pytest tests/` (all backend tests) |
| Manual run command | `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Manual signup from prod CF URL → email lands → click → CF prod URL → logged in → chat works | manual-only | n/a (D-15 manual checklist with timestamps + screenshots) | ❌ Wave 0 — captured as PLAN.md verification checklist |
| SEC-04 (limiter wired) | `@limiter.limit("20/minute")` applies to /api/chat with key_func=user_id | unit | `pytest tests/test_rate_limit.py::test_chat_route_decorated -x` | ❌ Wave 0 |
| SEC-04 (key extraction) | `user_id_key(request)` returns `request.state.user_id` when set, else "anonymous" | unit | `pytest tests/test_rate_limit.py::test_user_id_key_func -x` | ❌ Wave 0 |
| SEC-04 (429 contract) | 429 response carries JSON `{error, detail, retry_after_seconds}` + `Retry-After` header | unit | `pytest tests/test_rate_limit.py::test_429_response_shape -x` | ❌ Wave 0 |
| SEC-04 (e2e burst) | 25 rapid requests against deployed Fly URL produce ≥1 × 429 with correct body | smoke (manual run) | `bash backend/scripts/fly_smoke.sh $FLY_URL` (extended with Example 5 step 6) | ✅ existing — extend |
| SEC-04 (auth-fail bypass) | 5 requests with bad JWT do NOT tick the counter (Pitfall 8) | unit | `pytest tests/test_rate_limit.py::test_auth_fail_does_not_tick -x` | ❌ Wave 0 |
| SEC-05 (cap value) | `Settings.chat_max_iterations == 15` default, env-overridable | unit | `pytest tests/test_config.py::test_chat_max_iterations_default -x` | ❌ Wave 0 |
| SEC-05 (cap-hit graceful) | Loop exhausting cap emits final SSE `content_delta` with italic notice + ends with normal `done` event | integration | `pytest tests/test_chat_cap.py::test_cap_hit_graceful_exit -x` (mocks LLM to always return tool_calls) | ❌ Wave 0 |
| SEC-05 (logger.warning) | Cap-hit emits `logger.warning` containing user_id + thread_id | unit | `pytest tests/test_chat_cap.py::test_cap_hit_logs_warning -x` (caplog fixture) | ❌ Wave 0 |
| SEC-05 (LangSmith tag) | Cap-hit emits `iteration_cap_hit=true` metadata on the active LangSmith run | integration | `pytest tests/test_chat_cap.py::test_cap_hit_langsmith_tag -x` (mocks `get_current_run_tree`) | ❌ Wave 0 |
| SEC-05 (voluntary stop preserved) | Loop with no tool calls breaks normally; cap-hit branch NOT triggered | unit | `pytest tests/test_chat_cap.py::test_voluntary_stop_preserved -x` | ❌ Wave 0 |
| SEC-06 (free model active) | `LLM_MODEL` Fly secret is a `:free` slug after deploy | smoke (manual) | `flyctl secrets list -a boardgame-rag-prod \| grep LLM_MODEL` (digest only); body verified via deploying + chat smoke | ✅ existing |
| SEC-06 (alert configured) | $0.01 alert exists in OpenRouter dashboard with developer email | manual-only | n/a (PLAN.md verification with screenshot) | ❌ Wave 0 |
| SEC-06 (alert delivered) | Test paid swap → 1 chat → email received (D-20 procedure) | manual-only | n/a (PLAN.md verification with timestamp + screenshot) | ❌ Wave 0 |
| CORS rejection-path | Non-allowlisted Origin OPTIONS request lacks `Access-Control-Allow-Origin: https://evil.example` echo | smoke (manual run) | `bash backend/scripts/fly_smoke.sh $FLY_URL` (extended with Example 5 step 7) | ✅ existing — extend |

### Sampling Rate

- **Per task commit:** `pytest tests/test_rate_limit.py tests/test_chat_cap.py tests/test_config.py -x` (subset of new tests; <30 sec)
- **Per wave merge:** `pytest tests/` (full backend suite)
- **Phase gate:** Full suite green + `bash backend/scripts/fly_smoke.sh https://boardgame-rag-prod.fly.dev` exits 0 + manual D-15 + D-19 + D-20 checklists complete with screenshots → only then `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_rate_limit.py` — covers SEC-04 unit cases (decorated route, key_func, 429 shape, auth-fail bypass)
- [ ] `backend/tests/test_chat_cap.py` — covers SEC-05 (cap-hit graceful exit, logger, LangSmith tag, voluntary-stop preserved)
- [ ] `backend/tests/test_config.py` — covers SEC-05 default value (may already exist; planner verifies)
- [ ] `backend/tests/conftest.py` — shared fixtures: `mock_jwt`, `mock_user_id`, `mock_stream_chat_completion` (the last is critical — cap-hit test needs to drive the inner generator deterministically)
- [ ] `backend/scripts/fly_smoke.sh` extensions — Example 5 step 6 + step 7 appended to existing script

## Sources

### Primary (HIGH confidence)
- https://pypi.org/project/slowapi/ — version 0.1.9 confirmed as latest stable on 2026-05-08 via `pip index versions slowapi` against project venv
- https://github.com/laurentS/slowapi — `extension.py`, `examples.md`, decorator-must-be-above-limit-decorator rule
- https://slowapi.readthedocs.io/en/latest/ — Limiter setup, key_func contract, Request param requirement
- https://fly.io/docs/reference/suspend-resume/ — Firecracker snapshot preserves memory contents on suspend
- https://supabase.com/docs/guides/auth/redirect-urls — `/**` wildcard syntax, Site URL semantics, `{{ .SiteURL }}` template token
- https://openrouter.ai/openai/gpt-oss-120b:free — model card: 131K context, native tool-calling, GA since 2025-08
- https://openrouter.ai/docs/guides/features/tool-calling — tool calling support across models on OpenRouter
- https://fastapi.tiangolo.com/tutorial/cors/ — CORSMiddleware behavior on non-allowlisted Origin

### Secondary (MEDIUM confidence)
- https://costgoat.com/pricing/openrouter-free-models — May 2026 catalog of 29 free models with tool-call support indicators (verified against openrouter.ai for top picks)
- https://shiladityamajumder.medium.com/using-slowapi-in-fastapi-mastering-rate-limiting-like-a-pro-19044cb6062b — custom key_func with Request example
- https://openrouter.zendesk.com/hc/en-us/articles/39501163636379 — free-tier rate limit tiers (20 RPM / 50 RPD with $0 vs 1000 RPD with $10+)
- https://github.com/laurentS/slowapi/blob/master/docs/examples.md — examples including custom key functions and dynamic limits

### Tertiary (LOW confidence — flag for validation)
- LangSmith `run_helpers.get_current_run_tree()` behavior across SSE generator yields — Pitfall 5; verify in execution
- slowapi `exc.limit.limit.GRANULARITY.seconds` exact attribute path on 0.1.9 — verify when implementing handler; fallback to 60s constant
- Supabase Site URL change vs already-issued email tokens — D-15 sidesteps with fresh email; no authoritative source found

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — slowapi 0.1.9 verified against PyPI live; OpenRouter free tool-capable model verified via model card.
- Architecture: HIGH — patterns mirror existing explorer code; chat.py route signature gap identified concretely; CORS pattern locked.
- Pitfalls: MEDIUM — pitfalls 1-4 and 6 are well-grounded; 5 (LangSmith mid-generator) and 8 (JWT-expiry counter ticks) flagged as needing in-execution verification.

**Research date:** 2026-05-08
**Valid until:** 2026-06-07 (30 days; OpenRouter free-model catalog churns monthly — re-verify `:free` pick if planning slips past this date)

---

*Phase: 06-prod-wiring-auth-cors-rate-limiting-cost-caps*
