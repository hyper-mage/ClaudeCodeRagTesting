# Phase 14: Usage/Cost Display + Settings/Key-State UX - Pattern Map

**Mapped:** 2026-06-25
**Files analyzed:** 16 (4 backend modify, 3 backend test, 9 frontend modify/relocate)
**Analogs found:** 16 / 16 (all exact or strong — this is a "read + render + relocate" phase, so almost every analog is the file being extended or a sibling in the same codebase)

> This phase introduces no new architecture. The dominant pattern is **extend-in-place** plus **two thin new surfaces** (`GET /api/keys/balance`, `BalanceResponse`). The closest analog is usually the file itself (the pattern to follow is the existing handler/section right next to the edit). Where a file is genuinely new (`test_keys_balance.py`), the analog is the matching sibling test.

---

## File Classification

| File | Action | Role | Data Flow | Closest Analog | Match Quality |
|------|--------|------|-----------|----------------|---------------|
| `backend/routers/keys.py` | MODIFY (add `GET /balance`) | route | request-response (server-side proxy) | `keys.py` `/status` handler (`:76-93`) + `openrouter_service.exchange_code` (`:28-38`) | exact |
| `backend/models/schemas.py` | MODIFY (`usage` on `MessageResponse`; add `BalanceResponse`) | model | transform / serialization | `MessageResponse` (`:81-87`) + `KeyStatusResponse` (`:116-125`) | exact |
| `backend/config.py` | MODIFY (add `low_balance_threshold_usd`) | config | config | `model_cache_ttl_seconds` (`:51`) / `budget_safety_margin` (`:158`) | exact |
| `backend/routers/chat.py` | MODIFY (add `forbidden` 403 branch) | route | streaming (SSE error) | the 402 branch in the same `APIStatusError` handler (`:1207-1229`) | exact |
| `backend/tests/test_keys_balance.py` | NEW | test | request-response | `backend/tests/test_keys_status.py` (`:17-76`) | exact (same endpoint family) |
| `backend/tests/test_thread_usage_exposed.py` | NEW | test | request-response | `test_keys_status.py` (TestClient+MagicMock) + `test_usage_capture.py` `_done_payload` (`:242-252`) | role-match |
| `backend/tests/test_error_surfacing.py` | MODIFY (add `test_forbidden_code_on_403`) | test | streaming | `test_429_402_distinct_codes` in same file (`:146-166`) | exact |
| `frontend/src/hooks/useKeyStatus.ts` | MODIFY (balance fetch + derived `low`) | hook | request-response | `useKeyStatus.refresh` (`:34-44`) + broadcast contract (`:20-22, 52-56`) | exact |
| `frontend/src/hooks/useChat.ts` | MODIFY (`usage` + `errorType` on `Message`) | hook | streaming (SSE) | `done` branch (`:231-237`) + `error` branch (`:238-243`) + `loadMessages` map (`:58-61`) | exact |
| `frontend/src/components/MessageBubble.tsx` | MODIFY (cost caption) | component | render | bubble flex column + tool-toggle caption (`:16-31`) | exact |
| `frontend/src/components/ChatContainer.tsx` | MODIFY (Σ total; pass usage; typed error bubble) | component | render | header row (`:72-87`) + message map / `ErrorMessageBubble` render (`:116-129`) | exact |
| `frontend/src/components/ErrorMessageBubble.tsx` | MODIFY (typed recovery variant) | component | event-driven (button actions) | existing Retry button structure (`:15-42`) | exact |
| `frontend/src/components/IconSidebar.tsx` | MODIFY (amber dot state) | component | render | existing dot tri-logic (`:41-45`) | exact |
| `frontend/src/components/MobileTopBar.tsx` | MODIFY (amber dot state) | component | render | existing dot (`:35-39`) + `IconSidebar` dot | exact |
| `frontend/src/pages/SettingsPage.tsx` | MODIFY (3 sections; theme-aware; balance line) | page | request-response + render | existing OpenRouter section (`:36-95`) + `ChatContainer` theme tokens (`ChatContainer.tsx:68,73`) | exact |
| `frontend/src/pages/ChatPage.tsx` | MODIFY (remove temp `prefsControls` mounts) | page | render | `prefsControls` cluster (`:174-182`) + `footer` props (`:199, :219`) | exact |

