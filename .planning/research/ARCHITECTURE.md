# Architecture Research — v1.2 User Options & BYOK

**Domain:** BYOK (bring-your-own-key) integration into a shipped agentic RAG app
**Researched:** 2026-06-18
**Confidence:** HIGH (existing code read directly; OpenRouter OAuth + models API verified against official docs)

> Scope: this is an **integration** study for a subsequent milestone, not greenfield
> domain research. It maps the v1.2 BYOK + user-options features onto the existing,
> shipped architecture (React SPA + FastAPI + Supabase). Every section explicitly
> labels components as **NEW** or **MODIFIED** and identifies the exact files/tables
> that change. Downstream consumer: requirements + roadmap.

---

## Standard Architecture (current + v1.2 deltas)

### System Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React SPA, Vite)                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │ ChatPage │  │ Settings │  │ ModelPicker   │  │ ThemeToggle      │   │
│  │ (MOD)    │  │ Page(NEW)│  │ (NEW)         │  │ (NEW)            │   │
│  └────┬─────┘  └────┬─────┘  └──────┬────────┘  └────────┬─────────┘   │
│       │  OAuthCallback route (NEW)  │  useUserKey/useModels (NEW hooks) │
├───────┴─────────────┴───────────────┴────────────────────┴────────────┤
│   apiFetch / apiStream (api.ts, unchanged) + Supabase anon (auth only) │
├───────────────────────────────────────────────────────────────────────┤
│                       BACKEND (FastAPI, stateless)                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────────────┐   │
│  │ chat.py    │ │ keys.py    │ │ models.py  │ │ preferences.py     │   │
│  │ (MODIFIED) │ │ (NEW)      │ │ (NEW)      │ │ (NEW)             │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────────┬──────────┘   │
│        │              │              │                  │               │
│  ┌─────┴──────────────┴──────────────┴──────────────────┴───────────┐  │
│  │ services: llm_service(MOD) · crypto_service(NEW)                  │  │
│  │           openrouter_service(NEW) · model_cache_service(NEW)      │  │
│  └──────────────────────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────────────────────┤
│                         DATA (Supabase Postgres)                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ user_api_keys│ │ user_prefs   │ │ model_cache  │ │ threads      │   │
│  │ (NEW, RLS)   │ │ (NEW, RLS)   │ │ (NEW, public)│ │ +model col   │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ │ (MODIFIED)   │   │
│                                                       └──────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
         │ HTTPS                                  │ pg_cron / manual refresh
         ▼                                        ▼
   OpenRouter OAuth (/auth, /api/v1/auth/keys)   OpenRouter /api/v1/models
   OpenRouter chat completions (per-user key)    OpenRouter /api/v1/key (balance)
```

### Component Responsibilities

| Component | Responsibility | NEW / MODIFIED |
|-----------|----------------|----------------|
| `user_api_keys` table | One encrypted OpenRouter key per user, RLS-scoped | NEW |
| `user_preferences` table | Per-user default model + theme (+ future prefs) | NEW |
| `model_cache` table | Cached OpenRouter model catalog (shared, read-only to users) | NEW |
| `threads.model` column | Per-thread selected model slug (nullable → falls back to default) | MODIFIED |
| `crypto_service.py` | Fernet encrypt/decrypt of user keys, key from env secret | NEW |
| `openrouter_service.py` | OAuth code→key exchange, balance fetch, models fetch | NEW |
| `model_cache_service.py` | Refresh + read cached model list | NEW |
| `keys.py` router | OAuth callback exchange, key status, key delete, balance | NEW |
| `models.py` router | Serve cached model list to frontend | NEW |
| `preferences.py` router | Read/write default model + theme | NEW |
| `chat.py` router | Resolve per-request key + model; demo-fallback gate | MODIFIED |
| `llm_service.py` | Accept per-request key + model instead of global settings | MODIFIED |
| `config.py` | New settings: encryption key, demo-fallback flag, OAuth redirect base | MODIFIED |
| Frontend `SettingsPage`, `ModelPicker`, `OAuthCallback`, `ThemeToggle` | UI for BYOK + options | NEW |

---

## Database Schema Changes

Three new tables + one column on `threads`. All follow the existing migration
convention (`supabase/migrations/2024030100002X_*.sql`, applied via `supabase db push`
to both the dev `.env` and prod `.env.prod` Supabase projects). RLS is modeled on the
existing `threads` policies (per-user `auth.uid() = user_id`) — see
`20240301000001_create_threads.sql`.

### 1. `user_api_keys` (NEW — encrypted, RLS, one row per user)

```sql
create table user_api_keys (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  provider       text not null default 'openrouter',
  encrypted_key  text not null,          -- Fernet ciphertext (base64), never the plaintext
  key_label      text,                   -- OpenRouter-assigned label (display only)
  connected_at   timestamptz not null default now(),
  last_used_at   timestamptz
);

