# Project Research Summary

**Project:** Board Game Knowledge Base RAG — v1.2 User Options & BYOK
**Domain:** OpenRouter BYOK (OAuth PKCE-provisioned per-user keys) + encrypted key storage + model selection/usage UX, layered onto a shipped FastAPI + Supabase + React 19 agentic RAG app
**Researched:** 2026-06-18
**Confidence:** HIGH

## Executive Summary

v1.2 adds "bring your own key" to a shipped agentic RAG app: users connect their own OpenRouter account via OAuth, the app stores that key encrypted, and every chat runs on the user's credentials and chosen model. This is a narrow, additive integration — the agentic tool-use loop, auth, threads, and SSE streaming are unchanged. The right way to build it is verified and opinionated: **reuse what's already installed** (`cryptography`/Fernet for encryption-at-rest, `httpx` for all OpenRouter calls, `react-router-dom` + Web Crypto for PKCE) and add exactly one meaningful frontend dependency surface (shadcn/ui Combobox for a searchable 400+ model picker). Do **not** add APScheduler, Supabase Vault, `next-themes`, an OpenRouter SDK, or a manual key-paste path — each is either wrong for this runtime or a needless attack surface.

The dominant risk in this milestone is **secret custody**, not feature complexity. The moment the app persists *other people's* OpenRouter keys, its entire risk profile changes. Four cross-cutting security findings must be treated as release blockers, not polish: (1) **observability leaks** — the per-user key (`sk-or-v1-...`) must never reach LangSmith (`wrap_openai` traces inputs/outputs by default), Sentry (whose v1.1 scrubber only catches `Authorization` + Supabase JWTs), or SSE/`logger` error payloads (`chat.py` yields `json.dumps({"error": str(e)})` straight to the browser); (2) **Text-to-SQL exfiltration** — `execute_readonly_query` is `SECURITY DEFINER`, keyword-allowlisted but **table-agnostic**, so a prompt-injected `select * from user_api_keys` can dump every user's ciphertext unless the secret column is `REVOKE`'d from the `authenticated` role; (3) **fail-open fallback** — `key = user_key or owner_key` would bill the owner for every anonymous Try-demo visitor, so resolution must be fail-**closed**, flag-gated, and anon-aware, gated behind the deferred SEC-06 cost guardrail (backlog 999.2); and (4) **cross-user key bleed** — a cached singleton LLM client leaks one user's key to another under concurrent requests, so key+model must be explicit per-request parameters.