**Relocated (mount-only, no internal change — D-06):** `DefaultModelSelector` (`<DefaultModelSelector value={defaultModel} onChange={setDefaultModel} models={models} />`, currently `ChatPage.tsx:176`) and `ThemeToggle` (`<ThemeToggle />`, currently `ChatPage.tsx:179`) move into `SettingsPage` sections. The components themselves are not edited.

---

## Pattern Assignments

### `backend/routers/keys.py` — ADD `GET /api/keys/balance` (route, request-response)

**Analog A — the no-key empty-row guard + masked-only return shape:** `keys.py:76-93` (`/status`)
```python
@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    row = (
        get_supabase()
        .table("user_api_keys")
        .select("key_label, connected_at")   # balance selects "encrypted_key" instead
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {"connected": False}
    ...
```
Copy the `.maybe_single().execute()` + `if not row or not row.data` empty-row guard verbatim. For balance, `select("encrypted_key")` and additionally require `isinstance(row.data, dict) and row.data.get("encrypted_key")` (the exact guard `chat.py:190` uses).

**Analog B — sync `httpx` call to OpenRouter + propagate-vs-generic error:** `openrouter_service.exchange_code` (`backend/services/openrouter_service.py:28-38`)
```python
resp = httpx.post(
    "https://openrouter.ai/api/v1/auth/keys",
    json={...},
    timeout=15,
)
resp.raise_for_status()  # non-2xx → HTTPStatusError
return resp.json()["key"]
```
Balance uses `httpx.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"}, timeout=15)` — the **sync httpx in an async handler** is the established norm (do not switch to `AsyncClient`).

**Generic-error mapping (security):** `keys.py:46-55` (the `exchange` handler)
```python
except httpx.HTTPStatusError:
    raise HTTPException(
        status_code=502,
        detail="Couldn't complete the OpenRouter connection.",   # FIXED string, never resp.text / str(e)
    )
```
For balance, catch `httpx.HTTPError`, log `logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")`, and raise `HTTPException(502, "Couldn't fetch the OpenRouter balance.")`. **Do NOT add `exc_info=True`** on this path (it could capture the Bearer header) — note `keys.py` deliberately omits it; this differs from `chat.py`'s error branches which DO use `exc_info` but only after `scrub_secrets` + the `_ScrubFilter` belt.

**Imports already present in `keys.py:24-33`** (add `from config import get_settings`, `from services.crypto_service import decrypt_key`, `from services.log_scrub import scrub_secrets`, and `BalanceResponse` to the schemas import):
```python
import httpx
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user_id
from database import get_supabase
from models.schemas import ExchangeRequest, KeyStatusResponse
from services.crypto_service import encrypt_key
from services.openrouter_service import exchange_code

router = APIRouter(prefix="/api/keys", tags=["keys"])
```

**`is_low` is computed server-side** (threshold never crosses to the browser): `remaining = data.get("limit_remaining")`; `is_low = remaining is not None and remaining < get_settings().low_balance_threshold_usd`. Return only `{connected, limit_remaining, is_low}` — never `resp.json()`, `resp.text`, or `data.label`.

---

### `backend/models/schemas.py` — `usage` on `MessageResponse` + new `BalanceResponse` (model, transform)

**Analog — `MessageResponse` (`:81-87`), the read-path fix:**
```python
class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    tools_used: list[dict] | None = None
    # ADD: usage: dict | None = None   ← FastAPI strips any field NOT declared here on history load
    created_at: datetime
```
This is **load-bearing**: `threads.get_thread` (`threads.py:55`) returns `{**thread.data, "messages": messages.data}` validated against `ThreadWithMessages.messages: list[MessageResponse]`. `select("*")` returns `usage` from the DB but FastAPI drops it unless declared. Mirror the optional-with-default style of `tools_used` exactly (`dict | None = None`).