alter table user_api_keys enable row level security;

-- Defense-in-depth ONLY. The backend uses the service-role client (bypasses RLS),
-- so these policies guard against any future anon-key path / direct PostgREST access.
create policy "Users can view own key row"   on user_api_keys
  for select using (auth.uid() = user_id);
create policy "Users can insert own key row" on user_api_keys
  for insert with check (auth.uid() = user_id);
create policy "Users can update own key row" on user_api_keys
  for update using (auth.uid() = user_id);
create policy "Users can delete own key row" on user_api_keys
  for delete using (auth.uid() = user_id);
```

**Design notes (HIGH confidence):**
- **`user_id` as PK** enforces "exactly one key per user" without a separate unique index.
- **`encrypted_key` holds ciphertext only.** Plaintext never touches Postgres. Even a
  full DB dump leaks nothing usable without the env-held encryption secret.
- **RLS is belt-and-suspenders.** The backend always reads/writes this table through the
  service-role client in `database.py` (which bypasses RLS). The frontend must **never**
  read this table directly — plaintext is never returned to the client, and even the
  ciphertext should only be exposed through a backend "key status" endpoint that returns
  booleans/labels, not the encrypted blob. RLS still matters because (a) the project rule
  is that *all* tables have RLS, and (b) it closes the door if the anon client is ever
  pointed at this table.
- **`on delete cascade`** ties key lifecycle to the auth user (matches the anon-user
  7-day purge sweep in `demo_service.py`).

### 2. `user_preferences` (NEW — default model + theme, RLS)

```sql
create table user_preferences (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  default_model  text,                   -- OpenRouter model slug, nullable
  theme          text not null default 'system' check (theme in ('light','dark','system')),
  updated_at     timestamptz not null default now()
);

alter table user_preferences enable row level security;
create policy "Users manage own prefs (select)" on user_preferences
  for select using (auth.uid() = user_id);
create policy "Users manage own prefs (insert)" on user_preferences
  for insert with check (auth.uid() = user_id);
create policy "Users manage own prefs (update)" on user_preferences
  for update using (auth.uid() = user_id);
```

**Note:** `theme` *can* be read directly by the frontend anon client (RLS allows it) for
instant first-paint without a backend round-trip, OR served via `preferences.py`.
Recommendation: serve via backend for consistency with `default_model`, and additionally
mirror theme to `localStorage` so first paint is flash-free before the session resolves.
Theme is non-sensitive — either path is acceptable.

### 3. `model_cache` (NEW — shared catalog, read-only to users)

```sql
create table model_cache (
  id               text primary key,      -- OpenRouter model slug, e.g. "anthropic/claude-3.5-sonnet"
  name             text not null,
  is_free          boolean not null default false,
  prompt_price     numeric,               -- $/token from pricing.prompt
  completion_price numeric,               -- $/token from pricing.completion
  context_length   integer,
  popularity_rank  integer,               -- derived from sort=most-popular ordering
  raw              jsonb,                 -- full model object for forward-compat
  refreshed_at     timestamptz not null default now()
);

alter table model_cache enable row level security;
-- Catalog is non-sensitive and shared. Readable by all authenticated users; only the
-- service-role writer (refresh job) mutates it.
create policy "Anyone authenticated can read model cache" on model_cache
  for select using (auth.role() = 'authenticated');
