# Stack Research — v1.2 User Options & BYOK

**Domain:** OpenRouter BYOK (OAuth-provisioned keys), encrypted key storage, model picker, usage display — additive to an existing FastAPI + Supabase + React 19 RAG app
**Researched:** 2026-06-18
**Confidence:** HIGH (OpenRouter endpoints verified against official docs; versions verified via npm/pip/Context7)

**Scope note:** Existing stack (React 19, Vite 6, Tailwind 4, FastAPI 0.115, Supabase, OpenAI SDK over OpenRouter, Docling, LangSmith, Sentry) is frozen. This doc ONLY covers what's added/changed for BYOK + user options.

---

## TL;DR — What to add, what NOT to add

- **Encryption:** Reuse the **already-installed `cryptography` (Fernet)** — zero new deps. Do **not** adopt Supabase Vault/pgsodium.
- **OAuth PKCE:** No SDK needed. **No client secret.** Backend exchanges the code against one POST endpoint with stdlib + existing `httpx`.
- **Model list + balance:** Plain REST against OpenRouter. No SDK. Use existing `httpx`.
- **Scheduled refresh:** Do **NOT** add APScheduler/cron. Use a **lazy TTL cache** (refresh-on-request) — Fly.io free-tier auto-suspend makes in-process timers unreliable.
- **Frontend model picker:** Add **shadcn/ui Combobox** (cmdk + Radix Popover). This is the only meaningful new frontend dependency surface. OAuth redirect needs **no library** — `react-router-dom` (already present) + `crypto.subtle` (built-in).
- **Theme toggle:** Hand-roll with a tiny context + `localStorage` + Tailwind `dark:`. Do **NOT** add `next-themes` (it is a Next.js library).

---

## Recommended Stack

### Core Technologies (NEW for v1.2)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `cryptography` (Fernet) | **already pinned `46.0.5`** | Symmetric encryption-at-rest of user OpenRouter keys | Already a dependency (used for JWT ES256). Fernet = AES-128-CBC + HMAC-SHA256 authenticated encryption, URL-safe base64 output that drops straight into a Postgres `text` column. Zero new deps, audited, batteries-included. |
| OpenRouter REST (no SDK) | API v1 | OAuth code exchange, model list, balance/usage | Project rule is raw SDK / raw HTTP, no abstraction layers. Every BYOK need is one HTTP call; an SDK is pure overhead. Use the **already-used `httpx`**. |
| `httpx` | already in use (transitive, used directly) | HTTP client for OAuth exchange + models + `/key` balance calls | Already the project's chosen client for embedding/web-search/rerank calls. Reuse it; do not add `requests`/`aiohttp`. |
| shadcn/ui **Combobox** | install via `npx shadcn@latest add combobox` (pulls `cmdk@1.1.1`, `@radix-ui/react-popover@1.1.17`) | Searchable, keyboard-accessible model picker with free/paid + popularity tagging | The model list is ~400+ entries — a searchable combobox is mandatory UX. shadcn Combobox = Radix Popover + cmdk command palette; accessible, async-friendly, owns its own source (no runtime lock-in). |

### Supporting Libraries (NEW)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `cmdk` | **1.1.1** | Command/list primitive under the Combobox | Pulled in automatically by `shadcn add combobox`. |
| `@radix-ui/react-popover` | **1.1.17** | Popover positioning for the Combobox | Pulled in automatically by `shadcn add combobox`. |
| `class-variance-authority` | **0.7.1** | Variant styling for shadcn primitives | Pulled in by shadcn init if not present. Tiny. |
| `clsx` | **2.1.1** | `cn()` className helper for shadcn | Pulled in by shadcn init. |
| `tailwind-merge` | **3.6.0** | `cn()` class de-dupe for shadcn | Pulled in by shadcn init. Note: Tailwind 4 — `tailwind-merge` 3.x targets TW v4. |
| Python stdlib `secrets` + `hashlib` + `base64` | stdlib | PKCE `code_verifier`/`code_challenge` (S256) **if** generated server-side | Only if you choose backend-generated PKCE. Browser path uses `crypto.subtle` (no dep). |

### Reuse (already installed — DO NOT re-add)

