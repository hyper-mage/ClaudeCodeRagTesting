# Phase 10: OAuth PKCE — Backend Exchange + Frontend Connect - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 14 (8 new, 6 modified)
**Analogs found:** 13 / 14 (1 new-logic file — `lib/pkce.ts` — has no in-repo analog; its source is OpenRouter docs, captured in RESEARCH.md Pattern 3)

> Phase 10 is almost entirely *wiring existing hardened primitives together*. Every file below has a live, read-directly analog except `lib/pkce.ts` (Web Crypto, ~20 lines, no codebase precedent). Planner: copy the cited excerpts verbatim and adapt — do not invent new conventions.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/routers/keys.py` | route | request-response (exchange) + CRUD (status/delete) | `backend/routers/threads.py` (CRUD shape) + `backend/routers/demo.py` (POST + service-role) | exact |
| `backend/services/openrouter_service.py` | service | request-response (outbound httpx) | `backend/services/budget_service.py::fetch_model_context_length` | role+flow exact |
| `backend/models/schemas.py` (MODIFIED) | model | transform (Pydantic I/O) | existing `*Create`/`*Response` classes in same file | exact (self-analog) |
| `backend/main.py` (MODIFIED) | config | event-driven (router registration) | `app.include_router(demo.router)` line in same file | exact (self-analog) |
| `supabase/migrations/20240301000028_*.sql` | migration | batch (DDL) | `supabase/migrations/20240301000025_create_user_api_keys.sql` | exact (same table) |
| `backend/tests/test_keys_*.py` | test | request-response (TestClient) | `backend/tests/test_demo_bootstrap.py` | exact |
| `frontend/src/lib/pkce.ts` | utility | transform (crypto derivation) | **none in repo** — OpenRouter docs (RESEARCH Pattern 3) | no analog |
| `frontend/src/lib/sentry.ts` (MODIFIED) | config | event-driven (scrub hook) | the existing `beforeSend`/`beforeBreadcrumb` in same file | exact (self-analog) |
| `frontend/src/hooks/useKeyStatus.ts` | hook | request-response (fetch-into-state) | `frontend/src/hooks/useDocuments.ts::loadDocuments` | role+flow exact |
| `frontend/src/pages/SettingsPage.tsx` | component | request-response (status + connect/disconnect) | `frontend/src/pages/ChatPage.tsx` (page shell) + `ConfirmDialog` consumer pattern | role-match |
| `frontend/src/pages/OAuthCallbackPage.tsx` | component | request-response (one-shot exchange + state machine) | `frontend/src/hooks/useDocuments.ts` (apiFetch+try/catch) + `ToolCallCard` spinner | role-match |
| `frontend/src/App.tsx` (MODIFIED) | route | event-driven (route table) | existing `/documents` `<Route>` block in same file | exact (self-analog) |
| `frontend/src/components/IconSidebar.tsx` (MODIFIED) | component | event-driven (nav) | the Documents `<button>` in same file (rail + `IconNavRow`) | exact (self-analog) |
| `frontend/src/components/MobileTopBar.tsx` (MODIFIED) | component | request-response (consume `useKeyStatus`) | the `DemoPill` right-slot in same file | exact (self-analog) |

---

## Pattern Assignments

### `backend/routers/keys.py` (route, request-response + CRUD)

**Primary analog:** `backend/routers/threads.py`
**Secondary analog:** `backend/routers/demo.py` (POST handler + `get_supabase()` use)

**Imports + router prefix** (mirror `threads.py:1-6`):
```python
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id
from database import get_supabase
from models.schemas import ExchangeRequest, KeyStatusResponse
from services.openrouter_service import exchange_code
from services.crypto_service import encrypt_key