-- No insert/update/delete policy for anon → writes happen only via service role.
```

**Mirrors the existing mixed-visibility precedent** (`20240301000020_update_rls_policies.sql`)
where the default KB is public-readable. The model catalog is the same shape: one shared
dataset everyone reads, only the server writes.

### 4. `threads.model` column (MODIFIED)

```sql
alter table threads add column model text;   -- nullable; null ⇒ use user default ⇒ use owner default
```

- Nullable so existing rows keep working untouched.
- Resolution order at chat time: `thread.model` → `user_preferences.default_model` →
  `settings.llm_model` (owner default). This three-tier fallback is the heart of
  per-thread model selection.
- `ThreadCreate` / `ThreadResponse` in `models/schemas.py` gain an optional
  `model: str | None`; `create_thread` accepts it and a new `PATCH /api/threads/{id}`
  updates it.

---

## Key Encryption & Decryption (where it happens)

**All crypto lives in the backend service-role path. Plaintext keys never reach the
frontend or the database.** (HIGH confidence — grounded in the existing `database.py`
service-role pattern and the `cryptography` dependency already in `requirements.txt`.)

### `crypto_service.py` (NEW)

The `cryptography` library is **already a dependency** (`cryptography 46.0.5`, currently
used for ES256 JWT verification in `auth.py`). Use **Fernet** (symmetric AES-128-CBC +
HMAC) — the simplest correct option; envelope encryption is overkill at this scale.

```python
# backend/services/crypto_service.py
from cryptography.fernet import Fernet
from config import get_settings

def _fernet() -> Fernet:
    # KEY_ENCRYPTION_SECRET is a urlsafe-base64 32-byte Fernet key, stored as a
    # Fly.io / .env secret. NEVER in the image, frontend bundle, or git.
    return Fernet(get_settings().key_encryption_secret.encode())

def encrypt_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()