**Analog — `KeyStatusResponse` (`:116-125`) for the new `BalanceResponse` shape:**
```python
class KeyStatusResponse(BaseModel):
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None
```
New model mirrors this `connected` + optional-fields style:
```python
class BalanceResponse(BaseModel):
    connected: bool
    limit_remaining: float | None = None  # null = pay-as-you-go (uncapped); D-04
    is_low: bool = False                   # server-computed; null remaining → never low
```
Use the modern `float | None` union (project rule — never `Optional`). Place it near the other Phase-10 key models (after `KeyStatusResponse`).

---

### `backend/config.py` — ADD `low_balance_threshold_usd` (config)

**Analog — plain typed defaults like `budget_safety_margin` (`:158`) and `Field`-validated `model_cache_ttl_seconds` (`:51`):**
```python
model_cache_ttl_seconds: int = Field(default=86400, ge=0)
budget_safety_margin: float = 0.05
```
Add a plain float (no `ge=` needed, though a `Field(default=1.00, ge=0)` matches the validated-numeric precedent):
```python
low_balance_threshold_usd: float = 1.00  # COST-03 / D-03; warn when limit_remaining < this
```
pydantic-settings is case-insensitive, so env `LOW_BALANCE_THRESHOLD_USD` maps to this field automatically (same as every other setting). It has a code default, so absence from `.env`/`.env.prod` is harmless — but per MEMORY.md dual-env discipline, set per-env if overriding.

---

### `backend/routers/chat.py` — ADD `forbidden` 403 branch (route, SSE error)

**Analog — the 402 branch inside the existing `APIStatusError` handler (`:1207-1229`):**
```python
except openai.APIStatusError as e:
    if e.status_code == 402:
        logger.warning(f"Chat payment-required: {scrub_secrets(str(e))}", exc_info=True)
        _mark_error_row(db, assistant_msg_id)
        yield _sse_error("payment_required", "This model needs credits. Connect your OpenRouter account or add credits.")
    else:
        logger.error(f"Chat upstream error: {scrub_secrets(str(e))}", exc_info=True)
        _mark_error_row(db, assistant_msg_id)
        yield _sse_error("upstream_error", "The model provider returned an error. Try again or pick another model.")
```
Add an `elif e.status_code == 403:` branch BEFORE the `else`, mirroring the 402 branch exactly: `logger.warning(... scrub_secrets ...)`, `_mark_error_row(db, assistant_msg_id)`, then `yield _sse_error("forbidden", <fixed copy>)`. **Note:** the SSE `error` payload carries the structured CODE; the FE selects locked UI-SPEC copy from the code (do not surface `detail` verbatim). `_sse_error` (`:80-89`) already wraps the detail in `scrub_secrets`. The ordering rule (`RateLimitError` caught before `APIStatusError`, `:1196`) is unaffected.

---

### `backend/tests/test_keys_balance.py` — NEW (test, request-response)