router = APIRouter(prefix="/api/keys", tags=["keys"])
```

**Auth pattern — every endpoint** (verbatim from `threads.py` / `demo.py`):
```python
async def exchange(body: ExchangeRequest, user_id: str = Depends(get_user_id)) -> dict:
```
`Depends(get_user_id)` returns the JWT `sub` (binds the key to `auth.uid()` server-side — Pitfall 2 mitigation). No additional token check; reuse verbatim (`backend/auth.py:17-49`).

**Service-role DB write — upsert** (mirror `threads.py:23-30` insert + RESEARCH Pattern 1):
```python
db = get_supabase()                                    # service-role, bypasses RLS + REVOKE
db.table("user_api_keys").upsert({
    "user_id": user_id,
    "provider": "openrouter",
    "encrypted_key": encrypt_key(key),                 # crypto_service, Phase 9
    "key_label": masked,                               # non-secret last-4 tail, in-memory only
    "connected_at": <now-iso>,                         # set EXPLICITLY (Pitfall 4 — defaults don't re-stamp on conflict)
}).execute()
return {"connected": True}                             # NEVER returns the key
```

**Status read** (mirror `threads.py:33-44` `.maybe_single()` pattern):
```python
@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    db = get_supabase()
    row = (db.table("user_api_keys")
           .select("key_label, connected_at")
           .eq("user_id", user_id)
           .maybe_single()
           .execute())
    if not row.data:
        return {"connected": False}
    return {"connected": True, "masked_label": row.data["key_label"],
            "connected_at": row.data["connected_at"]}
```

**Delete** (mirror `threads.py:58-72` delete + `status_code=204`):
```python
@router.delete("", status_code=204)
async def disconnect(user_id: str = Depends(get_user_id)):
    get_supabase().table("user_api_keys").delete().eq("user_id", user_id).execute()
```

**Error handling — exchange leak guard (Pitfall 1 / SEC-01):** The exchange handler must catch `httpx.HTTPStatusError` from `exchange_code` and re-raise a generic `HTTPException` whose `detail` is a fixed string — **never** `resp.text` (it can contain `sk-or-v1-…`). Contrast with `threads.py:45` which safely echoes a static `"Thread not found"` detail. Do NOT add `exc_info=True` on the OpenRouter response.

---

### `backend/services/openrouter_service.py` (service, request-response)

**Analog:** `backend/services/budget_service.py::fetch_model_context_length` (lines 83-106) — the only live `httpx → openrouter.ai` pattern.

**httpx outbound pattern** (mirror `budget_service.py:89-106`; switch `.get` → `.post`):
```python
import httpx

def exchange_code(code: str, code_verifier: str) -> str:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/auth/keys",
        json={"code": code, "code_verifier": code_verifier,
              "code_challenge_method": "S256"},
        timeout=15,
    )
    resp.raise_for_status()        # 400/403/500 → HTTPStatusError; caller wraps generically
    return resp.json()["key"]      # response: {key, user_id?}
```

**Key divergence from the analog:** `budget_service` swallows every exception into a `logger.warning(...)` + `None` return (lines 104-106). The exchange must **NOT** copy that — it must let `HTTPStatusError` propagate so `keys.py` can map it to a 502, and it must **NEVER** log `resp.text`/`resp.json()` (the body holds the key — Pitfall 1). Synchronous `httpx.post` inside an `async def` router is the established codebase norm (`budget_service` does exactly this) — do not introduce `httpx.AsyncClient`.

---

### `backend/models/schemas.py` (model, transform) — MODIFIED

**Analog:** the existing `*Create` / `*Response` classes in the same file (lines 21-46).

**Add two models** (mirror `ThreadCreate`/`ThreadResponse` style — `str | None = None`, `*Request`/`*Response` suffix):
```python
class ExchangeRequest(BaseModel):
    code: str
    code_verifier: str

class KeyStatusResponse(BaseModel):
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None
```
Conventions to match (from same file): `BaseModel` import already present (line 1); `str | None` union (not `Optional`); no validators needed. `connected_at` is typed `str` (not `datetime`) so the status response passes the stored timestamp through as-is for FE date formatting.

---

### `backend/main.py` (config, event-driven) — MODIFIED

**Analog:** the `demo` registration in the same file (lines 9, 68).

**Two-line change** (mirror exactly):
```python
from routers import threads, chat, documents, folders, demo, keys   # add `keys` (line 9)
...
app.include_router(keys.router)                                       # after demo.router (line 68)
```
No CORS change (RESEARCH: exchange POST is same-origin, already in `settings.cors_origins_list`). No new middleware.

---

### `supabase/migrations/20240301000028_<name>.sql` (migration, batch DDL) — NEW

**Analog:** `supabase/migrations/20240301000025_create_user_api_keys.sql` (the table being altered).

**Next free number:** `20240301000028` (latest applied is `…027`; see `supabase/migrations/` — `…025/026/027` are the Phase 9 set).

**Pattern — additive `ALTER TABLE` only** (do NOT recreate the table; `…025` already shipped to dev/prod):
```sql
-- Phase 10 — add explicit connected_at for "Connected since {date}" (KEY-03).
-- key_label (the masked tail display column) ALREADY EXISTS from migration 025 — DO NOT re-add.
-- Additive + nullable: forward-compatible with the live (empty) table.
ALTER TABLE user_api_keys
  ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ;