def decrypt_key(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
```

### Per-request client construction (MODIFIED `llm_service.py`)

Today `get_llm_client()` reads `settings.resolved_llm_api_key` (the owner key) globally
and `stream_chat_completion()` reads `settings.llm_model`. The change is to **make the key
+ model per-request inputs**, resolved in `chat.py` and threaded down:

```python
# llm_service.py — MODIFIED
def get_llm_client(api_key: str | None = None) -> OpenAI:
    settings = get_settings()
    client = OpenAI(
        api_key=api_key or settings.resolved_llm_api_key,   # per-user key OR owner fallback
        base_url=settings.llm_base_url,
    )
    if wrap_openai and settings.langsmith_api_key:
        client = wrap_openai(client)
    return client

def stream_chat_completion(messages, *, api_key=None, model=None, tools=None, ...):
    settings = get_settings()
    client = get_llm_client(api_key)
    ...
    kwargs = {"model": model or settings.llm_model, "messages": full_messages, "stream": True}
```

**Critical security rule:** decryption happens **inside the request handler, in memory,
for the duration of one chat turn.** The decrypted plaintext is passed to the OpenAI client
constructor and never logged, never persisted, never returned in any response or SSE event.
(LangSmith tracing via `wrap_openai` captures prompts/responses but should not serialize the
client's `api_key` — verify against the prod LangSmith project's PII scrub; flagged in
PITFALLS.)

---

## OAuth Callback Flow (PKCE)

**Verified against OpenRouter official docs (HIGH confidence).** OpenRouter uses a PKCE
flow with **no client secret** — ideal for a SPA-initiated, backend-completed flow.

### Endpoints (OpenRouter, confirmed)

- **Authorize (redirect the browser here):**
  `https://openrouter.ai/auth?callback_url=<URL>&code_challenge=<CHALLENGE>&code_challenge_method=S256`
- **Exchange (POST, backend):** `https://openrouter.ai/api/v1/auth/keys`
  with JSON body `{ "code": "...", "code_verifier": "...", "code_challenge_method": "S256" }`
  → returns `{ "key": "sk-or-v1-..." }` (the user-controlled API key).
- S256 is the recommended `code_challenge_method` (challenge = base64 of SHA-256 of the
  verifier). There is **no pre-registration** of callback URLs (localhost any-port works);
  the callback URL is passed at authorize time.

> Note: docs show no explicit `state` param in OpenRouter's examples. **Add and verify
> `state` yourself** for CSRF protection — carry it through `callback_url` as a query param
> and validate it on return. Do not rely on OpenRouter to echo a dedicated `state`.

### Recommended split: frontend route + backend exchange

```
1. User clicks "Connect OpenRouter" (Settings or model-picker gate)
2. FRONTEND generates code_verifier (random) + code_challenge (S256) + state (random)
   - store verifier + state in sessionStorage (survives the redirect round-trip)
3. FRONTEND redirects browser → https://openrouter.ai/auth?callback_url=<FE_CALLBACK>
                                  &code_challenge=...&code_challenge_method=S256&state=...
4. OpenRouter authenticates user, redirects → <FE_CALLBACK>?code=...&state=...
5. FRONTEND OAuthCallback route (/settings/openrouter/callback):
   - validate returned state === stored state (CSRF check)
   - POST {code, code_verifier} to BACKEND /api/keys/openrouter/exchange
     (with the Supabase bearer token so the backend knows which user)
6. BACKEND keys.py:
   - openrouter_service.exchange_code(code, code_verifier)
     → POSTs to https://openrouter.ai/api/v1/auth/keys, gets {key}
   - encrypt_key(key) → upsert into user_api_keys for user_id
   - returns {connected: true, label: ...} (NEVER the key)
7. FRONTEND shows "Connected", re-fetches key status, clears the gate
```

**Why this split:**
- The `code_verifier` is generated and held **client-side** (correct PKCE — the verifier
  must never leave the party that created the challenge until exchange). Storing it in
  `sessionStorage` and posting it to *our own* backend for the exchange keeps the OpenRouter
  key off the wire to the client entirely. The backend does the exchange so the returned
  `sk-or-v1-...` key lands server-side and is encrypted before storage.
- **`callback_url` must be a frontend route**, because OpenRouter redirects a *browser*. A
  backend callback would work, but then the backend needs the verifier — pushing the verifier
  server-side means generating it server-side and round-tripping it, which is messier than
  letting the SPA own the PKCE pair. Frontend-callback + backend-exchange is the clean
  division.

### Redirect URL config across dev/prod (ties into existing CORS + auth-redirect)

This is the **highest-friction integration point** and parallels the v1.1 CORS hardening
(`config.py:cors_origins_list`, env-driven; PROJECT.md v1.1 Phases 1 & 6).

| Env | `callback_url` value | Source |
|-----|----------------------|--------|
| Dev | `http://localhost:5173/settings/openrouter/callback` | derived from FE origin |
| Prod | `https://boardgame-rag-prod.pages.dev/settings/openrouter/callback` | derived from FE origin |

Recommendations:
- **Frontend derives `callback_url` from `window.location.origin`** + fixed path. No new FE
  env var needed — it self-locates, robust across the Cloudflare Pages prod domain and
  localhost.
- The **backend exchange endpoint is same-origin to the API** (`/api/keys/...`), so it is
  already covered by the existing env-driven CORS allowlist (`cors_allowed_origins`). No CORS
  change is required for the exchange POST as long as the FE origin is already in the allowlist
  (it is, post-v1.1).
- **No Supabase auth-redirect change** is needed — this OAuth flow is OpenRouter's, fully
  independent of Supabase Auth's redirect URLs. The Supabase session is only used to
  authenticate the exchange POST to our backend. (Do not confuse this with Supabase's own
  redirect allowlist — separate systems.)
- Optional backend env `OAUTH_CALLBACK_BASE_URL` only if you ever want the backend to construct
  the URL; not required with the FE-derives approach.

---

## How the Agentic Chat Loop Selects Key + Model (MODIFIED `chat.py`)

The resolution logic slots into `send_message` **before** the `event_generator` builds the
budget and calls `stream_chat_completion`. The existing loop structure (chat.py lines
~545–848) is otherwise unchanged.

```python
# chat.py send_message — NEW resolution block (pseudocode)
settings = get_settings()
db = get_supabase()

# 1. Resolve MODEL: thread → user default → owner default
selected_model = (
    body.model                                   # optional per-message override (future)
    or thread.data.get("model")                  # per-thread persisted model
    or _get_user_default_model(db, user_id)      # user_preferences.default_model
    or settings.llm_model                         # owner default
)

# 2. Resolve KEY: user's encrypted key → (gated) owner-key demo fallback
key_row = db.table("user_api_keys").select("encrypted_key").eq("user_id", user_id) \
            .maybe_single().execute()
if key_row.data:
    api_key = decrypt_key(key_row.data["encrypted_key"])     # in-memory, this turn only
elif settings.demo_fallback_enabled:                         # GLOBAL FLAG, default OFF
    api_key = settings.resolved_llm_api_key                  # owner key — demo only
    selected_model = settings.demo_fallback_model or selected_model  # optionally pin a cheap model
else:
    # No key + fallback off → structured SSE error → frontend "connect key" prompt
    yield {"event": "error", "data": json.dumps({
        "error": "no_api_key",
        "detail": "Connect your OpenRouter account to chat.",
    })}
    return
```

Then thread the resolved values through the existing call sites:

```python
# dynamic context-length lookup currently uses settings.resolved_llm_api_key →
# change to the resolved api_key + selected_model
dynamic_length = fetch_model_context_length(selected_model, api_key)
...
for event in stream_chat_completion(
    current_messages, tools=tools, tool_guide=..., source_hint=..., scope_hint=...,
    api_key=api_key, model=selected_model,            # NEW args
):
```

**Demo-fallback flag check (key behavior):**
- `settings.demo_fallback_enabled: bool = False` — new in `config.py`, env-driven, **off by
  default** (matches PROJECT.md "global flag, off by default"). When off, keyless users get a
  clean "connect your account" prompt instead of silently burning the owner's credits.
- When on (e.g. for the public portfolio demo), keyless users transparently use the owner key.
  Pair this with the existing per-user rate limit (`chat_rate_limit`, slowapi) and the existing
  OpenRouter Guardrail cost cap to bound owner spend (PROJECT.md SEC-06).
- The `no_api_key` SSE error reuses the **existing** in-band error path that `useChat.ts`
  already handles (`parsed.error !== undefined` → throws → error bubble + toast). The frontend
  just special-cases `error === "no_api_key"` to render a "Connect OpenRouter" CTA instead of
  the generic retry bubble.

**The agent's tool loop itself is untouched** — tool selection, budget, SSE events all work
identically. BYOK only changes *which credentials + model* the per-request client uses. This
is a deliberately narrow, low-blast-radius integration.

---

## Model-List Cache: Table + Refresh Job Placement

**Recommendation: `model_cache` table + lazy refresh-if-stale + deploy-time seed for v1.2,
with pg_cron as a documented-but-optional upgrade.** (MEDIUM-HIGH confidence — table design
is certain; scheduler choice is a deployment-fit tradeoff.)

### Refresh options compared

| Option | Pros | Cons | Verdict for v1.2 |
|--------|------|------|------------------|
| **pg_cron** (Supabase) | True scheduled refresh, no app uptime needed | Needs HTTP-out of Postgres (`pg_net`) to OpenRouter or a backend ping; more moving parts | Document as optional upgrade |
| **In-process scheduler** (APScheduler / asyncio) | Lives in FastAPI, easy to write | **Fly.io free tier suspends the backend** (PROJECT.md "Fly suspend, no keep-warm") → scheduler dies; unreliable | **Reject** — incompatible with suspend |
| **Lazy refresh-if-stale** | Zero infra; refreshes on first request after TTL; survives suspend | First user after staleness eats a ~1s OpenRouter fetch | **Recommended primary** |
| **Manual / deploy-time seed** | Dead simple; deterministic | Requires redeploy or admin trigger to pick up new models | **Recommended baseline** |

**Why not the in-process scheduler:** the deployment explicitly accepts Fly.io suspend with no
keep-warm (v1.1 Phase 4 decision). A background scheduler thread is killed on suspend and never
reliably fires. This is the single most important infra-fit constraint for this feature.

**Recommended approach:**
1. `model_cache_service.refresh_models()` — fetches `GET https://openrouter.ai/api/v1/models`
   (with `sort=most-popular` to populate `popularity_rank`; auth with the owner key, since the
   catalog is global), maps fields, upserts into `model_cache`, stamps `refreshed_at`.
   - Free detection: `is_free = (pricing.prompt == "0" and pricing.completion == "0")` and/or
     `id` ends with `:free` (belt-and-suspenders — both signals confirmed in docs).
2. `model_cache_service.get_models()` — reads `model_cache`; if `max(refreshed_at)` is older
   than TTL (e.g. 24h), kicks `refresh_models()` first (lazy refresh), then returns rows.
3. Seed the cache at deploy time (a one-off `refresh_models()` call, same pattern as the
   default-KB seed in v1.1 Phase 3) so the table is never empty on first request.
4. **Optional upgrade path:** a Supabase `pg_cron` job calling a backend `POST /api/models/refresh`
   (shared-secret protected) on a daily schedule. Document it; don't build it for v1.2 unless
   staleness becomes a real complaint.

### How the frontend reads it

- Frontend calls **`GET /api/models`** (NEW `models.py` router) → backend returns cached rows
  via `model_cache_service.get_models()`. The frontend does **not** call OpenRouter directly
  (keeps the owner key server-side and centralizes the lazy-refresh trigger).
- `useModels()` (NEW hook) fetches once, caches in component state; `ModelPicker` renders
  free/paid tags + popularity ordering from the returned fields.
- Alternative (rejected): exposing `model_cache` to the anon client via RLS for a direct
  Supabase read. Workable since it's non-sensitive, but routing through the backend keeps the
  lazy-refresh logic in one place and matches the project's "frontend talks to backend, Supabase
  anon is auth+realtime only" convention.

---

## New API Endpoints & Frontend Routes/Components

### Backend endpoints

| Method + Path | Router | Purpose | NEW/MOD |
|---------------|--------|---------|---------|
| `GET /api/keys/status` | `keys.py` | `{connected, label, connected_at}` — never the key | NEW |
| `POST /api/keys/openrouter/exchange` | `keys.py` | Body `{code, code_verifier}` → exchange + encrypt + upsert | NEW |
| `DELETE /api/keys` | `keys.py` | Disconnect (delete the user's key row) | NEW |
| `GET /api/keys/balance` | `keys.py` | Proxy `GET openrouter.ai/api/v1/key` (+ `/credits`) with decrypted key | NEW |
| `GET /api/models` | `models.py` | Cached model catalog for the picker | NEW |
| `POST /api/models/refresh` | `models.py` | Force refresh (shared-secret; optional pg_cron target) | NEW |
| `GET /api/preferences` | `preferences.py` | `{default_model, theme}` | NEW |
| `PUT /api/preferences` | `preferences.py` | Update default model / theme | NEW |
| `PATCH /api/threads/{id}` | `threads.py` | Accept `model` to persist per-thread selection | MODIFIED |
| `POST /api/threads/{id}/messages` | `chat.py` | Resolve key+model per the block above | MODIFIED |

All NEW endpoints use the existing `Depends(get_user_id)` auth dependency and the service-role
`get_supabase()` client. Register the three new routers in `main.py` via `app.include_router(...)`
exactly like `demo.router`.

### Frontend routes/components

| Item | Type | Notes |
|------|------|-------|
| `/settings` route + `SettingsPage.tsx` | NEW page | Key status/connect/disconnect, default model, theme, balance |
| `/settings/openrouter/callback` route + `OAuthCallback.tsx` | NEW page | Validates state, posts code+verifier to exchange endpoint |
| `ModelPicker.tsx` | NEW component | Free/paid tags, popularity order; gates on key; in chat header + thread create |
| `ThemeToggle.tsx` + theme provider | NEW | Tailwind `dark:` class on `<html>`; persisted to prefs + localStorage |
| `useUserKey.ts` | NEW hook | Key status, connect (PKCE init), disconnect |
| `useModels.ts` | NEW hook | Fetch `/api/models`, expose list + free/paid filter |
| `usePreferences.ts` | NEW hook | default model + theme read/write |
| `lib/pkce.ts` | NEW util | `generateVerifier()`, `challengeFromVerifier()` via Web Crypto SubtleCrypto |
| `App.tsx` | MODIFIED | Add `/settings` + callback routes (callback can be public or protected) |
| `ChatPage.tsx` / `ThreadSidebar.tsx` | MODIFIED | Surface model picker; key-gate the send action |
| `IconSidebar.tsx` | MODIFIED | Add Settings nav entry |
| `useChat.ts` | MODIFIED (light) | Special-case `error === "no_api_key"` → "Connect" CTA |

---

## Data Flow

### OAuth connect flow

```
[Click "Connect OpenRouter"]
   ↓ (pkce.ts: verifier+challenge+state → sessionStorage)
[Browser redirect → openrouter.ai/auth?callback_url=<FE>&code_challenge=...&state=...]
   ↓ (user authenticates at OpenRouter)
[Redirect → FE /settings/openrouter/callback?code=...&state=...]
   ↓ (validate state)
[POST /api/keys/openrouter/exchange {code, verifier}]  ──→ openrouter.ai/api/v1/auth/keys
   ↓                                                          ↓ {key}
[encrypt_key → upsert user_api_keys]  ←───────────────────────┘
   ↓
[{connected:true} → FE refetches status → gate clears]
```

### Chat turn with BYOK (MODIFIED path)

```
[useChat → POST /api/threads/{id}/messages {content, model?}]
   ↓
[chat.py: resolve model (thread→pref→owner), resolve key (user→demo-fallback gate)]
   ↓ decrypt_key (in memory)
[stream_chat_completion(messages, api_key=<user key>, model=<resolved>)]
   ↓ (existing tool loop unchanged)
[SSE content_delta / tool_event / done]   — OR — [SSE error: no_api_key → "Connect" CTA]
```

---

## Anti-Patterns (BYOK-specific)

### Anti-Pattern 1: Returning the decrypted (or even encrypted) key to the frontend
**What people do:** add the key to a `/api/keys/status` response "so the UI can show it."
**Why it's wrong:** any client-exposed key is a leak; even the ciphertext is needless exposure
and tempts a frontend decrypt path.
**Do this instead:** return only `{connected, label, connected_at}`. The plaintext exists only
transiently in backend memory during a chat turn.

### Anti-Pattern 2: In-process scheduler for model refresh on a suspendable host
**What people do:** APScheduler/asyncio task in FastAPI to refresh models hourly.
**Why it's wrong:** Fly.io free tier suspends the app (existing decision) — the scheduler dies
and never fires reliably.
**Do this instead:** lazy refresh-if-stale + deploy-time seed; pg_cron only if needed.

### Anti-Pattern 3: Silent owner-key fallback by default
**What people do:** when a user has no key, transparently use the owner key.
**Why it's wrong:** the owner pays for everyone; defeats the entire BYOK purpose; unbounded cost.
**Do this instead:** demo-fallback behind a global flag **default off**; keyless users get a
"connect your account" prompt. Flag-on (demo) must be bounded by rate limit + Guardrail cap.

### Anti-Pattern 4: Skipping PKCE `state` because OpenRouter docs omit it
**What people do:** rely on OpenRouter to handle CSRF.
**Why it's wrong:** without `state` you can't bind the callback to the initiating session; CSRF
risk.
**Do this instead:** generate `state`, carry it via `callback_url`, validate on return.

### Anti-Pattern 5: Logging the decrypted key (incl. via tracing)
**What people do:** debug-log the resolved `api_key`, or trust tracing not to capture it.
**Why it's wrong:** LangSmith/Sentry could persist it.
**Do this instead:** never log it; confirm `wrap_openai` does not serialize the client's
`api_key`; keep the v1.1 Sentry PII scrub covering this path.

---

## Integration Points

### External services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenRouter `/auth` | Browser redirect (PKCE, no client secret) | `callback_url` = FE route; S256 challenge |
| OpenRouter `/api/v1/auth/keys` | Backend POST `{code, code_verifier}` → `{key}` | Exchange server-side; result encrypted |
| OpenRouter `/api/v1/models` | Backend GET (owner key), cached to `model_cache` | `sort=most-popular`; free via zero-pricing / `:free` |
| OpenRouter `/api/v1/key` (+ `/credits`) | Backend GET with decrypted user key | Balance / usage for the Settings page |
| OpenRouter chat completions | Per-request OpenAI client with user (or fallback) key | Only credentials+model change vs today |

### Internal boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `chat.py` ↔ `crypto_service` | Direct call, in-request | Decrypt once per turn, never persist |
| `chat.py` ↔ `llm_service` | New `api_key`/`model` kwargs | Smallest possible surface change to the loop |
| `keys.py` ↔ `openrouter_service` | Direct call | Exchange + balance HTTP via `httpx` (already used) |
| `models.py` ↔ `model_cache_service` | Direct call | Lazy refresh-if-stale; reads `model_cache` table |
| Frontend ↔ `model_cache` | **Via backend only** | Not a direct Supabase read (centralizes refresh) |
| Frontend ↔ `user_api_keys` | **Backend only, never direct** | Anon client must never touch this table |

---

## Suggested Build Order (dependency-respecting)

This ordering lets the roadmapper slice phases that are each independently testable.

1. **Crypto + key storage foundation** (no UI)
   - `crypto_service.py` (Fernet), `KEY_ENCRYPTION_SECRET` in config + Fly/`.env`/`.env.prod`.
   - `user_api_keys` migration (table + RLS).
   - Test: encrypt/decrypt round-trip; migration applies to dev + prod.
   - *Why first:* everything BYOK depends on safely storing a key.

2. **OAuth exchange backend** (`openrouter_service.exchange_code` + `keys.py`)
   - Exchange endpoint, `GET /api/keys/status`, `DELETE /api/keys`.
   - Test: exchange against a real OpenRouter round-trip; confirm key never echoed.
   - *Depends on:* step 1.

3. **Frontend OAuth connect flow** (`lib/pkce.ts`, `OAuthCallback.tsx`, `useUserKey`, route)
   - PKCE init + redirect, callback handling, state validation, calls step-2 exchange.
   - Test: full connect round-trip dev + prod (callback_url derivation; CORS already covers it).
   - *Depends on:* step 2.

4. **Model cache** (`model_cache` migration + `model_cache_service` + `models.py` + deploy seed)
   - Refresh-if-stale, `GET /api/models`, seed at deploy.
   - Test: catalog populated; free/paid + popularity fields correct.
   - *Independent of 1–3* — can run in parallel; only the picker UI (step 7) joins them.

5. **Preferences + threads.model** (`user_preferences` migration, `preferences.py`,
   `threads.model` column, schema updates, `PATCH /api/threads/{id}`)
   - Default model + theme storage; per-thread model column.
   - *Soft dependency:* consumed by the model picker (7) and chat resolution (6).

6. **Chat loop integration** (MODIFY `chat.py` + `llm_service.py`)
   - Key + model resolution block, demo-fallback flag, `no_api_key` SSE error,
     thread→pref→owner model resolution, per-request client.
   - `demo_fallback_enabled` flag in config (default off).
   - Test: keyed user chats with selected model; keyless user gets connect prompt; flag-on uses
     owner key.
   - *Depends on:* steps 1, 4, 5.

7. **Frontend options UI** (`SettingsPage`, `ModelPicker`, `ThemeToggle`, `useModels`,
   `usePreferences`, `useChat` no_api_key handling, balance display)
   - Wire it all: connect/disconnect, pick model (gates on key), theme, balance.
   - *Depends on:* steps 3, 4, 5, 6.

Phases 1→2→3 are the BYOK critical path; 4 can parallelize; 5 enables per-thread model; 6 is the
chat integration; 7 is the UI capstone. **Theme toggle** (a subset of 5/7) is the lowest-risk,
most independent slice — it can ship anytime after `user_preferences` exists, decoupled from BYOK.

---

## Sources

- OpenRouter OAuth PKCE — official docs (authorize URL, exchange endpoint, S256, response shape): https://openrouter.ai/docs/guides/overview/auth/oauth — HIGH
- OpenRouter exchange-code reference: https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key — HIGH
- OpenRouter list-models schema (fields, pricing, `sort=most-popular`, free detection, auth required): https://openrouter.ai/docs/api/api-reference/models/get-models — HIGH
- OpenRouter credits / key-balance endpoints: https://openrouter.ai/docs/api/api-reference/credits/get-credits — MEDIUM (exact response field names not fully confirmed)
- Python `cryptography` Fernet — already in `requirements.txt` (cryptography 46.0.5) — HIGH (existing dependency)
- Existing codebase (read directly): `backend/routers/chat.py`, `backend/services/llm_service.py`, `backend/config.py`, `backend/database.py`, `backend/auth.py`, `backend/main.py`, `backend/routers/threads.py`, `backend/routers/demo.py`, `backend/models/schemas.py`, `supabase/migrations/*`, `frontend/src/App.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/supabase.ts`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/hooks/useChat.ts`, `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md` — HIGH

---
*Architecture research for: v1.2 User Options & BYOK (BYOK integration into shipped agentic RAG)*
*Researched: 2026-06-18*
