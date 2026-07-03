# Phase 15: Options UI Capstone + Demo Gating - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 25 new/modified (6 new, 13 extended source, 6 extended tests) + 2 consumed-as-is references
**Analogs found:** 25 / 25 (3 new files are composites with partial analogs — see No Analog Found)

All line numbers verified against live code this session. Extended files are their own analogs: the excerpts below are the exact current code the planner's actions modify or must preserve. RESEARCH.md Code Examples supply the *target* shapes; this document supplies the *source* shapes and insertion points.

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `frontend/src/lib/fuzzy.ts` | utility | transform (pure) | `frontend/src/lib/pkce.ts` (conventions only) | role-match |
| `frontend/src/hooks/useKeyGate.tsx` | hook | request-response (gate + modal state) | `frontend/src/hooks/useKeyStatus.ts` + `SettingsPage.tsx` ConfirmDialog usage | composite |
| `supabase/migrations/20240301000033_add_favorite_models.sql` | migration | DDL (additive) | `supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql` | exact |
| `frontend/src/lib/fuzzy.test.ts` | test | unit | `frontend/src/test/themeBootstrap.test.ts` | exact |
| `frontend/src/hooks/useKeyGate.test.tsx` | test | component (hook) | `frontend/src/hooks/useChat.test.tsx` | exact |
| `frontend/src/pages/OAuthCallbackPage.test.tsx` | test | component (page) | `frontend/src/pages/ChatPage.test.tsx` | role-match |

### Extended files (analog = the file itself)

| Modified File | Role | Data Flow | Phase-15 Change |
|---------------|------|-----------|-----------------|
| `frontend/src/components/ModelSelector.tsx` | component | request-response (lazy fetch + listbox) | search input, sections, Popular chip, star (D-06/07/08, MODEL-08) |
| `frontend/src/components/DefaultModelSelector.tsx` | component | CRUD (fire-and-forget PUT) | route handleSelect through useKeyGate (D-04) |
| `frontend/src/components/ConfirmDialog.tsx` | component | presentation (portal modal) | `variant: 'danger' \| 'primary'` + light shell tokens (D-01) |
| `frontend/src/components/ChatContainer.tsx` | component | presentation (flex layout) | demo banner first shrink-0 child; wire demoEligible/onUseDemo (D-10/11) |
| `frontend/src/pages/OAuthCallbackPage.tsx` | page | request-response (OAuth exchange) | pending-selection resume (D-02) |
| `frontend/src/pages/ChatPage.tsx` | page | CRUD + streaming | gate wraps handleThreadModelChange (D-04) |
| `frontend/src/pages/SettingsPage.tsx` | page | CRUD | clear stale stash before plain connect (Pitfall 6) |
| `frontend/src/hooks/useKeyStatus.ts` | hook | request-response (shared store) | `KeyStatus.demo_enabled?` (Pattern 5) |
| `frontend/src/hooks/useChat.ts` | hook | streaming (SSE) | `lastTurnWasDemo` read + `use_demo` retry (D-10/11) |
| `backend/routers/keys.py` | router (controller) | request-response | `demo_enabled` in BOTH status branches (Pitfall 3) |
| `backend/routers/preferences.py` | router (controller) | CRUD (partial upsert) | `favorite_models` in both selects + both echoes (D-05) |
| `backend/routers/chat.py` | router (controller) | streaming (SSE) | `use_demo` override + D-03 free-guard in `_resolve_key_and_model` |
| `backend/models/schemas.py` | model (Pydantic) | validation | additive fields on 4 models |
| `frontend/src/components/ModelSelector.test.tsx` | test | component | focus-model migration (contract-sanctioned), sections/search/star/chip |
| `frontend/src/components/ChatContainer.test.tsx` | test | component | banner render condition + [Use demo] wiring |
| `frontend/src/hooks/useChat.test.tsx` | test | component (hook) | `mode:"demo"` done read + `{use_demo:true}` body |
| `backend/tests/test_key_model_resolution.py` | test | unit | free-guard + override tests; 3 killswitch tests stay green |
| `backend/tests/test_preferences_api.py` | test | unit | favorite_models roundtrip + no-clobber regression |
| `backend/tests/test_keys_status.py` | test | unit | demo_enabled in both branches |

### Consumed as-is (do not modify)

| File | Why it stays untouched |
|------|------------------------|
| `frontend/src/lib/pkce.ts` | `startOpenRouterConnect()` called as-is by the gate; the stash is written by `useKeyGate`, NOT here (keeps pkce pure — Pitfall 6 resolution) |
| `frontend/src/components/ErrorMessageBubble.tsx` | `demoEligible`/`onUseDemo` props already exist (lines 11-16) and the [Use demo] button already renders at lines 152-156; only the *call site* in ChatContainer changes |

---

## Pattern Assignments

### `supabase/migrations/20240301000033_add_favorite_models.sql` (migration, DDL)

**Analog:** `supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql` — exact match: same table, same additive-TEXT-non-FK convention.

**Additive non-FK column pattern** (migration 032, lines 19-24 — the rationale comment style + the plain-TEXT convention `favorite_models` follows):
```sql
-- default_model is intentionally NOT a FK to model_cache (D-06): a model can be
-- deprecated and disappear from the cache while a user's pin must persist as a
-- plain string (so the deprecation-fallback notice can fire instead of a FK error).
CREATE TABLE user_preferences (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  default_model TEXT,                       -- nullable: null = owner default (D-05); NOT a FK (D-06)
```