```

**Hard constraints carried from `…025` + Pitfall 6 (do NOT regress):**
- Do **NOT** add `GRANT SELECT ON user_api_keys TO authenticated` (line 53 of `…025` REVOKE'd it on purpose).
- Do **NOT** touch RLS policies (`…025` lines 29-46) or the FROM-allowlist (`…026/027`).
- Do **NOT** edit migrations `025/026/027` to "add" the column — they are already applied; a forward `028` is the only mechanism (RESEARCH Anti-Patterns + STATE.md lesson).
- The masked label lives in the same row as `encrypted_key` → keep the WHOLE table out of `sql_service.py::ALLOWED_SQL_TABLES` (`frozenset({"threads","messages","documents","document_chunks"})`, line 17 — must stay unchanged).

---

### `backend/tests/test_keys_*.py` (test, request-response) — NEW

**Analog:** `backend/tests/test_demo_bootstrap.py` (the exact TestClient + dep-override + patch pattern RESEARCH prescribes).

**TestClient + dependency-override + patch skeleton** (verbatim shape from `test_demo_bootstrap.py:59-89`):
```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from auth import get_user_id
from main import app

def test_exchange_upserts_and_hides_key():
    mock_db = MagicMock()
    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db), \
             patch("routers.keys.exchange_code", return_value="sk-or-v1-PLAINTEXTwXyZ") as m_ex, \
             patch("routers.keys.encrypt_key", return_value="ciphertext") as m_enc:
            resp = TestClient(app).post("/api/keys/openrouter/exchange",
                                        json={"code": "c", "code_verifier": "v"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "sk-or-v1" not in resp.text          # key NEVER in response (SEC-01)
    m_enc.assert_called_once()                   # encrypt was applied before upsert
```
Match these conventions from the analog: patch the names **as imported into `routers.keys`** (`patch("routers.keys.get_supabase")`, not `database.get_supabase`); always `app.dependency_overrides.clear()` in a `finally`; assert on `resp.text` for the key-absence (SEC-01) check. Files to create per RESEARCH §Wave 0 Gaps: `test_keys_exchange.py`, `test_keys_status.py`, `test_keys_delete.py`. Keep `test_sql_keys_lockdown.py` (Phase 9) green.

---

### `frontend/src/lib/pkce.ts` (utility, transform) — NEW — NO IN-REPO ANALOG

**No codebase analog.** This is the single genuinely-new logic file. Source pattern is RESEARCH.md §Pattern 3 (OpenRouter's own Web Crypto example). Conventions to follow from sibling `lib/` files (`api.ts`, `supabase.ts`): named exports only (no default export), `camelCase` function names, no React import, 2-space indent, single quotes, no semicolons.

```typescript
// Source: openrouter.ai/docs/guides/overview/auth/oauth (RESEARCH Pattern 3)
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
  const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64url(hash)
}
```
Store `{verifier, state}` in `sessionStorage` (NOT `localStorage` — D-07 + CSRF binding). See Shared Pattern "PKCE Connect + Callback" below for the call sites.

---

### `frontend/src/lib/sentry.ts` (config, event-driven) — MODIFIED

**Analog:** the existing `beforeSend`/`beforeBreadcrumb` in the same file (lines 36-70).

**Extend, do NOT rewrite.** Add a `sk-or-v1-…` regex rule beside the existing Authorization/JWT rules:
```typescript
const OR_KEY = /sk-or-v1-[A-Za-z0-9_-]+/g
const scrub = (s: unknown): unknown =>
  typeof s === 'string' ? s.replace(OR_KEY, '[redacted-key]') : s
```
**Apply across (mirror where the existing rules already hook in):**
- `beforeSend` (currently lines 36-49): scrub `event.message`, each `event.exception.values[].value`, and `event.request.url` — alongside the existing Authorization-header redaction (lines 38-44).
- `beforeBreadcrumb` (currently lines 50-70): scrub `breadcrumb.message` and stringy `breadcrumb.data` fields — alongside the existing `sb-…-auth-token` console drop (lines 62-68).

The existing file already proves the pattern (Authorization redaction + `/sb-[^-]+-auth-token/` console-breadcrumb drop). This is purely additive — one more regex.

---

### `frontend/src/hooks/useKeyStatus.ts` (hook, request-response) — NEW

**Analog:** `frontend/src/hooks/useDocuments.ts::loadDocuments` (lines 27-43).

**Fetch-into-state pattern** (mirror `useDocuments` exactly — session gate, `apiFetch`, silent-on-error catch, loading flag, `useEffect` kickoff):
```typescript
import { useState, useCallback, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface KeyStatus { connected: boolean; masked_label?: string; connected_at?: string }

export function useKeyStatus() {
  const [status, setStatus] = useState<KeyStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const { session } = useAuth()                       // gate on session, like useDocuments
  const refresh = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try { setStatus(await apiFetch('/api/keys/status')) }
    catch { /* preserve silent-on-error, like useDocuments loadDocuments */ }
    finally { setLoading(false) }
  }, [session])
  useEffect(() => { refresh() }, [refresh])
  return { status, loading, refresh }
}
```
Conventions matched: named export (`export function useKeyStatus`), `{ ... }` destructured return (like `useDocuments` returns), `useCallback([session])` gating, silent catch. **Do NOT poll** (UI-SPEC §Surface 3) — fetch once on mount, call `refresh()` after connect/disconnect. Unlike `useDocuments`, NO Supabase Realtime subscription (status changes only via the user's own connect/disconnect).

---

### `frontend/src/pages/SettingsPage.tsx` (component, request-response) — NEW

**Analogs:** `frontend/src/pages/ChatPage.tsx` (page-in-`AuthenticatedLayout` shell + `default export`) + `ConfirmDialog` consumer pattern + `useToast`.

**Page shell + default export** (mirror `ChatPage.tsx:17,70-71` — rendered inside `AuthenticatedLayout`, root `flex-1 bg-gray-950 text-white`):
```typescript
export default function SettingsPage() {
  const { status, loading, refresh } = useKeyStatus()
  // ... bg-gray-950 page, bg-gray-900 max-w-md rounded-lg p-6 card (per UI-SPEC Surface 1)
}
```

**Disconnect → ConfirmDialog** (consume the existing component — props verbatim from `ConfirmDialog.tsx:5-12`; copy locked by D-08 / UI-SPEC Copywriting):
```tsx
<ConfirmDialog
  heading="Disconnect OpenRouter?"
  body="You'll need to reconnect to chat with your own key."
  confirmLabel="Disconnect"
  cancelLabel="Cancel"
  onConfirm={async () => { await apiFetch('/api/keys', { method: 'DELETE' }); refresh() }}
  onCancel={() => setConfirmOpen(false)}
