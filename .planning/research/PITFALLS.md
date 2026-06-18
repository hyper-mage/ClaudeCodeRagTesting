# Pitfalls Research

**Domain:** Adding OpenRouter BYOK (OAuth PKCE + encrypted per-user key storage + model selection + usage display) to an already-deployed multi-user RAG app (FastAPI + Supabase + React, Fly.io + Cloudflare Pages)
**Researched:** 2026-06-18
**Confidence:** HIGH (OpenRouter OAuth/limits/usage verified against official docs; secret-handling and Supabase RLS pitfalls grounded in this repo's actual code — `llm_service.py`, `chat.py`, `sql_service.py`, `execute_readonly_query.sql`, `sentry.ts`, `tracing.py`)

> **Phase numbers below are suggestions** keyed to the natural v1.2 build order. They map to: **P1 Key Storage + Encryption**, **P2 OAuth PKCE**, **P3 Per-request Key/Model Resolution**, **P4 Model Picker + Cache**, **P5 Usage/Cost Display**, **P6 Settings/UX/Theme**, **P7 Demo-fallback Gating**. The roadmap may renumber — the pairing (pitfall → capability) is what matters.

> **Highest-risk area is SECTION 1 (handling user secrets).** Treat every pitfall there as a release blocker, not a polish item. This app already ships a single owner key in env; the entire risk profile changes the moment you persist *other people's* keys.

---

## Critical Pitfalls

### Pitfall 1: LangSmith `wrap_openai` traces the per-user OpenRouter key (and prompts) to a 3rd party

**What goes wrong:**
`backend/services/llm_service.py:get_llm_client()` wraps the OpenAI client with `wrap_openai(client)` whenever `langsmith_api_key` is set. Today that traces the *owner's* single key context. The moment `get_llm_client()` is changed to accept a per-user key, LangSmith captures the client config / request metadata for every BYOK call — and `wrap_openai` traces inputs and outputs by default. A user's OpenRouter key (and their full chat) leaves your trust boundary and lands in the prod LangSmith project. You are now custodian of other people's secrets in a vendor you don't control.

**Why it happens:**
The tracing wrapper is invisible at the call site — devs forget it serializes request data. The existing code wraps unconditionally; nobody re-evaluates it when the key source changes from "mine" to "theirs."

**How to avoid:**
- Pass the per-user key as a constructor arg to a fresh `OpenAI(...)` and **do not** rely on the wrapper to scrub it. Confirm the `Authorization` header is never placed in trace metadata.
- Set `LANGSMITH_HIDE_INPUTS=true` / `LANGSMITH_HIDE_OUTPUTS=true` for BYOK calls, OR register a client-side anonymizer hook that redacts `sk-or-` patterns before the payload serializes. LangSmith redaction must happen **client-side before the trace leaves the process**.
- Decide explicitly: do BYOK chats get traced at all? Safest default: trace owner-key/demo calls, **disable LangSmith tracing on per-user-key calls** (build the client without `wrap_openai`).

**Warning signs:**
A LangSmith run whose metadata or extra fields contain `api_key`, `default_headers`, or any `sk-or-v1-…` substring. A user's prompt visible in LangSmith when they used their own key.

**Phase to address:** P3 (per-request key resolution) — gate the wrapper on key source.

---

### Pitfall 2: User OpenRouter key leaks into Sentry — current scrubber only catches `Authorization` + Supabase token

**What goes wrong:**
`frontend/src/lib/sentry.ts` redacts only (a) `Authorization` request headers and (b) console breadcrumbs matching `sb-<ref>-auth-token`. An OpenRouter key (`sk-or-v1-…`) appears in **none** of those shapes. It can leak via: the OAuth callback URL in `event.request.url` / navigation breadcrumbs; a `console.log(key)` left in dev (the `consoleLoggingIntegration` captures `log`/`warn`/`error` as breadcrumbs AND `enableLogs: true` ships logs); an error message like `"OpenRouter rejected key sk-or-v1-…"`; or the key embedded in a fetch breadcrumb body. Backend has its own path: `chat.py` catches exceptions and yields `json.dumps({"error": str(e)})` over SSE — if an OpenRouter SDK error string echoes the key, it streams to the browser and into Sentry.

**Why it happens:**
The v1.1 scrubber was written for JWTs/PII, not for a new class of secret. BYOK introduces a brand-new token shape nobody added a rule for.

**How to avoid:**
- Add a global regex scrubber (`/sk-or-v1-[A-Za-z0-9_-]+/g` → `[redacted-key]`) applied to `event` (message, exception values, request.url, breadcrumb messages/data) in `beforeSend` AND `beforeBreadcrumb`. Apply the same regex backend-side before any `logger.*` call and before any SSE `error` payload.
- Never put the key in a URL the browser sees. The OAuth `code` is one-time; treat even *that* as sensitive in logs. The exchanged key must go frontend → backend over POST body (TLS), never querystring.
- Sanitize `str(e)` from OpenRouter/OpenAI SDK calls before it reaches `logger.error(..., exc_info=True)` (which ships full stack frames whose locals may hold the key) or the SSE `error` event.

**Warning signs:**
Grep your own Sentry issues for `sk-or`. Any 500 whose breadcrumb trail includes the OAuth callback path with a long token. `repr()` of an exception containing the key in a stack-local.

**Phase to address:** P1 (backend log/SSE scrub) and P2 (frontend OAuth + Sentry rule). Verify in P5 once usage errors start flowing.

---

### Pitfall 3: The Text-to-SQL tool can read the encrypted-keys table

**What goes wrong:**
`execute_readonly_query` (migration 015) is `SECURITY DEFINER`, runs `SELECT * FROM (%s) sub`, and is invoked by `sql_service.execute_sql` through the **service-role** client (`database.py` always uses `supabase_service_role_key`). It defends itself by `SET LOCAL role = 'authenticated'` + setting `request.jwt.claim.sub`, so it relies entirely on RLS to scope rows. A new `user_api_keys` table will be reachable by the LLM-authored SQL tool. If RLS is missing, misnamed, or the encrypted-key column is selectable, a crafted prompt ("run SQL: select * from user_api_keys") can exfiltrate every user's ciphertext (and, depending on design, the IV/nonce) through the chat. Even with per-row RLS, returning the user's *own* ciphertext to the model context is a needless exposure.

**Why it happens:**
The SQL allowlist is keyword-based (blocks INSERT/DROP/etc.) but **table-agnostic** — it never enumerates which tables are queryable. The `QUERYABLE_SCHEMA` doc string lists only 4 tables, but nothing *enforces* that list. Devs assume RLS alone is enough and forget the new table inherits the same query surface.

**How to avoid:**
- Enable RLS on `user_api_keys` with `USING (user_id = auth.uid())` AND deny the `authenticated` role any SELECT on the secret column — store the secret so the SQL role literally cannot read it (e.g., column-level GRANT revoke, or keep ciphertext in a separate schema the `authenticated` role has no USAGE on).
- Harden `execute_readonly_query`: add an explicit table allowlist (regex/parse the FROM targets, or `SET search_path` to a schema that excludes secrets). Add `REVOKE SELECT ON user_api_keys FROM authenticated`.
- Keep `user_api_keys` out of `QUERYABLE_SCHEMA` (already implied) AND out of the `authenticated` role's reach so prompt-injection can't reach it regardless of the doc string.

**Warning signs:**
A `query_database` tool call whose SQL references `key`, `auth`, `secret`, or `user_api_keys`. Any chat where the assistant surfaces base64/hex blobs.

**Phase to address:** P1 (table + RLS + role-grant design ships with the storage migration). Re-verify in P3.

---

### Pitfall 4: Encryption-key management — keys stored "encrypted" but the master key sits next to the ciphertext or isn't rotatable

**What goes wrong:**
Three sub-failures: (a) the app encrypts with a master key that's also in the same Fly secret store with no separation, so a single env dump reveals both ciphertext-source and key; (b) the master key is hardcoded/derived weakly (e.g., reusing `supabase_jwt_secret` or a short string) instead of a 32-byte random key; (c) no key-version/rotation path — when (not if) you need to rotate, every stored key is undecryptable or you can't tell which master key encrypted which row.

**Why it happens:**
"Encrypted at rest" feels done once `cryptography.Fernet`/AES-GCM is wired. Rotation and key-id tagging are invisible until a rotation event forces a painful migration. The repo already pins `cryptography 46.0.5`, so reaching for it is easy — but ergonomics ≠ key hygiene.

**How to avoid:**
- Generate a dedicated 32-byte master key (`OPENROUTER_KEY_ENC_KEY`), separate from JWT/Supabase secrets, stored only in Fly secrets — never in `.env` committed shape, never in the frontend bundle.
- Use AES-256-GCM (authenticated) or Fernet; store per-row: ciphertext, nonce/IV, and a **`key_version` integer**. Decrypt picks the master key by version.
- Design rotation up front: support two active master keys (current + previous) so you can re-encrypt rows lazily on next use and bump `key_version`. Document the rotation runbook now.
- Decrypt **only** in the backend, only at the moment of an LLM call; never return plaintext to any API response, log line, or trace.

**Warning signs:**
No `key_version` / `nonce` column. The enc key equals or derives from an existing secret. No written rotation procedure. Decryption code reachable from any endpoint that returns JSON to the client.

**Phase to address:** P1 — encryption scheme, key separation, and `key_version` column are part of the first storage migration.

---

### Pitfall 5: OAuth PKCE — `code_verifier` stored where the callback can't reach it, or no CSRF `state`

**What goes wrong:**
OpenRouter PKCE: redirect to `https://openrouter.ai/auth?callback_url=…&code_challenge=…&code_challenge_method=S256`, then exchange `POST https://openrouter.ai/api/v1/auth/keys` with `{code, code_verifier, code_challenge_method}`; the new key returns in the `key` field. Two classic breaks: (a) the `code_verifier` is generated in one tab/route but the callback lands in a fresh SPA load (or a different device) and the verifier is gone → exchange fails with "invalid credentials" (403); (b) **OpenRouter's flow has no built-in `state` parameter** — its docs do not document CSRF/state — so if you don't add your own, an attacker can feed a victim a crafted callback URL with the attacker's `code`, silently binding the *attacker's* OpenRouter key to the *victim's* account (or vice-versa). Also `code_challenge_method` must match between request and exchange (mismatch → 400).

**Why it happens:**
Teams copy the happy-path snippet, store `code_verifier` in volatile memory, and assume PKCE alone covers CSRF (it covers code interception, not session fixation on the callback).

**How to avoid:**
- Generate `code_verifier` + a random `state` together; persist BOTH in `sessionStorage` (survives the redirect within the same browser) keyed by `state`. On callback, look up the verifier *by the returned state*; reject if absent/mismatched.
- Bind the flow to the logged-in Supabase user: the exchange must happen backend-side under the user's JWT, so the returned key is associated with `auth.uid()` server-side, not trusted from the client.
- Send `code` + `code_verifier` to YOUR backend; the backend calls `/api/v1/auth/keys` and stores the encrypted key. Never exchange purely client-side (the key would transit/render in the browser → Pitfall 2).
- Keep `code_challenge_method=S256` consistent in both steps.

**Warning signs:**
Exchange works on the same tab but fails after a hard refresh. No `state` round-trip. The key returned to the browser before hitting your backend. 403 "invalid credentials" / 400 "invalid challenge method" in logs.

**Phase to address:** P2 (OAuth flow). The state/CSRF binding is the non-obvious must-have.

---

### Pitfall 6: Redirect/`callback_url` mismatch across dev/prod (and the SPA deep-link rewrite)

**What goes wrong:**
The exact `callback_url` sent in step 1 must match where OpenRouter redirects. This app runs three origins: `http://localhost:5173` (Vite), the Cloudflare Pages prod origin (`boardgame-rag-prod.pages.dev`), and the Fly backend. Hardcoding the callback (or building it from the wrong base) means OAuth started in prod returns the user to localhost, or the SPA's deep-link routing (Cloudflare Pages SPA rewrite, already configured in v1.1) 404s the `/auth/callback` path if it isn't whitelisted as an SPA route. OpenRouter allows localhost on any port, so dev works — masking the prod break until launch.

**Why it happens:**
CORS allowlist is already env-driven (`cors_allowed_origins`), so devs assume "origins are handled" — but the OAuth callback URL is a *separate* config that must derive from the same per-environment value. The dual-env setup (`.env` dev / `.env.prod`) makes it easy to ship the dev callback to prod.

**How to avoid:**
- Derive `callback_url` from a single env var per environment (reuse/extend the CORS origin source). Never hardcode.
- Ensure `/auth/callback` (or whatever path) is served by the SPA fallback on Cloudflare Pages (same fix class as the v1.1 deep-link routing).
- Test the full round-trip on the **prod origin** before close, not just localhost. Add the callback path to any auth redirect allowlist.

**Warning signs:**
OAuth returns to the wrong host. A 404 on the callback path in prod only. "works on localhost" with no prod round-trip test.

**Phase to address:** P2 (flow) + verify on prod origin during P6/P7 deploy gate.

---

### Pitfall 7: Demo/owner-key fallback misconfigured → owner pays for everyone (cost blowout)

**What goes wrong:**
The owner-key demo fallback is "global flag, default off." The danger: the resolution logic in the chat path (where `get_llm_client()` is called) silently falls back to the owner key whenever a user's key is missing/invalid/expired — instead of *only* when the global demo flag is ON. Combine with v1.1's **anonymous Try-demo auth** (any visitor gets an `authenticated` JWT with no key) and you have an open door: every anon user's chats bill the owner's OpenRouter account. The existing per-user rate limit (20/min) caps *velocity*, not *spend*, and SEC-06's cost guardrail trip-test was **deferred to backlog 999.2** — so the safety net is unproven.

**Why it happens:**
"Fallback" is written as `key = user_key or owner_key` — a one-liner that ignores the flag and ignores *who* the user is. Fail-open feels friendlier than fail-closed.

**How to avoid:**
- Resolution must be explicit and fail-**closed**: `if user_has_key: use user key; elif demo_flag_on and user_is_eligible: use owner key; else: refuse with a "connect your key" UX`. Never `user_key or owner_key`.
- Define `user_is_eligible` narrowly — consider excluding anonymous demo users from owner-key fallback, or apply a much tighter per-anon spend/iteration budget when on the owner key.
- Land the SEC-06 cost guardrail **before** enabling the fallback flag in prod (close backlog 999.2 as a dependency). Add a hard per-day owner-key spend cap and a kill switch.
- Tag every owner-key call so usage is attributable; alert on owner-key request volume.

**Warning signs:**
Owner OpenRouter spend rises without the flag being intentionally on. Anon users getting full chat responses with no key connected. Code containing `or settings.llm_api_key` / `or owner_key` in the resolution path.

**Phase to address:** P7 (demo-fallback gating) — but the fail-closed *shape* is set in P3 (resolution logic). Hard dependency on SEC-06 guardrail (backlog 999.2).

---

### Pitfall 8: Wrong key used for a request (cross-user / cached-singleton leakage)

**What goes wrong:**
`get_llm_client()` reads from a process-global `get_settings()` (`@lru_cache`d) and builds a client from global config. If BYOK is bolted on by mutating settings or caching the client per-process (not per-request), a concurrent request can use another user's key, or a stale key. Under FastAPI async + Fly's single small instance, requests interleave; a module-level `_client` singleton or `lru_cache`d client keyed on nothing is a cross-tenant bug. Also: the budget code already calls `fetch_model_context_length(settings.llm_model, settings.resolved_llm_api_key)` (chat.py ~592) — that path must switch to the per-user key/model too, or it'll probe OpenRouter with the wrong credentials.

**Why it happens:**
The whole backend is "stateless, all state in Supabase," so devs reach for module-level singletons for the LLM client without realizing the key is now request-scoped state.

**How to avoid:**
- Make key+model **explicit per-request parameters** threaded from `send_message` → `stream_chat_completion` → `get_llm_client(api_key=…, base_url=…, model=…)`. No global mutation, no cached client keyed on nothing.
- Audit every call site that reads `settings.resolved_llm_api_key` / `settings.llm_model` (currently `llm_service.py`, and the budget lookup in `chat.py`) and convert them to the resolved per-request values.
- Add a test: two concurrent requests with different keys never cross.

**Warning signs:**
A `_client = None` module global in `llm_service`. `@lru_cache` on a function that returns a key-bearing client. Budget lookups still using `settings.resolved_llm_api_key` after BYOK lands.

**Phase to address:** P3 (per-request resolution) — this is the architectural seam of the whole milestone.

---

### Pitfall 9: Model picker breaks when models disappear, rename, or change pricing shape

**What goes wrong:**
Four linked failures: (a) a model ID cached in the picker (and persisted **per-thread**, an active v1.2 feature) is later deprecated — OpenRouter returns **404 "no endpoints for this model found"** *at request time*, not in the model list — so a saved thread silently fails on next message; (b) pricing parsing assumes a shape — OpenRouter's `/api/v1/models` returns pricing as **strings** (`pricing.prompt`, `pricing.completion`, `pricing.image`, `pricing.request`) precisely to avoid float issues; parsing with `float()` blindly or assuming a field exists breaks when a model omits a field or the schema adds one; (c) a model renames and the persisted ID no longer resolves; (d) "free vs paid" tagging derived from naively checking `:free` suffix vs reading pricing → mislabels.

**Why it happens:**
The picker is built against a snapshot of the list; deprecation/rename happen out-of-band; pricing-as-string surprises devs who expect numbers.

**How to avoid:**
- Treat persisted per-thread model IDs as *unvalidated*: on use, if the model 404s, catch it, surface a clear "this model is no longer available — pick another" and fall back to a known-good default (don't crash the thread).
- Parse pricing defensively: `float(pricing.get("prompt", "0") or "0")`, tolerate missing/extra fields, never assume structure. Free = pricing all-zero OR `:free` suffix, computed not assumed.
- Cache the model list but **revalidate the chosen model at send time** (cheap: the request itself returns 404 if gone). Store a `(model_id, captured_at)` so the UI can warn on stale selections.

**Warning signs:**
A thread that worked yesterday now errors with "no endpoints for this model." `KeyError`/`ValueError` in pricing parse after a model-list refresh. Free/paid badge wrong for a model.

**Phase to address:** P4 (picker + cache) for parsing/tagging; P3 for the at-send 404 fallback.

---

### Pitfall 10: Stale model cache + scheduled-refresh fragility (and popularity data source)

**What goes wrong:**
"Scheduled refresh" of the model list is easy to get wrong on Fly free-tier: the instance **suspends** when idle (v1.1 chose suspend, no keep-warm), so an in-process scheduler (APScheduler/asyncio task) won't fire while suspended — the cache goes stale for days, new models never appear, deprecated ones linger. Separately, "popularity" has no official, stable OpenRouter field in the models list — if popularity is scraped from the rankings page or an unofficial source, it breaks silently when that source changes, leaving the picker with empty/garbage ordering.

**Why it happens:**
Devs assume a background scheduler "just runs"; on a suspend-on-idle free tier it doesn't. Popularity is assumed to be in the API when it isn't.

**How to avoid:**
- Refresh **lazily on demand** with a TTL (e.g., refresh if cache older than N hours when the picker is opened) rather than relying on a wall-clock scheduler in a suspending process. If a true schedule is needed, drive it from an external pinger (UptimeRobot already pings `/api/health`) hitting a refresh endpoint, or accept on-demand TTL.
- Store the cache in Supabase (survives instance restarts), not in-process memory (lost on every cold start).
- For popularity: confirm an official source exists before depending on it. If unofficial, isolate it behind a feature flag, degrade gracefully (alphabetical / free-first) when it's missing, and don't let its failure break the picker.

**Warning signs:**
New OpenRouter models never show up. Picker order empty or frozen after a deploy. Scheduler logs absent for long stretches (instance was suspended). Popularity null for all models.

**Phase to address:** P4 (cache strategy + refresh trigger + popularity source decision).

---

### Pitfall 11: Free-model rate limits cause silent mid-chat failures

**What goes wrong:**
`:free` models carry per-minute and per-day request caps (OpenRouter; daily cap is lower without purchased credits, higher with ≥ a credits threshold). With a negative balance you get **402 Payment Required even on free models**. In the agentic loop (`chat.py` runs up to `chat_max_iterations=15` tool round-trips, each an LLM call), a single user turn can fire many requests and trip the per-minute free cap mid-turn → a 429 surfaces as a generic streamed `error` event, looking like an app bug. The user picked a "free" model and gets opaque failures.

**Why it happens:**
The picker advertises free models as frictionless; nobody maps OpenRouter's 429/402 to a human explanation; the multi-iteration tool loop amplifies request count per user message far beyond "1 message = 1 request."

**How to avoid:**
- Detect 429 (rate limit) and 402 (payment/credit) from OpenRouter distinctly and surface tailored UX: "This free model hit its rate limit — wait a minute or pick another model / connect credits." Don't fold them into the generic `[An error occurred]`.
- Show free-model limits in the picker tooltip so expectations are set.
- Consider that the 15-iteration loop multiplies free-tier consumption; warn or cap iterations harder for free models.

**Warning signs:**
Free-model chats failing partway through multi-tool answers. Generic error events whose underlying status is 429/402. Complaints that "the free model doesn't work."

**Phase to address:** P3 (error mapping in the chat loop / SSE) + P5 (surfacing limits/credits in UI).

---

### Pitfall 12: Usage/cost display inaccuracy — re-deriving cost client-side instead of trusting OpenRouter

**What goes wrong:**
Two inaccuracy traps: (a) computing per-request cost by multiplying your cached `pricing.prompt/completion` by token counts — this drifts from OpenRouter's actual billing (native-tokenizer counts, caching discounts, BYOK provider differences) and will mismatch the user's real OpenRouter balance, eroding trust; (b) reading the `usage`/cost from the response too early. For **streaming** (this app streams via SSE), OpenRouter includes the usage object in the **last SSE message** — if `stream_chat_completion` returns on `finish_reason == "tool_calls"` (it does, `llm_service.py:148`) or the loop discards the final chunk, the usage object is never captured. The `/api/v1/generation` endpoint gives authoritative post-hoc cost but has a **delay** before stats are queryable.

**Why it happens:**
Devs assume cost = price × tokens and that the usage field is in every chunk. The existing streaming loop wasn't built to capture a trailing usage object.

**How to avoid:**
- Treat OpenRouter as the source of truth: capture the `usage` object from the final streamed chunk (request usage accounting / read the last SSE message), and read account balance from `GET /api/v1/key` (`limit`, `limit_remaining`, `usage`, `is_free_tier`) and `GET /api/v1/credits` (total purchased/used). Display *those*, don't recompute.
- If using `/api/v1/generation` for exact cost, tolerate the propagation delay (poll/retry, or show "calculating…").
- Update `stream_chat_completion` to surface the trailing usage chunk instead of discarding it after the last tool call. Account for the agentic loop summing usage across **multiple** LLM calls per user turn.

**Warning signs:**
Your displayed cost ≠ the user's OpenRouter dashboard. Usage shows 0 tokens for streamed responses. Cost only ever reflects the last LLM call, not all iterations of the loop.

**Phase to address:** P5 (usage/cost display). Streaming usage-capture change touches P3's `stream_chat_completion`.

---

### Pitfall 13: Key revoked/expired mid-session and "no key" dead-ends (UX traps)

**What goes wrong:**
A user connects a key, then revokes it on OpenRouter (or it expires / hits zero balance). Mid-chat, the next iteration of the tool loop 401/402s. If the app only checks key presence at connect time, the user is stranded with cryptic errors. The inverse dead-end: a new user with no key picks a paid model → key-gated selection must *trigger OAuth*, but if the trigger is missing or the demo state is ambiguous, the user can't tell whether they're on the demo, their own key, or stuck. Per-thread model selection compounds this: an old thread pinned to a model the user can no longer afford/access fails on resume.

**Why it happens:**
Validation is treated as a one-time gate, not a per-request reality. "Demo vs own-key" is a state nobody renders explicitly.

**How to avoid:**
- Make key state a first-class, always-visible UI signal: "Demo mode" vs "Your key: connected (balance $X)" vs "No key — connect to chat." Settings page shows key status + balance from `GET /api/v1/key`.
- On a mid-chat 401/402/403 from OpenRouter, catch it and surface a recoverable action ("Your key was rejected — reconnect / pick the demo / add credits"), preserving the partial answer like the existing cap-hit notice does.
- Key-gated selection: choosing a model with no connected key launches OAuth inline, then resumes the action. Don't silently no-op.
- For revived threads pinned to an unavailable model, fall back to default + tell the user (ties into Pitfall 9).

**Warning signs:**
Users reporting "it just stopped working." No visible indicator of which key/mode is active. OAuth never triggered from the picker. Cryptic 401 mid-stream.

**Phase to address:** P6 (settings + key-state UX) with hooks added in P3 (error catch) and P2 (OAuth trigger).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `key = user_key or owner_key` one-liner fallback | Fewer branches, demo "just works" | Cost blowout on owner key; fail-open security hole (Pitfall 7) | **Never** — must be flag-gated, fail-closed |
| Store key encrypted with no `key_version` column | Ships faster | Painful all-rows migration at first rotation (Pitfall 4) | Never for secrets |
| In-process model-list cache (module global) | Trivial to write | Lost on every Fly cold start; stale; cross-request races (Pitfall 10) | Prototype only; move to Supabase before prod |
| Exchange OAuth code fully client-side | No backend round-trip | Key transits/renders in browser → Sentry/log leak (Pitfall 2/5) | Never — exchange backend-side |
| Recompute cost = price × tokens | No extra API call | Drifts from real OpenRouter billing; user distrust (Pitfall 12) | Rough estimate only, clearly labeled "estimated" |
| Leave LangSmith `wrap_openai` on for BYOK calls | Zero code change | User keys + prompts shipped to 3rd party (Pitfall 1) | Never for per-user-key calls |
| Reuse `supabase_jwt_secret` as enc key | One fewer secret to manage | Co-located blast radius; weak separation (Pitfall 4) | Never |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenRouter OAuth `/auth` | Hardcoding `callback_url`; assuming PKCE covers CSRF | Per-env callback from one source; add own `state` param + verify on callback (Pitfall 5/6) |
| OpenRouter `/api/v1/auth/keys` exchange | Doing it client-side; mismatched `code_challenge_method` | Backend exchange under user JWT; keep `S256` consistent (Pitfall 5) |
| OpenRouter `/api/v1/models` | Parsing pricing as numbers; trusting cached IDs forever | Pricing fields are **strings**; revalidate model at send (Pitfall 9) |
| OpenRouter `/api/v1/key` & `/credits` | Recomputing balance locally | Read `limit_remaining`/`usage`/`is_free_tier` from API (Pitfall 12) |
| OpenRouter streaming usage | Discarding the final SSE chunk | Capture trailing `usage` object across all loop iterations (Pitfall 12) |
| OpenRouter free models | Treating as unlimited | Map 429/402 to clear UX; account for 15-iteration amplification (Pitfall 11) |
| Supabase `execute_readonly_query` RPC | Assuming RLS alone protects the new table | REVOKE select on secret column from `authenticated`; table allowlist (Pitfall 3) |
| LangSmith `wrap_openai` | Wrapping the per-user-key client | Disable tracing or hide inputs/outputs for BYOK calls (Pitfall 1) |
| Sentry `sk-or-` keys | Only redacting `Authorization` + JWT | Add `sk-or-v1-…` regex scrub in beforeSend/beforeBreadcrumb + backend (Pitfall 2) |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching balance (`/api/v1/key`) on every message render | Slow chat UI, OpenRouter rate noise | Cache balance, refresh on settings open / after a turn | Any real usage; immediately on a chatty user |
| Synchronous model-list fetch in the chat hot path | Added latency per request | Cache in Supabase with TTL; don't fetch in `send_message` | Every request once list is large (400+ models) |
| Decrypting key on a path that runs per-token/per-chunk | CPU + risk of plaintext lingering | Decrypt once per LLM call, hold in local scope, drop immediately | Streaming responses (many chunks) |
| In-process scheduler on suspend-on-idle Fly | Refresh never fires; stale cache | On-demand TTL or external pinger trigger | As soon as traffic is sparse (the portfolio's actual pattern) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Per-user key in LangSmith trace | User secret + chat exfiltrated to 3rd party | Gate `wrap_openai` off / hide inputs for BYOK (Pitfall 1) |
| Per-user key in Sentry (URL/console/error) | Secret leak to error vendor | `sk-or-` regex scrub everywhere (Pitfall 2) |
| Keys table readable by Text-to-SQL tool | Mass key exfiltration via prompt injection | RLS + REVOKE select on secret col from `authenticated` (Pitfall 3) |
| Master enc key co-located / non-rotatable | Single dump compromises all keys; no recovery | Dedicated key, AES-GCM, `key_version`, rotation runbook (Pitfall 4) |
| No CSRF `state` on OAuth callback | Attacker binds wrong key to victim account | Own `state` param, verified server-side (Pitfall 5) |
| Owner-key fail-open fallback | Owner billed for anonymous abuse | Fail-closed, flag-gated, anon-excluded, cost cap (Pitfall 7) |
| Plaintext key in SSE `error`/log | Secret to browser + Sentry | Sanitize `str(e)` before SSE/log (Pitfall 2) |
| Returning own ciphertext into LLM context | Needless exposure / injection surface | Never select key column into model-visible paths (Pitfall 3) |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visible "demo vs your key" state | User unsure who's paying / why limited | Always-visible mode badge + balance (Pitfall 13) |
| Picking paid model with no key silently no-ops | Dead-end, confusion | Key-gated selection launches OAuth inline (Pitfall 13) |
| Mid-chat key rejection → generic error | "It broke," lost trust | Recoverable action: reconnect / demo / add credits (Pitfall 13) |
| Free-model 429/402 shown as app error | Blames the app, not the limit | Tailored "free model rate limited" message (Pitfall 11) |
| Per-thread model now deprecated, thread crashes | Old conversations unusable | Fall back to default + notify (Pitfall 9) |
| Displayed cost ≠ OpenRouter dashboard | Distrust of usage numbers | Show OpenRouter-reported usage/balance, label estimates (Pitfall 12) |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Key storage:** Often missing `key_version`/`nonce` columns and a rotation runbook — verify a second master key can decrypt + lazy re-encrypt (Pitfall 4)
- [ ] **Encrypted keys table:** Often still readable by `execute_readonly_query` — verify `REVOKE SELECT … FROM authenticated` and a prompt-injection SQL probe returns nothing (Pitfall 3)
- [ ] **OAuth flow:** Often missing `state`/CSRF and per-env callback — verify a forged-callback attempt is rejected and prod-origin round-trip works (Pitfall 5/6)
- [ ] **Sentry/LangSmith:** Often only JWTs scrubbed — verify `sk-or-v1-…` is redacted in events, breadcrumbs, console logs, and BYOK chats aren't traced (Pitfall 1/2)
- [ ] **Key resolution:** Often fail-open `user_key or owner_key` — verify it's fail-closed and flag-gated, and anon users can't reach the owner key (Pitfall 7)
- [ ] **Per-request key:** Often a cached singleton client — verify two concurrent users with different keys never cross (Pitfall 8)
- [ ] **Model picker:** Often crashes on deprecated/renamed model or missing pricing field — verify graceful 404 fallback + defensive string parse (Pitfall 9)
- [ ] **Model cache refresh:** Often an in-process scheduler that never fires on suspended Fly — verify on-demand TTL or external trigger (Pitfall 10)
- [ ] **Usage/cost:** Often recomputed locally / missing streamed usage — verify it matches OpenRouter and sums across loop iterations (Pitfall 12)
- [ ] **Cost guardrail (SEC-06 / backlog 999.2):** Often still un-trip-tested — verify the owner-key cap actually fires *before* enabling demo fallback (Pitfall 7)

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Key leaked to Sentry/LangSmith (1,2) | HIGH | Treat as breach: rotate/instruct users to revoke OpenRouter keys, purge vendor events, add scrub rule, post-mortem |
| Keys readable via SQL tool (3) | HIGH | Immediately REVOKE grant + RLS, force key rotation for all users, audit `query_database` history |
| Master enc key needs rotation, no `key_version` (4) | HIGH | Add column, dual-key decrypt window, lazy re-encrypt; if no old key retained, force all users to reconnect |
| Owner-key cost blowout (7) | MEDIUM | Flip flag off (kill switch), cap spend at OpenRouter, identify abusing anon sessions, exclude anon from fallback |
| Deprecated model crashes threads (9) | LOW | Catch 404 at send, fall back to default, prompt re-selection |
| Stale model cache (10) | LOW | Manual refresh endpoint; switch to on-demand TTL |
| Cost display mismatch (12) | LOW | Switch source to OpenRouter `usage`/`/key`; relabel local numbers as estimates |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 LangSmith traces user key | P3 (key resolution) | No `sk-or-`/prompt in LangSmith for BYOK runs |
| 2 Sentry/log/SSE key leak | P1 (backend) + P2 (frontend) | `sk-or-` regex hits nothing in events/logs |
| 3 SQL tool reads keys table | P1 (storage migration) | Prompt-injected `select * from user_api_keys` returns nothing |
| 4 Enc key mgmt / rotation | P1 (storage migration) | Second master key decrypts; `key_version`/`nonce` present |
| 5 PKCE verifier/state/CSRF | P2 (OAuth) | Forged callback rejected; hard-refresh exchange works |
| 6 Callback URL mismatch | P2 (OAuth) + deploy gate | Prod-origin round-trip succeeds; callback path served by SPA |
| 7 Demo fallback cost blowout | P7 (gating) + P3 (shape) | Fail-closed; anon excluded; SEC-06 cap trips (dep: 999.2) |
| 8 Wrong/cross-user key | P3 (per-request resolution) | Concurrent different-key requests never cross |
| 9 Model disappears/renames/pricing | P4 (picker) + P3 (send 404) | Deprecated model → graceful fallback, no crash |
| 10 Stale cache / refresh / popularity | P4 (cache) | New model appears via on-demand TTL; popularity degrades gracefully |
| 11 Free-model rate limits | P3 (error map) + P5 (UI) | 429/402 → tailored message, not generic error |
| 12 Usage/cost accuracy | P5 (display) + P3 (stream usage) | Displayed cost matches OpenRouter; sums all iterations |
| 13 Mid-chat revoke / no-key UX | P6 (settings/UX) | Mode always visible; mid-chat 401 recoverable |

## Sources

- OpenRouter OAuth PKCE — auth URL, `callback_url`, `code_challenge`/`S256`, exchange `POST /api/v1/auth/keys`, `key` response field, localhost-any-port, error codes 400/403/405: https://openrouter.ai/docs/guides/overview/auth/oauth and https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key (HIGH)
- OpenRouter rate limits — `:free` model RPM/RPD caps, ≥-credits threshold, 402 on negative balance, `GET /api/v1/key` fields (`limit`, `limit_remaining`, `usage`, `is_free_tier`): https://openrouter.ai/docs/api/reference/limits (HIGH)
- OpenRouter credits/key endpoints — `GET /api/v1/credits` (total purchased/used), `GET /api/v1/key` (rate limit + spend): https://openrouter.ai/docs/api/api-reference/credits/get-credits (HIGH)
- OpenRouter models — pricing fields are **strings** (`prompt`/`completion`/`image`/`request`); deprecated model → 404 "no endpoints for this model found": https://openrouter.ai/docs/api/api-reference/models/get-models and https://openrouter.ai/docs/guides/overview/models (HIGH)
- OpenRouter usage accounting — `usage` object in last SSE message for streaming; `/api/v1/generation` for post-hoc cost (with delay); native-tokenizer counts: https://openrouter.ai/docs/cookbook/administration/usage-accounting (HIGH)
- LangSmith redaction — `wrap_openai` traces inputs/outputs; hide via `LANGSMITH_HIDE_INPUTS/OUTPUTS`, client-side anonymizer before payload leaves process: https://docs.langchain.com/langsmith/mask-inputs-outputs (HIGH)
- This repo's code (HIGH, direct read): `backend/services/llm_service.py` (`wrap_openai`, single-key client, stream returns on `finish_reason=='tool_calls'`), `backend/routers/chat.py` (15-iteration tool loop, SSE `error` events, budget key lookup), `backend/services/sql_service.py` + `supabase/migrations/20240301000015_execute_readonly_query.sql` (SECURITY DEFINER, service-role, RLS-reliant), `backend/database.py` (service-role only), `frontend/src/lib/sentry.ts` (Authorization+JWT-only scrub), `backend/config.py` (env single-key, `@lru_cache` settings)
- Project context: `.planning/PROJECT.md` (v1.2 features, anon Try-demo auth, free-tier Fly suspend, SEC-06 deferred to 999.2), `.planning/MILESTONES.md` (v1.1 hardening already done — don't duplicate)

---
*Pitfalls research for: OpenRouter BYOK addition to a deployed multi-user RAG app*
*Researched: 2026-06-18*