**Additive ALTER pattern** (migration 032, line 62 — mirror this single-statement shape):
```sql
ALTER TABLE threads ADD COLUMN model TEXT;
```

**Header comment pattern** (migration 032, lines 1-10): phase + decision IDs, "additive, no backfill, no destructive change", dependency note. RLS note: own-row policies from 032 (lines 31-55) cover new columns automatically — migration 033 adds NO policies. Target statement per RESEARCH: `ALTER TABLE user_preferences ADD COLUMN favorite_models TEXT[] NOT NULL DEFAULT '{}';`

---

### `backend/models/schemas.py` (model, validation) — EXTEND

**Analog:** itself. Four additive fields; every extension mirrors an existing sibling.

**Partial-update pattern to extend** (lines 53-63 — `PreferencesUpdate`; `favorite_models: list[str] | None = None` joins these fields so `exclude_unset` semantics keep working):
```python
class PreferencesUpdate(BaseModel):
    """PUT /api/preferences body — a PARTIAL update (RESEARCH Pattern 2).

    Both fields default to None so the endpoint's model_dump(exclude_unset=True)
    sends ONLY the keys the client actually provided — a theme-only body must NOT
    carry default_model (which would clobber the other field in the upsert).
    """
    default_model: str | None = None
    theme: Literal["light", "dark"] | None = None
```

**Response-default pattern** (lines 42-50 — `PreferencesResponse`; gains `favorite_models: list[str] = []`):
```python
class PreferencesResponse(BaseModel):
    default_model: str | None = None
    theme: str = "dark"
```

**Status response to extend** (lines 122-131 — `KeyStatusResponse`; gains `demo_enabled: bool = False`):
```python
class KeyStatusResponse(BaseModel):
    connected: bool
    masked_label: str | None = None
    connected_at: str | None = None
```

**Body model to extend** (lines 77-78 — `MessageCreate`; gains `use_demo: bool = False`):
```python
class MessageCreate(BaseModel):
    content: str
```

Docstring convention: every field group carries a phase + requirement-ID comment (see `MessageResponse.usage`, lines 87-92). Bounds insurance (Open Q3): `Field(max_length=...)` precedent at `ExplorerFinding` (lines 172-177).

---

### `backend/routers/keys.py` (router, request-response) — EXTEND

**Analog:** itself. The change is confined to `status()`.

**Both-branches shape to extend** (lines 82-99 — the early return at 93-94 is the keyless branch that MUST also carry `demo_enabled`, Pitfall 3):
```python
@router.get("/status", response_model=KeyStatusResponse)
async def status(user_id: str = Depends(get_user_id)):
    """Masked-only connection state (KEY-03). Never selects/returns encrypted_key."""
    row = (
        get_supabase()
        .table("user_api_keys")
        .select("key_label, connected_at")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {"connected": False}
    return {
        "connected": True,
        "masked_label": row.data["key_label"],
        "connected_at": row.data["connected_at"],
    }
```
Change: compute `demo_enabled = get_settings().demo_fallback_enabled` once at the top; add the key to BOTH return dicts. `get_settings` is already imported (line 32). Flag source: `config.py:37` (`demo_fallback_enabled: bool = False`) — env-driven, pydantic-settings reads `DEMO_FALLBACK_ENABLED` case-insensitively.

---

### `backend/routers/preferences.py` (router, CRUD partial upsert) — EXTEND

**Analog:** itself. `favorite_models` must be added to BOTH selects and BOTH response dict literals (4 touch points).

**GET select + no-row default** (lines 42-55):
```python
    row = (
        get_supabase()
        .table("user_preferences")
        .select("default_model, theme")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not row or not row.data:
        return {"default_model": None, "theme": "dark"}
    return {
        "default_model": row.data.get("default_model"),
        "theme": row.data.get("theme") or "dark",
    }
```

**Partial-upsert + JWT-bound user_id** (lines 70-75 — the `exclude_unset` mechanics that make whole-array-replace favorites PUTs safe against theme clobber, Pitfall 12):
```python
    patch = body.model_dump(exclude_unset=True)
    patch["user_id"] = user_id
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()

    db = get_supabase()
    db.table("user_preferences").upsert(patch, on_conflict="user_id").execute()
```
The PUT echo select (lines 77-89) repeats the GET shape — extend it identically (`select("default_model, theme, favorite_models")`, plus `"favorite_models": row.data.get("favorite_models") or []` in both dict literals).

---

### `backend/routers/chat.py` (router, streaming) — EXTEND

**Analog:** itself + two defensive in-file patterns to mirror.

**The resolver being changed** (lines 152-207, `_resolve_key_and_model`). Current demo branch to replace (lines 196-204 — pins the fallback, ignores the picked model):
```python
    if settings.demo_fallback_enabled:
        # Owner-key fallback is PINNED to a free model (D-06): the cost bound comes
        # from the MODEL, not from who's eligible (D-05).
        return (
            settings.resolved_llm_api_key,
            settings.demo_fallback_model or model,
            "demo",
            False,
        )
```
D-03 change: both demo entries route through a `_demo_model_for(db, model, settings)` helper (RESEARCH Code Examples has the full target). New resolution order: `use_demo+flagON → demo` › `user key → user` › `flagON keyless → demo` › `no_key`. The `use_demo` override check inserts AFTER the model tier resolution (lines 171-177) and BEFORE the user-key row read (line 181).