/>
```

**Connect handler:** see Shared Pattern "PKCE Connect + Callback" below.

**Loading guard (UI-SPEC):** while `loading`, render the inline `animate-spin` ring (Shared Pattern "Inline Spinner") — do NOT flash the not-connected CTA before status resolves. Color/copy/spacing tokens are fully specified in `10-UI-SPEC.md` §Surface 1 — follow that contract.

---

### `frontend/src/pages/OAuthCallbackPage.tsx` (component, request-response state machine) — NEW

**Analogs:** `useDocuments.ts` (apiFetch + try/catch shape) + `ToolCallCard.tsx` spinner (lines 121/168) + `useToast` + `react-router` `useNavigate`.

**One-shot exchange state machine** (RESEARCH Code Examples "Callback exchange flow" + D-05/06/07):
```typescript
const params = new URLSearchParams(window.location.search)
const code = params.get('code'); const returnedState = params.get('state')
const verifier = sessionStorage.getItem('or_pkce_verifier')
const storedState = sessionStorage.getItem('or_pkce_state')
try {
  if (!code || !verifier || returnedState !== storedState) throw new Error('state')  // CSRF check (Pitfall 2)
  await apiFetch('/api/keys/openrouter/exchange', {
    method: 'POST', body: JSON.stringify({ code, code_verifier: verifier }),
  })
  sessionStorage.removeItem('or_pkce_verifier'); sessionStorage.removeItem('or_pkce_state')
  showToast('OpenRouter connected.', 'success')   // useToast 'success' variant
  navigate('/settings', { replace: true })
} catch {
  setState('failure')   // renders the HARD-CODED D-06 sentence — never the error (Pitfall 1)
}
```

**Spinner (in-flight state)** — reuse the inline `animate-spin` ring (see Shared Pattern below).

**Critical conventions:** read `verifier`/`state` from `sessionStorage` (NOT React state — Pitfall 3, hard-refresh = success); failure branch renders the locked sentence only ("Couldn't connect your OpenRouter account — please try again.") — never interpolate the caught error (Pitfall 1 / D-06). Wrap in `ProtectedRoute` (RESEARCH Open Question 2 recommendation — session must survive the round-trip for the bearer'd exchange POST). UI states/tokens fully specified in `10-UI-SPEC.md` §Surface 4.

---

### `frontend/src/App.tsx` (route, event-driven) — MODIFIED

**Analog:** the existing `/documents` `<Route>` block in the same file (lines 36-45).

**Add two routes** — mirror the `/documents` block (Protected + `AuthenticatedLayout` for `/settings`):
```tsx
<Route path="/settings" element={
  <ProtectedRoute><AuthenticatedLayout><SettingsPage /></AuthenticatedLayout></ProtectedRoute>
} />
<Route path="/settings/openrouter/callback" element={
  <ProtectedRoute><OAuthCallbackPage /></ProtectedRoute>   // callback is bare (no sidebar) per UI-SPEC Surface 4; Protected per RESEARCH Q2
} />
```
Imports mirror existing page imports (lines 5-8): `import SettingsPage from './pages/SettingsPage'`, `import OAuthCallbackPage from './pages/OAuthCallbackPage'`. `ProtectedRoute` + `AuthenticatedLayout` already in scope.

---

### `frontend/src/components/IconSidebar.tsx` (component, event-driven) — MODIFIED

**Analog:** the Documents `<button>` in the same file — present in BOTH the desktop rail (lines 23-29) and `IconNavRow` (lines 80-86). Add the gear to BOTH.

**Gear nav button — identical footprint to Documents** (mirror lines 23-29; add `Settings` to the lucide import on line 1):
```tsx
const isSettings = location.pathname === '/settings'
...
<button
  onClick={() => navigate('/settings')}
  className={`p-2 rounded mb-2 ${isSettings ? 'bg-gray-800 text-white' : 'text-gray-500 hover:text-white'}`}
  title="Settings"
