# Phase 6: Prod Wiring — Auth, CORS, Rate Limiting, Cost Caps - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the loop between the prod CF Pages frontend and the prod Fly backend so a real end user can sign up, log in, and chat on the prod URL — and no agentic or rate-based runaway can drain the LLM budget. Concretely:

1. **SEC-01 — Supabase Auth redirect URLs:** Site URL + Redirect URLs allowlist updated in the prod Supabase dashboard so signup/email-confirm/password-reset links land on `https://boardgame-rag-prod.pages.dev` without redirect loops. Manual signup E2E verifies.
2. **SEC-04 — Per-user `/api/chat` rate limit:** `slowapi` in-memory limiter, keyed by Supabase `user_id` from the JWT, capped at **20 requests/minute** on `/api/chat` only. 429 responses carry a JSON body `{"error":"rate_limited","detail":...,"retry_after_seconds":N}` plus an HTTP `Retry-After` header.
3. **SEC-05 — Max-iter cap on the main chat tool-use loop:** New `Settings.chat_max_iterations = 15` consumed by `routers/chat.py:564` (`while True:` becomes counter-bounded). On cap-hit the SSE stream emits a graceful assistant message ("I hit the tool-call limit before finishing — try narrowing the question."), persists it as the assistant turn's `content`, then ends cleanly. `logger.warning(...)` fires AND a LangSmith trace tag `iteration_cap_hit=true` is recorded.
4. **SEC-06 — OpenRouter cost cap + alert:** Portfolio runs on `:free` OpenRouter models by default (zero credit balance loaded → spend physically impossible). A dashboard alert at `$0.01` is configured. Alert delivery is verified once: temporarily load $1, swap `LLM_MODEL` to a paid model, send a single chat, confirm alert email arrives, swap back to `:free`, drain/withdraw the remaining balance. Outcome documented with dated screenshot.
5. **CORS rejection-path verification (small):** Phase 5 already wrote the prod CF origin into `CORS_ALLOWED_ORIGINS`. Phase 6 only PROVES the rejection path: a curl request with a non-allowlisted `Origin` header to `/api/chat` is rejected (no `Access-Control-Allow-Origin` echo). Folded into `fly_smoke.sh` (or a sibling) — no new wiring.

**Out of scope (other phases / future milestones):**
- LangSmith prod project, Sentry frontend, UptimeRobot, OBS-04 `/api/health` Supabase reachability — Phase 7
- "Try demo" button, graceful chat error surface (PORT-02), README, deploy badge — Phase 8
- BYOK (per-user API keys) — deferred to v1.2+ (see Deferred Ideas)
- Custom email templates, light branding — defaults sufficient
- Document upload rate limit, global rate limit across all routes
- `allow_origin_regex` / preview-deploy CORS — preview deploys disabled (Phase 5 D-07)
- Persistent rate-limit storage (Redis/Upstash) — single Fly machine + free-tier accept counter reset on suspend/resume

</domain>

<decisions>
## Implementation Decisions

### Rate Limiting — Library, Storage, Scope, Key

- **D-01:** Use `slowapi` (FastAPI-native, decorator + dependency model). Add `slowapi==<latest>` to `backend/requirements.txt` (researcher picks pinned version per Phase 1 D-12 reproducibility convention). Rationale: FastAPI-idiomatic, well-maintained, integrates with `Request` and dependency injection cleanly.
- **D-02:** **In-memory storage.** `Limiter(storage_uri="memory://")`. Single Fly machine + `auto_stop_machines="suspend"` (Phase 4 D-09) means counters reset on resume — acceptable for portfolio. No Redis/Upstash dependency, no new secret.
- **D-03:** **Scope: `/api/chat` only.** Threads/documents/folders/auth routes are not rate-limited — they are cheap CRUD already gated by Supabase RLS + JWT. Smallest surface satisfying SEC-04 verbatim ("`/api/chat` enforces a per-authenticated-user rate limit").
- **D-04:** **Key: Supabase `user_id` from the JWT** (already extracted by `get_user_id()` dependency in `auth.py`). The slowapi key function reads `request.state.user_id` (or equivalent) populated by the auth dependency. **Never key by IP** — auth is required for `/api/chat`, and IP-keying is meaningless behind CF Pages → Fly proxies.
- **D-05:** **Cap value: `20/minute` per user.** Generous for legit chat (one message every 3s sustained); blocks scripted bursts. Configurable via `Settings.chat_rate_limit: str = "20/minute"` so adjustment is a `flyctl secrets set` away (slowapi accepts string format `"N/minute"` natively).