**Analog — `test_keys_status.py` (`:17-76`): the `MagicMock` + `patch("routers.keys.get_supabase")` + `dependency_overrides` pattern.**
```python
from unittest.mock import MagicMock, patch

def test_status_returns_masked_only() -> None:
    from fastapi.testclient import TestClient
    from auth import get_user_id
    from main import app

    mock_db = MagicMock()
    status_chain = mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    status_chain.execute.return_value = MagicMock(data={...})

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert "encrypted_key" not in resp.text   # ← SEC assertion to replicate for the key
```
For balance, additionally `patch("routers.keys.decrypt_key", return_value="sk-or-v1-FAKE")` and patch `httpx.get` (mirror `test_error_surfacing.py:122-127`'s `httpx.Response` construction). Cover the RESEARCH Test Map cases: `test_balance_returns_remaining`, `test_balance_no_key` (no OpenRouter call), `test_balance_null_uncapped` (`is_low False`), `test_balance_is_low`, `test_balance_provider_error_scrubbed` (assert no `sk-or-` in response/raised detail). Use the `select(...).eq(...).maybe_single().execute()` chain shape.

---

### `backend/tests/test_thread_usage_exposed.py` — NEW (test, request-response)

**Analog — `test_keys_status.py` TestClient pattern (for the GET) + `test_usage_capture.py:242-252` `_done_payload` extractor style (for parsing a known JSON shape).**
Build a `MagicMock` db where `threads.select...maybe_single().execute()` returns a thread row and `messages.select...order().execute()` returns rows that include a `usage` dict (mirror `_table` in `test_usage_capture.py:157-181`). Call `GET /api/threads/{id}` and assert the JSON for each message includes `usage` (the read-path fix). This directly proves Pitfall 1 is closed.

---

### `backend/tests/test_error_surfacing.py` — EXTEND (test, streaming)

**Analog — `test_429_402_distinct_codes` in the same file (`:146-166`):**
```python
def _status_error(status_code, message):
    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(status_code, request=req)
    cls = openai.RateLimitError if status_code == 429 else openai.APIStatusError
    return cls(message, response=resp, body=None)

def test_429_402_distinct_codes(monkeypatch):
    lines_402 = _drive_with_raising_stream(monkeypatch, _status_error(402, "payment required"))
    assert _sse_error_payload(lines_402)["error"] == "payment_required"
```
Add `test_forbidden_code_on_403`: drive `_drive_with_raising_stream(monkeypatch, _status_error(403, "forbidden"))` and assert `_sse_error_payload(lines)["error"] == "forbidden"`. Reuse the existing helpers `_drive_with_raising_stream` (`:70-107`), `_sse_error_payload` (`:110-119`), `_status_error` (`:122-127`) — no new scaffolding.

---

### `frontend/src/hooks/useKeyStatus.ts` — EXTEND for balance + derived `low` (hook, request-response)

**Analog — the existing `refresh` fetch-into-state + no-poll broadcast contract (`:20-22, 34-44, 52-56`):**
```typescript
const refresh = useCallback(async () => {
  if (!session) return
  setLoading(true)
  try {
    setStatus(await apiFetch('/api/keys/status'))
  } catch {
    // silent-on-error: keep last-known status
  } finally {
    setLoading(false)
  }
}, [session])
```
Add a sibling `GET /api/keys/balance` fetch following the SAME shape: gate on `session`, `apiFetch`, silent-on-error catch (keep last-known balance), set loading in `finally`. Surface `{ limit_remaining, is_low }` from the response (server already computed `is_low` — do NOT recompute against a FE threshold). Whether balance is a new field on `KeyStatus`/`useKeyStatus` or a sibling hook is the planner's call (D-50 discretion); either way preserve the `notifyKeyStatusChanged()` cross-instance broadcast (`:20-22`) and the `KEY_STATUS_EVENT` listener (`:52-56`). **Do NOT add polling or a Realtime subscription** — fetch on demand (settings open / after a turn). Extend the `KeyStatus` interface (`:5-9`) with the optional balance fields.

---

### `frontend/src/hooks/useChat.ts` — capture `done.usage` + typed `errorType` (hook, SSE)

**Analog A — the `done` branch (`:231-237`), currently swaps id only:**
```typescript
} else if (parsed.message_id) {
  setMessages(prev => prev.map(m =>
    m.id === assistantId ? { ...m, id: parsed.message_id } : m   // ADD: usage: parsed.usage ?? m.usage
  ))
}
```

**Analog B — the `error` branch (`:238-243`), currently throws a generic `Error`:**
```typescript
} else if (parsed.error !== undefined) {
  throw new Error(typeof parsed.error === 'string' ? parsed.error : 'Chat stream error')
}
```
For typed recovery (D-09), the error CODE (`parsed.error`: `no_api_key` / `payment_required` / `forbidden` / `rate_limit` / `upstream_error`) must reach the rendered bubble as a structured `errorType`, not just a thrown string. The outer `catch` (`:254-283`) sets `role: 'error'` on the placeholder — extend it to also stamp `errorType` so `ChatContainer` can pick the typed `ErrorMessageBubble` variant. **Do NOT display `parsed.detail` verbatim** (Pitfall 3) — the FE maps the code to UI-SPEC locked copy. Preserve the existing generic-failure toast ONLY for non-key stream errors (the typed 401/402/403 path is the in-thread bubble alone — no toast).

**Analog C — `loadMessages` map (`:58-61`), to make `usage` survive reload:**
```typescript
setMessages(data.messages.map((m: Record<string, unknown>) => ({
  ...m,
  toolsUsed: m.tools_used as ToolEvent[] | undefined,   // ADD: usage: m.usage as Usage | undefined
})))
```
**`Message` interface (`:25-32`)** gains `usage?: Usage` and `errorType?: 'no_api_key' | 'payment_required' | 'forbidden'`; add a `Usage` interface (`prompt_tokens?`, `completion_tokens?`, `total_tokens?`, `cost?`) exported alongside `ToolEvent` (`:15-23`).

---

### `frontend/src/components/MessageBubble.tsx` — ADD per-message cost caption (component, render)

**Analog — the bubble's flex column + the muted tool-toggle caption (`:16-31`):**
```typescript
<div className={`max-w-[70%] px-4 py-2 rounded-lg ${role === 'user' ? '...' : 'bg-gray-800 text-gray-100'}`}>
  {hasTools && (
    <button className="text-xs text-gray-500 hover:text-gray-300 mb-1">...</button>
  )}
  {role === 'assistant' ? (<div className="prose ...">...</div>) : content}
</div>
```
Add a caption row at the bottom of the assistant bubble's column (assistant role only — never user). Use the **muted caption token from UI-SPEC**: `text-xs text-gray-600 dark:text-gray-400 mt-1` (NOT `gray-500` on white — contrast guardrail). Format `${cost} · ${tokens} tok`; omit the cost segment + `·` when `usage.cost` is null/absent; render nothing when there is no `usage`. The component needs a new `usage?: Usage` prop on its `Props` (`:6-10`) — `ChatContainer` passes it down. Note: this bubble is currently dark-only (`bg-gray-800`, `prose-invert`); the cost caption must carry both `gray-600`/`gray-400` variants per the Phase 13 light-mode coherence bar.

---

### `frontend/src/components/ChatContainer.tsx` — Σ total + pass usage + typed error bubble (component, render)

**Analog A — the existing `h-12` thread-header row (`:72-87`):**
```typescript
{activeThreadId !== null && (
  <div className="shrink-0 h-12 flex items-center gap-2 px-3 border-b bg-gray-50 border-gray-200 dark:bg-gray-900 dark:border-gray-800">
    <span className="shrink-0 text-xs font-semibold text-gray-600 dark:text-gray-400">{THREAD_SELECTOR_COPY.heading}</span>
    <div className="max-w-xs flex-1"><ModelSelector .../></div>
  </div>
)}
```
Add the per-thread total into THIS SAME row (do not add a second row) with `ml-auto` to right-align: a muted caption `Σ ${total}`. Derive `const threadCost = messages.reduce((s, m) => s + (m.usage?.cost ?? 0), 0)` (D-02 persisted sum = source of truth); render only when `> 0`.

**Analog B — the message map + `ErrorMessageBubble` render (`:116-129`):**
```typescript
{messages.map(msg =>
  msg.role === 'error' ? (
    <ErrorMessageBubble key={msg.id} onRetry={onRetry} isStreaming={isStreaming} />
  ) : msg.role === 'notice' ? (
    <DeprecationNotice key={msg.id} content={msg.content} />
  ) : (
    <MessageBubble key={msg.id} role={msg.role} content={msg.content} toolsUsed={msg.toolsUsed} />
  )
)}
```
Pass `usage={msg.usage}` into `MessageBubble`; pass `type={msg.errorType}` (+ optional `demoEligible`) into the extended `ErrorMessageBubble`. The local `Message`/`ToolEvent` interfaces (`:8-22`) must be widened to include `usage` + `errorType` to match `useChat`'s exported types (or import them directly from `../hooks/useChat`).

---

### `frontend/src/components/ErrorMessageBubble.tsx` — typed recovery variant (component, event-driven)

**Analog — the existing red-wash container + single Retry button (`:15-42`):**
```typescript
interface Props { onRetry: () => void; isStreaming: boolean }

<div role="alert" className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100">
  <div className="flex items-start gap-2">
    <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
    <p className="text-sm leading-[1.5]">The assistant ran into a problem. ...</p>
  </div>
  <div className="mt-2">
    <button onClick={onRetry} disabled={isStreaming}
      className="inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50">
      <RotateCw size={14} /> Retry
    </button>
  </div>
</div>
```
Add a typed variant: accept `type?: 'no_api_key' | 'payment_required' | 'forbidden'` (+ `demoEligible?: boolean` defaulting false, + action callbacks `onReconnect`, and the `[Add credits ⇗]` link). Render the UI-SPEC locked sentence + mapped buttons per code:
- `no_api_key` → `Connect your OpenRouter account to keep chatting.` + `[Reconnect]` (primary `bg-blue-600`).
- `payment_required` → `Your key is out of credit (402).` + `[Add credits ⇗]` (primary, opens openrouter.ai credits `target="_blank" rel="noopener noreferrer"`) + `[Reconnect]` (secondary neutral).
- `forbidden` → `Your key was rejected (403).` + `[Reconnect]` (primary) + `[Use demo]` only when `demoEligible` (default false → `[Reconnect]` alone this phase).
Keep `role="alert"`, the red container, and the existing Retry button sizing (`px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold`). ADD light-mode tokens (`bg-red-50 border-red-300 text-gray-900`, icon `text-red-600`) — the container is dark-only today. Secondary button = neutral surface (`gray-700 hover:gray-600` dark / `gray-200 hover:gray-300` light, matching ConfirmDialog's cancel). The generic non-typed Retry path stays intact.

---

### `frontend/src/components/IconSidebar.tsx` + `MobileTopBar.tsx` — amber dot (component, render)

**Analog — `IconSidebar.tsx:41-45` (and the identical `MobileTopBar.tsx:35-39`):**
```typescript
<span
  role="status"
  aria-label={status?.connected ? 'OpenRouter connected' : 'OpenRouter not connected'}
  className={`h-2 w-2 rounded-full mb-2 ${status?.connected ? 'bg-green-500' : 'bg-gray-500'}`}
/>
```
Extend to a tri-state driven by the extended `useKeyStatus` `{ connected, isLow }`: not-connected → `bg-gray-500` dark / `bg-gray-400` light (`aria-label="OpenRouter not connected"`); connected + low → `bg-amber-500` (`aria-label="OpenRouter balance low"`); connected + OK/unknown → `bg-green-500` (`aria-label="OpenRouter connected"`). Keep `h-2 w-2 rounded-full role="status"`, no animation — only fill + `aria-label` change. Apply identically to both files (they share the pattern). `MobileTopBar` keeps its inline placement (`:35-39`); `IconSidebar` keeps the `mb-2`.

---

### `frontend/src/pages/SettingsPage.tsx` — grow to 3 sections + theme-aware (page, request-response + render)

**Analog A — the existing OpenRouter section + connected/no-key states (`:36-95`):** keep the connect/status/disconnect flow, masked label, `formatConnectedSince` helper (`:9-17`), and the `ConfirmDialog` disconnect (`:86-95`) AS-IS. Insert the NEW balance line + low-balance warning line directly under the `Connected since` line (`:56-60`), inside the `status?.connected` block.

**Analog B — theme-aware surface tokens from `ChatContainer.tsx:68, 73`** (the page is currently dark-only `bg-gray-950` / `bg-gray-900` at `:37-38`):
```typescript
// ChatContainer page wrapper (the light/dark token to copy):
<div className="flex-1 ... bg-white text-gray-900 dark:bg-gray-950 dark:text-white">
// ChatContainer card/header surface:
<div className="... bg-gray-50 border-gray-200 dark:bg-gray-900 dark:border-gray-800">
```
Rewrite the page wrapper (`:37`) to `bg-white text-gray-900 dark:bg-gray-950 dark:text-white` and the card (`:38`) to `bg-gray-50 dark:bg-gray-900`, applying muted `gray-600 dark:gray-400` to caption text. Add two new sections AFTER OpenRouter using the existing `h2 className="text-base font-semibold mt-6"` heading pattern (`:41`): **Default model** (mount the relocated `<DefaultModelSelector value={...} onChange={...} models={...}/>`) and **Theme** (heading row + `<ThemeToggle />`). The page must now own the `defaultModel` + `models` state that ChatPage previously held for these controls (or fetch `/api/preferences` + `/api/models` here, mirroring `ChatPage.tsx:59-90`).

**Balance/warning copy (UI-SPEC locked):** capped → `Balance: $${remaining}`; null → `Pay-as-you-go — no limit set`; loading → `Checking balance…`; failed → `Balance unavailable right now.`; low → `AlertTriangle` (lucide, 14px `amber-500`) + `Balance low: $${remaining} — add credits` in `amber-700` (light) / `amber-300` (dark). Caption typography (`text-xs`).

---

### `frontend/src/pages/ChatPage.tsx` — REMOVE temp `prefsControls` mounts (page, render)

**Analog — the temporary `prefsControls` cluster (`:174-182`) + its two `footer` consumers (`:199, :219`):**
```typescript
const prefsControls = (
  <div className="flex flex-col gap-3">
    <DefaultModelSelector value={defaultModel} onChange={setDefaultModel} models={models} />
    <div className="flex items-center justify-between">
      <span className="text-base font-semibold ...">Theme</span>
      <ThemeToggle />
    </div>
  </div>
)
// ...passed as footer={prefsControls} to ThreadSidebar (:199) and ThreadListContent (:219)
```
DELETE the `prefsControls` block, drop the `DefaultModelSelector` + `ThemeToggle` imports (`:6-7`), and **remove the `footer` prop entirely from both `ThreadSidebar` (`:199`) and `ThreadListContent` (`:219`)** — do NOT leave a dangling empty `footer={...}` wrapper (Pitfall 6). If `defaultModel`/`setDefaultModel` state (`:31`) is now only used by Settings, remove it here too (or keep `models` if still needed by the per-thread `ModelSelector`, which it is — `:209`). Keep the per-thread selector wiring (`:201-210`) untouched (D-07: it stays in the thread header). Verify `ThreadSidebar`/`ThreadListContent` tolerate an absent `footer` prop after removal.

---

## Shared Patterns

### Server-side key handling (decrypt in-memory, never return/log the key)
**Sources:** `backend/services/crypto_service.py:40-42` (`decrypt_key`), `backend/services/log_scrub.py:18-26` (`scrub_secrets`), `backend/routers/keys.py:46-55` (generic-error mapping).
**Apply to:** `keys.py` balance endpoint (and reinforced in `chat.py` 403 branch).
```python
# decrypt in-memory, this request only — never stashed, never returned to the FE
key = decrypt_key(row.data["encrypted_key"])
# on any provider error: generic detail + scrubbed log line, never resp.text / str(e) raw
logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")
raise HTTPException(502, "Couldn't fetch the OpenRouter balance.")
```
Return only `{connected, limit_remaining, is_low}`. Same chokepoint that `_resolve_key_and_model` (`chat.py:190-194`) and `_sse_error` (`chat.py:80-89`) use.

### FastAPI response-model field hygiene (the silent-strip trap)
**Source:** `backend/models/schemas.py:81-87` + `backend/routers/threads.py:55`.
**Apply to:** any field expected to survive a `response_model`-typed read. FastAPI drops undeclared fields even when the DB row carries them. Add `usage` to `MessageResponse`; cover with `test_thread_usage_exposed.py`.

### Hook fetch-into-state (gate on session, silent-on-error, no poll)
**Source:** `frontend/src/hooks/useKeyStatus.ts:34-44` (`refresh`) — itself modeled on `useDocuments.loadDocuments`.
**Apply to:** the balance fetch (and any new on-demand fetch). `apiFetch` (`frontend/src/lib/api.ts:26-42`) attaches the Supabase bearer and throws on non-2xx; the hook swallows to keep last-known state. The `notifyKeyStatusChanged()` broadcast (`useKeyStatus.ts:20-22, 52-56`) is the cross-instance refresh contract — preserve it; never add polling/Realtime for balance.

### Muted caption token (Phase 13 light-mode contrast guardrail)
**Source:** `MessageBubble.tsx:29` tool-toggle (`text-xs text-gray-500`) + UI-SPEC § Color lock.
**Apply to:** per-message cost line, per-thread Σ total, balance line. Use `text-xs text-gray-600 dark:text-gray-400` — **not** `gray-500` on white (borderline AA). Captions are 12px/400, never bold, never a heading.

### Locked copy keyed on the structured error CODE (not raw detail)
**Source:** `chat.py:_sse_error` (`:80-89`) emits `{error: <code>, detail: <fixed>}`; UI-SPEC § Copywriting Contract.
**Apply to:** `useChat` error branch + `ErrorMessageBubble` typed variant + the balance failure line. Map `parsed.error` (code) → UI-SPEC sentence; treat `detail` as log/fallback only. The numeric `(401)/(402)/(403)` in copy is the structured code, allowed; raw HTTP bodies / `sk-or-…` are never interpolated.

### Theme-aware surface tokens (class strategy, both themes)
**Source:** `ChatContainer.tsx:68` (page wrapper) + `:73` (card/header surface).
**Apply to:** `SettingsPage` (currently dark-only), the extended `ErrorMessageBubble`, and both status dots. Page `bg-white dark:bg-gray-950`, card `bg-gray-50 dark:bg-gray-900`, border `gray-200 dark:gray-800`. Every NEW/EXTENDED surface must carry both variants (Phase 13 coherence bar).

### Backend test scaffold (TestClient + MagicMock chain + dependency_overrides)
**Sources:** `test_keys_status.py:17-47` (REST endpoint), `test_error_surfacing.py:70-127` (SSE error driver + `_status_error`), `test_usage_capture.py:157-181, 242-252` (db `_table` mock + `_done_payload`).
**Apply to:** `test_keys_balance.py`, `test_thread_usage_exposed.py`, the new `test_error_surfacing` case. Patch `routers.keys.get_supabase` / `routers.chat.get_supabase`, patch `decrypt_key`, override `get_user_id`, clear `app.dependency_overrides` in `finally`, assert no `sk-or-`/`encrypted_key` in the response.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | None. Every Phase 14 file is either an extension of an existing file or has a direct sibling analog in the codebase. The two genuinely new artifacts — `GET /api/keys/balance` and `BalanceResponse` — closely mirror `keys.py`/`openrouter_service.py` and `KeyStatusResponse` respectively, and the OpenRouter `GET /api/v1/key` contract is fully cited in 14-RESEARCH.md § "OpenRouter `GET /api/v1/key` — Response Contract". |

The only thing with no in-repo precedent is the **outbound `GET https://openrouter.ai/api/v1/key`** call shape — but the httpx mechanics are identical to `exchange_code` (`POST .../auth/keys`), and the JSON response fields (`data.limit_remaining`, etc.) are specified in RESEARCH. The planner should treat RESEARCH § OpenRouter contract as the spec for that one external surface.

---

## Metadata

**Analog search scope:** `backend/routers/`, `backend/services/`, `backend/models/`, `backend/tests/`, `frontend/src/hooks/`, `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/lib/`.
**Files scanned (read in full or targeted):** `keys.py`, `config.py`, `models/schemas.py`, `routers/threads.py`, `routers/chat.py` (`:75-204`, `:1160-1249`), `services/crypto_service.py`, `services/log_scrub.py`, `services/openrouter_service.py`, `tests/test_keys_status.py`, `tests/test_error_surfacing.py`, `tests/test_usage_capture.py`, `hooks/useChat.ts`, `hooks/useKeyStatus.ts`, `components/ErrorMessageBubble.tsx`, `components/MessageBubble.tsx`, `components/ChatContainer.tsx`, `components/IconSidebar.tsx`, `components/MobileTopBar.tsx`, `pages/SettingsPage.tsx`, `pages/ChatPage.tsx`, `lib/api.ts`.
**Pattern extraction date:** 2026-06-25
