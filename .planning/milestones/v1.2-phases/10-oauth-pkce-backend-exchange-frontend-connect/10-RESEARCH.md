# Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect - Research

**Researched:** 2026-06-19
**Domain:** OAuth 2.0 PKCE (SPA-initiated, backend-completed) + encrypted BYOK key custody integrated into a shipped React/FastAPI/Supabase RAG app
**Confidence:** HIGH (OpenRouter OAuth verified against official docs this session; all codebase claims read directly from the live repo, not from possibly-stale maps)

## Summary

Phase 10 wires the **connect / status / disconnect** half of BYOK on top of the Phase 9 storage+crypto foundation. The flow is a classic PKCE split: the **SPA owns the PKCE pair** (`code_verifier` + S256 `code_challenge`) and an **own CSRF `state`**, persists both to `sessionStorage`, and redirects the browser to OpenRouter's `/auth`. On return, a frontend callback route validates `state`, then `POST`s `{code, code_verifier}` to **our backend** (`POST /api/keys/openrouter/exchange`) under the Supabase bearer. The backend calls OpenRouter `/api/v1/auth/keys` via `httpx`, gets `{key}`, encrypts it with the Phase 9 `crypto_service`, captures a non-secret masked tail, and upserts into `user_api_keys`. The key never returns to the browser — `GET /api/keys/status` returns booleans + masked label + connected-since only; `DELETE /api/keys` disconnects.

The critical security invariants are all verified-feasible against the live codebase: the Phase 9 `user_api_keys` table already exists with `key_label` (intended "Phase 10" display column) and `created_at`; the SQL-tool lockdown (REVOKE + FROM-allowlist in migrations 025/026/027 + the Python mirror) is in place and **must not be undone**; `crypto_service.encrypt_key()` is stable; `httpx` is already a direct backend dependency; the Cloudflare Pages `_redirects` catch-all (`/* /index.html 200`) already serves any callback path; and the frontend Sentry scrubber exists and only needs a new `sk-or-v1-…` regex rule alongside the existing JWT rule. The official OpenRouter PKCE example itself uses Web Crypto `crypto.subtle.digest('SHA-256', …)` + `base64url`, confirming the no-dependency `lib/pkce.ts` approach.

**Primary recommendation:** Add a single migration (next number `20240301000028`) that adds a non-secret `key_label` masked tail (column already present — reuse it) and a `connected_at TIMESTAMPTZ` column (or reuse `created_at` via upsert-reset). Build `openrouter_service.exchange_code()` (httpx POST), a `keys.py` router mirroring `demo.py`/`threads.py` (`Depends(get_user_id)` + service-role `get_supabase()`), `lib/pkce.ts` (Web Crypto), two pages (`SettingsPage`, `OAuthCallbackPage`), a shared `useKeyStatus` hook, and extend `lib/sentry.ts`. Verify the prod round-trip on the Cloudflare Pages origin as the closing gate.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Connect surface (KEY-01, KEY-03)**
- **D-01:** Build a **minimal `/settings` route stub** this phase — connect / status / disconnect ONLY. Phase 14 grows it into the full Settings/account page. Real testable route, no throwaway UI, no scope creep into P14.
- **D-02:** Entry point = a **Settings/gear entry in the existing `IconSidebar`** → opens `/settings`, **PLUS a persistent "key connected / not connected" dot in the chat header** so key state is always visible at a glance.

**Status indicator (KEY-03 — "masked label only")**
- **D-03:** Connected state on `/settings` shows a **masked key tail (last 4 chars, e.g. `sk-or-v1-…wXyZ`) + a connected-since date**. Backend captures the masked hint at exchange time (plaintext is in memory then), stores it as a small non-secret display label, never stores/returns more of the key.
- ⚠ **Schema check for researcher/planner:** Phase 9's `user_api_keys` stores ciphertext + `key_version` + timestamps. Confirm whether a **masked-label column** and a **`connected_at`/`connected_since` column** exist; add them in a follow-on migration if absent. The masked label is non-secret (last-4 only) and must NOT be reachable by the Text-to-SQL tool (table already REVOKE'd + excluded from the FROM-allowlist in Phase 9 — no change needed, just don't undo it).