**Defensive maybe_single guard to mirror in the free-guard** (lines 188-194 — the exact dict-guard + short-lived-key shape):
```python
    # Empty-row guard (keys.py:79-88). maybe_single() returns a dict-or-None .data;
    # defensively require a dict (a list/None means "no key row" → fall through).
    if row and isinstance(row.data, dict) and row.data.get("encrypted_key"):
        # Decrypt in-memory, this turn only. The plaintext is a short-lived local —
        # never stashed in a closure that outlives the turn, never returned to the FE.
        api_key = decrypt_key(row.data["encrypted_key"])
        return api_key, model, "user", True
```
Free-guard equivalent: `row and isinstance(row.data, dict) and row.data.get("is_free") is True` → picked model; ANY other outcome → `settings.demo_fallback_model` (unknown ≠ free, Pitfall 5).

**Crash-tolerant cache-read pattern to mirror** (lines 848-852 — the T-13-CRASH except shape the free-guard's try/except copies):
```python
                except Exception as e:  # T-13-CRASH: a cache-read error never crashes the turn
                    logger.warning(
                        f"model_cache deprecation check failed; skipping notice: "
                        f"{scrub_secrets(str(e))}"
                    )
```

**Emission already done — do not re-implement** (lines 1181-1195, the done event; FE just reads `mode`):
```python
            # done event — carry the summed usage; signal mode:"demo" so the FE
            # can surface the owner-key demo banner (Phase 15). useChat.ts:185
            # keys only on message_id, so extra keys are inert (D-08).
            done_payload = {
                "message_id": assistant_msg_id,
                "content": full_content,
            }
            if turn_usage:
                done_payload["usage"] = turn_usage
            if mode == "demo":
                done_payload["mode"] = "demo"
```

Fail-closed caller contract that must survive (lines 798-805): `mode == "no_key"` → `yield _sse_error("no_api_key", ...)` → `return`, no LLM call.

---

### `frontend/src/lib/fuzzy.ts` (utility, pure transform) — NEW

**Conventions analog:** `frontend/src/lib/pkce.ts` header (lines 1-10) states the lib/ module rules explicitly:
```typescript
// Source pattern: openrouter.ai OAuth docs (Phase 10 RESEARCH §Pattern 3) —
// there is no in-repo analog. Conventions follow sibling lib/ files
// (api.ts, supabase.ts): named exports only, no default export, no React
// import, camelCase functions, 2-space indent, single quotes, no semicolons.
```
Apply the same rules: named exports `fuzzyScore` / `matchModel`, no default export, no React import. Algorithm has NO in-repo analog — the RESEARCH.md "Fuzzy matcher" code example (locked ranking: substring > word-boundary > tighter subsequence span; `null` = removed row) is the implementation spec; UI-SPEC locks the ranking contract the tests assert.

---

### `frontend/src/hooks/useKeyGate.tsx` (hook, gate + modal state) — NEW

**Composite of three in-repo patterns** (no single analog — this is the phase's one new abstraction):

**1. Shared-store read** — `useKeyStatus.ts` lines 5-9 (interface gains `demo_enabled?: boolean`) and the hook's public surface (lines 169-178). The gate reads `status?.connected` + `status?.demo_enabled`; while `status === null` (first load), do not open a modal (RESEARCH Pattern 1; Assumption A3):
```typescript
export interface KeyStatus {
  connected: boolean
  masked_label?: string
  connected_at?: string
}
```

**2. ConfirmDialog state management** — `SettingsPage.tsx` lines 27, 177-186 (the only existing ConfirmDialog call site; `variant` defaults to `'danger'` so this call site needs zero changes):
```tsx
  const [confirmOpen, setConfirmOpen] = useState(false)
  ...
      {confirmOpen && (
        <ConfirmDialog
          heading="Disconnect OpenRouter?"
          body="You'll need to reconnect to chat with your own key."
          confirmLabel="Disconnect"
          cancelLabel="Cancel"
          onConfirm={handleDisconnect}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
```
The gate returns `{ guardedSelect, gateModal }` — the modal JSX renders `<ConfirmDialog variant="primary" ...>` with the UI-SPEC locked copy (`Connect OpenRouter?`, paid/demo-OFF bodies, `${model}` display-name interpolation only).

**3. PKCE launch + stash sibling** — `pkce.ts` lines 34-45. The gate writes `sessionStorage.setItem('or_pending_selection', JSON.stringify({kind, modelId, threadId?, returnTo}))` immediately before calling `startOpenRouterConnect()`, whose own writes it sits beside:
```typescript
export async function startOpenRouterConnect(): Promise<void> {
  const verifier = randomString(64)
  const state = randomString(32)
  const challenge = await challengeFromVerifier(verifier)
  sessionStorage.setItem('or_pkce_verifier', verifier)
  sessionStorage.setItem('or_pkce_state', state)
  const callback = `${window.location.origin}/settings/openrouter/callback`
  window.location.assign(
    `https://openrouter.ai/auth?callback_url=${encodeURIComponent(callback)}` +
      `&code_challenge=${challenge}&code_challenge_method=S256&state=${state}`,
  )
}
```
Decision table (UI-SPEC locked): connected → apply; keyless+demoON+`m.is_free` → apply; keyless+demoON+paid → modal (paid body); keyless+demoOFF → modal (demo-OFF body). `is_free` comes from the catalog row (`ModelResponse.is_free`, ModelSelector.tsx:13) — never recomputed client-side.

---

### `frontend/src/components/ConfirmDialog.tsx` (component, portal modal) — EXTEND

**Analog:** itself (62 lines total — small enough to see every variant touch point).

**Variant extension points** — icon (line 39), shell (line 36), confirm button (lines 50-56); dark output must stay byte-identical for the default `'danger'` (UI-SPEC theme rule):
```tsx
      <div
        className="bg-gray-900 border border-gray-700 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <AlertTriangle size={24} className="text-red-400" />
        ...
          <button
            type="button"
            onClick={onConfirm}
            className="bg-red-600 hover:bg-red-700 text-white text-sm px-4 py-2 rounded"
          >
            {confirmLabel}
          </button>