### Rate Limiting — 429 Response Shape

- **D-06:** Custom 429 handler returns JSON: `{"error": "rate_limited", "detail": "Too many chat requests — slow down.", "retry_after_seconds": <int>}` with HTTP header `Retry-After: <int>`. Status 429. Implemented as a slowapi `_rate_limit_exceeded_handler` override (or `@app.exception_handler(RateLimitExceeded)` in `main.py`).
- **D-07:** Frontend handling is NOT in scope for this phase (Phase 8 PORT-02 owns graceful error surfacing). Backend just emits the contract — Phase 8 wires UI toast/banner. Document the 429 shape in PLAN so Phase 8 has the contract.

### Max-Iter Cap — Value, Behavior, Field, Telemetry

- **D-08:** **Value: 15 iterations.** Mirrors explorer's pattern (`explorer_max_iterations = 6`) but higher because the main loop has more legitimate tools (~10: kb_tree/ls/grep/glob/read, search_documents, sql_query, web_search, analyze_document, explore_kb). Strict literal "6" from the ROADMAP cuts off real multi-tool research chains; the spirit ("mirror explorer's pattern") is satisfied by the same counter+graceful-stop architecture, not by an identical numeric value. Document this rationale in PLAN.md so verifier doesn't flag the divergence.
- **D-09:** **Field: `Settings.chat_max_iterations: int = 15`** in `backend/config.py`, placed adjacent to the existing `explorer_max_iterations` field for visual consistency. Configurable via `CHAT_MAX_ITERATIONS` env var (pydantic-settings auto-maps).
- **D-10:** **On-cap behavior: graceful assistant message.** Replace `while True:` at `routers/chat.py:564` with a counted loop. When `iteration >= settings.chat_max_iterations` and a tool call would have happened on the next turn, the loop:
  1. Yields a final SSE `content_delta` with the message: `"\n\n_I hit the tool-call limit (${N}) before finishing this answer. Try narrowing the question or breaking it into steps._"` (markdown-italic so the chat UI styles it as a meta-note).
  2. Appends the message to `full_content` so it persists in the assistant `messages.content` row.
  3. Exits the loop cleanly (no exception, no SSE `error` event). Stream ends with the normal `done` SSE event. Thread remains usable.
- **D-11:** **Telemetry on cap-hit:** `logger.warning(f"Chat loop hit max_iterations cap ({N}) for user {user_id}, thread {thread_id}")` plus a LangSmith trace metadata tag `iteration_cap_hit=true` (use `services/tracing.py` helper or inline `with tracing_v2_enabled` add_metadata). Surfaces cap-hits in the LangSmith prod project (Phase 7) without paging.

### Supabase Auth — Site URL, Redirect URLs, Templates, Verification

- **D-12:** **Site URL = `https://boardgame-rag-prod.pages.dev`** (Supabase Dashboard → Authentication → URL Configuration → Site URL). Replaces dev `localhost:5173` default in the prod Supabase project. This token (`{{ .SiteURL }}`) is what default email templates expand to, so confirmation/reset links auto-point at prod once Site URL is correct.
- **D-13:** **Redirect URLs allowlist:**
  - `https://boardgame-rag-prod.pages.dev/**`
  - `http://localhost:5173/**`
  Both with the `/**` wildcard suffix so Supabase can append `/auth/callback`, hash fragments, or arbitrary post-auth paths. Localhost retained so future dev-against-prod-auth sessions don't break (no harm — localhost can never be reached except from the developer's own machine).