**Callback + return UX (KEY-01)**
- **D-05:** Happy path — callback route (`/settings/openrouter/callback`) shows a **"Connecting your OpenRouter account…" spinner** during `state`-validate → `POST exchange`, then **auto-redirects to `/settings` (now Connected) + a success toast**. No extra click.
- **D-06:** Failure path (forged/mismatched CSRF `state`, exchange `403`, or network error) — **inline error on the callback page** + a Retry / Back-to-settings action. The surfaced failure reason MUST be scrubbed of `sk-or-…` before any log/Sentry/UI render. Recoverable, stays on the route.
- **D-07:** Hard-refresh on the callback page is the **SUCCESS path, not a failure** — `code_verifier` + `state` live in `sessionStorage` (survive same-tab refresh), so a refreshed exchange still works (ROADMAP success criterion #2).

**Disconnect / reconnect (KEY-04)**
- **D-08:** Disconnect uses a **confirm dialog** → `DELETE /api/keys` → state flips to not-connected + Connect button.
- **D-09:** **Reconnect = re-run the Connect flow.** The exchange **upserts** (PK = `user_id`), so a new connect overwrites the prior row. One key per user (Phase 9 anti-feature lock).

**Locked by research / success criteria (do NOT re-litigate)**
- **Backend-side exchange.** SPA posts `{code, code_verifier}` to OUR backend under the Supabase bearer; backend calls OpenRouter `/api/v1/auth/keys`. Key lands server-side, encrypted, **never returned to the client**.
- **PKCE S256**, `code_challenge_method=S256` consistent across authorize + exchange.
- **Own CSRF `state`** generated by the SPA (OpenRouter omits it), carried via `callback_url`, validated on return.
- **`callback_url` derives from `window.location.origin`** + fixed path (`/settings/openrouter/callback`). Callback path served by the **SPA fallback**.
- **Exchange via `httpx`** (already used in the backend).
- **No Supabase auth-redirect / CORS change** needed — exchange POST is same-origin to the API, already in the v1.1 CORS allowlist.

### Claude's Discretion
- Exact endpoint/handler signatures, `openrouter_service.exchange_code` shape, masked-label/`connected_at` column names + migration filename (next free number), `lib/pkce.ts` helper API, route guard (callback public vs protected), spinner/toast component choice, confirm-dialog component — planner/executor decide following existing conventions.

### Deferred Ideas (OUT OF SCOPE)
- **Always-visible "Demo mode vs Your key (balance $X) vs No key" state machine** + mid-chat 401/402/403 recovery (Pitfall 13 full scope) — **Phase 14**. P10 only ships the connected/not dot.
- **`GET /api/keys/balance`** (OpenRouter balance proxy) — **Phase 14** (COST-02).
- **Key-gated model selection launching OAuth inline + resume-on-return** — **Phase 15** (KEY-05).
- **Backend `sk-or` log/SSE scrub + LangSmith `wrap_openai` gate** — **Phase 11** (backend half of SEC-01).
- Per-request key+model chat resolution / chat-loop seam / fail-closed `no_api_key` — **Phase 11**.
- Model catalog / picker — **Phase 12 / 15**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KEY-01 | User can connect their OpenRouter account via OAuth (PKCE) without manually pasting a key | PKCE flow verified against OpenRouter docs (§Code Examples); FE owns `code_verifier`+S256+`state` in `sessionStorage` (`lib/pkce.ts`, Web Crypto); BE `openrouter_service.exchange_code` via `httpx` POST to `/api/v1/auth/keys`; callback route + SPA fallback (`_redirects` confirmed present). |
| KEY-03 | User can see their key connection status (connected vs not connected, masked label only) | `GET /api/keys/status` returns `{connected, masked_label?, connected_at?}` — never the key. Masked tail captured at exchange time → stored in non-secret `key_label` column (already on the table). `/settings` stub + chat-header dot consume it (`useKeyStatus`). |
| KEY-04 | User can disconnect and reconnect their OpenRouter key | `DELETE /api/keys` deletes the row (service-role); reconnect re-runs Connect, exchange **upserts** on PK `user_id`. ConfirmDialog gates disconnect (existing component). |

**SEC-01 (frontend half, this phase):** Extend `frontend/src/lib/sentry.ts` scrubber with `/sk-or-v1-[A-Za-z0-9_-]+/g` across `beforeSend` (message, exception values, `request.url`) and `beforeBreadcrumb` (console/fetch breadcrumb messages + data). Backend `sk-or` scrub + LangSmith gate is Phase 11.
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| PKCE pair generation (`code_verifier` + S256 `code_challenge`) | Browser / Client (Web Crypto) | — | Verifier MUST be created and held by the party that builds the challenge until exchange; never server-generated/round-tripped (correct PKCE). |
| CSRF `state` generation + validation | Browser / Client (`sessionStorage`) | — | OpenRouter omits `state`; the SPA owns and verifies it on return. Bound to the same browser/tab. |
| Redirect to OpenRouter `/auth` | Browser / Client | — | OpenRouter redirects a *browser*; `callback_url` must be a FE route derived from `window.location.origin`. |
| Code→key exchange (`/api/v1/auth/keys`) | API / Backend (`httpx`) | — | The returned `sk-or-v1-…` key MUST land server-side only, off the wire to the client. Backend runs under the user's JWT so the key binds to `auth.uid()`. |
| Key encryption | API / Backend (`crypto_service`) | — | Phase 9 Fernet/MultiFernet; plaintext exists only transiently in backend memory. |
| Masked-label capture (last-4) | API / Backend | — | Plaintext is in memory only at exchange time; the non-secret tail is derived there and persisted. |
| Key persistence (upsert / delete) | Database / Storage (`user_api_keys`, service-role) | — | Service-role client bypasses RLS; frontend NEVER touches this table directly. |
| Connection status (`{connected, masked_label, connected_at}`) | API / Backend → Browser | — | Backend reads the row, returns booleans+label only. No ciphertext, no plaintext. |
| `/settings` stub UI + callback states + header dot | Browser / Client | — | Reuses existing dark-only Tailwind tokens; no new design language (per UI-SPEC). |
| `sk-or-` scrub (frontend) | Browser / Client (`lib/sentry.ts`) | — | Frontend error-vendor leak surface; `beforeSend`/`beforeBreadcrumb` regex. |
| SPA fallback for callback path | CDN / Static (Cloudflare Pages `_redirects`) | — | Already configured (`/* /index.html 200`); no change required. |

## Standard Stack

This phase introduces **no new dependencies** (frontend or backend). Everything is reuse.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | unpinned (transitive, used directly) `[VERIFIED: backend/services/budget_service.py, embedding_service.py, web_search_service.py, rerank_service.py all import + call httpx]` | Backend POST to OpenRouter `/api/v1/auth/keys` | Already the project's outbound HTTP client; `budget_service.fetch_model_context_length` already calls `openrouter.ai/api/v1/models` with `httpx.get` — mirror that exact pattern. |
| `cryptography` (Fernet/MultiFernet via `crypto_service`) | 46.0.5 `[VERIFIED: CLAUDE.md tech stack + backend/services/crypto_service.py]` | Encrypt the exchanged key before upsert | Phase 9 foundation; `encrypt_key()` is the stable, minimal API. |
| Web Crypto `SubtleCrypto` (browser built-in) | n/a (platform) `[CITED: openrouter.ai/docs/guides/overview/auth/oauth — official example uses crypto.subtle.digest('SHA-256', …)]` | `lib/pkce.ts`: `code_verifier` (random), S256 `code_challenge`, CSRF `state` | OpenRouter's own docs example uses Web Crypto; no PKCE library needed. `crypto.getRandomValues` + `crypto.subtle.digest`. |
| `react-router-dom` | ^7.13.1 `[VERIFIED: CLAUDE.md + frontend/src/App.tsx imports BrowserRouter/Routes/Route, useNavigate, useLocation]` | New `/settings` + `/settings/openrouter/callback` routes; `useNavigate`/`useSearchParams` in the callback | Already the SPA router. |
| `@supabase/supabase-js` | ^2.99.3 `[VERIFIED: CLAUDE.md]` | Bearer token for `apiFetch` (auth'd exchange/status/delete) | `apiFetch` already reads `supabase.auth.getSession()`. No direct table reads. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | ^0.577.0 `[VERIFIED: CLAUDE.md + IconSidebar/ConfirmDialog usage]` | `Settings` gear glyph, `AlertCircle` (callback failure), optional `RotateCw` | Per UI-SPEC; already imported across components. |
| `pydantic` | 2.11.1 `[VERIFIED: CLAUDE.md]` | Request/response models for `keys.py` (`ExchangeRequest`, `KeyStatusResponse`) | Project rule: Pydantic for structured outputs. Mirror `models/schemas.py` `*Response`/`*Create` suffixes. |
| `PyJWT` (via `auth.get_user_id`) | 2.10.1 `[VERIFIED: CLAUDE.md + backend/auth.py]` | `Depends(get_user_id)` on every `keys.py` endpoint | Existing auth dependency; reuse verbatim. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Web Crypto in `lib/pkce.ts` | A PKCE npm library (e.g. `pkce-challenge`) | Rejected — adds a dependency for ~15 lines; UI-SPEC explicitly says "No new npm dependencies"; OpenRouter's own example is Web Crypto. |
| `sessionStorage` for verifier+state | `localStorage` | `sessionStorage` is correct (D-07): survives same-tab refresh, auto-clears on tab close, not shared across tabs — tighter CSRF binding. `localStorage` would leak the verifier across tabs/sessions. |
| Reuse `key_label` for the masked tail | A new dedicated column | Reuse is fine — `key_label` is already nullable, non-secret, and was annotated "(Phase 10)" in migration 025. The masked tail (e.g. `sk-or-v1-…wXyZ`) IS the display label. No schema change needed for the label; only `connected_at` may need adding. |
| Add `connected_at` column | Reuse existing `created_at` | `created_at` already exists. On reconnect the row is upserted (overwritten) so `created_at` naturally re-stamps to "connected since". A dedicated `connected_at` is clearer semantically but optional — planner discretion. **Recommendation: reuse `created_at`** to avoid a migration if upsert resets it, OR add `connected_at` if upsert preserves `created_at`. Verify upsert behavior (see Pitfall 4). |

**Installation:** None — no new packages.

**Version verification:** `openai==1.74.0` is pinned and is far behind the current PyPI release (2.43.0, 2026-06-17) `[VERIFIED: pypi.org/project/openai via WebSearch]`, **but this phase does not touch the OpenAI SDK at all** — the exchange is raw `httpx`, and the chat-loop key resolution is Phase 11. The version gap is out of scope here. No package versions change in Phase 10.

## Architecture Patterns

### System Architecture Diagram

```
  ┌─────────────────────────── BROWSER (React SPA) ───────────────────────────┐
  │                                                                            │
  │  [/settings stub]  ──Connect──► lib/pkce.ts                                │
  │       ▲                          │ generate code_verifier (random 43+ chars)│
  │       │                          │ + S256 code_challenge (base64url SHA-256)│
  │       │ status                   │ + CSRF state (random)                    │
  │       │                          ▼                                          │
  │  useKeyStatus ◄──┐         sessionStorage{verifier,state}                  │
  │   GET /status    │                │                                        │
  │       │          │                ▼ window.location.assign                 │
  │  [header dot] ───┘   ┌──────────────────────────────────────────┐         │
  │                      │ openrouter.ai/auth?callback_url=<origin>+  │         │
  │                      │  /settings/openrouter/callback             │         │
  │                      │  &code_challenge=…&code_challenge_method=S256│        │
  │                      │  &state=…                                  │         │
  │                      └──────────────────┬─────────────────────────┘         │
  │                                         │ user authenticates @ OpenRouter   │
  │  [/settings/openrouter/callback] ◄──────┘ redirect ?code=…&state=…          │
  │     1. read code+state from URL                                            │
  │     2. read verifier+state from sessionStorage                             │
  │     3. validate returned state === stored state ──fail──► inline error     │
  │     4. POST {code, code_verifier} ──┐    (D-06; scrubbed, generic copy)    │
  │        via apiFetch (Bearer JWT)    │                                       │
  └────────────────────────────────────┼───────────────────────────────────────┘
                                        │ same-origin to /api (CORS already OK)
  ┌─────────────────────────── BACKEND (FastAPI) ──┼──────────────────────────┐
  │  keys.py router (Depends(get_user_id))         ▼                          │
  │   POST /api/keys/openrouter/exchange                                      │
  │     ├─ openrouter_service.exchange_code(code, code_verifier) ──httpx POST─┼──► openrouter.ai
  │     │     body {code, code_verifier, code_challenge_method:S256}          │    /api/v1/auth/keys
  │     │     ◄── {key, user_id?}                                             │    └── returns {key}
  │     ├─ masked = mask_tail(key)   (last-4, in memory only)                 │
  │     ├─ encrypt_key(key)          (crypto_service, Phase 9)                │
  │     └─ service-role upsert user_api_keys{user_id, encrypted_key,          │
  │           key_label=masked, key_version, created_at}                      │
  │     return {connected:true}      ◄── NEVER the key                        │
  │   GET /api/keys/status  → read row → {connected, masked_label, connected_at}│
  │   DELETE /api/keys      → service-role delete row                         │
  └──────────────────────────────────────────────┬──────────────────────────┘
                                                  │ service-role (bypasses RLS)
  ┌─────────────────────────── SUPABASE ──────────▼──────────────────────────┐
  │  user_api_keys (PK user_id) — REVOKE SELECT FROM authenticated +          │
  │  FROM-allowlist excludes it (Phase 9 SEC-02) — DO NOT UNDO                │
  └───────────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
backend/
├── routers/
│   └── keys.py              # NEW — POST exchange, GET status, DELETE (mirror demo.py/threads.py)
├── services/
│   └── openrouter_service.py # NEW — exchange_code(code, verifier) via httpx (mirror budget_service httpx)
├── models/
│   └── schemas.py            # MODIFIED — add ExchangeRequest, KeyStatusResponse pydantic models
└── main.py                   # MODIFIED — app.include_router(keys.router) (mirror demo.router)

supabase/migrations/
└── 20240301000028_*.sql      # NEW (next free number) — add connected_at if needed (key_label exists)

frontend/src/
├── lib/
│   ├── pkce.ts               # NEW — Web Crypto verifier/challenge/state helpers
│   ├── sentry.ts             # MODIFIED — add /sk-or-v1-[A-Za-z0-9_-]+/g scrub rule
│   └── api.ts                # REUSED — apiFetch for exchange/status/delete
├── pages/
│   ├── SettingsPage.tsx      # NEW — /settings stub (connect/status/disconnect)
│   └── OAuthCallbackPage.tsx # NEW — spinner → redirect+toast / inline error+retry
├── hooks/
│   └── useKeyStatus.ts       # NEW — shared GET /api/keys/status, refetch on connect/disconnect
├── components/
│   ├── IconSidebar.tsx       # MODIFIED — add Settings gear (desktop rail + IconNavRow)
│   ├── MobileTopBar.tsx      # MODIFIED (likely) — host connection dot left of DemoPill
│   └── ConfirmDialog.tsx     # REUSED, NOT MODIFIED — disconnect confirmation
└── App.tsx                   # MODIFIED — register /settings + /settings/openrouter/callback
```

### Pattern 1: Backend router mirroring `demo.py` / `threads.py`
**What:** A resource-named router with `Depends(get_user_id)` + service-role `get_supabase()`, registered in `main.py`.
**When to use:** Every new `keys.py` endpoint.
**Example:**
```python
# Source: backend/routers/threads.py + backend/routers/demo.py (live repo)
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id
from database import get_supabase
from services.openrouter_service import exchange_code
from services.crypto_service import encrypt_key
from models.schemas import ExchangeRequest, KeyStatusResponse

router = APIRouter(prefix="/api/keys", tags=["keys"])

@router.post("/openrouter/exchange")
async def exchange(body: ExchangeRequest, user_id: str = Depends(get_user_id)) -> dict:
    key = exchange_code(body.code, body.code_verifier)   # httpx → openrouter; raises on non-2xx
    masked = f"sk-or-v1-…{key[-4:]}"                       # non-secret tail, in memory only
    db = get_supabase()                                    # service-role, bypasses RLS
    db.table("user_api_keys").upsert({
        "user_id": user_id,
        "provider": "openrouter",
        "encrypted_key": encrypt_key(key),
        "key_label": masked,
        "key_version": 1,
    }).execute()
    return {"connected": True}                              # NEVER returns the key

@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    db = get_supabase()
    row = db.table("user_api_keys").select("key_label, created_at") \
            .eq("user_id", user_id).maybe_single().execute()
    if not row.data:
        return {"connected": False}
    return {"connected": True, "masked_label": row.data["key_label"],
            "connected_at": row.data["created_at"]}

@router.delete("", status_code=204)
async def disconnect(user_id: str = Depends(get_user_id)):
    get_supabase().table("user_api_keys").delete().eq("user_id", user_id).execute()
```
**Register in main.py (mirror demo.router):** `app.include_router(keys.router)` and add `keys` to the `from routers import ...` line.

### Pattern 2: `httpx` outbound to OpenRouter (mirror `budget_service`)
**What:** Synchronous `httpx` POST with `raise_for_status()` and a tight timeout; never log the response body (it contains the key).
**Example:**
```python
# Source: backend/services/budget_service.py:90 (httpx.get to openrouter.ai/api/v1/models)
import httpx

def exchange_code(code: str, code_verifier: str) -> str:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/auth/keys",
        json={"code": code, "code_verifier": code_verifier,
              "code_challenge_method": "S256"},
        timeout=15,
    )
    resp.raise_for_status()          # 400/403/405/500 → HTTPStatusError (do NOT log resp.text — has key)
    return resp.json()["key"]        # response: {key, user_id?}
```
Note: routers are `async def` but the existing codebase calls **synchronous** `httpx.*` inside them (e.g. `budget_service.fetch_model_context_length`). Mirror that — do not introduce `httpx.AsyncClient` unless the planner standardizes it. Wrap `raise_for_status` failures into a generic `HTTPException(502/400)` whose detail NEVER echoes the OpenRouter response (Pitfall 1).

### Pattern 3: `lib/pkce.ts` via Web Crypto (no library)
**What:** Generate a high-entropy `code_verifier`, derive the S256 `code_challenge`, generate a `state`.
**Example:**
```typescript
// Source: openrouter.ai/docs/guides/overview/auth/oauth (official S256 example)
function base64url(bytes: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}
export function randomString(len = 64): string {
  const arr = new Uint8Array(len)
  crypto.getRandomValues(arr)
  return base64url(arr.buffer).slice(0, len)
}
export async function challengeFromVerifier(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier)
  const hash = await crypto.subtle.digest('SHA-256', data)  // OpenRouter's own example
  return base64url(hash)
}
// Connect: store {verifier, state} in sessionStorage, then window.location.assign(authUrl)
```

### Pattern 4: Frontend data hook mirroring `useDocuments`
**What:** `useKeyStatus` — `apiFetch('/api/keys/status')` into state, gated on session, refetch on connect/disconnect. Shared by `/settings` and the header dot.
**Example:**
```typescript
// Source: frontend/src/hooks/useDocuments.ts (loadDocuments pattern)
export function useKeyStatus() {
  const [status, setStatus] = useState<{connected: boolean; masked_label?: string; connected_at?: string} | null>(null)
  const [loading, setLoading] = useState(true)
  const { session } = useAuth()
  const refresh = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try { setStatus(await apiFetch('/api/keys/status')) }
    catch { /* leave prior status; dot shows last-known */ }
    finally { setLoading(false) }
  }, [session])
  useEffect(() => { refresh() }, [refresh])
  return { status, loading, refresh }
}
```
**Do NOT poll** (UI-SPEC §Surface 3) — fetch once on mount, refetch after connect/disconnect.

### Anti-Patterns to Avoid
- **Returning the key (plaintext OR ciphertext) to the frontend:** `/status` returns `{connected, masked_label, connected_at}` only. Never add the key "so the UI can show it."
- **Client-side exchange:** Never POST `{code, verifier}` directly to `openrouter.ai` from the browser — the `sk-or-v1-…` key would render in the browser and leak to Sentry/console. Exchange backend-side only.
- **`key = user_key or owner_key` style fallback:** Out of scope here (Phase 11), but do not pre-build any owner-key fallback in `keys.py`.
- **Logging `resp.text` / `resp.json()` from the exchange:** the body contains the key. Catch and re-raise a generic error; never `logger.error(..., exc_info=True)` on the raw OpenRouter response.
- **`localStorage` for the verifier/state:** use `sessionStorage` (D-07 + CSRF binding).
- **Interpolating a server message into the callback failure UI:** the copy is hard-coded ("Couldn't connect your OpenRouter account — please try again."); never render the raw exchange error (D-06).
- **Editing migrations 025/026/027 to "add" the label column:** those are already applied to dev — a new forward migration (028) is required; editing applied migrations does nothing (STATE.md notes this exact lesson for 025/026).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PKCE challenge/verifier | A custom SHA-256 + base64 routine from scratch | `crypto.subtle.digest('SHA-256', …)` + `getRandomValues` | Web Crypto is the platform primitive OpenRouter's own docs use; hand-rolled SHA-256 is a footgun. |
| Key encryption | Any new crypto | Phase 9 `crypto_service.encrypt_key()` | Already MultiFernet, rotation-aware, tested. |
| Auth on new endpoints | A new token check | `Depends(get_user_id)` (`backend/auth.py`) | Handles HS256/ES256, JWKS, `request.state.user_id` bridge. |
| DB access from backend | A new client | `get_supabase()` (service-role) | Bypasses RLS server-side; the only sanctioned write path to `user_api_keys`. |
| Confirm dialog (disconnect) | A new modal | `ConfirmDialog` (`frontend/src/components/ConfirmDialog.tsx`) | Portal, Escape-to-cancel, click-outside, red confirm — props already match D-08 copy. |
| Toast (connect success) | A toast library (sonner/react-hot-toast) | `useToast()` `'success'` variant (`ToastContext.tsx`) | Already `aria-live`, auto-dismiss 4s, green ramp. |
| Spinner | An SVG spinner component / lib | Inline `border-2 border-gray-400 border-t-transparent rounded-full animate-spin` | Existing pattern in `ToolCallCard.tsx` (per UI-SPEC). |
| SPA fallback for callback path | A new route config / Cloudflare rule | Existing `frontend/public/_redirects` (`/* /index.html 200`) | Catch-all already serves any deep path including `/settings/openrouter/callback`. |
| Sentry scrubber | A new beforeSend pipeline | Extend the existing `lib/sentry.ts` `beforeSend`/`beforeBreadcrumb` | Add one regex rule beside the JWT rule; don't rewrite. |
| Outbound HTTP | `requests` / `urllib` | `httpx` | Already the project's HTTP client across 4 services. |

**Key insight:** Phase 10 is almost entirely *wiring existing, hardened primitives together*. The only genuinely new logic is (a) the ~20-line `lib/pkce.ts`, (b) the `openrouter_service.exchange_code` httpx call, (c) the masked-tail capture, and (d) the callback state machine. Everything else is reuse. Resist building new components.

## Runtime State Inventory

> This phase is additive (new code + one forward migration), not a rename/refactor. The relevant "runtime state" concern is the **Phase 9 live DB state** and the **SQL-tool lockdown that must not regress**.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `user_api_keys` table is LIVE on the dev Supabase project (`ntkkmljbariflblldmha`) — migrations 025/026/027 applied (STATE.md). Columns: `user_id` (PK), `provider`, `encrypted_key`, `key_version` (default 1), `key_label` (nullable, "Phase 10"), `created_at`, `updated_at`. **No `connected_at` column.** No rows yet expected (no connect flow shipped). | If a dedicated `connected_at` is chosen: add via migration 028 to dev now, prod at deploy step (D-03 dual-env discipline). If reusing `created_at`: no migration needed. `key_label` reuse for the masked tail: no migration needed. |
| Live service config | OpenRouter OAuth flow uses NO pre-registered callback URL (any localhost port + the Pages origin work without registration — verified in docs). No OpenRouter dashboard config to set. Cloudflare Pages `_redirects` catch-all already covers the callback path. | None — verified by `frontend/public/_redirects` = `/* /index.html 200` and OpenRouter "localhost any port / no pre-registration" docs. |
| OS-registered state | None — no schedulers, no OS tasks. | None — verified (no cron/scheduler in this phase). |
| Secrets/env vars | `KEY_ENCRYPTION_SECRET` already in `config.Settings` (Phase 9 D-04), per-env in `.env`/`.env.prod`. No NEW secret needed for Phase 10 — `callback_url` is FE-derived from `window.location.origin`; the optional `OAUTH_CALLBACK_BASE_URL` backend var is NOT needed. | None — verified by `backend/config.py:23` (`key_encryption_secret`). No new env var. |
| Build artifacts | None — no compiled packages renamed. Frontend builds via Vite; `frontend/dist/_redirects` is a build copy of `public/_redirects` (auto-regenerated). | None. |

**The canonical question — after every file is updated, what runtime systems still have stale state?** None for Phase 10 specifically; the live dev `user_api_keys` table is forward-compatible (a new nullable `connected_at` or reused `created_at` does not break existing rows; none exist yet). The one hard "do not regress" item is the SQL-tool lockdown (migrations 025/026/027 + `sql_service.ALLOWED_SQL_TABLES`) — Phase 10 must not add `user_api_keys` to any allowlist or grant SELECT to `authenticated`.

## Common Pitfalls

### Pitfall 1: Exchange error / key echoed into a log, SSE, or the callback UI (SEC-01)
**What goes wrong:** `openrouter_service.exchange_code` raises on a 403 (bad code/verifier); a naive handler does `logger.error(f"exchange failed: {resp.text}")` or `raise HTTPException(400, detail=resp.text)`. The OpenRouter error body (and stack-local `key` on a partial success path) can contain `sk-or-v1-…`. The frontend then renders the raw detail, or it lands in Sentry.
**Why it happens:** The v1.1 Sentry scrubber only catches `Authorization` + Supabase JWT shapes — `sk-or-v1-…` matches neither. `chat.py`-style `json.dumps({"error": str(e)})` patterns echo exception strings.
**How to avoid:**
- Backend: catch `httpx.HTTPStatusError`, raise a generic `HTTPException` (e.g. 502 "exchange failed") whose detail is a fixed string — never `resp.text`. Do NOT `exc_info=True` on the raw response.
- Frontend: the callback failure copy is hard-coded (D-06) — "Couldn't connect your OpenRouter account — please try again." — never interpolate the server message.
- Frontend backstop: extend `lib/sentry.ts` with `/sk-or-v1-[A-Za-z0-9_-]+/g → '[redacted-key]'` across `beforeSend` (message, exception values, `request.url`) and `beforeBreadcrumb` (console + fetch breadcrumb message/data).
**Warning signs:** Grep your own Sentry for `sk-or`. Any callback-path breadcrumb with a long token. A 4xx whose body shows the key.
**Confidence:** HIGH `[CITED: PITFALLS.md Pitfall 2; VERIFIED: live lib/sentry.ts only handles Authorization + sb-<ref>-auth-token]`

### Pitfall 2: Missing / unverified CSRF `state` (forged callback binds the wrong key)
**What goes wrong:** OpenRouter omits `state`. Without a self-generated `state`, an attacker feeds a victim a crafted callback URL with the attacker's `code`, binding the attacker's key to the victim's account (or the victim's session exchanges a planted code).
**Why it happens:** Teams assume PKCE covers CSRF — it covers code *interception*, not callback session fixation.
**How to avoid:** Generate `state` alongside `verifier`, persist BOTH in `sessionStorage`, append `&state=…` to the authorize URL via `callback_url` query, and on return reject if `returnedState !== storedState`. The exchange runs backend-side under the Supabase JWT so the key binds to `auth.uid()` server-side regardless.
**Warning signs:** Exchange works same-tab but no `state` round-trip in the URL. A forged-callback test isn't rejected (ROADMAP success criterion #2).
**Confidence:** HIGH `[CITED: PITFALLS.md Pitfall 5 + ARCHITECTURE.md; VERIFIED: OpenRouter docs show no state param]`

### Pitfall 3: `code_verifier`/`state` lost on hard refresh → false failure
**What goes wrong:** If the verifier is in volatile React state or `useMemo`, a hard refresh on the callback page loses it and the exchange 403s — wrongly shown as a failure. D-07 requires hard-refresh to be the SUCCESS path.
**Why it happens:** Devs store the verifier in component state rather than `sessionStorage`.
**How to avoid:** `sessionStorage` survives same-tab refresh. On callback mount, read verifier+state from `sessionStorage`, not from any in-memory state. Only clear `sessionStorage` AFTER a successful exchange (or on explicit Retry, which re-inits).
**Warning signs:** "Works until I refresh the callback page." Exchange 403 only after reload.
**Confidence:** HIGH `[CITED: D-07 + PITFALLS.md Pitfall 5]`

### Pitfall 4: Upsert semantics — does reconnect reset "connected since"?
**What goes wrong:** D-09 says reconnect upserts on PK `user_id`. If the masked label/`connected_at` semantics depend on `created_at`, a supabase-py `upsert` may or may not re-stamp `created_at` (the column has `DEFAULT now()` which only fires on INSERT, not on a conflict-UPDATE). So an upsert that hits the conflict path keeps the ORIGINAL `created_at` — "connected since" would show the *first-ever* connect, not the latest reconnect.
**Why it happens:** Postgres `ON CONFLICT DO UPDATE` does not re-apply column defaults; `updated_at` would change but `created_at` stays.
**How to avoid:** Decide the desired semantic explicitly. If "connected since latest reconnect" is wanted, set the timestamp EXPLICITLY in the upsert payload (e.g. include `"connected_at": <now>` or `"created_at": <now>` in the dict) so it overwrites on conflict. **Recommendation:** add a dedicated `connected_at` column (migration 028) and set it explicitly in the exchange upsert — clearest semantic, decoupled from row-creation time. Verify with a reconnect test (connect → check date → disconnect → reconnect → date updates).
**Warning signs:** "Connected since" never changes after a reconnect. `updated_at` moves but the displayed date doesn't.
**Confidence:** MEDIUM `[ASSUMED: Postgres ON CONFLICT default behavior is well-known, but supabase-py upsert default conflict target + whether it sends created_at is not verified this session — flag for the planner to confirm with a quick test]`

### Pitfall 5: SPA fallback / callback path 404 in prod (Pitfall 6)
**What goes wrong:** OAuth started in prod returns to `<origin>/settings/openrouter/callback`; if the SPA deep-link rewrite doesn't cover it, Cloudflare Pages 404s. "Works on localhost" masks it because Vite serves index for any path.
**Why it happens:** Per-env callback config differs from per-env CORS config.
**How to avoid:** Verified mitigated — `frontend/public/_redirects` is `/* /index.html 200` (catch-all). The callback path is already served. Still **test the full round-trip on the Cloudflare Pages prod origin** before closing (ROADMAP success criterion #4 + dual-env D-03).
**Warning signs:** 404 on the callback path in prod only.
**Confidence:** HIGH `[VERIFIED: frontend/public/_redirects content read directly]`

### Pitfall 6: Regressing the Phase 9 SQL-tool lockdown
**What goes wrong:** Adding the masked-label column or "fixing" the allowlist accidentally re-grants `SELECT ON user_api_keys TO authenticated`, or adds `user_api_keys` to `ALLOWED_SQL_TABLES` / the RPC FROM-allowlist — re-opening the prompt-injection exfil path (SEC-02).
**Why it happens:** The label is "non-secret," tempting a dev to make it SQL-queryable.
**How to avoid:** The masked label is non-secret but lives in the SAME row as `encrypted_key`. Keep the WHOLE table out of the SQL tool's reach. Do NOT touch `backend/services/sql_service.py::ALLOWED_SQL_TABLES` (frozenset `{threads, messages, documents, document_chunks}`) or migrations 026/027's allowlist. The backend reads the label via the service-role client only.
**Warning signs:** Any diff touching `ALLOWED_SQL_TABLES`, `execute_readonly_query`, or a `GRANT SELECT ON user_api_keys`. `test_sql_keys_lockdown.py` failing.
**Confidence:** HIGH `[VERIFIED: migrations 025/026/027 + sql_service.py ALLOWED_SQL_TABLES read directly; STATE.md confirms live lockdown]`

### Pitfall 7: Callback route guard — session must survive the OAuth round-trip
**What goes wrong:** The exchange POST carries the Supabase bearer; if the callback page renders before the Supabase session resolves (or the route is unguarded and the user landed without a session), `apiFetch` sends no/expired token and the exchange 401s.
**Why it happens:** The OAuth redirect is a full-page navigation; `AuthContext` re-initializes from `localStorage` on the fresh load.
**How to avoid:** Recommendation — wrap the callback in `ProtectedRoute` (the session is restored from Supabase's `localStorage` token on load, so a logged-in user keeps their session across the OpenRouter round-trip). Confirm the session is present before posting (await `supabase.auth.getSession()` via `apiFetch`'s existing flow). If `ProtectedRoute` redirects to `/login`, fall back to a session-wait. Planner discretion (D — Claude's Discretion), but protected is the safer default per UI-SPEC Open Question 4.
**Warning signs:** Exchange 401 right after the OpenRouter redirect; works on a second manual attempt.
**Confidence:** MEDIUM `[ASSUMED: Supabase session restores from localStorage on full reload — standard behavior, but the exact AuthContext loading-gate interaction with the callback should be verified by the planner]`

## Code Examples

### Pydantic models for `keys.py` (mirror `models/schemas.py`)
```python
# Source: backend/models/schemas.py conventions (*Response / *Create suffixes, str | None)
from pydantic import BaseModel

class ExchangeRequest(BaseModel):
    code: str
    code_verifier: str

class KeyStatusResponse(BaseModel):
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None
```

### Frontend Connect init (in `SettingsPage` Connect handler)
```typescript
// Source: derived from lib/pkce.ts (this phase) + OpenRouter authorize URL (docs)
import { randomString, challengeFromVerifier } from '../lib/pkce'

async function connect() {
  const verifier = randomString(64)
  const state = randomString(32)
  const challenge = await challengeFromVerifier(verifier)
  sessionStorage.setItem('or_pkce_verifier', verifier)
  sessionStorage.setItem('or_pkce_state', state)
  const callback = `${window.location.origin}/settings/openrouter/callback`
  const url = `https://openrouter.ai/auth?callback_url=${encodeURIComponent(callback)}`
    + `&code_challenge=${challenge}&code_challenge_method=S256&state=${state}`
  window.location.assign(url)
}
```

### Callback exchange flow (in `OAuthCallbackPage`)
```typescript
// Source: D-05/D-06/D-07 + apiFetch (frontend/src/lib/api.ts)
const params = new URLSearchParams(window.location.search)
const code = params.get('code'); const returnedState = params.get('state')
const verifier = sessionStorage.getItem('or_pkce_verifier')
const storedState = sessionStorage.getItem('or_pkce_state')
try {
  if (!code || !verifier || returnedState !== storedState) throw new Error('state')
  await apiFetch('/api/keys/openrouter/exchange', {
    method: 'POST', body: JSON.stringify({ code, code_verifier: verifier }),
  })
  sessionStorage.removeItem('or_pkce_verifier'); sessionStorage.removeItem('or_pkce_state')
  showToast('OpenRouter connected.', 'success')
  navigate('/settings', { replace: true })
} catch {
  setState('failure')   // renders the hard-coded D-06 sentence — never the error
}
```

### Sentry scrub extension
```typescript
// Source: frontend/src/lib/sentry.ts (extend the existing beforeSend/beforeBreadcrumb)
const OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g
const scrub = (s: unknown): unknown =>
  typeof s === 'string' ? s.replace(OR_KEY, '[redacted-key]') : s
// In beforeSend: scrub event.message, event.exception.values[].value, event.request.url
// In beforeBreadcrumb: scrub breadcrumb.message and stringy breadcrumb.data fields
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OAuth implicit flow / client secret in SPA | PKCE (no client secret), S256 challenge | OAuth 2.1 / RFC 7636 era | OpenRouter uses PKCE-no-secret — exactly fits SPA-init + backend-exchange. |
| Plain `code_challenge_method` | `S256` (SHA-256) | Long-standing best practice | OpenRouter supports both; S256 is the only acceptable choice (Pitfall: mismatch → 400). |
| Hand-rolled SHA-256/base64 for PKCE | Web Crypto `crypto.subtle.digest` | Universal browser support (all evergreen) | OpenRouter's own docs example uses it — no PKCE library needed. |

**Deprecated/outdated:**
- The milestone `ARCHITECTURE.md` (2026-06-18) predates the Phase 9 implementation. Its proposed `user_api_keys` schema (`encrypted_key`, `key_label`, `connected_at`, `last_used_at`) differs from what actually shipped (`encrypted_key`, `key_version`, `key_label`, `created_at`, `updated_at` — **no `connected_at`, no `last_used_at`**). Trust the live migration 025, not the milestone research, for column names. This RESEARCH closes that gap (Open Question 1 below).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | supabase-py `upsert` on conflict does NOT re-stamp `created_at` (Postgres `ON CONFLICT DO UPDATE` skips column defaults), so "connected since" needs an explicit timestamp in the payload | Pitfall 4 | If wrong (created_at does re-stamp), no harm — explicit set is still correct; if right and not handled, "connected since" shows the first connect, not the latest reconnect. Planner should add a reconnect test. |
| A2 | Wrapping the callback route in `ProtectedRoute` preserves the Supabase session across the OpenRouter full-page round-trip (session restores from `localStorage` on reload) | Pitfall 7 | If the AuthContext loading-gate races the exchange, the first exchange 401s. Planner should verify session-present before POST, or add a session-wait. |
| A3 | Reusing `key_label` for the masked tail (`sk-or-v1-…wXyZ`) is acceptable — the column is non-secret and was annotated "(Phase 10)" | Standard Stack / Schema | Low — the column is explicitly nullable + display-only. Only risk is if a planner expected a separate label vs tail; D-03 treats the masked tail AS the display label. |
| A4 | No backend env var (`OAUTH_CALLBACK_BASE_URL`) is needed — `callback_url` is fully FE-derived | Runtime State Inventory / Env | Low — confirmed by D-04 (CONTEXT) + ARCHITECTURE; the exchange never constructs the callback URL. |

## Open Questions

1. **`connected_at` column: add or reuse `created_at`?** (D-03 ⚠ schema check — RESOLVED to a recommendation)
   - What we know: The live `user_api_keys` table has `created_at`, `updated_at`, `key_label` (nullable) — but **no `connected_at`**. Verified by reading migration `20240301000025_create_user_api_keys.sql` directly.
   - What's unclear: Whether the planner wants "connected since" to track the latest reconnect (then an explicit timestamp is needed — see Pitfall 4) or first-ever connect.
   - Recommendation: **Add a `connected_at TIMESTAMPTZ` column in migration `20240301000028`** and set it explicitly in the exchange upsert. Reuse the existing `key_label` for the masked tail (no new column for the label). Apply to dev now, prod at deploy (D-03). This is the cleanest semantic and avoids the upsert/default ambiguity. The migration must NOT touch RLS/REVOKE/allowlist.

2. **Callback route guard: public vs `ProtectedRoute`?** (UI-SPEC Open Question 4)
   - What we know: The exchange POST requires a valid Supabase bearer (`apiFetch` reads the session). A logged-in user's session persists across the OAuth redirect via Supabase's `localStorage` token.
   - Recommendation: Wrap in `ProtectedRoute` (safer default); confirm during implementation that the session is present before the exchange POST (Pitfall 7 / A2). If a race appears, gate the exchange on `useAuth().session` being non-null.

3. **Frontend test framework absent.** No Vitest/Jest in `frontend/package.json` (verified). `lib/pkce.ts` (challenge derivation) and the Sentry regex are the only pure-logic FE units worth testing. If FE unit tests are desired, that's a Wave 0 install (Vitest) — otherwise these are covered by the manual prod round-trip + a backend-side regex assertion.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | `openrouter_service.exchange_code` | ✓ | unpinned (transitive, used directly in 4 services) | — |
| `cryptography` (Fernet) via `crypto_service` | encrypt at exchange | ✓ | 46.0.5 | — |
| `KEY_ENCRYPTION_SECRET` env | encrypt/decrypt | ✓ (dev `.env`, prod `.env.prod`) | Phase 9 D-04 | none — exchange fails clearly if unset (RuntimeError) |
| Web Crypto `SubtleCrypto` | `lib/pkce.ts` | ✓ (all evergreen browsers; HTTPS or localhost) | platform | none needed |
| Supabase dev project + `user_api_keys` table | upsert/status/delete | ✓ | migrations 025/026/027 LIVE on dev | — |
| Cloudflare Pages `_redirects` SPA fallback | callback deep-link in prod | ✓ | `/* /index.html 200` | — |
| OpenRouter `/auth` + `/api/v1/auth/keys` | the whole flow | ✓ (public, no pre-registration, localhost any port) | live API | none — external dependency, verified via docs |
| pytest (backend) | exchange/status/delete tests | ✓ | configured (`backend/pytest.ini`, `asyncio_mode=auto`) | — |
| Vitest/Jest (frontend) | optional FE unit tests | ✗ | — | manual prod round-trip + backend regex test cover the critical paths |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Frontend test framework (Vitest) — absent; FE logic is thin (PKCE derivation, Sentry regex) and verifiable via the manual round-trip. Installing Vitest would be a Wave 0 decision if FE unit coverage is required.

## Validation Architecture

> `workflow.nyquist_validation: true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) — `[VERIFIED: backend/pytest.ini, testpaths=tests, asyncio_mode=auto, --strict-markers]`. Frontend: none detected. |
| Config file | `backend/pytest.ini` (backend); no frontend test config |
| Quick run command | `cd backend && venv/Scripts/python -m pytest tests/test_keys_exchange.py -x` (new file) |
| Full suite command | `cd backend && venv/Scripts/python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KEY-01 | Exchange POSTs to OpenRouter, encrypts, upserts; key never in response | unit (mock httpx + crypto + db) | `pytest tests/test_keys_exchange.py::test_exchange_upserts_and_hides_key -x` | ❌ Wave 0 |
| KEY-01 | Exchange handler does NOT echo OpenRouter error/key on 403 (SEC-01) | unit | `pytest tests/test_keys_exchange.py::test_exchange_403_generic_error -x` | ❌ Wave 0 |
| KEY-03 | `GET /api/keys/status` returns `{connected, masked_label, connected_at}`, never the key | unit (TestClient + dep override) | `pytest tests/test_keys_status.py::test_status_returns_masked_only -x` | ❌ Wave 0 |
| KEY-03 | Status `connected:false` when no row | unit | `pytest tests/test_keys_status.py::test_status_not_connected -x` | ❌ Wave 0 |
| KEY-04 | `DELETE /api/keys` removes the row; subsequent status = not connected | unit | `pytest tests/test_keys_delete.py::test_disconnect -x` | ❌ Wave 0 |
| KEY-04 | Reconnect upserts (overwrites prior row, one key per user) | unit | `pytest tests/test_keys_exchange.py::test_reconnect_upserts -x` | ❌ Wave 0 |
| SEC-01 (FE) | `lib/sentry.ts` scrub maps `sk-or-v1-…` → `[redacted-key]` | unit (FE, optional) OR manual | manual / Vitest if installed | ❌ Wave 0 (or manual) |
| SEC-02 (regression) | SQL tool still cannot read `user_api_keys` after this phase | existing | `pytest tests/test_sql_keys_lockdown.py -x` | ✅ (Phase 9 — must stay green) |
| KEY-01 (CSRF) | Forged/mismatched `state` rejected; hard-refresh succeeds | manual (browser) | manual round-trip dev + prod | manual |
| KEY-01 (prod) | Full round-trip on Cloudflare Pages origin | manual (browser, prod) | manual deploy gate | manual |

### Sampling Rate
- **Per task commit:** `cd backend && venv/Scripts/python -m pytest tests/test_keys_*.py tests/test_sql_keys_lockdown.py -x`
- **Per wave merge:** `cd backend && venv/Scripts/python -m pytest -q` (full backend suite — confirms no regression incl. Phase 9 lockdown)
- **Phase gate:** Full backend suite green + manual forged-callback rejection + manual prod-origin round-trip before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `backend/tests/test_keys_exchange.py` — covers KEY-01 (httpx mock, encrypt called, upsert, key absent from response, 403 generic error, reconnect upsert)
- [ ] `backend/tests/test_keys_status.py` — covers KEY-03 (masked-only, not-connected)
- [ ] `backend/tests/test_keys_delete.py` — covers KEY-04 (disconnect)
- [ ] Test pattern: FastAPI `TestClient(app)` + `app.dependency_overrides[get_user_id]` + `patch("routers.keys.get_supabase")` / `patch("routers.keys.exchange_code")` — mirror `backend/tests/test_demo_bootstrap.py` exactly.
- [ ] (Optional) Frontend Vitest install + `lib/pkce.test.ts` (challenge derivation determinism) + `lib/sentry` scrub test — only if FE unit coverage is desired; otherwise manual.
- [ ] Manual checklist artifact for the CSRF-forge + hard-refresh + prod-origin round-trip (cannot be automated headlessly without an OpenRouter test account).

## Security Domain

> `security_enforcement` not present in `.planning/config.json` → treated as enabled. Section included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication / OAuth | yes | OAuth 2.0 PKCE (S256), own CSRF `state`, backend-side exchange under Supabase JWT (`Depends(get_user_id)`) |
| V3 Session Management | yes | `sessionStorage` for verifier+state (same-tab, auto-clear on close); Supabase bearer for the exchange POST; `ProtectedRoute` on callback (recommended) |
| V4 Access Control | yes | Service-role write path only; RLS own-row policies (defense-in-depth); REVOKE SELECT FROM authenticated keeps the SQL tool out (Phase 9 SEC-02 — do not regress) |
| V5 Input Validation | yes | Pydantic `ExchangeRequest` validates `{code, code_verifier}`; `state` equality check; OpenRouter response parsed for `key` only |
| V6 Cryptography | yes | Reuse Phase 9 `crypto_service` (Fernet/MultiFernet) — NEVER hand-roll; Web Crypto `crypto.subtle.digest` for S256 |
| V7 Error Handling / Logging | yes | Generic exchange errors (never `resp.text`); `sk-or-v1-…` scrub in `lib/sentry.ts` (frontend half of SEC-01); no `exc_info=True` on the OpenRouter response |
| V9 Communications | yes | TLS to OpenRouter (`https://`, POST not querystring); the key never crosses to the browser; same-origin exchange POST already in CORS allowlist |

### Known Threat Patterns for OAuth-PKCE-BYOK

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF / callback session fixation (forged `code`) | Tampering / Spoofing | Self-generated `state` in `sessionStorage`, verified on return (Pitfall 2) |
| Key leak to Sentry/console/URL (`sk-or-v1-…`) | Information Disclosure | Regex scrub in `beforeSend`/`beforeBreadcrumb`; generic UI/error copy; key never in querystring (Pitfall 1) |
| Key exfil via Text-to-SQL prompt injection | Information Disclosure / Elevation | Phase 9 REVOKE SELECT + FROM-allowlist — keep `user_api_keys` out of `ALLOWED_SQL_TABLES`; do NOT regress (Pitfall 6) |
| Client-side exchange (key renders in browser) | Information Disclosure | Backend-side exchange only; SPA posts `{code, verifier}` to our API, never to `openrouter.ai` |
| `code_verifier` interception | Information Disclosure | PKCE S256 — verifier never sent until exchange; held in `sessionStorage`, posted over TLS to our backend |
| Re-owning another user's key row | Tampering / Elevation | RLS UPDATE policy `USING + WITH CHECK auth.uid() = user_id` (added in migration 027 WR-04); backend binds upsert to JWT `user_id` |
| Returning ciphertext/plaintext to client | Information Disclosure | `/status` returns booleans + masked tail only; exchange returns `{connected:true}` |

## Sources

### Primary (HIGH confidence)
- OpenRouter OAuth PKCE guide — authorize URL (`/auth?callback_url&code_challenge&code_challenge_method=S256`), S256 = base64url(SHA-256(verifier)) with Web Crypto example, exchange `POST /api/v1/auth/keys`, no `state` param, localhost any-port: https://openrouter.ai/docs/guides/overview/auth/oauth `[CITED]`
- OpenRouter exchange-code API reference — request fields (`code` required, `code_verifier`/`code_challenge_method` optional), response `{key, user_id?}`, errors 400/403/500: https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key `[CITED]`
- Live repo (read directly this session) `[VERIFIED]`:
  - `supabase/migrations/20240301000025_create_user_api_keys.sql` (columns: user_id PK, provider, encrypted_key, key_version, key_label, created_at, updated_at; REVOKE SELECT FROM authenticated; own-row RLS)
  - `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql` + `…027_harden_sql_allowlist_and_rls.sql` (FROM-allowlist `{threads, messages, documents, document_chunks}`; UPDATE WITH CHECK fix)
  - `backend/services/crypto_service.py` (`encrypt_key`/`decrypt_key`/`rotate_token`, MultiFernet)
  - `backend/routers/demo.py`, `threads.py` (router + `Depends(get_user_id)` + service-role pattern)
  - `backend/auth.py` (HS256/ES256 JWT, `request.state.user_id` bridge)
  - `backend/config.py` (`key_encryption_secret`, no callback env needed), `backend/database.py` (service-role client), `backend/main.py` (`include_router` pattern)
  - `backend/services/budget_service.py` (httpx → openrouter.ai pattern), `sql_service.py` (`ALLOWED_SQL_TABLES` frozenset)
  - `backend/pytest.ini`, `backend/tests/conftest.py`, `test_demo_bootstrap.py` (TestClient + dep-override + patch pattern), `test_crypto_service.py`
  - `frontend/src/App.tsx`, `lib/api.ts`, `lib/sentry.ts`, `components/IconSidebar.tsx`, `ConfirmDialog.tsx`, `contexts/ToastContext.tsx`, `components/ProtectedRoute.tsx`, `MobileTopBar.tsx`, `DemoPill.tsx`, `hooks/useDocuments.ts`, `pages/ChatPage.tsx`
  - `frontend/public/_redirects` (`/* /index.html 200` — SPA fallback)
  - `.planning/config.json` (nyquist_validation true, no security_enforcement key → enabled)

### Secondary (MEDIUM confidence)
- OpenRouter exchange response `key` field confirmation via WebSearch (cross-checked with the API reference): https://openrouter.ai/docs/api/api-reference/o-auth/exchange-auth-code-for-api-key `[CITED]`
- `openai` PyPI latest 2.43.0 (irrelevant to this phase) via WebSearch — https://pypi.org/project/openai/ `[VERIFIED]`

### Tertiary (LOW confidence)
- supabase-py `upsert` on-conflict `created_at` default behavior — inferred from standard Postgres `ON CONFLICT DO UPDATE` semantics, NOT verified against supabase-py 2.13.0 this session `[ASSUMED — A1, flagged for planner test]`

### Milestone research (consumed, milestone-aware — verified against live code where they diverge)
- `.planning/research/ARCHITECTURE.md` §OAuth Callback Flow / §New API Endpoints — flow split + endpoint table (schema since superseded by live migration 025 — see State of the Art)
- `.planning/research/PITFALLS.md` — Pitfalls 2 (Sentry), 5 (PKCE/state), 6 (callback URL/SPA)
- `.planning/phases/09-crypto-encrypted-key-storage-foundation/09-CONTEXT.md` + `.planning/STATE.md` (live migration status, SQL-lockdown lessons)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every library/pattern verified in the live repo; no new deps; OpenRouter endpoints verified against official docs.
- Architecture (flow + tier map): HIGH — PKCE split verified against OpenRouter docs; backend/frontend patterns read directly from the codebase.
- Schema (D-03 resolution): HIGH for what exists (migration 025 read directly); MEDIUM for the `connected_at`-vs-`created_at` upsert semantic (A1, flagged).
- Pitfalls: HIGH for 1/2/3/5/6; MEDIUM for 4 (upsert default) and 7 (session-across-redirect) — both flagged as assumptions with recommended verification tests.
- Security domain: HIGH — Phase 9 lockdown read directly; ASVS/STRIDE mapped to the verified stack.

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (30 days — OpenRouter OAuth flow is stable; codebase facts valid until the next migration). The OpenRouter API is the only external moving part; re-verify the exchange response shape if the flow regresses.