>
  <Settings size={20} />
</button>
```
Placement (UI-SPEC Surface 2): immediately after the Documents button, before the `<div className="flex-1" />` spacer (line 30 desktop / line 87 `IconNavRow`). In `IconNavRow` drop the `mb-2` to match its siblings (lines 73-86 use `p-2 rounded` without `mb-2`). Active state `bg-gray-800` (NOT blue — UI-SPEC Color).

---

### `frontend/src/components/MobileTopBar.tsx` (component, request-response) — MODIFIED

**Analog:** the `DemoPill` right-slot in the same file (lines 33-35).

**Connection dot, LEFT of DemoPill** (UI-SPEC Surface 3 — `h-2 w-2 rounded-full`, green/gray, distinct from DemoPill):
```tsx
// consume useKeyStatus(); render an 8px dot with aria-label
<span
  role="status"
  aria-label={connected ? 'OpenRouter connected' : 'OpenRouter not connected'}
  className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-500'}`}
/>
```
Mirror the `DemoPill`'s `role="status"` + `aria-label` non-interactive badge convention (`DemoPill.tsx:11-19`). Place the dot in the existing right region next to (left of) `<DemoPill />` so demo-identity and key-state read as two distinct signals (UI-SPEC Surface 3). Desktop chat dot anchor is planner discretion (RESEARCH Open Question; `ChatContainer`/`ThreadSidebar` seam) — the contract is "visible on the chat route, distinct from DemoPill."

---

## Shared Patterns

### Auth (every backend `keys.py` endpoint)
**Source:** `backend/auth.py:17-49` (`get_user_id`), consumed via `Depends(get_user_id)` exactly as in `threads.py` / `demo.py`.
**Apply to:** all three `keys.py` handlers.
```python
async def handler(..., user_id: str = Depends(get_user_id)):
```
Returns the JWT `sub`; binds every write/read/delete to `auth.uid()`. No per-endpoint token logic — reuse verbatim.

### Service-role DB access (backend writes to `user_api_keys`)
**Source:** `backend/database.py:5-7` (`get_supabase()`), used as in `threads.py` / `demo.py`.
**Apply to:** `keys.py` exchange (upsert), status (select+`maybe_single`), delete.
The service-role client bypasses RLS **and** the `REVOKE SELECT … FROM authenticated` on `user_api_keys` — it is the ONLY sanctioned path to this table. The frontend must NEVER read it via `@supabase/supabase-js`.

### `apiFetch` (every frontend → backend call)
**Source:** `frontend/src/lib/api.ts:26-42`.
**Apply to:** `useKeyStatus` (GET status), `SettingsPage` disconnect (DELETE), `OAuthCallbackPage` exchange (POST).
Attaches the Supabase bearer automatically, sets `Content-Type: application/json` for non-FormData bodies, throws on non-2xx, returns `null` for 204 (use for the DELETE). Reuse — do not hand-roll `fetch`.

### Inline spinner (callback in-flight + settings loading)
**Source:** `frontend/src/components/ToolCallCard.tsx:121` (and `:168`).
**Apply to:** `OAuthCallbackPage` in-flight state, `SettingsPage` loading guard.
```tsx
<span className="border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
```
No SVG component, no spinner library (UI-SPEC §Reused primitives). Size per UI-SPEC (~24px callback, smaller for settings line).

### Success toast (connect)
**Source:** `frontend/src/contexts/ToastContext.tsx` — `useToast()`, `'success'` variant (green ramp, `aria-live`, auto-dismiss 4000ms).
**Apply to:** `OAuthCallbackPage` happy path: `showToast('OpenRouter connected.', 'success')`. Reused unmodified.

### Confirm dialog (disconnect)
**Source:** `frontend/src/components/ConfirmDialog.tsx` (portal, Escape-to-cancel, click-outside, red confirm).
**Apply to:** `SettingsPage` Disconnect. Props already match D-08 copy verbatim. Reused unmodified.

### PKCE Connect + Callback (the OAuth round-trip)
**Source:** `frontend/src/lib/pkce.ts` (NEW) + RESEARCH Code Examples "Frontend Connect init".
**Apply to:** `SettingsPage` Connect handler (init) + `OAuthCallbackPage` (return).
```typescript
// Connect (SettingsPage):
const verifier = randomString(64); const state = randomString(32)
const challenge = await challengeFromVerifier(verifier)
sessionStorage.setItem('or_pkce_verifier', verifier)
sessionStorage.setItem('or_pkce_state', state)
const callback = `${window.location.origin}/settings/openrouter/callback`   // self-locating, no FE env var
window.location.assign(
  `https://openrouter.ai/auth?callback_url=${encodeURIComponent(callback)}`
  + `&code_challenge=${challenge}&code_challenge_method=S256&state=${state}`)