```
`primary` variant per UI-SPEC: confirm `bg-blue-600 hover:bg-blue-700 text-white`; icon `KeyRound` 24px `text-blue-600`. Light shell tokens: `bg-white border-gray-300 dark:bg-gray-900 dark:border-gray-700`; heading `text-gray-900 dark:text-white`; body `text-gray-600 dark:text-gray-400`; cancel `bg-gray-200 hover:bg-gray-300 text-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-white`. Esc handler (lines 22-28) and overlay-click (lines 31-34) stay untouched.

---

### `frontend/src/components/ModelSelector.tsx` (component, lazy-fetch listbox) — EXTEND

**Analog:** itself — the biggest surgery of the phase. Load-bearing current code:

**Flat options array being restructured into section rows** (lines 96-100):
```tsx
  const options: { key: string; value: string | null; label: string; model: ModelResponse | null }[] =
    [
      ...(extraOption ? [{ key: '__extra__', value: extraOption.value, label: extraOption.label, model: null }] : []),
      ...rows.map(m => ({ key: m.id, value: m.id, label: m.name ?? m.id, model: m })),
    ]
```
Section-scoped keys required post-change (`fav:${id}` / `pop:${id}` / `all:${id}`) — plain `m.id` keys collide once a model appears in multiple sections (Pitfall 1).

**Free tag the Popular chip mirrors exactly** (lines 315-330, `ModelHint` — the chip is a sibling `<span>` with identical classes, rendered whenever `popularity_rank != null`, order `[Free] [Popular] 128K context`):
```tsx
function ModelHint({ model }: { model: ModelResponse }) {
  const price = priceHint(model.price_per_mtok_prompt, model.price_per_mtok_completion)
  const context = contextHint(model.context_length)
  return (
    <span className="flex flex-wrap items-center gap-x-2 text-xs text-gray-600 dark:text-gray-400">
      {model.is_free ? (
        <span className="rounded bg-gray-200 px-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200">
          {COPY.free}
        </span>
      ) : (
        price && <span>{price}</span>
      )}
      {context && <span>{context}</span>}
    </span>
  )
}
```

**Seed effect that fights live filtering** (lines 146-152 — re-fires on `options.length`, which changes per keystroke once search exists; Pitfall 2 fix: seed on open only, clamp/reset on query change):
```tsx
  useEffect(() => {
    if (!open) return
    const idx = options.findIndex(o => o.value === value)
    setActiveIndex(idx >= 0 ? idx : 0)
    // Only re-seed on open / option count changes, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, options.length])
```

**Focus-the-list effect replaced by focus-the-input** (lines 167-172 — the locked a11y migration; input gains `aria-autocomplete="list"`, `aria-controls={listboxId}`, `aria-activedescendant`):
```tsx
  useEffect(() => {
    if (open && options.length > 0) {
      listRef.current?.focus()
    }
  }, [open, options.length])
```

**PANEL_MAX drop-up estimate to bump ~320 → ~370** (lines 135-143 — accounts for the new `h-11` search row; the settings sidebar-footer selector relies on drop-up):
```tsx
  useEffect(() => {
    if (!open) return
    const rect = triggerRef.current?.getBoundingClientRect()
    if (!rect) return
    const PANEL_MAX = 320 // ~ max-h-72 list + chrome
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    setDropUp(spaceBelow < PANEL_MAX && spaceAbove > spaceBelow)
  }, [open])
```

**Keyboard machinery migrating from UL to input** (lines 188-222, `onListKeyDown` — ArrowUp/Down/Enter/Esc/Tab-trap logic survives but moves to the input's keydown; Home/End become native caret ops; Shift+Enter gains favorite-toggle; printable keys type into the filter). Arrow-nav must skip `role="presentation"` headers — keep a flat *navigable* array (options only) for `activeIndex`.

**Behaviors that must survive verbatim:** LOCKED `COPY` const (lines 41-45); lazy fetch (lines 102-118); empty-`models`-prop-means-unfetched (lines 75-78, 93); outside-click close (lines 155-164); `max-h-72` scroll (line 272); `min-h-11` rows (line 285); selected check `left-1.5 text-blue-600` in every duplicate instance (lines 291-297); loading/error/`No models available.` states (lines 246-262).

**Favorite star (new sub-element):** button `absolute right-0 inset-y-0 w-11 flex items-center justify-center`, `tabIndex={-1}`, `stopPropagation()` on click, row content `pr-12`; favorited `text-blue-600 fill-blue-600`, unfavorited `text-gray-400 dark:text-gray-500`; NOT on the extraOption row. Favorites data: GET `/api/preferences` once at mount; toggle = optimistic local set + fire-and-forget PUT (pattern below).

---

### `frontend/src/components/DefaultModelSelector.tsx` (component, CRUD) — EXTEND

**Analog:** itself. The gate must intercept BEFORE this handler's optimistic `onChange` + PUT fire (Pitfall 7).

**Current apply path the gate wraps** (lines 30-40 — also THE house-style excerpt for the favorites fire-and-forget PUT):
```tsx
  function handleSelect(modelId: string | null) {
    // The default-model control never offers a clear row, so modelId is always a concrete id here;
    // guard defensively so a null can never PUT {default_model: null}.
    if (modelId == null) return
    onChange?.(modelId)
    // Best-effort server persist; never block the UI and never revert on failure (house style).
    void apiFetch('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify({ default_model: modelId }),
    }).catch(() => {})
  }
```
Post-change shape: `handleSelect` delegates to `guardedSelect` from `useKeyGate({ kind: 'default', onApply })`; only `onApply` runs the `onChange` + PUT above. On gate-open the trigger keeps showing the prior model.

---

### `frontend/src/pages/ChatPage.tsx` (page, CRUD + streaming) — EXTEND

**Analog:** itself.

**Thread apply path the gate wraps** (lines 92-109 — optimistic local mirror + PATCH + error toast; this becomes the `onApply` of `useKeyGate({ kind: 'thread', threadId })`):
```tsx
  const handleThreadModelChange = useCallback(
    async (modelId: string | null) => {
      if (!activeThreadId) return
      setThreads(prev =>
        prev.map(t => (t.id === activeThreadId ? { ...t, model: modelId } : t))
      )
      try {
        await apiFetch(`/api/threads/${activeThreadId}`, {
          method: 'PATCH',
          body: JSON.stringify({ model: modelId }),
        })
      } catch (err) {
        Sentry.captureException(err)
        showToast("Couldn't update the model for this chat. Try again.", 'error')
      }
    },
    [activeThreadId, showToast]
  )
```
ChatPage already holds the `models` catalog (lines 56-64) — the gate can look up `is_free` there (RESEARCH Pattern 1 option (b), avoids touching ModelSelector's `onSelect` signature). The `extraOption` clear row (`value: null`) bypasses the gate (RESEARCH Open Q1 recommendation — document in the plan).

---

### `frontend/src/pages/OAuthCallbackPage.tsx` (page, OAuth exchange) — EXTEND

**Analog:** itself. Resume inserts after the exchange succeeds, replacing the fixed toast+navigate.

**StrictMode guard the resume rides inside** (lines 25-27 — no double-apply):
```tsx
  useEffect(() => {
    if (ranRef.current) return
    ranRef.current = true
```

**Success path = exact insertion point** (lines 40-47 — resume replaces lines 46-47; RESEARCH "OAuthCallbackPage resume" example is the target):
```tsx
        await apiFetch('/api/keys/openrouter/exchange', {
          method: 'POST',
          body: JSON.stringify({ code, code_verifier: verifier }),
        })
        sessionStorage.removeItem('or_pkce_verifier')
        sessionStorage.removeItem('or_pkce_state')
        showToast('OpenRouter connected.', 'success')
        navigate('/settings', { replace: true })
```
One-shot rule: `removeItem('or_pending_selection')` FIRST, then apply; apply failure → warning toast, still navigate (never the failure screen for an apply error).

**Retry preserves the stash / Back clears it** (lines 74-87 — Retry at 76 rewrites only verifier/state via `startOpenRouterConnect()` so the stash survives naturally; "Back to settings" at 81-87 must gain an explicit `sessionStorage.removeItem('or_pending_selection')`):
```tsx
              <button
                type="button"
                onClick={() => startOpenRouterConnect()}
                ...
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => navigate('/settings')}
                ...
              >
                Back to settings
              </button>
```

---

### `frontend/src/pages/SettingsPage.tsx` (page, CRUD) — EXTEND

**Analog:** itself. Minimal change: the plain-connect CTA must clear any stale stash before launching (Pitfall 6 per-call-site table — non-gate `startOpenRouterConnect()` callers clear; callback Retry preserves).

**Connect CTA to prepend the clear to** (lines 59-61):
```tsx
  const handleConnect = () => {
    startOpenRouterConnect()
  }
```
Same one-line clear applies to `ErrorMessageBubble`'s [Reconnect] onClick (ErrorMessageBubble.tsx:117-127) — that is the third non-gate launcher. The preferences seed fetch (lines 48-57) already reads `GET /api/preferences`; it is unaffected by the new `favorite_models` field (additive).

---

### `frontend/src/hooks/useKeyStatus.ts` (hook, shared store) — EXTEND

**Analog:** itself. One interface field; the store machinery is untouched.

**Interface to extend** (lines 5-9, shown under useKeyGate above): add `demo_enabled?: boolean`. While status is null/loading, `demo_enabled` is undefined → banner condition false → no flash (Pattern 5).

**Contract that must stay untouched** (lines 105-120 — silent-on-error, in-flight dedup):
```typescript
async function loadStatus(): Promise<void> {
  if (statusInFlight) return statusInFlight
  setStore({ loading: true })
  statusInFlight = (async () => {
    try {
      setStore({ status: await apiFetch('/api/keys/status') })
    } catch {
      // Preserve silent-on-error behavior (keep last-known status)
    } finally {
      setStore({ loading: false })
      statusInFlight = null
    }
  })()
  await statusInFlight
  await loadBalance()
}
```
No broadcast needed on the resume path: the OAuth round-trip is a full page reload, so every instance remounts and refetches (doc comment, lines 21-27).

---

### `frontend/src/hooks/useChat.ts` (hook, SSE streaming) — EXTEND

**Analog:** itself. Three small additions: `lastTurnWasDemo` state, `use_demo` in the send body, a demo-retry callback.

**Done-event branch gaining the one-line read** (lines 251-261 — `if (parsed.mode === 'demo') setLastTurnWasDemo(true)` slots in here):
```typescript
              } else if (parsed.message_id) {
                // done event - update with final message ID and capture the live turn's summed
                // usage (cost + tokens). ...
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, id: parsed.message_id, usage: parsed.usage ?? m.usage }
                      : m
                  )
                )
              }