- **D-14:** **Email templates: Supabase defaults.** No custom HTML/CSS. Default templates already use `{{ .SiteURL }}` + `{{ .ConfirmationURL }}` tokens that Just Work once Site URL is set. Light branding deferred to v1.2+ polish.
- **D-15:** **Verification flow (manual, documented in PLAN):**
  1. From prod CF URL, sign up with a fresh throwaway email (e.g. `ragtest+phase6-${date}@gmail.com` or a `+suffix` alias).
  2. Open inbox; confirm email arrives within ~1 minute; click confirmation link.
  3. Confirm browser lands on `https://boardgame-rag-prod.pages.dev/...` (NOT `localhost`); user is logged in.
  4. Send a chat message to verify end-to-end auth → SSE works on prod.
  5. Trigger a password reset; confirm reset link also lands on prod.
  Document each step pass/fail with timestamp in PLAN.md verification section. Mirrors Phase 5 D-13 manual-checklist style.

### OpenRouter Cost Controls — Free-Tier Default + Toggle

- **D-16:** **Default model = OpenRouter `:free` tier model**, picked by `gsd-phase-researcher`. Researcher MUST verify candidate `:free` models for: (a) **tool-use / function-calling support** (the agent loop in `routers/chat.py` requires it — non-tool-capable models break the app), (b) availability stability (some `:free` models are experimental and rate-limited), (c) sufficient context window for `Settings.model_context_length=128000` budget assumptions. Candidate set to evaluate: `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.3-70b-instruct:free`, `deepseek/deepseek-r1:free`, plus any newer `:free` entries OpenRouter ships at research time. **Researcher returns one chosen model id** with rationale; PLAN locks it.
- **D-17:** **Paid toggle = single `LLM_MODEL` env swap.** Already env-driven (Phase 4 secrets). To upgrade to a paid model: `flyctl secrets set LLM_MODEL=<paid-id>` then `flyctl deploy` (or rely on auto-restart). No code change. PLAN locks both ids: `LLM_MODEL_FREE_DEFAULT` (in PLAN/runbook narrative, the `:free` id) and `LLM_MODEL_PAID_OPTION` (a researcher-suggested paid alternative for reference, e.g. `anthropic/claude-3.5-haiku` or `openai/gpt-4o-mini`). Add a comment in `.env.prod` showing both options with the current active value.
- **D-18:** **Cost cap config: zero balance.** Do NOT load OpenRouter credit. With `:free` model active, requests bypass the balance check entirely. SEC-06 verbatim ("monthly spend cap or alert configured") satisfied by the alert (D-19) plus the structural guarantee that no paid request can fire while balance is $0.
- **D-19:** **Alert configuration: $0.01 threshold** in OpenRouter dashboard → Account Settings → Alerts. Email recipient = developer email of record.
- **D-20:** **Alert delivery test (one-time, satisfies SC#5 "test alert confirmed delivered"):**
  1. Load $1 USD into OpenRouter balance.
  2. `flyctl secrets set LLM_MODEL=<a-cheap-paid-id>` (researcher's `LLM_MODEL_PAID_OPTION`); deploy.
  3. Send a single chat message via prod UI ("hello" — minimal token cost).
  4. Wait for alert email at the developer inbox; capture screenshot with timestamp.
  5. Revert: `flyctl secrets set LLM_MODEL=<:free-id>`; deploy.
  6. Drain/withdraw remaining balance (or burn via tiny test request) to return account to zero.
  Document each step + screenshot in PLAN.md verification section.

### CORS Rejection-Path Verification

- **D-21:** **No new wiring.** Phase 5 D-11 already set `CORS_ALLOWED_ORIGINS=https://boardgame-rag-prod.pages.dev`. Phase 6 only PROVES rejection works.
- **D-22:** **Test mechanism: extend `backend/scripts/fly_smoke.sh`** (Phase 4 D-13) with an additional final assertion: send `curl -H "Origin: https://evil.example" -X OPTIONS https://boardgame-rag-prod.fly.dev/api/chat` and assert the response either lacks `Access-Control-Allow-Origin: https://evil.example` OR returns 400. Captures SC#2's "non-allowlisted origin is rejected" cleanly within the existing smoke harness. Alternative: standalone `cors_smoke.sh` — pick whichever fits Phase 4 script conventions (Claude's discretion).

### Claude's Discretion

- Exact slowapi version pin (D-01) — researcher checks current stable release; planner pins explicitly.
- Whether to expose `chat_rate_limit` as a string env var ("20/minute") or split into `chat_rate_limit_per_minute: int = 20` — pick whichever slowapi consumes most cleanly.
- Where the CORS rejection assertion lives (D-22) — extend `fly_smoke.sh` vs sibling `cors_smoke.sh`. Either is fine.
- Markdown-italic vs plain text wording for the cap-hit graceful message (D-10) — wording can be refined in execution as long as semantics match.
- LangSmith trace metadata key spelling (D-11) — `iteration_cap_hit` vs `chat.cap_hit` — pick the namespacing that matches `services/tracing.py` patterns.
- Whether the `:free` model id swap (D-20 step 5) is documented as a manual `flyctl secrets set` or scripted as a small `revert_to_free.sh` helper — manual is fine for a one-time test.
- `chat_max_iterations` default value can stay 15 OR be lowered after observing real usage; not blocking for verification.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` §Phase 6 — 5 success criteria (Auth signup/login E2E, CORS allowlist + rejection, /api/chat 429, max-iter cap, OpenRouter alert delivered)
- `.planning/REQUIREMENTS.md` — SEC-01, SEC-04, SEC-05, SEC-06 definitions

### Research (existing)
- `.planning/research/SUMMARY.md` — Project rationale + free-tier hosting shape
- `.planning/research/STACK.md` — FastAPI middleware patterns, OpenRouter contract
- `.planning/research/PITFALLS.md` — SSE buffering, runaway agent loop, CORS spec issues
- `.planning/research/ARCHITECTURE.md` — Backend/frontend integration; CORS + Auth flow

### Prior-phase context (carry forward, do not re-plan)
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §CORS Allowlist (D-01..D-04) — `CORS_ALLOWED_ORIGINS` is comma-separated env var consumed by `Settings.cors_origins_list`; `allow_credentials=True` preserved; no `*`+credentials combo. **No re-wiring this phase.**
- `.planning/phases/01-secrets-repo-hygiene/01-CONTEXT.md` §Docling + Dep Pinning (D-12) — All new deps (slowapi) MUST be pinned in `backend/requirements.txt`.
- `.planning/phases/04-deploy-backend-to-fly-io/04-CONTEXT.md` §App identity (D-01) — Fly app `boardgame-rag-prod`, public URL `https://boardgame-rag-prod.fly.dev`. Used for `flyctl secrets set` commands.
- `.planning/phases/04-deploy-backend-to-fly-io/04-CONTEXT.md` §Smoke test (D-13) — `backend/scripts/fly_smoke.sh` exists; D-22 above extends it with CORS rejection assertion.
- `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-CONTEXT.md` §Backend CORS update (D-11/D-12) — Phase 5 already overwrote `CORS_ALLOWED_ORIGINS` to prod CF origin. Phase 6 builds on that — only verification needed, no re-set.
- `.planning/phases/05-deploy-frontend-to-cloudflare-pages/05-CONTEXT.md` §Project identity (D-03) — CF Pages public URL = `https://boardgame-rag-prod.pages.dev`. Identical string used in D-12, D-13 above.

### Source files this phase TOUCHES
- `backend/main.py` — MODIFY: register slowapi `Limiter` on app state, register 429 exception handler (per D-01, D-06)
- `backend/routers/chat.py` — MODIFY: apply `@limiter.limit(settings.chat_rate_limit)` decorator to `/api/chat` POST (or equivalent dependency); replace `while True:` (line 564) with counter loop bounded by `settings.chat_max_iterations`; emit graceful cap-hit message + telemetry (per D-08..D-11)
- `backend/config.py` — MODIFY: add `chat_max_iterations: int = 15`, `chat_rate_limit: str = "20/minute"` to `Settings` (per D-05, D-09)
- `backend/auth.py` — REFERENCE / possibly MODIFY: ensure `user_id` is exposed on `request.state` (or accessible via dependency) so the slowapi key function can read it without a second JWT decode (per D-04)
- `backend/requirements.txt` — MODIFY: add pinned `slowapi==<version>` (per D-01 + Phase 1 D-12)
- `backend/scripts/fly_smoke.sh` — MODIFY: extend with rate-limit burst test (e.g. 25 rapid requests, expect ≥1 × 429 with correct body shape) AND CORS rejection-path assertion (per D-22)
- `.env.prod` — MODIFY: comment block showing `LLM_MODEL` free-default + paid-option (per D-17). Gitignored; local change only.

### Source files this phase REFERENCES (do not modify)
- `backend/services/explorer_service.py:232` — Pattern for counter-bounded loop with graceful exhaustion. `routers/chat.py` mirrors this architecture (not the numeric value).
- `backend/services/tracing.py` — LangSmith helper for D-11 trace metadata tag.
- `backend/services/llm_service.py` — Stream chat completion entry point; cap-hit logic intercepts BEFORE re-entering on the next iteration.

### Out-of-repo configuration (manual, document in PLAN)
- Supabase Dashboard (prod project) → Authentication → URL Configuration: Site URL + Redirect URLs allowlist (per D-12, D-13)
- OpenRouter Dashboard → Account → Alerts: $0.01 threshold + email recipient (per D-19)
- OpenRouter alert delivery test: load $1 → swap to paid model → 1 chat → confirm email → revert → drain (per D-20)

### Upstream docs
- https://slowapi.readthedocs.io/ — `Limiter`, key func, exception handler patterns
- https://supabase.com/docs/guides/auth/redirect-urls — Site URL + Redirect URLs semantics, wildcard syntax
- https://openrouter.ai/docs#models — `:free` model catalog (researcher uses this to pick D-16)
- https://openrouter.ai/docs/limits — `:free` tier rate limits + balance semantics
- Fly.io `fly.toml` reference — `flyctl secrets set` semantics (already covered in Phase 4 refs)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Settings.cors_origins_list` (Phase 1) — already parses `CORS_ALLOWED_ORIGINS`; nothing new needed for CORS this phase.
- `explorer_service.py` counter pattern (lines 220-314) — exact template for D-10 main-loop refactor: `iteration += 1` inside the loop, voluntary stop on no-tool-calls (already present in chat.py too), capped iterations as the upper bound. The chat.py change is a direct port of this pattern.
- `auth.py` JWT-extracted `user_id` — already a dependency; slowapi key function reuses it, no second JWT decode.
- `services/tracing.py` — existing LangSmith integration; D-11 trace tag fits the existing pattern.
- `backend/scripts/fly_smoke.sh` (Phase 4 D-13) — extension point for D-22 (CORS rejection assertion) + a rate-limit burst test that proves SEC-04.

### Established Patterns
- All env-driven config goes through `Settings` (`backend/config.py`); `flyctl secrets set` map 1:1, no glue code.
- Counter-bounded LLM loops use `iteration` counter + voluntary `break` on no-tool-calls + flag (`budget_exhausted` / new `iteration_cap_hit`) for cap-reached path — `explorer_service.py` is the canonical reference.
- New deps land in `backend/requirements.txt` pinned (Phase 1 D-12).
- Tool-use loop emits SSE events via generator-style `yield {"event": ..., "data": ...}`; cap-hit path appends one final `content_delta` then lets the existing `done` event fire.
- Naming: `boardgame-rag-prod` across all four surfaces (Fly, CF Pages, Supabase, LangSmith). No new identifier introduced this phase.

### Integration Points
- slowapi `Limiter` lives on `app.state.limiter` (or via `add_middleware`). `/api/chat` route function gets `@limiter.limit("20/minute", key_func=user_id_from_request)` decorator. 429 exception handler in `main.py` formats the JSON body per D-06.
- `routers/chat.py` line 564 `while True:` is THE single integration point for D-08..D-11. No other loop needs change.
- Supabase Auth dashboard config is OUT-OF-REPO; PLAN documents the steps + a screenshot to capture them.
- OpenRouter dashboard alert config is OUT-OF-REPO; same treatment.

### Gotchas surfaced during scout / discussion
- `routers/chat.py` already breaks the loop on `not tool_call_happened` (voluntary stop). Cap is the BACKSTOP for adversarial/buggy cases, not the main exit. Keep both.
- `slowapi`'s default `_rate_limit_exceeded_handler` returns a plain text body — must override per D-06 to return JSON. One-liner exception handler in `main.py`.
- In-memory slowapi counters are PER-PROCESS; if Fly ever scales to >1 machine, counter is sharded. Acceptable for free-tier single machine; flag in deferred ideas if scaling appears.
- `:free` OpenRouter models historically have **inconsistent tool-use support** — researcher MUST verify `tool_calls` round-trip on the picked model with a smoke request before locking. If no `:free` model supports tools reliably, fallback decision is "load $1 prepaid + cheapest paid model" — but flag immediately, do not silently downgrade.
- Supabase Auth Site URL change MAY invalidate already-issued email confirmation tokens (untested). Sign up a NEW throwaway email for D-15 verification — don't re-test with old links.
- OpenRouter `:free` tier rate limits (~20/min, 200/day per account) effectively act as a SECOND backstop on top of slowapi — your app cap (20/min/user) is at or below the upstream cap, so users won't hit OpenRouter's limit before they hit yours. Document so future planners don't double-limit.

</code_context>

<specifics>
## Specific Ideas

- **"Free portfolio" interpretation locked:** truly $0 default via `:free` model + single-env-var toggle for paid. BYOK explicitly deferred to a future milestone.
- ROADMAP SC#4 says "mirroring the explorer's 6-cap" — the SPIRIT (counter+graceful-stop architecture) is mirrored; the NUMERIC value diverges to 15 because the main loop has more legitimate tools (~10 vs explorer's 5). Document the rationale in PLAN.md so verifier doesn't flag the divergence.
- Test user for verification flows: `ragtest1@gmail.com` / `testpass123` (CLAUDE.md, prod-seeded in Phase 4) for chat/SSE checks. **Signup E2E (D-15) requires a FRESH throwaway email**, not the existing test user, because we're proving the email-confirm path lands on prod.
- `chat_rate_limit` AND `chat_max_iterations` are both env-tunable so future-you can dial them without a code deploy — only `flyctl secrets set` + auto-restart.
- Researcher's `:free` model pick is a hard gate: if no current `:free` model supports tool-calling reliably, planner MUST stop and surface this BEFORE writing the plan, because the entire phase model assumption breaks otherwise.

</specifics>

<deferred>
## Deferred Ideas

- **BYOK (per-user provider keys)** — DEFERRED to v1.2+. Scope creep evaluated 2026-05-07: requires per-user encrypted key storage (new Supabase table + Vault/KMS), frontend settings UI, refactor of all LLM-calling services (`llm_service`, `embedding_service`, `rerank_service`, `subagent_service`, `explorer_service`) from singleton client to per-user factory, model-picker UI, and breaks Phase 8 PORT-01 "Try demo" one-click (anonymous demo has no key). Not foldable into Phase 6.
- **Persistent rate-limit storage (Redis/Upstash)** — Defer until Fly scales beyond 1 machine. In-memory + counter-reset-on-suspend is fine for portfolio.
- **Document upload rate limit** — Defer; current scope is `/api/chat` only. Revisit if abuse observed.
- **Global rate limit across all authenticated routes** — Defer; over-broad for current phase.
- **`allow_origin_regex` for CF Pages preview deploys** — Preview deploys disabled (Phase 5 D-07). Revisit only if previews re-enabled.
- **Frontend 429 toast/banner UI** — Backend emits the JSON contract this phase; UI rendering belongs in Phase 8 (PORT-02 graceful error surface).
- **Custom email templates / branding** — Default Supabase templates suffice for portfolio.
- **Light alert-test automation script (`alert_delivery_test.sh`)** — Manual one-time procedure (D-20) is sufficient; automation is over-engineering.
- **`pip-tools` / lockfile** — Already deferred in Phase 1 D-13; same here. Flat pinned `requirements.txt` continues.
- **Telemetry dashboard for cap-hits** — LangSmith tag (D-11) is enough for now; richer dashboard belongs in Phase 7 observability or later.

</deferred>

---

*Phase: 06-prod-wiring-auth-cors-rate-limiting-cost-caps*
*Context gathered: 2026-05-07*