```
`sessionStorage` (not `localStorage`) is load-bearing: survives same-tab hard refresh (D-07) and tightens CSRF binding (Pitfall 2/3).

### Sentry `sk-or-v1-…` scrub (frontend half of SEC-01)
**Source:** `frontend/src/lib/sentry.ts` (extend `beforeSend`/`beforeBreadcrumb`).
**Apply to:** the one file. Backstops every other file — generic UI copy + backend generic errors are the primary defenses; the regex is the safety net. `/sk-or-v1-[A-Za-z0-9_-]+/g → '[redacted-key]'`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/lib/pkce.ts` | utility | transform | No PKCE/Web-Crypto code exists in the repo. Source is OpenRouter's official docs example (RESEARCH §Pattern 3). Follow sibling `lib/` file *conventions* (named exports, no React, camelCase) but the *logic* has no in-repo precedent. ~20 lines; the only genuinely-new code in the phase. |

---

## Metadata

**Analog search scope:** `backend/routers/`, `backend/services/`, `backend/models/`, `backend/tests/`, `backend/` (config/database/auth/main), `supabase/migrations/`, `frontend/src/lib/`, `frontend/src/hooks/`, `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/contexts/`
**Files scanned (read directly):** 19 — `demo.py`, `threads.py`, `budget_service.py`, `crypto_service.py`, `main.py`, `database.py`, `schemas.py`, `auth.py`, `config.py`, `sql_service.py`, `20240301000025_create_user_api_keys.sql`, `test_demo_bootstrap.py`, `App.tsx`, `sentry.ts`, `api.ts`, `IconSidebar.tsx`, `useDocuments.ts`, `ConfirmDialog.tsx`, `ToastContext.tsx`, `ProtectedRoute.tsx`, `MobileTopBar.tsx`, `ToolCallCard.tsx`, `DemoPill.tsx`, `ChatPage.tsx`
**Pattern extraction date:** 2026-06-19
