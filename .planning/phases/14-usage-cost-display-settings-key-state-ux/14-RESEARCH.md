# Phase 14: Usage/Cost Display + Settings/Key-State UX - Research

**Researched:** 2026-06-25
**Domain:** Read-side rendering of cost/usage + OpenRouter balance proxy + settings consolidation (React + FastAPI + Supabase)
**Confidence:** HIGH (most surface is locked by CONTEXT/UI-SPEC and verified against live code; the one external unknown — OpenRouter `GET /api/v1/key` shape — is now CITED from official docs)

## Summary

Phase 14 is overwhelmingly a **read + render + relocate** phase. The backend *capture* side is already shipped: Phase 11 sums OpenRouter `usage` (incl. `cost`) across the tool loop, persists it to `messages.usage` (JSONB, migration 029), and carries it on the `done` SSE event; the structured error taxonomy (`no_api_key` / `rate_limit` / `payment_required` / `upstream_error`) and the `mode:"demo"` signal already ride the SSE stream. Phase 10 shipped the `/settings` stub, `keys.py` (`exchange` / `status` / `DELETE`), masked label, `connected_at`, and `useKeyStatus`. Phase 13 shipped `DefaultModelSelector` + `ThemeToggle` mounted temporarily in `ChatPage`. Phase 9 shipped `crypto_service` (`decrypt_key`) and `log_scrub.scrub_secrets`. [VERIFIED: codebase]

The genuinely new work is small and well-scoped: (1) one new backend endpoint `GET /api/keys/balance` that decrypts the user's key server-side and proxies OpenRouter `GET /api/v1/key`, tolerating a null `limit_remaining`; (2) one new backend config field for the low-balance threshold; (3) **two plumbing gaps in the read path that must be closed** — `MessageResponse` does not currently expose `usage` (FastAPI strips it on history load) and `useChat` does not capture `usage` from the `done` event or carry an error *type*; (4) front-end render surfaces (cost line, per-thread total, balance line, amber dot, typed recovery bubble) and the settings relocation. [VERIFIED: codebase]