The OpenRouter integration facts are verified against official docs and correct several easy-to-get-wrong assumptions. OAuth is **PKCE with no client secret** (`/auth` then backend `POST /api/v1/auth/keys`), and OpenRouter omits `state`, so the app must add and verify its own CSRF `state`. Free vs paid is read from **string** pricing fields (`pricing.prompt == "0"` and `pricing.completion == "0"`, plus the `:free` id convention) — parse defensively, never `float()` blindly. **There is no popularity field** — curate a short allowlist in config; do not scrape. Per-message cost arrives automatically in the **final SSE chunk's** `usage.cost` (the old `usage.include`/`stream_options.include_usage` flags are deprecated no-ops) — but the current loop returns on `finish_reason == "tool_calls"`, so the terminal-turn usage must be captured deliberately. Account balance uses **`GET /api/v1/key`** with the user's own key, **not `/api/v1/credits`** (which requires a management key BYOK users don't have). Refresh of the ~400-model catalog must be a **lazy TTL cache** (Supabase-backed), never an in-process scheduler — Fly.io free-tier suspend kills timers.

## Key Findings

### Recommended Stack

The existing stack is frozen; v1.2 is almost entirely additive-by-reuse. Encryption uses the **already-pinned `cryptography 46.0.5`** (Fernet, AES-128-CBC + HMAC-SHA256) with an app-layer master key held only in a Fly secret — decryption happens in FastAPI per request, so a DB dump alone leaks nothing. All OpenRouter interaction (OAuth exchange, `/models`, `/key` balance) is raw `httpx` per project rule — no SDK. The only real new dependency surface is the **shadcn/ui Combobox** (pulls `cmdk@1.1.1` + `@radix-ui/react-popover@1.1.17`), required because an unfiltered 400+ model list is unusable; this project has not used shadcn before, so a one-time `npx shadcn@latest init` against the Vite + Tailwind 4 setup is a prerequisite. PKCE is generated in-browser with Web Crypto (no library); the theme toggle is a hand-rolled `ThemeContext` + `localStorage` + Tailwind `dark:` (NOT `next-themes`, which is Next.js-only).

**Core technologies:**
- `cryptography` Fernet (already pinned 46.0.5): encrypt user keys at rest — zero new deps, master key in Fly secret only, decrypt per-request in backend
- `httpx` (already in direct use): OAuth code exchange + `/models` + `/key` balance — raw HTTP per project rule, no SDK
- shadcn/ui Combobox (`cmdk` + Radix Popover, React 19-safe): searchable model picker with free/paid badges — the only meaningful new frontend surface
- Web Crypto (`crypto.subtle`) + `react-router-dom@7` (both built-in/present): PKCE generation + OAuth callback route — no new library
- Lazy TTL cache in Supabase (zero deps): model-list refresh that survives Fly suspend — explicitly NOT APScheduler/cron

### Expected Features

The MVP delivers "users run their own models with near-zero-friction onboarding, and the public demo still works." Twelve features are promoted to v1.2 core (P1), including per-thread model selection — the schema/loop change is best done once with the rest of the model work. Cost surfacing is nearly free because `usage.cost` is inline. Several differentiators (auto-refresh + "New" badge, trending/curated marking, low-balance warning, per-thread cost rollup, inline ctx/price hints) are cheap riders that defer to v1.2.x triggered by real usage signals.

**Must have (table stakes):**
- OAuth PKCE "Connect OpenRouter" + success/failure/cancel callback states — the headline feature
- Encrypted server-side key storage, RLS-scoped, never returned to frontend — the security foundation
- Key status indicator + disconnect/reconnect — trust and rotation
- Model picker (free/paid tags + search/filter) + a sensible default model — the "options" half
- Key-gated model selection that triggers OAuth — the conversion moment
- Owner-key demo fallback (global flag, default OFF) + obvious non-dismissible "demo mode" banner
- Per-message cost display (inline `usage.cost`) + balance display via `GET /api/v1/key`
- Settings/account page + Light/Dark/System theme toggle, persisted
- Per-thread model selection (persisted on the `threads` row)

**Should have (competitive):**
- Popularity/"trending" marking (curated allowlist) + favorites/pinned models — cuts choice paralysis at 400+ models
- Context-length + per-Mtok price hints inline — helps pick the right tool for long manuals
- Low-balance warning + per-thread cost rollup — cheap riders on existing balance/cost data
- Auto model-list refresh + "New" badge (TTL refresh-on-read first)

**Defer (v2+):**
- Manual API key paste (anti-feature — OAuth-only posture; doubles failure/security surface)
- Multi-provider native BYOK (OpenRouter already aggregates 400+ models behind one key)
- Admin UI for allowlist/demo config (project rule: no admin UI — env/flag-driven)
- Real-time balance polling, in-app billing/top-up, true background scheduler (anti-features)
- Org/shared-key team billing, heavy picker keyboard-nav/reordering

### Architecture Approach

This is an integration study, not greenfield. v1.2 adds **3 new tables** (`user_api_keys` encrypted + RLS, `user_preferences` for default model/theme, `model_cache` shared catalog) plus **one column** (`threads.model`, nullable), **3 new routers** (`keys.py`, `models.py`, `preferences.py`) and **2 modified** (`chat.py`, `threads.py`), and new services (`crypto_service`, `openrouter_service`, `model_cache_service`). The architectural seam is making the LLM client's **key + model per-request inputs** instead of global settings, resolved in `chat.py` and threaded into `stream_chat_completion` / `get_llm_client`. The agentic tool loop itself is untouched — only *which credentials + model* the per-request client uses changes. Model resolution is three-tier: `thread.model` then `user_preferences.default_model` then owner `settings.llm_model`.

**Major components:**
1. `crypto_service.py` (NEW) — Fernet encrypt/decrypt; master key from env secret; decrypt only in-request, never logged/persisted/returned
2. `keys.py` + `openrouter_service.py` (NEW) — OAuth code-to-key exchange, key status (booleans/label only), disconnect, balance proxy via `GET /api/v1/key`
3. `model_cache_service.py` + `models.py` (NEW) — Supabase-backed catalog with lazy refresh-if-stale + deploy-time seed; frontend reads via backend, never OpenRouter directly
4. `chat.py` + `llm_service.py` (MODIFIED) — per-request key+model resolution block with fail-closed demo-fallback gate; `no_api_key` SSE error reusing the existing error path
5. Frontend (NEW) — `SettingsPage`, `OAuthCallback` (validates `state`), `ModelPicker`, `ThemeToggle`, `lib/pkce.ts`, `useUserKey`/`useModels`/`usePreferences` hooks

### Critical Pitfalls

The four cross-cutting security findings are emphasized here as the milestone's defining risk; the remaining operational pitfalls follow.

1. **Per-user key leaks to observability (LangSmith / Sentry / SSE-error).** `wrap_openai` traces inputs/outputs by default; Sentry's v1.1 scrubber only catches `Authorization` + `sb-...-auth-token` (not `sk-or-v1-...`); `chat.py` streams `str(e)` to the browser and `logger.error(exc_info=True)` ships stack-local key values. **Avoid:** disable LangSmith tracing (build the client without `wrap_openai`) on per-user-key calls; add an `/sk-or-v1-[A-Za-z0-9_-]+/g` regex scrub in Sentry `beforeSend`/`beforeBreadcrumb` AND backend before any log/SSE-error; never put the key in a browser-visible URL.
2. **Text-to-SQL tool can exfiltrate the keys table.** `execute_readonly_query` is `SECURITY DEFINER`, service-role-invoked, keyword-allowlisted but **table-agnostic** — RLS alone is not enough. **Avoid:** `REVOKE SELECT ON user_api_keys FROM authenticated` (or isolate the secret in a schema the role has no USAGE on), add an explicit FROM-table allowlist to the RPC, and never select the key column into any model-visible path. Verify with a prompt-injected `select * from user_api_keys` returning nothing.
3. **Fail-open owner-key fallback leads to cost blowout.** `key = user_key or owner_key` silently bills the owner for every keyless (incl. anonymous Try-demo) user. **Avoid:** fail-**closed** resolution — `if user_has_key ... elif demo_flag_on and user_is_eligible ... else refuse with connect-key UX`; exclude/tighten anon users; land the SEC-06 cost guardrail (backlog 999.2) + kill switch **before** enabling the flag in prod.
4. **Wrong/cross-user key via cached singleton.** A module-level `_client` or `@lru_cache`d key-bearing client leaks keys across concurrent requests. **Avoid:** key+model are explicit per-request params threaded `send_message` to `stream_chat_completion` to `get_llm_client`; audit and convert every `settings.resolved_llm_api_key` / `settings.llm_model` read (incl. the budget context-length lookup in `chat.py`); test that two concurrent different-key requests never cross.
5. **Encryption-key hygiene + OAuth PKCE correctness + model/catalog fragility.** Use a dedicated 32-byte master key separate from the JWT/Supabase secrets with a `key_version` for rotation; generate `state` + `code_verifier` together in `sessionStorage` and verify `state` on callback (OpenRouter omits it); derive `callback_url` per-env (dev localhost vs prod Cloudflare Pages) and ensure the SPA serves the callback path; parse string pricing defensively and revalidate the persisted per-thread model at send time (deprecated model leads to 404 leads to graceful fallback, not a crashed thread); map free-model 429/402 to tailored UX given the 15-iteration loop amplifies request count.

## Implications for Roadmap

Based on the dependency-ordered build sequence in ARCHITECTURE.md (and the pitfall-to-phase mapping in PITFALLS.md), the suggested phase structure is below. The build order is a hard chain for the BYOK critical path (1-2-3), with the model cache (4) parallelizable, and the chat-loop integration (6) the seam where security correctness is enforced.

### Phase 1: Crypto + Encrypted Key Storage Foundation
**Rationale:** Everything BYOK depends on safely storing a key; the highest-risk security decisions (encryption scheme, key separation, RLS, SQL-tool lockdown) must be set here, not retrofitted.
**Delivers:** `crypto_service.py` (Fernet), `KEY_ENCRYPTION_SECRET` in config + Fly/`.env`/`.env.prod`, `user_api_keys` migration (table + RLS + `key_version`), `REVOKE SELECT ... FROM authenticated` on the secret column, backend log/SSE `sk-or-` scrub.
**Addresses:** Encrypted server-side key storage (table stakes).
**Avoids:** Pitfall 3 (SQL-tool exfiltration), Pitfall 4 (enc-key hygiene/rotation), Pitfall 2 (backend leak). Verify with a prompt-injected SQL probe and an encrypt/decrypt round-trip across dev + prod.

### Phase 2: OAuth PKCE — Backend Exchange + Frontend Connect Flow
**Rationale:** Depends on Phase 1 (need somewhere to put the key); provisioning a key is useless without secure storage existing first.
**Delivers:** `openrouter_service.exchange_code` + `keys.py` (`POST /api/keys/openrouter/exchange`, `GET /api/keys/status`, `DELETE /api/keys`); frontend `lib/pkce.ts` (Web Crypto), `OAuthCallback.tsx`, `useUserKey`, callback route; frontend `sk-or-` Sentry scrub.
**Uses:** Web Crypto PKCE (no dep), `httpx` backend exchange, `react-router-dom@7` route.
**Implements:** OAuth callback flow; backend-side exchange so the key lands server-side and is encrypted before storage.
**Avoids:** Pitfall 5 (verifier/`state`/CSRF — add and verify own `state`), Pitfall 6 (per-env `callback_url` derived from `window.location.origin`; prod-origin round-trip test), Pitfall 2 (frontend leak).

### Phase 3: Per-Request Key + Model Resolution (chat loop seam)
**Rationale:** The architectural seam of the whole milestone; both the fail-closed fallback *shape* and the cross-user-key correctness live here, plus the LangSmith gating decision.
**Delivers:** MODIFIED `chat.py` (resolution block: thread-pref-owner model; user-key to gated-demo-fallback key; `no_api_key` SSE error) + `llm_service.py` (per-request `api_key`/`model` kwargs; gate `wrap_openai` off for BYOK calls); convert the budget context-length lookup to the per-request key.
**Avoids:** Pitfall 8 (cross-user/cached-singleton key), Pitfall 1 (LangSmith traces user key), Pitfall 7 *shape* (fail-closed), Pitfall 11 (map 429/402 distinctly), Pitfall 12 *capture* (read trailing `usage` on the terminal non-tool-call turn). Test: concurrent different-key requests never cross.

### Phase 4: Model Cache + Catalog (parallelizable)
**Rationale:** Independent of 1-3; only the picker UI joins them. Supabase-backed cache survives Fly suspend.
**Delivers:** `model_cache` migration + `model_cache_service` (refresh-if-stale + deploy seed) + `models.py` (`GET /api/models`); free/paid from string pricing, curated popularity allowlist.
**Uses:** Lazy TTL cache (no scheduler), `httpx` with owner key for the global catalog.
**Avoids:** Pitfall 10 (in-process scheduler never fires on suspend; popularity has no API field — curate + degrade gracefully), Pitfall 9 *parsing* (string pricing parsed defensively).

### Phase 5: Preferences + threads.model
**Rationale:** Soft dependency consumed by the picker (Phase 7) and chat resolution (Phase 3); enables per-thread model and theme storage. The theme toggle is the lowest-risk slice and can ship anytime once `user_preferences` exists.
**Delivers:** `user_preferences` migration, `preferences.py` (`GET`/`PUT`), `threads.model` column, schema updates, `PATCH /api/threads/{id}`.
**Addresses:** Per-thread model selection, default model, persisted theme.

### Phase 6: Usage/Cost Display + Settings/Key-State UX
**Rationale:** Trust features that depend on the resolved request path and the connected key.
**Delivers:** Per-message cost from inline `usage.cost` summed across loop iterations; balance via `GET /api/v1/key`; settings page key-state UX (demo vs own-key vs no-key always visible); mid-chat 401/402/403 recoverable actions.
**Addresses:** Per-message cost, balance display, settings page.
**Avoids:** Pitfall 12 (trust OpenRouter-reported usage; don't recompute), Pitfall 13 (mid-chat revoke / no-key dead-ends), Pitfall 11 *surfacing* (free-model limit messaging).

### Phase 7: Frontend Options UI Capstone + Demo-Fallback Gating
**Rationale:** Wires picker + connect/disconnect + theme + balance; demo-fallback enablement is last and gated on SEC-06.
**Delivers:** `SettingsPage`, `ModelPicker` (gates on key, free/paid badges, curated popularity), `ThemeToggle`, `useModels`/`usePreferences`, `useChat` `no_api_key` CTA; `demo_fallback_enabled` flag wiring.
**Addresses:** Key-gated selection, demo banner, full options surface.
**Avoids:** Pitfall 7 (demo-fallback cost blowout) — **hard dependency on SEC-06 cost guardrail / backlog 999.2 landing before enabling the flag in prod**; Pitfall 9 *at-send* (deprecated per-thread model leads to graceful fallback).

### Phase Ordering Rationale

- **1-2-3 is the BYOK critical path** (store, provision, use); each later phase is meaningless without the prior. Security-critical decisions front-load into Phase 1 (storage/RLS/SQL-lockdown) and Phase 3 (fail-closed resolution + cross-user isolation + tracing gate) where they're cheapest to enforce.
- **Phase 4 (model cache) parallelizes** — it has no dependency on the key path and only meets the rest at the picker UI, so it can run alongside 1-3 to compress the schedule.
- **Phase 5 (prefs + threads.model) is a soft dependency** of both 3 and 7; the theme toggle within it is the most independent, lowest-risk slice and can ship early.
- **Demo-fallback enablement is deliberately last (Phase 7)** and explicitly blocked on the deferred SEC-06 cost guardrail (backlog 999.2) — the fail-closed *shape* lands in Phase 3, but flipping the flag on in prod without a proven owner-key spend cap + kill switch is a release blocker.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (per-request resolution):** the LangSmith `wrap_openai` gating + Sentry/SSE scrub + concurrent-key isolation are the highest-blast-radius security work; validate the LangSmith client-side anonymizer/disable approach against the prod LangSmith project and confirm `wrap_openai` does not serialize `api_key`.
- **Phase 7 (demo-fallback gating):** depends on SEC-06 cost guardrail (backlog 999.2), which was deferred and trip-untested; needs the guardrail's actual fire-before-blowout behavior validated, plus the anon-eligibility budget design.

Phases with standard patterns (skip research-phase):
- **Phase 1 (crypto + storage):** Fernet + Supabase RLS migration are well-trodden in this repo; the one novel item (`REVOKE SELECT ... FROM authenticated` + RPC table allowlist) is specified in ARCHITECTURE/PITFALLS.
- **Phase 4 (model cache):** lazy TTL + Supabase-backed cache + `GET /api/models` is a documented, low-risk pattern; only the curated-popularity allowlist is a decision, not research.
- **Phase 5 (prefs + threads.model):** standard migration + CRUD router mirroring existing `threads` conventions.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | OpenRouter endpoints verified against official docs; package versions verified live via npm/pip/Context7; encryption/HTTP/PKCE all reuse already-installed deps. |
| Features | MEDIUM-HIGH | OpenRouter API behaviors HIGH (official docs); UX conventions MEDIUM (T3 Chat / LibreChat / Open WebUI / OpenRouter UI + general BYOK practice). |
| Architecture | HIGH | Existing code read directly; integration points (files/tables/routers) identified concretely; OAuth + models API verified against docs. |
| Pitfalls | HIGH | OpenRouter OAuth/limits/usage verified against docs; secret-handling and RLS pitfalls grounded in this repo's actual code (`llm_service.py`, `chat.py`, `sql_service.py`, `execute_readonly_query.sql`, `sentry.ts`, `tracing.py`). |

**Overall confidence:** HIGH

### Gaps to Address

- **OpenRouter `/api/v1/key` exact field names** for balance display: ARCHITECTURE notes MEDIUM confidence on the precise response shape. Validate live during Phase 6 against a real OAuth-provisioned key; use `limit_remaining` (may be null for pay-as-you-go) + `usage*` fields and tolerate nulls.
- **SEC-06 cost guardrail (backlog 999.2) is deferred and trip-untested.** It is a hard dependency for enabling demo-fallback in prod (Phase 7). Plan to close/verify it (a real fire-before-blowout test + kill switch) before flipping the flag; the fail-closed default keeps the milestone safe to ship without it.
- **LangSmith redaction of `api_key`:** confirm `wrap_openai` does not serialize the client's `Authorization`/`api_key` into trace metadata; safest default is to build the BYOK client without the wrapper entirely. Validate in Phase 3.
- **Fly.io exact suspend timing** is MEDIUM; the constraint (timers unreliable when idle, "schedule + suspend" mutually exclusive) is HIGH and already drives the lazy-TTL-cache decision — no scheduler dependency, so the gap doesn't block.
- **shadcn `init` against this Vite + Tailwind 4 project:** the project has not used shadcn before despite the CLAUDE.md line; verify `components.json` does not pre-exist and that init targets `src/` + Tailwind v4 + the existing alias setup before adding Combobox. Handle as a Phase 7 prerequisite step.
- **Per-thread model deprecation/rename** happens out-of-band; persisted IDs are unvalidated — revalidate at send time and fall back to default with a user-visible notice (Phase 3 at-send + Phase 7 UX).

## Sources

### Primary (HIGH confidence)
- OpenRouter OAuth PKCE — https://openrouter.ai/docs/guides/overview/auth/oauth — `/auth` params, `POST /api/v1/auth/keys` exchange, no client secret, S256, `{key, user_id}` response, localhost-any-port, error codes
- OpenRouter list models — https://openrouter.ai/docs/api/api-reference/models/get-models — model+pricing shape, pricing as **strings**, `"0"`=free, `sort=most-popular`, no popularity field, deprecated model leads to 404 at request time
- OpenRouter usage accounting — https://openrouter.ai/docs/cookbook/administration/usage-accounting — `usage.cost`/`cost_details` in final SSE chunk, deprecated `include` flags
- OpenRouter API limits / `GET /api/v1/key` — https://openrouter.ai/docs/api/reference/limits — `limit`/`limit_remaining`/`usage`/`is_free_tier`, `:free` RPM/RPD caps, 402 on negative balance
- OpenRouter get credits — https://openrouter.ai/docs/api/api-reference/credits/get-credits — `/api/v1/credits` requires a management key (informs the `/key` correction)
- LangSmith redaction — https://docs.langchain.com/langsmith/mask-inputs-outputs — `wrap_openai` traces inputs/outputs; `LANGSMITH_HIDE_INPUTS/OUTPUTS`; client-side anonymizer before payload leaves process
- Fly.io autostop/suspend — https://fly.io/docs/launch/autostop-autostart/ , https://fly.io/docs/reference/suspend-resume/ — suspend vs schedule conflict; in-process timers unreliable when idle
- shadcn/ui Combobox — https://ui.shadcn.com/docs/components/radix/combobox — built on Popover + cmdk; install path
- npm/pip/Context7 (verified live) — `cmdk@1.1.1`, `@radix-ui/react-popover@1.1.17`, `class-variance-authority@0.7.1`, `clsx@2.1.1`, `tailwind-merge@3.6.0`; `cryptography 46.0.5` (latest 49.0.0); APScheduler `3.11.2` (rejected for Fly suspend)
- This repo's code (direct read) — `backend/services/llm_service.py`, `backend/routers/chat.py`, `backend/services/sql_service.py`, `supabase/migrations/...execute_readonly_query.sql`, `backend/database.py`, `backend/config.py`, `backend/auth.py`, `frontend/src/lib/sentry.ts`, `frontend/src/hooks/useChat.ts`, `frontend/src/App.tsx`, `frontend/src/lib/api.ts`, `backend/models/schemas.py`, `.planning/PROJECT.md`, `.planning/MILESTONES.md`

### Secondary (MEDIUM confidence)
- T3 Chat model picker / favorites / BYOK — https://feedback.t3.chat/p/better-model-picker , https://t3.chat/ — UX conventions for picker + BYOK
- LibreChat model specs / selector grouping — https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/model_specs
- Open WebUI vs LibreChat — https://docs.openwebui.com/alternatives/librechat/ — multi-provider BYOK landscape

### Tertiary (LOW confidence)
- Freemium conversion / shared-key demo UX (general) — https://userpilot.com/blog/freemium-strategy/ — informs the demo-banner conversion framing

---
*Research completed: 2026-06-18*
*Ready for roadmap: yes*