| Already have | Now also powers |
|--------------|-----------------|
| `cryptography==46.0.5` | Fernet encrypt/decrypt of user keys |
| `httpx` (direct use) | OAuth exchange, `/models`, `/key` balance |
| `pydantic==2.11.1` / `pydantic-settings==2.9.1` | New settings (`KEY_ENCRYPTION_KEY`, `DEMO_FALLBACK_ENABLED`), structured model-list parsing |
| `supabase==2.13.0` (service-role) | New `user_api_keys` table read/write, RLS-scoped per `user_id` |
| `sse-starlette==2.2.1` | Emit per-request `usage.cost` in the existing chat SSE stream |
| `react-router-dom@^7.13.1` | OAuth callback route (`/auth/openrouter/callback`) |
| `@supabase/supabase-js@^2.99.3` | Session token for authed calls to new backend endpoints |
| `lucide-react@^0.577.0` | Icons for settings page, key status, theme toggle |
| `slowapi==0.1.9` | Rate-limit the new OAuth-exchange + balance endpoints |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `npx shadcn@latest init` | One-time: wire shadcn into Vite project (creates `components.json`, `lib/utils.ts`, CSS vars) | **This project has NOT used shadcn before** despite the CLAUDE.md line — verify `components.json` does not exist, then init. Confirm it targets `src/`, Tailwind v4, and the existing alias setup. |
| `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | Generate the 32-byte master `KEY_ENCRYPTION_KEY` | Store as a Fly.io secret + `.env`/`.env.prod`. Never in the image. |

---

## Detailed Findings

### (1) Encryption-at-rest of user API keys

**Recommendation: `cryptography` Fernet, app-layer encryption, master key from env.** HIGH confidence.

**Why Fernet over Supabase Vault/pgsodium:**

| Option | Verdict | Reason |
|--------|---------|--------|
| **`cryptography` Fernet** | ✅ Use | Already installed. Authenticated symmetric encryption (AES-128-CBC + HMAC-SHA256). Decrypt happens **only in FastAPI per request** — exactly the milestone requirement. Master key lives in a Fly secret, not the DB, so a DB leak alone does not expose keys. |
| Supabase Vault | ❌ Avoid | Couples secret access to DB roles; the backend already uses the service-role key (bypasses RLS) so Vault adds DB-side machinery without the "decrypt only in backend with a separate key" isolation. Extra migration + operational surface for no security gain here. |
| pgsodium (raw) | ❌ Avoid | Being de-emphasized in favor of Vault on Supabase; column-encryption ergonomics are awkward and the key lives in the DB cluster. |
| Postgres `pgcrypto` | ❌ Avoid | Key would travel in SQL / live near the data. Worse isolation than app-layer Fernet. |

**Concrete approach:**
- New table `user_api_keys (user_id uuid pk references auth.users, provider text default 'openrouter', encrypted_key text not null, key_label text, created_at, updated_at)`.
- **RLS:** owner-only (`user_id = auth.uid()`) for any frontend visibility; backend writes/reads with the service-role client. Never return the decrypted (or encrypted) key to the frontend — expose only a boolean `connected` + masked label.
- Master key: `KEY_ENCRYPTION_KEY` env var (a `Fernet.generate_key()` value, 32 url-safe base64 bytes). Load via the existing `pydantic-settings` `Settings`.
- Encrypt on store: `Fernet(key).encrypt(raw_key.encode())`. Decrypt per request in `llm_service` when building the per-user client.
- **Key rotation:** Fernet supports `MultiFernet` for zero-downtime rotation — model the setting as a list (primary first) so a future rotation re-encrypts lazily. Document but don't over-build.

**Integration point:** `backend/services/llm_service.get_llm_client()` currently reads a single global `settings.resolved_llm_api_key`. It must become per-user: fetch+decrypt the user's key, fall back to the owner key **only if** `DEMO_FALLBACK_ENABLED` is true. Add a new `services/crypto_service.py` (encrypt/decrypt helpers) and a `services/user_key_service.py` (DB CRUD + decrypt).

### (2) OpenRouter OAuth PKCE — exact endpoints

Verified against OpenRouter official docs. HIGH confidence. **No client secret required** (PKCE public-client flow).

**Step 1 — Authorization redirect (browser):**
```
https://openrouter.ai/auth
  ?callback_url=<YOUR_REDIRECT_URI>          (required, e.g. https://app/.../auth/openrouter/callback)
  &code_challenge=<BASE64URL_SHA256(code_verifier)>   (recommended)
  &code_challenge_method=S256                 (recommended; "plain" also allowed)
```
User logs in to OpenRouter, authorizes, and is redirected back to `callback_url` with `?code=<AUTH_CODE>`.

**Step 2 — Exchange code for key (backend POST):**
```
POST https://openrouter.ai/api/v1/auth/keys
Content-Type: application/json
{
  "code": "<AUTH_CODE>",
  "code_verifier": "<original code_verifier>",   // required if code_challenge was used
  "code_challenge_method": "S256"                // required if code_challenge was used
}
```
**Response:**
```json
{ "key": "sk-or-v1-...", "user_id": "..." | null }
```
The `key` field is the user-controlled OpenRouter API key — encrypt it (see §1) and store it.

**PKCE generation (S256):** `code_verifier` = high-entropy random string; `code_challenge` = `base64url( sha256(code_verifier) )` (no padding). Do this in the browser with `crypto.subtle.digest('SHA-256', ...)` (no dependency) and stash `code_verifier` in `sessionStorage`, **or** generate server-side with stdlib `secrets`/`hashlib`/`base64` and keep `code_verifier` in a short-lived server session. Browser-side generation is simplest and avoids server state.

**Security notes:**
- Add a CSRF `state` param yourself (OpenRouter doesn't mandate it) and verify on callback.
- Do the code→key **exchange on the backend**, not the browser, so the key never touches client JS and goes straight to encrypted storage.
- Register the exact `callback_url` origin in your prod/dev configs; it must match the deployed frontend URL.

### (3) Model list + free/paid detection + balance

**List models — `GET https://openrouter.ai/api/v1/models`** (no auth required for the public list). HIGH confidence.

Response: `{ "data": [ Model, ... ] }`. Each `Model` includes:
- `id`, `canonical_slug`, `name`, `created` (unix), `description`
- `context_length` (int|null)
- `architecture` → `{ modality, tokenizer, input_modalities, output_modalities, instruct_type }`
- `pricing` → all values are **strings, USD per token** (prompt/completion are per-token in this object): `prompt`, `completion`, `request`, `image`, `web_search`, `internal_reasoning`, `input_cache_read`, `input_cache_write`, plus audio/image variants
- `top_provider` → `{ is_moderated, context_length, max_completion_tokens }`
- `supported_parameters` (array), `per_request_limits`, `hugging_face_id`

**Free vs paid detection:**
- **Free** = `pricing.prompt == "0"` **and** `pricing.completion == "0"` (string `"0"`). Also, free models conventionally carry a `:free` suffix in `id` (e.g. `...:free`) and have rate limits (≈20 req/min, 200 req/day).
- **Paid** = any nonzero pricing string. Parse to float for sorting/display (remember per-token → multiply by 1e6 for "per-million" display).
- **Popularity:** the `/models` endpoint does **not** expose a usage/popularity rank. Recommendation: maintain a small **curated allowlist of "popular" model ids** in backend config (a constant set), and tag matches `popular: true`. Optionally sort by `created` desc for "newest." Do not invent a popularity metric.

**Per-request token/cost:** OpenRouter returns it **automatically** in the chat completion `usage` object — no special param (the old `usage:{include:true}` / `stream_options:{include_usage:true}` are deprecated/no-ops). For **streaming**, `usage` arrives in the **final SSE chunk**. Fields:
- `usage.prompt_tokens`, `usage.completion_tokens`, `usage.total_tokens`
- `usage.cost` (USD charged for the request)
- `usage.cost_details.upstream_inference_cost` (nonzero only for BYOK)
- `usage.prompt_tokens_details` / `usage.completion_tokens_details`

Integration: in `llm_service.stream_chat_completion`, read `chunk.usage` on the terminal chunk and `yield {"type": "usage", ...}` so the chat SSE surfaces per-request cost. The current loop returns early on `tool_calls`; ensure the final assistant turn (no tool calls) captures `usage`.

**Account balance — use `GET https://openrouter.ai/api/v1/key`** (NOT `/credits`). Important correction:
- `GET /api/v1/credits` returns `{ data: { total_credits, total_usage } }` but **requires a management/provisioning key** — BYOK users authorize via OAuth and receive a normal inference key, so `/credits` will not work for them.
- `GET /api/v1/key` works with the **user's own (OAuth-obtained) key** and returns its own usage/limits:
  ```
  GET https://openrouter.ai/api/v1/key
  Authorization: Bearer <user_key>
  → { data: { label, limit, limit_remaining, limit_reset,
              usage, usage_daily, usage_weekly, usage_monthly,
              byok_usage, byok_usage_*, is_free_tier, include_byok_in_limit } }
  ```
  Use `limit_remaining` (may be null for unlimited/pay-as-you-go) and `usage*` for the balance/usage display. Call this from the backend (decrypt key → call → return non-sensitive fields).

### (4) Scheduled model-list refresh on FastAPI + Fly.io free tier

**Recommendation: lazy TTL cache (refresh-on-request), NOT a scheduler.** HIGH confidence on the Fly constraint; MEDIUM on exact suspend timing.

**Why not APScheduler/cron:**
- Fly.io free-tier uses **auto-stop / auto-suspend** when idle (this app already runs "Fly suspend, no keep-warm" per v1.1 Key Decisions). A suspended/stopped machine **cannot run in-process timers** — APScheduler jobs simply don't fire while asleep, and Fly docs note a machine **cannot use suspend if it has a schedule configured**. So a timer either won't run, or forces you to keep the machine warm (defeats the free-tier cost model).
- A Fly **scheduled Machine / external cron** would work but adds infra and a second deployable for a trivial cache warm — over-engineering for a ~400-row JSON file that changes slowly.

**Use instead — in-memory TTL cache with stale-while-revalidate:**
- Cache the `/models` response in a module-level singleton with a timestamp (mirror the existing `_jwk_client` / `_converter` singleton pattern).
- On request, if `now - fetched_at > TTL` (e.g. `MODEL_LIST_TTL_SECONDS = 21600` / 6h), refetch; otherwise serve cache.
- Serve stale on fetch failure (resilience). First request after a cold start pays one ~200ms fetch — acceptable.
- Optional: also fetch once in a FastAPI **lifespan/startup** hook so the first user doesn't wait — but TTL-on-request is the source of truth.

This requires **zero new dependencies** and is the idiomatic fit for an auto-suspending free-tier box.

### (5) Frontend: OAuth redirect handling + model-picker combobox (React 19 + shadcn/ui)

**OAuth redirect — no new library.** HIGH confidence.
- Add a route in the existing `react-router-dom@7` setup: `/auth/openrouter/callback`.
- Generate PKCE `code_verifier`/`code_challenge` with the built-in **Web Crypto** (`crypto.getRandomValues` + `crypto.subtle.digest('SHA-256')`) — no dep. Store `code_verifier` + a `state` in `sessionStorage`.
- Callback component reads `?code`/`?state`, POSTs `{code, code_verifier}` to a **new backend endpoint** (e.g. `POST /api/keys/openrouter/exchange`) which does the actual OpenRouter exchange + encrypt + store, then redirects to settings.

**Model picker — shadcn/ui Combobox.** HIGH confidence on approach.
- shadcn Combobox = Radix **Popover** + **cmdk** Command list. Install: `npx shadcn@latest add combobox` (or add `button` + `popover` + `command` individually). This pulls `cmdk@1.1.1` and `@radix-ui/react-popover@1.1.17`, both React 19-compatible.
- **Integration caveat (important):** this project does **not** currently use shadcn — `frontend/package.json` shows no Radix/cmdk and a hand-rolled Tailwind UI. You must run `npx shadcn@latest init` first (creates `components.json`, `lib/utils.ts` with `cn()`, CSS variables). Verify it targets the Vite + Tailwind 4 setup and `src/` aliasing. Keep it scoped — adopt only Combobox/Popover/Command (+ their utils), not the whole library, to avoid bloat and visual drift from the existing custom UI.
- Render free/paid + popular as small badges inside each cmdk item; group "Free" / "Paid" sections. With ~400 models, cmdk's built-in fuzzy filter handles search client-side.
- **Per-thread persistence:** store the selected `model` on the `threads` row (new column) and in the message-send payload; the model picker reads/writes it. Backend uses the per-thread model in `stream_chat_completion` instead of the global `settings.llm_model`.

**Theme toggle — hand-roll, no `next-themes`.** HIGH confidence.
- `next-themes@0.4.6` exists but is built for Next.js — wrong runtime. For Vite + React 19 + Tailwind 4, use a tiny `ThemeContext` (like the existing `AuthContext`) that toggles a `dark` class on `<html>` and persists to `localStorage` (and optionally to the user's settings row). Tailwind 4 `dark:` variant does the rest. Zero deps.

---

## Installation

```bash
# Backend — NO new pip packages required for sections 1-4.
#   cryptography==46.0.5 already pinned; httpx already used; APScheduler intentionally NOT added.
#   (Optional) bump cryptography to a newer 46.x/48.x at upgrade time — 46.0.5 is fine.

# Frontend — one-time shadcn wiring, then the picker primitives:
cd frontend
npx shadcn@latest init          # creates components.json, lib/utils.ts (cn), CSS vars
npx shadcn@latest add combobox  # pulls cmdk@1.1.1 + @radix-ui/react-popover@1.1.17 + button/command
# (shadcn init also adds, if missing: class-variance-authority@0.7.1, clsx@2.1.1, tailwind-merge@3.6.0)

# Generate the master encryption key (store as Fly secret + .env / .env.prod, NEVER in image):
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# -> set KEY_ENCRYPTION_KEY=<value>
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `cryptography` Fernet (app-layer) | Supabase Vault | If you wanted DB-managed secrets accessed via SQL roles and were NOT already running a service-role backend. Not the case here. |
| Fernet | pgsodium / pgcrypto column encryption | If keys had to be queried/filtered encrypted at the DB layer. Here decryption is per-request in the backend only — app-layer wins. |
| Raw `httpx` to OpenRouter | `openrouter` Python SDK / OpenAI SDK helpers | Never — project rule is raw HTTP/SDK only; an OAuth/models SDK adds a dependency for 3 trivial calls. |
| Lazy TTL cache | APScheduler (`3.11.2`) in-process | Only if the machine were always-on (paid, no auto-suspend). On free-tier auto-suspend it won't fire reliably. |
| Lazy TTL cache | Fly scheduled Machine / external cron | If the model list grew huge or needed guaranteed freshness independent of traffic. Overkill here. |
| shadcn Combobox (cmdk + Radix) | Native `<select>` | Only as a throwaway; 400+ options with search/badges need a combobox. |
| shadcn Combobox | Headless UI / Downshift / react-select | If you wanted a different design system. shadcn matches the Tailwind / owns-the-source ethos and is the de facto React combobox. |
| Hand-rolled theme context | `next-themes@0.4.6` | Never in Vite — it's a Next.js library. |
| Web Crypto PKCE in browser | A PKCE npm helper (e.g. `pkce-challenge`) | Only if you dislike ~8 lines of `crypto.subtle`. Avoid the dep. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `GET /api/v1/credits` for BYOK balance | Requires a **management key**; OAuth users only have an inference key — call fails | `GET /api/v1/key` with the user's own key |
| APScheduler / any in-process timer for refresh | Fly free-tier auto-suspend stops the machine; timers don't fire; "schedule + suspend" is mutually exclusive on Fly | Lazy TTL cache (refresh-on-request) + optional startup warm |
| Supabase Vault / pgsodium / pgcrypto | More DB surface, key lives near data, worse isolation than app-layer | `cryptography` Fernet with env-held master key |
| `next-themes` | Next.js-specific; wrong runtime for Vite | Tiny `ThemeContext` + `localStorage` + Tailwind `dark:` |
| Any OpenRouter/OAuth SDK, `requests`, `aiohttp` | Violates raw-HTTP rule; new deps for trivial calls | Existing `httpx` |
| `usage:{include:true}` / `stream_options:{include_usage:true}` | **Deprecated, no-ops** at OpenRouter | Read `usage` from the final SSE chunk automatically |
| Storing/returning the decrypted (or encrypted) key to the frontend | Leaks credentials to client JS | Backend-only decrypt; expose `connected: bool` + masked label only |
| Adopting all of shadcn/ui | Bloat + visual drift from existing custom Tailwind UI | Add only Combobox/Popover/Command |
| Client secret in the OAuth flow | PKCE public-client flow has none; inventing one adds a leakable secret | PKCE `code_verifier` + `state` only |

## Stack Patterns by Variant

**If `DEMO_FALLBACK_ENABLED=true` (public demo):**
- `get_llm_client(user_id)` resolves the user key → falls back to the owner key → forces a restricted/cheap default model.
- Anonymous "Try demo" users (already supported) never trigger OAuth; they ride the owner key.

**If `DEMO_FALLBACK_ENABLED=false` (default / portfolio-safe):**
- Selecting any model with no connected key → frontend triggers the OAuth redirect (key-gating). No owner key is ever used for a user request.

**If the user has connected a key:**
- All requests use the per-user decrypted key + per-thread model; balance/usage shown via `/api/v1/key`.

## Version Compatibility

| Package | Version | Notes |
|---------|---------|-------|
| `cryptography` | 46.0.5 (installed; latest 49.0.0) | Fernet API stable across these; no upgrade required for v1.2. |
| `cmdk` | 1.1.1 | React 19 compatible. |
| `@radix-ui/react-popover` | 1.1.17 | React 19 compatible. |
| `tailwind-merge` | 3.6.0 | 3.x targets Tailwind v4 (project is Tailwind ^4.2.2) — required pairing. |
| `class-variance-authority` | 0.7.1 | Peer-compatible with shadcn. |
| `clsx` | 2.1.1 | — |
| shadcn CLI | `shadcn@latest` | Run `init` for Vite/Tailwind-4; confirm `components.json` aliases match `src/`. |
| React | 19.2.4 (project) | All above verified React-19-safe. |
| OpenRouter API | v1 | OAuth `/auth` + `/api/v1/auth/keys`; `/api/v1/models`; `/api/v1/key`. |

## Sources

- OpenRouter — OAuth PKCE guide: https://openrouter.ai/docs/guides/overview/auth/oauth — auth URL, params, exchange endpoint, no client secret (HIGH)
- OpenRouter — Exchange auth code for API key: https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key — `POST /api/v1/auth/keys`, response `{key, user_id}` (HIGH)
- OpenRouter — List models: https://openrouter.ai/docs/api/api-reference/models/get-models — `GET /api/v1/models`, model+pricing shape, string `"0"`=free (HIGH)
- OpenRouter — Usage accounting: https://openrouter.ai/docs/cookbook/administration/usage-accounting — `usage.cost`, token detail fields, auto-included in final SSE chunk (HIGH)
- OpenRouter — Get credits: https://openrouter.ai/docs/api/api-reference/credits/get-credits — `GET /api/v1/credits` requires management key (HIGH; informs the `/key` correction)
- OpenRouter — API limits / `GET /api/v1/key`: https://openrouter.ai/docs/api/reference/limits — `/key` response shape, works with own key (HIGH)
- shadcn/ui — Combobox: https://ui.shadcn.com/docs/components/radix/combobox — built on Popover + cmdk; install path (HIGH)
- Context7 `/agronholm/apscheduler` + pip — APScheduler `3.11.2` (verified, then rejected for Fly free-tier) (HIGH)
- Fly.io — Autostop/autostart + suspend docs/community: https://fly.io/docs/launch/autostop-autostart/ , https://fly.io/docs/reference/suspend-resume/ , https://community.fly.io/t/handling-long-running-tasks-with-automatic-machine-shutdown-on-fly-io/24256 — suspend vs schedule conflict; timers unreliable when idle (HIGH constraint, MEDIUM exact-timing)
- npm registry — `cmdk@1.1.1`, `@radix-ui/react-popover@1.1.17`, `class-variance-authority@0.7.1`, `clsx@2.1.1`, `tailwind-merge@3.6.0`, `next-themes@0.4.6` (HIGH, verified live)
- pip — `cryptography` latest `49.0.0`, project pinned `46.0.5` (HIGH, verified live)
- Project files: `backend/config.py`, `backend/services/llm_service.py`, `backend/auth.py`, `backend/requirements.txt`, `frontend/package.json` (existing-stack integration points)

---
*Stack research for: OpenRouter BYOK additions to an existing FastAPI + Supabase + React 19 RAG app*
*Researched: 2026-06-18*