**Primary recommendation:** Add `usage` to `MessageResponse` first (it is the load-bearing read-path fix), add `GET /api/keys/balance` reusing the exact `keys.py`/`crypto_service`/`scrub_secrets` security pattern from Phase 10/11, compute `is_low` **server-side** so the threshold never crosses to the browser, and extend `useChat`'s `Message` + `done`/error handling with `usage` and `errorType` fields. Build every UI surface hand-rolled in Tailwind per the locked UI-SPEC — **do not** run `npx shadcn init` (deferred to Phase 15).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Cost display placement (COST-01, COST-04):**
- **D-01:** Per-message cost = an always-visible muted line under each assistant bubble (e.g. `$0.0021 · 1.2k tok`). Not hover-only. Read from `messages.usage` (persisted) and from the live `done` SSE event mid-stream.
- **D-02:** Per-thread running total lives in the thread header (e.g. `Σ $0.0142`), always visible. Computed by summing persisted `messages.usage.cost` across the thread so it is correct on reload — not a session-only live accumulator. (Live turn updates may add optimistically, but the source of truth is the persisted sum.)
- Display cost exactly as OpenRouter reports it (`usage.cost`), never recomputed client-side (ROADMAP SC#1 + Phase 11 D-04).

**Low-balance warning (COST-02, COST-03):**
- **D-03:** Threshold is configurable — a backend config field (e.g. `LOW_BALANCE_THRESHOLD_USD`, default `1.00`). Warn when remaining credit `< threshold`.
- **D-04:** Null `limit_remaining` (pay-as-you-go, no cap) → no warning. `GET /api/keys/balance` must tolerate null `limit_remaining` gracefully (ROADMAP SC#2).
- **D-05:** Warning surfaces two non-intrusive ways: (1) the always-visible header key indicator turns amber/warning-colored when low; (2) the settings page shows a clear warning line near the balance. No toast spam, no blocking banner.

**Settings page composition (PREF-01):**
- **D-06:** Move both the default-model control AND the theme toggle into the Settings page as proper sections; remove their temporary inline mounts (`ChatPage.tsx:176` `<DefaultModelSelector>`, `ChatPage.tsx:179` `<ThemeToggle>`). Settings sections: OpenRouter (tri-state key status + masked label + balance + disconnect) · Default model · Theme.
- **D-07:** The per-thread model selector STAYS in the thread header — it is a distinct control and does not move to Settings.
- **D-08:** Tri-state key status copy: `"Demo mode"` vs `"Your key: connected"` (+ masked label + `connected_since` + balance) vs `"No key — connect to chat"`. The `mode:"demo"` signal already rides the SSE/response from Phase 11 D-08 — read it, don't re-derive.

**Mid-chat key-failure recovery (PREF-01, SC#4):**
- **D-09:** Surface 401/402/403 as an in-thread `ErrorMessageBubble` with action button(s) keyed to the error type: `no_api_key`/401 → [Reconnect]; `payment_required`/402 → [Add credits ⇗] (link to OpenRouter) + [Reconnect]; 403 → [Reconnect] / [Use demo]. Persists in thread history, survives reload, reuses the existing structured error taxonomy (Phase 11 D-12) and the in-thread error component. NOT a toast or blocking modal.
- ⚠ `ErrorMessageBubble` currently only accepts `{ onRetry, isStreaming }` with a single generic retry button. P14 must extend it (or add a typed variant) to render error-type-specific copy + the mapped action buttons.

### Claude's Discretion
- Exact `LOW_BALANCE_THRESHOLD_USD` config field name + default value.
- `GET /api/keys/balance` response shape and the `useKeyStatus`/new-hook surface for balance.
- Settings-section ordering and visual layout; precise copy wording (NOTE: most copy is now LOCKED in 14-UI-SPEC § Copywriting Contract — defer to it).
- Whether per-thread total is a separate selector vs derived in `useChat`.
- Exact amber color token (NOTE: UI-SPEC locks `amber-500` dot / `amber-700` light text / `amber-300` dark text).
- Whether balance refresh-after-turn is debounced/cached.

### Deferred Ideas (OUT OF SCOPE)
- **Rich model picker** (favorites/pinning, key-gated selection that launches OAuth inline, demo banner UI) — Phase 15 (MODEL-08, KEY-05, SEC-03, DEMO-01/02).
- **Enabling `demo_fallback_enabled` in prod** — Phase 15, gated on SEC-03 / backlog 999.2.
- **Profile section on settings** (name/avatar beyond key/model/theme) — deferred unless a later requirement asks.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COST-01 | User sees the cost of each message (from OpenRouter `usage.cost`) | `messages.usage` JSONB persisted (Phase 11) + `done` event carry usage. **GAP:** `MessageResponse` must expose `usage`; `useChat.Message` must add `usage`; `MessageBubble` must render a caption row. (see Don't Hand-Roll, Pitfall 1) |
| COST-02 | User sees their OpenRouter account balance (via `GET /api/v1/key`) | New `GET /api/keys/balance` proxy; OpenRouter response shape CITED below (`data.limit_remaining`, `data.limit`, `data.usage`, `is_free_tier`). Reuse `decrypt_key` + `scrub_secrets` security pattern from `keys.py`. |
| COST-03 | User is warned when their balance is low | Server-computed `is_low` against `low_balance_threshold_usd` (config field); null `limit_remaining` → never low (D-04). Surfaces as amber dot (`IconSidebar`/`MobileTopBar`) + settings warning line. |
| COST-04 | User sees a running cost total per chat thread | Sum `usage.cost` across persisted assistant messages (same `usage` plumbing as COST-01); render `Σ ${total}` in the existing `ChatContainer` header row. Source of truth = persisted sum (D-02). |
| PREF-01 | User can access a settings/account page (key status, default model, theme, profile) | Grow `SettingsPage.tsx` (P10 stub); relocate `DefaultModelSelector` + `ThemeToggle` (D-06); add tri-state key copy (D-08); make page theme-aware. Profile editing explicitly deferred. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-message cost render | Browser/Client | — | Pure render of persisted `usage` + live `done` payload; no computation (cost shown as reported). |
| Per-thread total | Browser/Client | — | Derived sum over already-loaded message rows; D-02 says persisted sum is source of truth (no DB aggregate needed). |
| Balance fetch + key decrypt | API/Backend | Database | Key MUST be decrypted and used server-side only (SEC-01/SEC-02); the `sk-or-` value never crosses to the browser. The OpenRouter call originates on the backend. |
| Low-balance threshold + `is_low` | API/Backend | — | Threshold is a backend config field (D-03). Compute `is_low` server-side so the threshold value never ships to the client and the warning logic has one source of truth. |
| Settings page composition + relocation | Browser/Client | — | UI consolidation; `ThemeToggle`/`DefaultModelSelector` already call their own backend endpoints (`/api/preferences`). |
| `usage` exposure on history load | API/Backend | Database | `GET /api/threads/{id}` response is shaped by `MessageResponse`; FastAPI strips undeclared fields, so `usage` must be added to the schema (read path fix). |
| Mid-chat recovery bubble | Browser/Client | API/Backend | Backend already emits structured codes on the SSE `error` event; FE maps code → typed bubble. **403 currently maps to `upstream_error`, not a distinct code** — see Open Questions. |

---

## Standard Stack

This phase introduces **no new dependencies**. Every tool needed is already installed and in active use. [VERIFIED: codebase — backend/requirements.txt, frontend/package.json, CLAUDE.md]

### Core (already present — use these, add nothing)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | (transitive, used directly) | Backend → OpenRouter `GET /api/v1/key` proxy | Established norm for openrouter.ai calls in `openrouter_service.py` / `budget_service.py` (sync `httpx` inside async routers). [VERIFIED: codebase] |
| `cryptography` (Fernet/MultiFernet) | 46.0.5 | `decrypt_key()` for the stored BYOK key | Phase 9 `crypto_service`; never re-implement. [VERIFIED: codebase] |
| `pydantic` / `pydantic-settings` | 2.11.1 / 2.9.1 | `BalanceResponse` model + new `low_balance_threshold_usd` Settings field | CLAUDE.md rule: Pydantic for structured outputs. [VERIFIED: codebase] |
| `sse-starlette` | 2.2.1 | (read-only) the `done`/`error` SSE events already emitted | No change — FE consumes existing events. [VERIFIED: codebase] |
| `react` | ^19.2.4 | Render surfaces | — |
| `lucide-react` | ^0.577.0 | `AlertTriangle` (low-balance), `RotateCw` (reconnect), `ExternalLink` (add credits) icons | UI-SPEC icon library; `AlertTriangle` is the warning mark. [VERIFIED: codebase] |
| `react-markdown` | ^10.1.0 | (existing) assistant bubble rendering — unchanged | — |

### Supporting (existing components to reuse / extend)
| Asset | Location | Purpose | Action |
|-------|----------|---------|--------|
| `useKeyStatus` | `frontend/src/hooks/useKeyStatus.ts` | Key connection + (new) balance + derived `low` | EXTEND (or add sibling hook — Claude's discretion) |
| `useChat` | `frontend/src/hooks/useChat.ts` | Consumes `done`/`error` SSE | EXTEND `Message` with `usage` + `errorType`; capture `done.usage`; branch on structured codes |
| `ErrorMessageBubble` | `frontend/src/components/ErrorMessageBubble.tsx` | In-thread error | EXTEND with typed variant (D-09) |
| `MessageBubble` | `frontend/src/components/MessageBubble.tsx` | Assistant bubble | ADD per-message cost caption (assistant role only) |
| `ChatContainer` | `frontend/src/components/ChatContainer.tsx` | Header row + message list | ADD per-thread total to existing `h-12` header row; pass `usage` to `MessageBubble`; render typed `ErrorMessageBubble` |
| `SettingsPage` | `frontend/src/pages/SettingsPage.tsx` | Settings | GROW to 3 sections; make theme-aware |
| `ConfirmDialog`, `DefaultModelSelector`, `ThemeToggle` | `frontend/src/components/` | Reuse / relocate | REUSE (disconnect) / RELOCATE (D-06) |
| `crypto_service.decrypt_key` | `backend/services/crypto_service.py` | Decrypt BYOK key | REUSE in new balance endpoint |
| `log_scrub.scrub_secrets` | `backend/services/log_scrub.py` | SEC-01 scrub | REUSE on any logged error in the balance endpoint |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `GET /api/v1/key` (`limit_remaining`) | `GET /api/v1/credits` (`total_credits - total_usage`) | `/credits` returns the *actual* prepaid wallet balance and would be non-null for pay-as-you-go users — but COST-02 **locks** `/api/v1/key`, and `/credits` per current docs requires a **management key** (an OAuth-exchanged inference key likely 401s). Stay on `/api/v1/key`. [CITED: openrouter.ai/docs] |
| Server-computed `is_low` | FE computes `low` from a FE-exposed threshold | Exposing the threshold to the FE leaks a config value and duplicates the rule. Server-computed `is_low` keeps the threshold backend-only (D-03 intent). Recommend server-side. |
| Sync `httpx.get` in async handler | `httpx.AsyncClient` | Async is technically cleaner (non-blocking event loop), but the codebase norm is **sync httpx** (`exchange_code`, `budget_service`). On-demand, low-frequency, single-user fetch → blocking is negligible. Match the established sync pattern for consistency. |
| Per-thread total derived in `useChat` | Separate selector/util | Either is fine (Claude's discretion, D-02). Derived sum over loaded messages is simplest and survives reload because rows carry `usage`. |

**Installation:** None. `npm install` / `pip install` add nothing this phase.

**Version verification:** No new packages → no `npm view` needed. Existing versions confirmed from `CLAUDE.md` Technology Stack and `backend/requirements.txt` (pytest 8.4.2, pytest-asyncio 0.23.8). [VERIFIED: codebase]

---

## OpenRouter `GET /api/v1/key` — Response Contract

This is the one external unknown. Now CITED from official docs. [CITED: openrouter.ai/docs/api/api-reference/api-keys/get-current-key + openrouter.ai/docs/api/reference/limits]

**Request:** `GET https://openrouter.ai/api/v1/key` with header `Authorization: Bearer <the user's sk-or-… key>`.

**Response shape (top-level `data` wrapper):**
```json
{
  "data": {
    "label": "sk-or-v1-...abcd",
    "limit": null,
    "limit_remaining": null,
    "limit_reset": "monthly",
    "include_byok_in_limit": false,
    "usage": 12.34,
    "usage_daily": 0.50, "usage_weekly": 3.10, "usage_monthly": 8.00,
    "byok_usage": 0.0,
    "is_free_tier": false,
    "is_provisioning_key": false,
    "rate_limit": { "requests": 200, "interval": "10s", "note": "..." }
  }
}
```

**Field semantics for this phase:**
| Field | Type | Meaning | Phase 14 use |
|-------|------|---------|--------------|
| `data.limit_remaining` | number \| **null** | Remaining USD allowance under the key's spending cap; **null = uncapped** | The "balance" figure. Null → `Pay-as-you-go — no limit set`, no warning (D-04). |
| `data.limit` | number \| **null** | The cap; null = no cap | Context only; null reinforces uncapped. |
| `data.usage` | number | All-time credits consumed by the key (USD) | Not displayed this phase (cost-per-message comes from `usage.cost`, not this). |
| `data.is_free_tier` | boolean | Free-tier indicator | Not required this phase. |
| `data.rate_limit` | object | `{requests, interval, note}` | Not required this phase. |

**Computing "remaining" / detecting uncapped (D-04):**
- Remaining = `data.limit_remaining` **as reported** (never recompute).
- Uncapped ⇔ `data.limit_remaining is None` → render `Pay-as-you-go — no limit set`; `is_low = False` unconditionally.
- Low ⇔ `data.limit_remaining is not None and data.limit_remaining < low_balance_threshold_usd`.

⚠ **Important nuance (CITED + reasoned):** `/api/v1/key` reports the *key's spending-limit headroom*, **not** the account's prepaid wallet balance. OAuth-exchanged BYOK keys are typically minted **without a limit**, so `limit_remaining` will frequently be `null` for real users — meaning the balance line will usually show `Pay-as-you-go — no limit set` and the low-balance warning will rarely fire in practice. This is correct and intended per D-04, but the planner/executor and user should expect that the amber-warning path is the exception, not the norm. The actual wallet balance lives behind `/api/v1/credits` (management-key gated), which COST-02 deliberately does not use. [CITED: openrouter.ai/docs] [ASSUMED: that OAuth-minted keys default to null limit — verify against a live connected test key during execution]

---

## Architecture Patterns

### System Architecture Diagram

```
                         ┌───────────────────────────── BROWSER ─────────────────────────────┐
  user opens thread ───▶ │  useChat.loadMessages()                                            │
                         │     └─ GET /api/threads/{id} ──▶ (rows incl. usage) ──▶ Message[]  │
                         │            with usage:{cost,total_tokens}                           │
                         │                       │                                            │
  user sends message ──▶ │  useChat.sendMessage() │                                           │
                         │     └─ POST /messages (SSE) ── content_delta… ── done{usage,mode}  │
                         │            │                                  └─ error{error,detail}│
                         │            ▼                                         │              │
                         │   Message{ usage, errorType }                        ▼              │
                         │      ├──▶ MessageBubble ── cost caption  "$0.0021 · 1.2k tok"       │
                         │      ├──▶ ChatContainer header ── Σ sum(usage.cost) "Σ $0.0142"     │
                         │      └──▶ ErrorMessageBubble(typed) ── [Reconnect]/[Add credits ⇗]  │
                         │                                                                     │
  settings open / ─────▶ │  useKeyStatus.refresh() ─┬─ GET /api/keys/status  ─▶ {connected…}  │
  after a turn           │   (no poll, on-demand)   └─ GET /api/keys/balance ─▶ {limit_remaining, is_low}
                         │                                  │                                  │
                         │   status dot color ◀── connected? + is_low? ── amber/green/gray     │
                         └──────────────────────────────────┼──────────────────────────────────┘
                                                             ▼
                         ┌──────────────────────────── FASTAPI ──────────────────────────────┐
                         │  GET /api/keys/balance  (NEW)                                       │
                         │   1. Depends(get_user_id)                                           │
                         │   2. get_supabase().table("user_api_keys").select(encrypted_key)    │
                         │   3. decrypt_key(row.encrypted_key)   ← Phase 9, in-memory only      │
                         │   4. httpx GET /api/v1/key  Bearer <key>                             │
                         │   5. compute is_low vs settings.low_balance_threshold_usd            │
                         │   6. return {limit_remaining, is_low}  ← key/raw body NEVER returned  │
                         │      on non-2xx → generic detail (scrub_secrets), no body echo        │
                         └──────────────────────────────────┼──────────────────────────────────┘
                                                             ▼
                                          OpenRouter  GET /api/v1/key  →  { data: { limit_remaining, … } }
```

The cost data flow is the load-bearing insight: **`usage` must survive three hops** — DB row → `MessageResponse` (currently strips it) → `useChat.Message` (currently omits it) → `MessageBubble` prop (does not exist yet). All three must be added for COST-01/COST-04.

### Recommended File Touch Map (no new folders)
```
backend/
├── routers/keys.py            # ADD GET /api/keys/balance
├── config.py                  # ADD low_balance_threshold_usd: float = 1.00
└── models/schemas.py          # ADD usage to MessageResponse; ADD BalanceResponse
frontend/src/
├── hooks/useKeyStatus.ts      # ADD balance fetch + derived low (or sibling hook)
├── hooks/useChat.ts           # ADD usage + errorType to Message; capture done.usage; branch on codes
├── components/MessageBubble.tsx     # ADD per-message cost caption
├── components/ChatContainer.tsx     # ADD per-thread Σ total; pass usage; render typed error bubble
├── components/ErrorMessageBubble.tsx# EXTEND with typed recovery variant
├── components/IconSidebar.tsx       # recolor dot amber on is_low
├── components/MobileTopBar.tsx      # recolor dot amber on is_low
├── pages/SettingsPage.tsx           # GROW to 3 sections; theme-aware; balance line
└── pages/ChatPage.tsx               # REMOVE temp DefaultModelSelector + ThemeToggle mounts (lines ~174-182)
```

### Pattern 1: Server-side key proxy (mirror `keys.py` exactly)
**What:** New endpoint reads the encrypted key via the service-role client, decrypts in-memory, calls OpenRouter, returns only derived non-secret fields.
**When to use:** The balance endpoint.
```python
# Source: pattern mirrored verbatim from backend/routers/keys.py:38-93 + chat.py:_resolve_key_and_model [VERIFIED: codebase]
@router.get("/balance", response_model=BalanceResponse)
async def balance(user_id: str = Depends(get_user_id)):
    row = (
        get_supabase().table("user_api_keys")
        .select("encrypted_key").eq("user_id", user_id).maybe_single().execute()
    )
    if not row or not isinstance(row.data, dict) or not row.data.get("encrypted_key"):
        # No connected key → nothing to fetch. Match the status no-key shape.
        return BalanceResponse(connected=False)
    key = decrypt_key(row.data["encrypted_key"])   # in-memory, this request only
    try:
        resp = httpx.get(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        # NEVER echo resp.text / the key. Generic detail; scrub the log line.
        logger.warning(f"balance fetch failed: {scrub_secrets(str(e))}")
        raise HTTPException(status_code=502, detail="Couldn't fetch the OpenRouter balance.")
    data = resp.json().get("data", {})
    remaining = data.get("limit_remaining")        # None = uncapped (D-04)
    threshold = get_settings().low_balance_threshold_usd
    is_low = remaining is not None and remaining < threshold
    return BalanceResponse(connected=True, limit_remaining=remaining, is_low=is_low)
```
**Recommended `BalanceResponse`:**
```python
class BalanceResponse(BaseModel):
    connected: bool
    limit_remaining: float | None = None  # null = pay-as-you-go (uncapped)
    is_low: bool = False                   # server-computed; null remaining → never low
```

### Pattern 2: Expose `usage` on history load (the read-path fix)
**What:** Add `usage` to `MessageResponse`; map it in `loadMessages`.
**Why critical:** FastAPI serializes `ThreadWithMessages.messages` against `MessageResponse`. `select("*")` returns `usage` from the DB, but **FastAPI drops any field not declared on the response model.** Without this, per-message cost works live (via `done`) but vanishes on reload — breaking D-01/D-02's "survives reload" guarantee. [VERIFIED: codebase — schemas.py:81-87 has no `usage`; threads.py:55 returns `{**thread.data, "messages": messages.data}`]
```python
# Source: backend/models/schemas.py:81 [VERIFIED: codebase]
class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    tools_used: list[dict] | None = None
    usage: dict | None = None          # ← ADD: prompt/completion/total tokens + cost
    created_at: datetime
```
```typescript
// frontend/src/hooks/useChat.ts loadMessages map — ADD usage alongside the existing toolsUsed map
setMessages(data.messages.map((m: Record<string, unknown>) => ({
  ...m,
  toolsUsed: m.tools_used as ToolEvent[] | undefined,
  usage: m.usage as Usage | undefined,   // ← ADD
})))
```

### Pattern 3: Capture `done.usage` live + carry an error type
**What:** Two small edits in `useChat`'s SSE loop.
```typescript
// frontend/src/hooks/useChat.ts — the done branch (currently only swaps id, line ~231) [VERIFIED: codebase]
} else if (parsed.message_id) {
  setMessages(prev => prev.map(m =>
    m.id === assistantId
      ? { ...m, id: parsed.message_id, usage: parsed.usage ?? m.usage }  // ← capture usage
      : m))
}
// the error branch (currently throws the code as a generic Error, line ~238)
// must instead set a TYPED error message so ChatContainer renders the right recovery.
// parsed.error is the structured CODE ("no_api_key" | "payment_required" | "rate_limit"
// | "upstream_error"); parsed.detail is FIXED copy (do NOT display raw — use UI-SPEC copy).
```
**Message interface additions:**
```typescript
export interface Usage { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number; cost?: number }
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'error' | 'notice'
  content: string
  toolsUsed?: ToolEvent[]
  usage?: Usage                                   // ← ADD (COST-01/04)
  errorType?: 'no_api_key' | 'payment_required' | 'forbidden'  // ← ADD (D-09)
}
```

### Pattern 4: Per-thread total — derive, don't store
```typescript
// In ChatContainer (or useChat) — sum persisted usage.cost over assistant rows. D-02: persisted = source of truth.
const threadCost = messages.reduce((s, m) => s + (m.usage?.cost ?? 0), 0)
// Render only when > 0 (UI-SPEC: omit Σ $0.0000 for free/empty threads).
```

### Anti-Patterns to Avoid
- **Recomputing cost from tokens × price.** Show `usage.cost` exactly as reported (SC#1, D-01). Never multiply.
- **Returning the OpenRouter raw body (or the key) from `/balance`.** Return only `{connected, limit_remaining, is_low}`. The raw `data` carries `label` and other fields you don't need; don't pass them through. (SEC-01)
- **Exposing the threshold to the frontend.** Compute `is_low` server-side (D-03 keeps it a backend config field).
- **Firing a toast on the typed 401/402/403 path.** D-09 + UI-SPEC: the in-thread bubble is the single surface. The existing generic-failure toast stays only for non-key stream errors.
- **Running `npx shadcn init`.** UI-SPEC: deferred to Phase 15; hand-roll Tailwind.
- **Polling the balance.** UI-SPEC + REQUIREMENTS "Out of Scope": fetch on demand only (settings open / after a turn).
- **Leaving a dangling empty `prefsControls` wrapper** in `ChatPage`/sidebar footer/mobile drawer after relocating the controls (UI-SPEC consistency req).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cost figure | A tokens×price calculator | `usage.cost` as reported | OpenRouter already computes it incl. provider markup; recomputing drifts and violates SC#1. |
| Usage capture/sum | A new accumulator | `_accumulate_usage` + `messages.usage` (Phase 11) | Already sums across the tool loop and persists. P14 only reads. [VERIFIED: codebase] |
| Key decryption | Fernet calls | `crypto_service.decrypt_key()` | Phase 9 MultiFernet with rotation. [VERIFIED: codebase] |
| Secret scrubbing | A regex | `log_scrub.scrub_secrets()` + `_ScrubFilter` | SEC-01 chokepoint; broadened `sk-or-` regex already covers future prefixes. [VERIFIED: codebase] |
| Key connection state + cross-instance refresh | New state mgmt | `useKeyStatus` + `notifyKeyStatusChanged()` | Existing no-poll broadcast contract keeps the dot accurate. [VERIFIED: codebase] |
| Tri-state copy / colors / spacing | Ad-hoc strings & classes | 14-UI-SPEC § Copywriting + § Color (locked) | Every string and token is already locked; deviating fails the UI checker. |
| Disconnect confirm | New modal | `ConfirmDialog` (existing copy) | The only destructive action; reuse as-is. |
| Date formatting | New formatter | `formatConnectedSince` in `SettingsPage` | Existing `toLocaleDateString('en-US', …)`. [VERIFIED: codebase] |

**Key insight:** This phase's risk is not "build the wrong thing" — it's "re-plumb something Phase 11 already shipped" or "leak a key." Treat the backend usage path and the key-handling pattern as immutable; the work is rendering and one thin proxy.

---

## Common Pitfalls

### Pitfall 1: `MessageResponse` silently strips `usage` on history load
**What goes wrong:** Per-message cost shows live (from `done`) but disappears after reload; per-thread `Σ` total resets to nothing on reload — directly violating D-01/D-02 "survives reload."
**Why it happens:** FastAPI's `response_model` (`ThreadWithMessages.messages: list[MessageResponse]`) drops fields not declared on `MessageResponse`. The DB `select("*")` returns `usage`, but it never reaches the wire.
**How to avoid:** Add `usage: dict | None = None` to `MessageResponse` (Pattern 2). Add a test asserting `GET /api/threads/{id}` includes `usage`.
**Warning signs:** Cost line present mid-stream, gone after refresh. [VERIFIED: codebase — schemas.py:81-87]

### Pitfall 2: 403 has no distinct structured code today
**What goes wrong:** D-09 wants a 403 recovery bubble (`[Reconnect]` / `[Use demo]`), but `chat.py` only emits `no_api_key`, `rate_limit`, `payment_required`, and a catch-all `upstream_error` (the `APIStatusError` else branch). A real 403 currently arrives as `upstream_error`, so the FE can't key the 403 recovery copy.
**Why it happens:** Phase 11 D-12 taxonomy enumerated 401/402/429; 403 wasn't a distinct branch.
**How to avoid:** Add an `elif e.status_code == 403:` branch in `chat.py`'s `APIStatusError` handler emitting a `forbidden` code (mirror the 402 branch). Then map `forbidden` in `useChat`/`ErrorMessageBubble`. Small, surgical backend edit.
**Warning signs:** 403 from OpenRouter renders the generic error bubble instead of the 403 recovery actions. [VERIFIED: codebase — chat.py:1207-1229]

### Pitfall 3: Displaying the structured `detail` string instead of locked copy
**What goes wrong:** The SSE `error` event carries `detail` (e.g. "This model needs credits…"). Rendering it verbatim diverges from the UI-SPEC's locked recovery sentences and risks future drift.
**Why it happens:** It's tempting to show `parsed.detail` directly.
**How to avoid:** Use `parsed.error` (the CODE) to select the **UI-SPEC locked sentence + buttons**. Treat `detail` as a fallback/log only. The allowed numeric `(401)/(402)/(403)` in copy is the structured code, not a raw HTTP body.
**Warning signs:** Recovery bubble text doesn't match § Copywriting Contract.

### Pitfall 4: Key or raw OpenRouter body leaking from `/balance`
**What goes wrong:** Echoing `resp.text`, `resp.json()`, or the exception into the HTTP detail/logs exposes `data.label` (a masked-ish tail) or, worse, surfaces the key in a traceback.
**Why it happens:** Convenience error handling (`detail=str(e)`).
**How to avoid:** Fixed generic detail string; `scrub_secrets()` on any log line; return only `{connected, limit_remaining, is_low}`; never `exc_info=True` on the balance failure path that could capture the Bearer header. Mirror `keys.py:48-55` exactly.
**Warning signs:** `sk-or-` or a raw provider message appears in logs/response. [VERIFIED: codebase — log_scrub.py, keys.py docstring]

### Pitfall 5: `null` cost / free models breaking the cost line
**What goes wrong:** Free models report `usage.cost == null` (or absent). Rendering `$null` or `$0.0000 · …` clutters or misleads.
**Why it happens:** Assuming `cost` is always present.
**How to avoid:** Per UI-SPEC: when `usage.cost` is null/absent, omit the cost segment + the `·` separator, show `${tokens} tok` only; omit the `Σ` total entirely when summed cost is 0.
**Warning signs:** `$null`/`$0.0000` captions on free-model turns.

### Pitfall 6: Relocation leaves an empty wrapper / breaks light mode
**What goes wrong:** Removing the `ChatPage` `prefsControls` cluster leaves a dangling empty footer/drawer wrapper; or `SettingsPage` (currently `bg-gray-950`/`gray-900`, dark-only) shows an orphan dark panel in light mode now that the theme toggle lives inside it.
**Why it happens:** Partial relocation; the page predates the Phase 13 theme system.
**How to avoid:** Remove the wrapper cleanly; apply the core-surface palette (`bg-white dark:bg-gray-950`, card `bg-gray-50 dark:bg-gray-900`, muted `gray-600 dark` / `gray-400`… per UI-SPEC) to the whole page.
**Warning signs:** Empty box in the sidebar footer; dark panel bleeding through light theme. [VERIFIED: codebase — SettingsPage.tsx:37-38 dark-only; ChatPage.tsx:174-182, 199]

---

## Code Examples

### Per-message cost caption (MessageBubble, assistant only)
```typescript
// Caption row inside the existing bubble flex column. Muted token per UI-SPEC § Color.
// Format: "${cost} · ${tokens} tok"; omit cost segment when usage.cost == null.
function CostLine({ usage }: { usage?: Usage }) {
  if (!usage) return null
  const tok = usage.total_tokens
  const tokStr = tok == null ? null : tok >= 1000 ? `${(tok / 1000).toFixed(1).replace(/\.0$/, '')}k` : `${tok}`
  const costStr = usage.cost != null ? `$${usage.cost.toFixed(4)}` : null
  const text = costStr && tokStr ? `${costStr} · ${tokStr} tok` : tokStr ? `${tokStr} tok` : null
  if (!text) return null
  return <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">{text}</p>
}
```

### Status-dot tri-state (IconSidebar + MobileTopBar)
```typescript
// Driven by extended useKeyStatus: { connected, isLow }. Only fill + aria-label change.
// Source pattern: IconSidebar.tsx:42-44 / MobileTopBar.tsx:36-38 [VERIFIED: codebase]
const dot = !connected
  ? { cls: 'bg-gray-500 dark:bg-gray-500', label: 'OpenRouter not connected' }   // light uses gray-400 per UI-SPEC
  : isLow
  ? { cls: 'bg-amber-500', label: 'OpenRouter balance low' }
  : { cls: 'bg-green-500', label: 'OpenRouter connected' }
<span role="status" aria-label={dot.label} className={`h-2 w-2 rounded-full ${dot.cls}`} />
```

### Config field
```python
# backend/config.py — alongside the other Settings fields. pydantic-settings is
# case-insensitive, so env LOW_BALANCE_THRESHOLD_USD maps to this field. [VERIFIED: codebase pattern]
low_balance_threshold_usd: float = 1.00  # COST-03 / D-03; warn when limit_remaining < this
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Usage discarded when a response also had tool_calls | Drain + sum usage across every tool-loop iteration, persist to `messages.usage` | Phase 11 (migration 029) | P14 reads a complete per-turn cost; no capture work. [VERIFIED: codebase] |
| Single generic in-thread error bubble | Structured taxonomy on SSE `error` event (`no_api_key`/`rate_limit`/`payment_required`/`upstream_error`) | Phase 11 D-12 | P14 maps codes → typed recovery actions (needs a 403 branch added). [VERIFIED: codebase] |
| Default-model + theme mounted inline in ChatPage | Relocated into SettingsPage sections | Phase 14 (this) | Fulfills Phase 13 D-04 ("temp spot until P14 absorbs it"). |

**Deprecated/outdated:**
- The temporary `prefsControls` cluster in `ChatPage.tsx:174-182` — removed this phase (D-06).
- OpenRouter docs URL `openrouter.ai/docs/api-reference/limits` 404s; the live path is `openrouter.ai/docs/api/reference/limits` and `…/api/api-reference/api-keys/get-current-key`. [VERIFIED: web]

---

## Runtime State Inventory

Not a rename/refactor/migration phase — but the D-06 relocation touches runtime mounts, so a brief check:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None new. `messages.usage` already populated by Phase 11; `low_balance_threshold_usd` is read-only config. | None — read only. |
| Live service config | `LOW_BALANCE_THRESHOLD_USD` is a NEW env var. Lives in `.env` (dev) + `.env.prod` (prod) — both untracked. Has a code default (`1.00`) so absence is harmless. | Optionally set in `.env`/`.env.prod`; default works if unset. Note dual-env discipline (MEMORY.md). |
| OS-registered state | None — verified, no scheduler/task changes this phase. | None. |
| Secrets/env vars | No new secret. `KEY_ENCRYPTION_SECRET` reused read-only via `decrypt_key`. | None. |
| Build artifacts | None — no package rename, no new dependency. | None. |

**Mount/state note:** Removing the `ChatPage` `prefsControls` mounts is a code edit only; the `DefaultModelSelector`/`ThemeToggle` persist their state through `/api/preferences` (Phase 13), so relocating the mount point does not lose any stored preference.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv | Backend (CLAUDE.md rule) | ✓ | `backend/venv/` | — |
| pytest | Backend tests | ✓ | 8.4.2 | — |
| pytest-asyncio | Async SSE tests | ✓ | 0.23.8 | — |
| httpx | Balance proxy | ✓ | (installed, used directly) | — |
| OpenRouter `/api/v1/key` | COST-02 live balance | ✓ (reachable; needs a connected test key) | — | Endpoint returns `Balance unavailable right now.` on failure (graceful) |
| Frontend test framework | FE render tests | ✗ | — | **No FE test framework configured** — verify cost line / settings / recovery bubble via browser MCP per CLAUDE.md Dev Flow step 3 |
| shadcn / Radix | (not used) | ✗ (intentionally) | — | Hand-roll Tailwind (UI-SPEC) |

**Missing dependencies with no fallback:** None block execution.

**Missing dependencies with fallback:**
- Frontend has **no test framework** (`frontend/package.json` has no test runner — confirmed in CLAUDE.md). All FE behavior (cost caption, `Σ` total, balance line, amber dot, typed recovery bubble, settings relocation, light/dark coherence) is verified manually via browser testing (CLAUDE.md mandates browser MCP validation). Backend behavior is unit-testable with pytest.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included. [VERIFIED: codebase]

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 + pytest-asyncio 0.23.8 (`asyncio_mode = auto`) — backend only |
| Config file | `backend/pytest.ini` (`testpaths = tests`, `--strict-markers`) |
| Quick run command | `backend/venv/Scripts/python -m pytest tests/test_keys_balance.py -x` (Windows venv) |
| Full suite command | `backend/venv/Scripts/python -m pytest` (from `backend/`) |
| Frontend | **No test framework** — browser MCP manual verification per CLAUDE.md |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COST-02 | `/balance` proxies OpenRouter, returns `limit_remaining`; key never in response | unit | `pytest tests/test_keys_balance.py::test_balance_returns_remaining -x` | ❌ Wave 0 |
| COST-02 | No connected key → `{connected:false}`, no OpenRouter call | unit | `pytest tests/test_keys_balance.py::test_balance_no_key -x` | ❌ Wave 0 |
| COST-02/03 | null `limit_remaining` → `is_low=false`, tolerated (D-04) | unit | `pytest tests/test_keys_balance.py::test_balance_null_uncapped -x` | ❌ Wave 0 |
| COST-03 | `limit_remaining < threshold` → `is_low=true` | unit | `pytest tests/test_keys_balance.py::test_balance_is_low -x` | ❌ Wave 0 |
| COST-02 | OpenRouter non-2xx → generic 502, no key/body leak (SEC-01) | unit | `pytest tests/test_keys_balance.py::test_balance_provider_error_scrubbed -x` | ❌ Wave 0 |
| COST-01/04 | `GET /api/threads/{id}` returns `usage` on each message (read-path fix) | unit | `pytest tests/test_thread_usage_exposed.py::test_get_thread_returns_usage -x` | ❌ Wave 0 |
| D-09 (PREF-01) | `chat.py` emits `forbidden` on a 403 (new branch) | unit | `pytest tests/test_error_surfacing.py::test_forbidden_code_on_403 -x` | ⚠ extend existing `test_error_surfacing.py` |
| COST-01 | Per-message cost caption renders ($/tok; omits cost on free model) | manual (no FE framework) | browser MCP | — |
| COST-04 | Per-thread `Σ` total survives reload | manual | browser MCP (send turn → reload → total persists) | — |
| COST-03 | Amber dot + settings warning line on low balance | manual | browser MCP | — |
| PREF-01 | Settings 3-section page, controls relocated, light+dark coherent | manual | browser MCP | — |
| D-09 | Typed recovery bubble (401/402/403) persists in thread | manual | browser MCP | — |

### Sampling Rate
- **Per task commit:** `backend/venv/Scripts/python -m pytest tests/test_keys_balance.py -x` (plus the touched file's tests)
- **Per wave merge:** `backend/venv/Scripts/python -m pytest` (full backend suite) + browser smoke of the FE surfaces
- **Phase gate:** Full backend suite green + browser verification of all six UI surfaces before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_keys_balance.py` — covers COST-02/COST-03 (proxy, no-key, null/uncapped, is_low, provider-error scrub). Mirror the `MagicMock` + `patch("routers.keys.get_supabase")` pattern in `test_keys_status.py`; patch `routers.keys.decrypt_key` and `httpx.get`.
- [ ] `backend/tests/test_thread_usage_exposed.py` — covers COST-01/COST-04 read path (assert `GET /api/threads/{id}` JSON includes `usage`).
- [ ] Extend `backend/tests/test_error_surfacing.py` — add `test_forbidden_code_on_403` for the new `forbidden` branch.
- Framework install: none — pytest already present.
- Frontend: no framework to install; manual browser verification is the contract (CLAUDE.md).

---

## Security Domain

> `security_enforcement` not present in config → treated as enabled. Section included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `Depends(get_user_id)` (JWT sub) on `/balance`; key bound to `auth.uid()` server-side, never request body. [VERIFIED: codebase pattern] |
| V3 Session Management | no | No new session surface; Supabase Auth unchanged. |
| V4 Access Control | yes | Per-user RLS on `messages`/`user_api_keys`; balance read via service-role client scoped by `user_id`; `MessageResponse.usage` inherits per-user RLS (no cross-user read). |
| V5 Input Validation | yes | `BalanceResponse` Pydantic model; no user-supplied input to `/balance` beyond the JWT; threshold is server config (not client-supplied). |
| V6 Cryptography | yes | Reuse `crypto_service` MultiFernet (`decrypt_key`) — never hand-roll. Key decrypted in-memory per request, never returned/logged. [VERIFIED: codebase] |
| V7 Error/Logging | yes | `scrub_secrets()` on all balance-path logs; generic detail on provider failure; no `exc_info` that could capture the Bearer header. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| BYOK key leak via balance endpoint (response/log) | Information Disclosure | Return only `{connected, limit_remaining, is_low}`; never echo `resp.text`/key; `scrub_secrets` log lines (SEC-01). [VERIFIED: codebase pattern] |
| BYOK key leak via SSE error / recovery copy | Information Disclosure | Display UI-SPEC locked copy keyed on the structured code, never raw `detail`/error body. Backend `_sse_error` already scrubs (SEC-01). [VERIFIED: codebase] |
| Cross-user usage/balance read | Information Disclosure / Elevation | RLS on `messages`; `/balance` scoped by `get_user_id()`; per-request key decrypt (no caching → no cross-user bleed, SEC-04). [VERIFIED: codebase] |
| Text-to-SQL reading the key table | Information Disclosure | SEC-02 lockdown (Phase 9): `encrypted_key` REVOKE'd from `authenticated`, table off the SQL allowlist — untouched here. [VERIFIED: codebase] |
| Threshold tampering from client | Tampering | `is_low` computed server-side from server config; client cannot influence it. |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OAuth-exchanged BYOK keys default to **no spending limit**, so `limit_remaining` is usually `null` and the balance line will typically read "Pay-as-you-go — no limit set" | OpenRouter contract | Low — D-04 handles null gracefully either way. If wrong, the warning fires more often (still correct behavior). Verify against a live connected test key during execution. |
| A2 | A 403 from OpenRouter currently surfaces as `upstream_error` (no distinct code) | Pitfall 2 / Open Q1 | Low — verified the taxonomy branches; if a hidden 403 path exists it only means less new code. The planner must still add the `forbidden` code for D-09. |
| A3 | Sync `httpx.get` in the async `/balance` handler is acceptable (matches `exchange_code` norm) | Standard Stack alternatives | Low — on-demand, single-user, 15s timeout; negligible event-loop block. Switch to `AsyncClient` only if a perf concern surfaces. |
| A4 | `/api/v1/credits` requires a management key (so it's unsuitable for OAuth inference keys) | Alternatives Considered | Low — COST-02 locks `/api/v1/key` regardless; this only justifies not switching. |

## Open Questions (RESOLVED)

1. **403 → `forbidden` code: add a backend branch or map `upstream_error`?** — **RESOLVED**
   - What we know: `chat.py` emits `no_api_key`/`rate_limit`/`payment_required`/`upstream_error`; D-09 + UI-SPEC need a 403-specific recovery (`[Reconnect]`/`[Use demo]`). [VERIFIED: codebase]
   - What's unclear: whether to add `elif e.status_code == 403:` emitting `forbidden`, or to treat `upstream_error` as the 403 trigger.
   - Recommendation: Add the explicit `forbidden` branch in `chat.py` (mirror the 402 branch). It's a few lines, keeps the taxonomy honest, and makes the FE mapping unambiguous. Cover with a test in `test_error_surfacing.py`.
   - **RESOLUTION:** Add the explicit `forbidden` 403 branch — implemented by Plan 14-01 Task 2. **Plan-check addendum:** the mid-stream **401** case (revoked/rejected stored key) was a blind spot here — it must ALSO get an explicit `elif e.status_code == 401:` branch emitting `no_api_key`, since SC#4 enumerates 401/402/403. Added to Plan 14-01 Task 2 during plan revision.

2. **`[Use demo]` button visibility (403 recovery).** — **RESOLVED**
   - What we know: UI-SPEC says `[Use demo]` renders only when demo fallback is eligible (the `mode`/eligibility signal). `demo_fallback_enabled` defaults OFF in dev+prod this phase. [VERIFIED: config.py:37]
   - What's unclear: there is no per-turn "demo eligibility" signal on the error path today (the `mode:"demo"` signal only rides the `done` event of a *successful* demo turn).
   - Recommendation: Since demo is OFF this phase, render `[Reconnect]` alone for 403 (the UI-SPEC's stated Phase-14 prod default). Wiring a live demo-eligibility signal is a Phase 15 concern (DEMO-01/02). Plan the typed bubble to accept an optional `demoEligible` prop defaulting false.
   - **RESOLUTION:** `[Reconnect]` alone for 403 this phase; typed bubble accepts optional `demoEligible` prop (default false). Demo eligibility deferred to Phase 15 — implemented by Plan 14-03.

3. **Balance refresh trigger timing.** — **RESOLVED**
   - What we know: fetch on demand only — "settings open / after a turn" (UI-SPEC, REQUIREMENTS out-of-scope: no polling).
   - What's unclear: whether "after a turn" should debounce/cache (Claude's discretion).
   - Recommendation: Fetch on `SettingsPage` mount and after a successful `done` event (optionally throttle to once per N seconds). Keep `useKeyStatus`'s no-poll contract; do not add a Realtime subscription.
   - **RESOLUTION:** On-demand fetch (SettingsPage mount + after `done`), no polling/Realtime — implemented by Plan 14-02.

---

## Project Constraints (from CLAUDE.md)

The planner must verify compliance with these directives (same authority as locked decisions):

- **No LangChain / LangGraph** — raw SDK only. (No LLM SDK touched this phase; balance is a plain `httpx` GET.)
- **Python backend must use `venv`** — test/run commands use `backend/venv/`.
- **Pydantic for structured outputs** — `BalanceResponse` is a Pydantic model; `MessageResponse` extended via Pydantic.
- **All tables need RLS; users only see their own data** — `/balance` reads `user_api_keys` scoped by `user_id`; `messages.usage` inherits per-user RLS (migration 029 note). No new table.
- **Stream chat responses via SSE** — unchanged; P14 only reads the existing `done`/`error` events.
- **Supabase Realtime for ingestion status** — N/A this phase; explicitly DO NOT add Realtime for balance (on-demand only).
- **Module 2+ stateless completions** — unchanged.
- **Ingestion manual upload only** — N/A this phase.
- **Frontend: React+Vite+Tailwind+shadcn/ui** — note: shadcn is NOT initialized; UI-SPEC mandates hand-rolled Tailwind this phase (shadcn deferred to Phase 15 per STATE.md). Do not contradict the UI-SPEC.
- **GSD Workflow Enforcement** — file edits go through the GSD execute-phase flow (this is research only).
- **Plans saved to `.agent/plans/`** with complexity indicator + per-task validation test (CLAUDE.md Planning rules) — the planner must honor this naming/validation convention in addition to the GSD phase plan layout.
- **Test credentials** for browser validation: `ragtest1@gmail.com` / `testpass123`.
- **Dual Supabase envs** (MEMORY.md): `.env` = dev, `.env.prod` = prod — set `LOW_BALANCE_THRESHOLD_USD` per-env if overriding the default; verify prod against `.env.prod`.

---

## Sources

### Primary (HIGH confidence)
- Codebase (VERIFIED via Read/Grep): `backend/routers/keys.py`, `backend/routers/chat.py` (`_accumulate_usage` :106, `_resolve_key_and_model` :152, `_sse_error` :80, done event :1169-1195, error branches :1196-1238), `backend/routers/threads.py`, `backend/models/schemas.py`, `backend/config.py`, `backend/services/crypto_service.py`, `backend/services/openrouter_service.py`, `backend/services/log_scrub.py`, `backend/services/demo_service.py`, `supabase/migrations/20240301000029_add_usage_to_messages.sql`, `backend/tests/test_usage_capture.py`, `backend/tests/test_keys_status.py`, `backend/pytest.ini`, `frontend/src/hooks/useChat.ts`, `frontend/src/hooks/useKeyStatus.ts`, `frontend/src/components/ErrorMessageBubble.tsx`, `frontend/src/components/MessageBubble.tsx`, `frontend/src/components/ChatContainer.tsx`, `frontend/src/components/IconSidebar.tsx`, `frontend/src/components/MobileTopBar.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/ChatPage.tsx`.
- `.planning/phases/14-…/14-CONTEXT.md` (D-01..D-09), `14-UI-SPEC.md` (locked visual + copy contract), `.planning/REQUIREMENTS.md` (COST-01..04, PREF-01), `.planning/config.json`.
- OpenRouter official docs (CITED): `openrouter.ai/docs/api/api-reference/api-keys/get-current-key`, `openrouter.ai/docs/api/reference/limits` — `GET /api/v1/key` response shape (`data.limit_remaining`/`limit`/`usage`/`is_free_tier`/`rate_limit`; null = uncapped).

### Secondary (MEDIUM confidence)
- OpenRouter `openrouter.ai/docs/api/api-reference/credits/get-credits` — `/api/v1/credits` shape (`total_credits`/`total_usage`); noted as an alternative not used (management-key gated).

### Tertiary (LOW confidence)
- None relied upon. The OAuth-key-defaults-to-null-limit behavior (A1) is reasoned, not directly verified — flagged in Assumptions Log for runtime confirmation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; all assets verified present in codebase.
- Architecture / read-path fixes: HIGH — `MessageResponse` strip, `useChat` gaps, and the balance pattern verified directly against source.
- OpenRouter contract: HIGH (shape CITED from official docs) with one MEDIUM nuance (A1: typical null `limit_remaining` for OAuth keys — verify at runtime).
- Pitfalls: HIGH — each tied to a specific verified line/behavior.
- Security: HIGH — reuses verified Phase 9/10/11 controls.

**Research date:** 2026-06-25
**Valid until:** 2026-07-25 (stable internal contract). OpenRouter `/api/v1/key` shape: re-verify if balance rendering misbehaves; OpenRouter occasionally adds `data` fields (additive, low risk).