```

**Send body to extend** (lines 148-155 — opts gain `useDemo?: boolean`; body becomes `JSON.stringify({ content, ...(opts?.useDemo ? { use_demo: true } : {}) })`):
```typescript
      const url = isRetry
        ? `/api/threads/${effectiveThreadId}/messages?retry=true`
        : `/api/threads/${effectiveThreadId}/messages`
      const res = await apiStream(url, {
        method: 'POST',
        body: JSON.stringify({ content }),
        signal: controller.signal,
      })
```

**Retry pattern the demo retry mirrors** (lines 354-362 — same strip-errors + explicit-threadId shape, plus `useDemo: true`):
```typescript
  const retryLastUserMessage = useCallback(() => {
    if (isStreaming) return
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUser) return
    setMessages(prev => prev.filter(m => m.role !== 'error'))
    // WR-05: pass the current thread explicitly so retry targets it deterministically ...
    void sendMessage(lastUser.content, { retry: true, threadId: threadId ?? undefined })
  }, [messages, isStreaming, sendMessage, threadId])
```
`lastTurnWasDemo` reset: per-hook state resets naturally on thread switch (RESEARCH Open Q2 recommendation).

---

### `frontend/src/components/ChatContainer.tsx` (component, layout) — EXTEND

**Analog:** itself + the thread-header row as the shrink-0 sibling pattern.

**Root flex + the shrink-0 sibling pattern the banner copies** (lines 56-63 — banner becomes the FIRST shrink-0 child, ABOVE this header row, present with or without an active thread; Pitfall 11):
```tsx
    <div className="flex-1 flex flex-col h-full bg-white text-gray-900 dark:bg-gray-950 dark:text-white">
      {/* Per-thread model selector row (D-05). shrink-0 sibling above the scroll area so the
          existing flex-1 flex flex-col h-full layout is preserved (UI-SPEC Consistency req). */}
      {activeThreadId !== null && (
        <div className="shrink-0 h-12 flex items-center gap-2 px-3 border-b bg-gray-50 border-gray-200 dark:bg-gray-900 dark:border-gray-800">
```
Banner target (UI-SPEC locked classes + RESEARCH "Demo banner" example): `role="status"`, `shrink-0 flex items-center gap-2 px-4 py-2 text-xs border-b bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300`, `Info` 14px `text-amber-500 shrink-0`, LOCKED Phase-11 sentence only. Render condition: `(!keyStatus.connected && demoEnabled) || lastTurnWasDemo`.

**Dead props to wire** (lines 113-123 — replace `demoEligible={false}` with the real flag; pass `onUseDemo` = the demo retry):
```tsx
        {messages.map(msg =>
          msg.role === 'error' ? (
            // errorType set → typed recovery variant (D-09); undefined → generic Retry path.
            // demoEligible is false this phase (Phase 15 owns enabling demo fallback).
            <ErrorMessageBubble
              key={msg.id}
              onRetry={onRetry}
              isStreaming={isStreaming}
              type={msg.errorType}
              demoEligible={false}
            />
```
The receiving end already works (ErrorMessageBubble.tsx:152-156 renders [Use demo] on `type === 'forbidden' && demoEligible`) — no bubble changes. Amber-family precedent for light-mode text: SettingsPage low-balance line (SettingsPage.tsx:132-137, `text-amber-700 dark:text-amber-300` + `text-amber-500` icon). DemoPill is a DIFFERENT "demo" concept (anon sessions) — leave untouched.

---

## Test Pattern Assignments

### FE component tests (extend `ModelSelector.test.tsx`, `ChatContainer.test.tsx`)

**Analog:** `frontend/src/components/ModelSelector.test.tsx` — boundary-mock setup (lines 1-11) + fixture shape (lines 14-35):
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
import ModelSelector from './ModelSelector'

// ModelSelector fetches GET /api/models via apiFetch on first open — mock the api boundary.
vi.mock('../lib/api', () => makeApiMock())

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>
```
Existing UL-focus assertions (e.g. Esc-returns-focus, line 141-153) will need the input-focus rewrite — contract-sanctioned (Pitfall 8); do NOT weaken `min-h-11`, locked-copy, or role assertions. Fixture rows already carry `popularity_rank` (lines 22, 32) — Popular-chip tests extend this fixture.

### FE hook tests (new `useKeyGate.test.tsx`, extend `useChat.test.tsx`)

**Analog:** `frontend/src/hooks/useChat.test.tsx` (lines 1-19 — renderHook + ProvidersWrapper + SSE mock):
```tsx
import { renderHook, act, waitFor } from '@testing-library/react'
import { ProvidersWrapper, mockSSEResponse } from '../test/utils'
import { useChat } from './useChat'
import { apiStream, apiFetch } from '../lib/api'

vi.mock('../lib/api', () => ({
  apiFetch: vi.fn(),
  apiStream: vi.fn(),
}))
...
function streamReply() {
  return mockSSEResponse(['data: {"text":"hello"}', 'data: {"message_id":"m1"}'])
}
```
`mode:"demo"` test: `mockSSEResponse(['data: {"text":"hi"}', 'data: {"message_id":"m1","mode":"demo"}'])`. useKeyGate tests additionally mock `../lib/pkce` (assert `startOpenRouterConnect` called) and assert the `or_pending_selection` sessionStorage write.

### FE page test (new `OAuthCallbackPage.test.tsx`)

**Analog:** `frontend/src/pages/ChatPage.test.tsx` — MemoryRouter wrap + module mocks (lines 4, 12-35):
```tsx
import { MemoryRouter } from 'react-router-dom'
...
vi.mock('../lib/api', () => ({ apiFetch: vi.fn(), apiStream: vi.fn() }))
vi.mock('../contexts/AuthContext', () => makeAuthMock())
...
function renderChatPage(opts: { isAnon?: boolean } = {}) {
  return renderWithProviders(
    (<MemoryRouter><ChatPage /></MemoryRouter>) as ReactElement,
    opts
  )
}
```
OAuthCallbackPage reads `window.location.search` + sessionStorage — seed both in the test, render inside MemoryRouter, assert PATCH/PUT calls + stash removal + toast text.

### FE lib unit test (new `fuzzy.test.ts`)

**Analog:** `frontend/src/test/themeBootstrap.test.ts` (lines 1-3, 27-37 — pure-function test, no providers, no api mock):
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { applyStoredTheme } from '../lib/themeBootstrap'
...
describe('applyStoredTheme', () => {
  it('adds the dark class and returns "dark" when storage.theme === "dark"', () => {
```
fuzzy tests assert the UI-SPEC locked ranking tiers (substring > boundary > span; `'lama33'` matches `'llama-3.3'`; non-subsequence → `null`).

### BE resolution tests (extend `test_key_model_resolution.py`)

**Analog:** itself — scaffolding built for exactly this extension. `_fake_settings` (lines 30-42) and `_db_with_key_row` (lines 45-87):
```python
def _fake_settings(**overrides):
    s = MagicMock()
    s.llm_model = "owner/default-model"
    s.resolved_llm_api_key = "sk-or-v1-OWNERKEY"
    s.demo_fallback_enabled = False
    s.demo_fallback_model = "meta-llama/llama-3.3-70b-instruct:free"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s
```
`_db_with_key_row`'s `_table` dispatcher (lines 57-84) needs a `model_cache` branch for the free-guard tests (`.select("is_free").eq(...).maybe_single().execute()` → `{"is_free": True/False}` / None / raises). Killswitch test that must stay green — the exact assertion shape new flag-OFF-override-inert tests copy (lines 110-133):
```python
def test_sec03_killswitch_no_owner_spend_when_flag_off():
    db = _db_with_key_row(None)  # no user_api_keys row → keyless turn
    settings = _fake_settings(demo_fallback_enabled=False)
    body = MagicMock(spec=[])  # no .model attribute

    with patch.object(chat, "get_settings", return_value=settings):
        api_key, model, mode, is_user_key = chat._resolve_key_and_model(
            db, "user-1", {"id": "t1"}, body
        )

    assert api_key is None
    assert mode == "no_key"
    ...
    assert api_key != settings.resolved_llm_api_key
```
Note `body = MagicMock(spec=[])` — the resolver reads `getattr(body, "use_demo", False)`, so spec-limited mocks default safely; `use_demo` tests pass `MagicMock(spec=["use_demo"], use_demo=True)` or a simple namespace.

### BE router tests (extend `test_keys_status.py`, `test_preferences_api.py`)

**Analog:** `test_keys_status.py` lines 25-39 — the TestClient + dependency-override + patch-get_supabase + finally-clear shape ALL backend router tests use:
```python
    mock_db = MagicMock()
    status_chain = (
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value
    )
    status_chain.execute.return_value = MagicMock(
        data={"key_label": "sk-or-v1-…wXyZ", "connected_at": "2026-06-19T20:00:00+00:00"}
    )

    app.dependency_overrides[get_user_id] = lambda: "user-uuid"
    try:
        with patch("routers.keys.get_supabase", return_value=mock_db):
            resp = TestClient(app).get("/api/keys/status")
    finally:
        app.dependency_overrides.clear()
```
demo_enabled tests additionally monkeypatch the flag: follow the file's own guidance — `monkeypatch.setenv("DEMO_FALLBACK_ENABLED", "true")` + `get_settings.cache_clear()` (per test_key_model_resolution.py header, lines 13-15), or patch `routers.keys.get_settings`. `test_preferences_api.py` has `_mock_db_with_pref_row` (lines 25-38) — extend its row dicts with `favorite_models`; add the no-clobber regression (theme-only PUT preserves favorites) asserting on the upsert payload.

---

## Shared Patterns

### Auth (backend)
**Source:** `backend/routers/preferences.py` lines 70-72 (+ module docstring lines 12-17)
**Apply to:** every extended endpoint (keys, preferences, chat)
```python
    patch = body.model_dump(exclude_unset=True)
    patch["user_id"] = user_id          # bound from Depends(get_user_id) — the JWT sub, NEVER the body
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
```

### Defensive maybe_single guard (backend)
**Source:** `backend/routers/chat.py` line 190 / `backend/routers/keys.py` line 122
**Apply to:** the new `_demo_model_for` free-guard
```python
if row and isinstance(row.data, dict) and row.data.get("encrypted_key"):
```
Unknown/None/list/exception → NOT a match. For the free-guard: `... row.data.get("is_free") is True` (unknown ≠ free).

### SEC-01 locked copy + scrubbed logs
**Source:** `backend/routers/keys.py` lines 154-161 (fixed generic detail, `scrub_secrets`, no exc_info near keys); `frontend/src/components/ErrorMessageBubble.tsx` lines 19-27 (locked sentences, never interpolate parsed.detail)
**Apply to:** ALL new copy (modal, toasts, banner) — `${model}` display name is the ONLY interpolation; every new backend except-branch logs via `scrub_secrets(str(e))`.

### LOCKED copy const (frontend)
**Source:** `frontend/src/components/ModelSelector.tsx` lines 40-45
**Apply to:** gate-modal strings, banner sentence, toast strings, search placeholder/empty state
```tsx
// LOCKED copy (UI-SPEC § Copywriting). Do not paraphrase.
const COPY = {
  loading: 'Loading models…',
  error: "Couldn't load models. Tap to retry.",
  free: 'Free',
} as const
```

### Optimistic fire-and-forget PUT (frontend)
**Source:** `frontend/src/components/DefaultModelSelector.tsx` lines 35-39
**Apply to:** favorites toggle (whole-array replace, no revert on failure, NO toast)
```tsx
    void apiFetch('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify({ default_model: modelId }),
    }).catch(() => {})
```

### Toast usage
**Source:** `frontend/src/contexts/ToastContext.tsx` — `useToast()` (lines 96-102), variants incl. `success`/`warning` (lines 11, 25-30), bottom-right 4s auto-dismiss (line 32)
**Apply to:** auto-apply combined toasts (success), apply-failure toast (warning). Rule: pending-selection apply fires ONLY the combined toast, never `OpenRouter connected.` as well.

### sessionStorage `or_*` key family
**Source:** `frontend/src/lib/pkce.ts` lines 38-39 (`or_pkce_verifier`, `or_pkce_state`)
**Apply to:** `or_pending_selection` (UI-SPEC locked name) — sessionStorage only, NEVER localStorage (tab-scoping + hard-refresh semantics). Writer: useKeyGate only. Clearers: callback resume (one-shot, remove-first), callback "Back to settings", and the three non-gate launch sites (Settings CTA, bubble [Reconnect]); callback Retry PRESERVES it.

### Silent, array-guarded catalog fetch (frontend)
**Source:** `frontend/src/pages/ChatPage.tsx` lines 56-64 (mirrored at SettingsPage.tsx:36-44)
**Apply to:** any new mount-time fetch (e.g. favorites read at picker mount)
```tsx
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/models')
      .then((data: unknown) => {
        if (!cancelled && Array.isArray(data)) setModels(data as ModelResponse[])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])
```

### Env-driven flags via cached settings (backend)
**Source:** `backend/config.py` lines 32-42 (`demo_fallback_enabled: bool = False`, `demo_fallback_model`); POPULAR_MODELS curated order at lines 66-77 (already feeds `popularity_rank` — picker just renders it)
**Apply to:** `demo_enabled` exposure (read `get_settings().demo_fallback_enabled`; never settable via API — no admin UI). Config-touching tests: `monkeypatch.setenv(...)` + `get_settings.cache_clear()`.

---

## No Analog Found

Files whose CORE logic has no in-repo precedent (conventions/analogs above still apply; RESEARCH.md Code Examples carry the implementation spec):

| File | Role | Data Flow | Reason / Spec Source |
|------|------|-----------|----------------------|
| `frontend/src/lib/fuzzy.ts` (algorithm) | utility | transform | No fuzzy/search code exists anywhere in the repo. Spec: RESEARCH "Fuzzy matcher" example + UI-SPEC locked ranking. Conventions: pkce.ts header rules. |
| `frontend/src/hooks/useKeyGate.tsx` (gate decision) | hook | request-response | No gating hook exists; it composes three verified in-repo patterns (shared store read, ConfirmDialog state, PKCE launch + stash). Decision table: UI-SPEC locked. |
| Search-in-popup a11y model (`ModelSelector` focus migration) | component | — | The repo's only listbox uses UL-focus; the combobox-with-list-popup pattern (input focus, `aria-activedescendant`) is new here. Contract: UI-SPEC § Interaction Contract (LOCKED, supersedes listbox-focus). |
| Deploy step (Fly secret flip, prod migrations 029-033) | ops | — | No file — operator-run checklist. Spec: RESEARCH Pattern 7 (ordered, human-gated; migration-repair contingency per project memory). |

---

## Metadata

**Analog search scope:** `frontend/src/{components,hooks,pages,lib,contexts,test}`, `backend/{routers,models,tests}`, `backend/config.py`, `supabase/migrations/`
**Files scanned:** 33 migrations globbed; 24 source/test files line-counted; 22 read (full or targeted); chat.py (1301 lines) read via 3 targeted ranges (120-219, 780-874, 1170-1229) + grep
**Key cross-checks:** `demoEligible={false}` confirmed at ChatContainer.tsx:122; `mode:"demo"` emission confirmed at chat.py:1190-1191; `?free_only=true` confirmed at models.py:36+51-52 (zero FE consumers); `popularity_rank` confirmed declared-unrendered (ModelSelector.tsx:16 vs ModelHint 315-330); next migration number 033 confirmed free
**Pattern extraction date:** 2026-07-02
