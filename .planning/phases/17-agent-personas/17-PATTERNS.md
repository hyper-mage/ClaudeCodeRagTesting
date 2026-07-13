# Phase 17: Agent Personas - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 18 (7 new, 11 modified)
**Analogs found:** 18 / 18 (17 exact/near-exact clones of the shipped v1.2 model-pin; 1 novel refactor with a partial analog)

> **One-line thesis:** Every file in this phase clones a shipped, tested v1.2 model-pin file. The ONE genuinely new behavior is splitting `settings.system_prompt` into an operational base + per-persona voice overlay (Pattern A below). Everything else is "copy the model-pin file, s/model/persona/, delete the key/cost/demo machinery."

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/services/persona_service.py` | service (registry) | transform / lookup | `backend/services/model_catalog_service.py` (split model) + `backend/config.py` constants | role-match (no cost/refresh) |
| `backend/routers/personas.py` | router | request-response (GET catalog) | `backend/routers/models.py` | exact |
| `backend/config.py` (`system_prompt`) | config | transform (prompt text) | itself (in-place refactor) — see Pattern A | novel (partial) |
| `backend/services/llm_service.py` (`stream_chat_completion`) | service | streaming (LLM) | itself, `system_content` assembly L90-92 | exact (add param) |
| `backend/routers/chat.py` (`_resolve_persona` + call sites) | router | request-response / streaming | `_safe_thread_model` L144 / `_safe_user_default_model` L153 / `_resolve_key_and_model` L224 | exact (minus key/cost tiers) |
| `supabase/migrations/20240301000035_add_persona_columns.sql` | migration | schema DDL | `...032_create_user_preferences_and_thread_model.sql` L57-62 | exact |
| `backend/routers/threads.py` (`PATCH`) | router | CRUD (partial write) | `update_thread_model` L58-89 + `preferences.py` `exclude_unset` L75 | exact (switch to exclude_unset) |
| `backend/routers/preferences.py` (GET/PUT) | router | CRUD (upsert) | `favorite_models` block L48-96 | exact (add field) |
| `backend/models/schemas.py` (Persona/Thread/Prefs) | model | data shape | `ThreadResponse` L25-33, `PreferencesResponse` L42-53, `ThreadModelUpdate` L73-81, `ModelResponse` L165-181 | exact |
| `backend/main.py` (router register) | config | wiring | L9 import + L64-71 `include_router` | exact |
| `frontend/src/components/PersonaSelector.tsx` | component | request-response (fetch+select) | `ModelSelector.tsx` (structure only) / `DefaultModelSelector.tsx` (self-contained) | role-match (strip gate/pricing) |
| `frontend/src/components/DefaultPersonaSelector.tsx` | component | request-response (self-PUT) | `DefaultModelSelector.tsx` L30-60 | exact (strip `useKeyGate`) |
| `frontend/src/pages/ChatPage.tsx` (Thread + handler) | page | event-driven (optimistic PATCH) | `Thread` iface L15-22 + `handleThreadModelChange` L103-120 | exact (strip `useKeyGate`) |
| `frontend/src/components/ChatContainer.tsx` (header) | component | presentation | model selector row L91-116 | exact |
| `frontend/src/pages/SettingsPage.tsx` (render) | page | presentation | `DefaultModelSelector` placement (§L167-171 per research) | role-match |
| `backend/tests/test_persona_resolution.py` | test | unit | `test_key_model_resolution.py` (`_db_with_key_row`, MagicMock chain) | exact |
| `backend/tests/test_thread_persona_patch.py` + `test_personas_api.py` | test | unit | `test_thread_model_patch.py` / `test_models_api.py` | exact |
| `frontend/src/components/PersonaSelector.test.tsx` + `DefaultPersonaSelector.test.tsx` | test | unit | `DefaultModelSelector.test.tsx` (minus `useKeyStatus` mock) | exact (drop gate mock) |

---

## Pattern Assignments

### Pattern A (NOVEL) — `backend/config.py` + `backend/services/persona_service.py` + `backend/services/llm_service.py`: split system prompt into base + voice overlay

This is the only non-clone in the phase (D-01/D-02/D-03). Three files move together.

**A1. `backend/config.py` — strip `system_prompt` to the operational base.**

**Current code** (`backend/config.py:95-109`) — bundles opener + KB-first bias + operational rules:
```python
system_prompt: str = (
    "You are a helpful assistant with access to tools. Answer questions clearly and concisely. "   # ← opener: DROP (voice supplies its own)
    "Prefer the knowledge base for game rules and mechanics; use web_search only for current or "   # ← KB-first bias: MOVE to Expert voice (D-03)
    "external facts the knowledge base cannot answer (prices, availability, upcoming expansions, "
    "BGG rankings, designer/publisher news). "
    "When you use web search results, cite each source as an inline markdown link at the point the " # ← citation: KEEP in base (D-02)
    "fact is used (e.g. [BGG](https://boardgamegeek.com/...)), and end your answer with a short "
    "\"Sources:\" list of the links you relied on. "
    "If a tool returns an error, briefly tell the user it couldn't be reached, then answer "         # ← tool-error: KEEP in base (D-02)
    "best-effort from the knowledge base or your own knowledge. "
    "When showing database query results, format them as markdown tables when appropriate. "        # ← tables: KEEP in base (D-02)
    "When a user asks about a specific document by name (e.g. summarize, extract key points, "       # ← analyze_document: KEEP in base (D-02)
    "or answer detailed questions requiring the whole document), use the analyze_document tool "
    "instead of search_documents."
)
```
Executor: DELETE lines 96-99 (opener + KB-first bias) from the base; the remaining citation/tool-error/tables/analyze rules become the persona-agnostic base. `subagent_system_prompt` (L142) and `explorer_system_prompt` (L151) are OUT OF SCOPE — do not touch.

> **Runtime gotcha (Pitfall 6, verified via MEMORY / STATE Phase 16):** a `SYSTEM_PROMPT` value in `.env`/`.env.prod` SHADOWS this default via pydantic-settings. Remove it or the refactored base never reaches the running app.

**A2. `backend/services/persona_service.py` (NEW) — registry constant + 3 helpers.**
Definition-in-code mirrors how `system_prompt`/`TOOL_SELECTION_GUIDE` live in code (D-07). No DB, no cache. Recommended shape (voice wording is Claude's discretion):
```python
DEFAULT_PERSONA_ID = "board_game_expert"

PERSONAS = [
    {"id": "board_game_expert", "label": "Board-Game Expert", "is_default": True,
     "voice_block": "You are a board-game expert ... Prefer the knowledge base for game rules "
                    "and mechanics; use web_search only for current or external facts ..."},   # D-03 bias lives HERE
    {"id": "general_assistant", "label": "General Assistant", "is_default": False,
     "voice_block": "You are a helpful, general-purpose assistant ... do not assume the user's "
                    "question is about board games."},                                          # D-06
]

def list_personas() -> list[dict]:   # public catalog: id/label/is_default ONLY (never voice_block, A5)
    return [{"id": p["id"], "label": p["label"], "is_default": p["is_default"]} for p in PERSONAS]

def resolve_persona_id(pinned: str | None) -> str:   # D-10: valid id wins, else system default (never raises)
    ids = {p["id"] for p in PERSONAS}
    return pinned if pinned in ids else DEFAULT_PERSONA_ID

def get_persona_voice(persona_id: str) -> str:
    by_id = {p["id"]: p for p in PERSONAS}
    return by_id.get(persona_id, by_id[DEFAULT_PERSONA_ID])["voice_block"]
```

**A3. `backend/services/llm_service.py` — thread a `persona_voice` param and compose.**
Analog is the function itself. Current signature (`llm_service.py:62-71`) and current single-line assembly (`L90-92`):
```python
def stream_chat_completion(
    messages: list[dict], tools: list[dict] | None = None, tool_guide: str | None = None,
    source_hint: str | None = None, scope_hint: dict | None = None,
    api_key: str | None = None, model: str | None = None, trace: bool = True,   # ← add persona_voice: str | None = None here, mirroring api_key/model
) -> Generator[dict, None, None]:
    ...
    system_content = settings.system_prompt          # ← now the operational BASE
    if tool_guide:                                    # ← UNCHANGED (D-04) — appended for ALL personas
        system_content += "\n\n" + tool_guide
```
Executor change: add `persona_voice: str | None = None` to the signature (same slot style as `api_key`/`model`), then compose voice FIRST so exactly one "You are…" leads (Pitfall 2):
```python
system_content = settings.system_prompt              # operational base (D-02)
if persona_voice:                                     # None → base-only (back-compat for sub-agent callers)
    system_content = persona_voice + "\n\n" + system_content
if tool_guide:
    system_content += "\n\n" + tool_guide             # unchanged (D-04)
# ... existing source_hint / scope_hint blocks (L94-123) stay verbatim ...
```

---

### `backend/routers/personas.py` (NEW router, request-response)

**Analog:** `backend/routers/models.py` (exact clone, minus refresh/cache).

**Imports + router + auth-gated GET** (`models.py:24-53`):
```python
from fastapi import APIRouter, Depends
from auth import get_user_id
from models.schemas import ModelResponse
from services.model_catalog_service import build_model_response, refresh_if_stale

router = APIRouter(prefix="/api/models", tags=["models"])

@router.get("", response_model=list[ModelResponse])
def list_models(free_only: bool = False, user_id: str = Depends(get_user_id)) -> list[dict]:
    db = get_supabase()
    rows = refresh_if_stale(db)
    ...
```
Persona version drops the DB/refresh entirely (catalog is a code constant):
```python
# backend/routers/personas.py
from fastapi import APIRouter, Depends
from auth import get_user_id
from models.schemas import PersonaResponse
from services.persona_service import list_personas

router = APIRouter(prefix="/api/personas", tags=["personas"])

@router.get("", response_model=list[PersonaResponse])
def get_personas(user_id: str = Depends(get_user_id)) -> list[dict]:
    return list_personas()   # [{id,label,is_default}] — voice_block NEVER shipped to client (A5)
```

**Register in `backend/main.py`** — mirror L9 + L64-71:
```python
from routers import threads, chat, documents, folders, demo, keys, models, preferences   # ← add `personas`
...
app.include_router(preferences.router)
app.include_router(personas.router)   # ← ADD
```

---

### `backend/routers/chat.py` — per-turn persona resolver (request-response, no-bleed)

**Analog:** `_safe_thread_model` (L144-150), `_safe_user_default_model` (L153-171), and the resolver call site inside `event_generator` (L898-901) + stream call (L1077-1086). **DO NOT widen `_resolve_key_and_model`'s 4-tuple** — ~15 tests unpack exactly `api_key, model, mode, is_user_key` (Pitfall 8). Add a SIBLING resolver.

**Clone these two helpers** (`chat.py:144-171`), stripping the DB-query one to a `default_persona` select:
```python
def _safe_thread_model(thread_row: dict | None) -> str | None:
    return thread_row.get("model") if thread_row else None   # absent-KEY read off SELECT * (no 42703)

def _safe_user_default_model(db, user_id: str) -> str | None:
    try:
        r = (db.table("user_preferences").select("default_model")
             .eq("user_id", user_id).maybe_single().execute())
        return r.data.get("default_model") if r and r.data else None
    except Exception as e:   # 42P01 pre-migration tolerance — swallow, fall through
        logger.debug(f"user_preferences not available (pre-P13): {scrub_secrets(str(e))}")
        return None
```
New sibling (`_safe_thread_persona`/`_safe_user_default_persona`/`_resolve_persona`) — same shape, but the tier chain ends at `resolve_persona_id(...)` + `get_persona_voice(...)` instead of `settings.llm_model`, and has NO key/mode/demo/free-guard branches:
```python
def _resolve_persona(db, user_id: str, thread_row: dict | None, body) -> str:
    """Per-request persona VOICE. NOT @lru_cache'd (Pitfall 4 no-bleed) — called once per turn."""
    pinned = (
        getattr(body, "persona", None)              # optional future override (A4 — may omit)
        or _safe_thread_persona(thread_row)         # per-thread pin
        or _safe_user_default_persona(db, user_id)  # user default (42P01-tolerant)
    )
    return get_persona_voice(resolve_persona_id(pinned))   # D-10 validate → default; then voice
```

**Call site** — the existing per-request resolve inside `event_generator` (`chat.py:898-901`), add ONE line immediately after:
```python
api_key, model, mode, is_user_key = _resolve_key_and_model(db, user_id, thread.data, body)
persona_voice = _resolve_persona(db, user_id, thread.data, body)   # NEW — same non-cached per-turn scope
```

**Stream call** — the existing kwargs at `chat.py:1077-1086`, add one kwarg:
```python
for event in stream_chat_completion(
    current_messages, tools=tools,
    tool_guide=TOOL_SELECTION_GUIDE if tools else None,   # unchanged (D-04)
    source_hint=source_scope, scope_hint=scope_hint if scope_hint else None,
    api_key=api_key, model=model, trace=(not is_user_key),
    persona_voice=persona_voice,                          # NEW
):
```

> **PERS-02 guard (Pitfall 3):** the `tools=tools` list is built from doc/web availability ONLY (chat.py `_traced_turn` per research L963-980) — persona must NEVER gate it. Leave tool assembly untouched.

---

### `supabase/migrations/20240301000035_add_persona_columns.sql` (NEW, schema DDL)

**Analog:** `20240301000032_create_user_preferences_and_thread_model.sql:57-62`. Migration head is confirmed `034` (last file in `supabase/migrations/`) → next = `035`.

The exact additive-column pattern to clone (from `032`, L58-62):
```sql
-- (2) threads.model — per-thread model pin (nullable, no DEFAULT, no backfill).
-- Existing threads keep model = NULL and resolve through the default tier (D-05).
-- Inherits the existing own-row threads RLS automatically (no new policy needed).
ALTER TABLE threads ADD COLUMN model TEXT;
```
Persona migration = two such lines, no RLS (own-row policies from `032` cover the whole row), no CHECK/FK (D-10 requires a removed id to fall back, never raise):
```sql
-- Phase 17 — persona pin columns (additive, mirrors migration 032). Nullable, no backfill.
ALTER TABLE threads ADD COLUMN persona TEXT;
ALTER TABLE user_preferences ADD COLUMN default_persona TEXT;
```
> **Apply gotcha (Pitfall 7, MEMORY):** `db push` may replay old migrations ("already exists"); run `supabase migration repair --status applied` on the prior range first. Apply to BOTH dev (`.env`) and prod (`.env.prod`) projects; prod deferred to deploy.

---

### `backend/routers/threads.py` — PATCH accepts `persona` (CRUD, partial write)

**Analog:** `update_thread_model` (`threads.py:58-89`) for the ownership re-check; `preferences.py:75` for the `exclude_unset` mechanism. The model PATCH currently hardcodes `{"model": body.model}` — switch to a partial dump so a persona-only PATCH does not clobber `model` and vice-versa.

**Current (hardcoded single field)** `threads.py:81-89`:
```python
updated = (
    db.table("threads")
    .update({"model": body.model})            # ← hardcodes one field
    .eq("id", thread_id).eq("user_id", user_id).execute()   # ownership re-check (IDOR)
)
return updated.data[0]
```
**Partial-write mechanism to adopt** — `preferences.py:75`:
```python
patch = body.model_dump(exclude_unset=True)   # only the keys the client actually sent
```
**Recommended merged form** (keep the ownership re-check L70-79 verbatim; body becomes `ThreadUpdate`):
```python
patch = body.model_dump(exclude_unset=True)   # {"persona":"..."} OR {"model":None} — never both unless sent
updated = (db.table("threads").update(patch)
           .eq("id", thread_id).eq("user_id", user_id).execute())
return updated.data[0]
```
> Existing `test_thread_model_patch.py` stays GREEN: `{model:"x/y"}` → `exclude_unset` → `{"model":"x/y"}`; `{model:null}` → `{"model":None}` (both explicit-set → included).

---

### `backend/routers/preferences.py` — `default_persona` in GET + PUT (CRUD, upsert)

**Analog:** the `favorite_models` field, already threaded through both handlers (`preferences.py:48-60` GET, `L75-96` PUT). Persona clones it exactly.

GET select + null-tolerant response (`L45-60`):
```python
.select("default_model, theme, favorite_models")     # ← add default_persona
...
return {
    "default_model": row.data.get("default_model"),
    "theme": row.data.get("theme") or "dark",
    "favorite_models": row.data.get("favorite_models") or [],   # ← add "default_persona": row.data.get("default_persona")
}
```
PUT is already generic via `exclude_unset` (`L75-80`) — no logic change, just add `default_persona` to the two `.select(...)` strings and the two return dicts (GET + the post-upsert re-select). `user_id` stays JWT-bound (`patch["user_id"] = user_id`, L76).

---

### `backend/models/schemas.py` — response/request field additions (model)

**Analogs (all in one file):**
- New `PersonaResponse` → clone `ModelResponse` (L165-181) but 3 fields only:
  ```python
  class PersonaResponse(BaseModel):
      id: str
      label: str
      is_default: bool          # voice_block deliberately absent (A5 — prompt text stays server-side)
  ```
- `ThreadResponse` (L25-33) — add `persona: str | None = None` beside `model: str | None = None` (L33). **Pitfall 1: without this, `response_model` STRIPS `persona` even though `select('*')` returns it** — documented on this very file (the `usage` field, L97-102).
- `ThreadModelUpdate` (L73-81) → rename `ThreadUpdate`, add `persona`:
  ```python
  class ThreadUpdate(BaseModel):
      model: str | None = None
      persona: str | None = None
  ```
  Update the import in `threads.py:4` (`ThreadModelUpdate` → `ThreadUpdate`).
- `PreferencesResponse` (L42-53) — add `default_persona: str | None = None`.
- `PreferencesUpdate` (L56-70) — add `default_persona: str | None = None` (keeps `exclude_unset` partial semantics like `favorite_models` L70).

---

### `frontend/src/components/DefaultPersonaSelector.tsx` (NEW) + `PersonaSelector.tsx` (NEW)

**Analog:** `DefaultModelSelector.tsx` (self-contained self-PUT). **Do NOT reuse `ModelSelector.tsx`** — it is hard-typed to `ModelResponse` (is_free/pricing/popularity/favorites/search, see `ModelSelector.tsx:10-19`) and wraps every pick in `useKeyGate`. Persona has none of that. Build a ~40-line dropdown over 2 items.

**The self-PUT + optimistic-onChange pattern to clone** — `DefaultModelSelector.tsx:37-47`, MINUS the `useKeyGate` wrapper (L34):
```tsx
// DefaultModelSelector currently gates first:
const { guardedSelect, gateModal } = useKeyGate({ kind: 'default', models, onApply: (modelId) => {
    if (modelId == null) return
    onChange?.(modelId)
    void apiFetch('/api/preferences', { method: 'PUT', body: JSON.stringify({ default_model: modelId }) }).catch(() => {})
}})
```
Persona version — call `apiFetch` DIRECTLY (no gate, no modal); a keyless user must be able to pick a persona:
```tsx
function onSelect(personaId: string) {
  onChange?.(personaId)
  void apiFetch('/api/preferences', {
    method: 'PUT', body: JSON.stringify({ default_persona: personaId }),   // fire-and-forget (house style)
  }).catch(() => {})
}
```
**Catalog fetch** — both persona pickers fetch `GET /api/personas` (never hardcode the list, D-07); the fetch idiom is `apiFetch('/api/personas')` returning `[{id,label,is_default}]` (mirror the `apiFetch('/api/models')` mount fetch in `ChatPage.tsx:67-75`, which guards `Array.isArray` before setState).

---

### `frontend/src/pages/ChatPage.tsx` — `persona` on Thread + PATCH handler (event-driven)

**Analog:** `Thread` interface (`ChatPage.tsx:15-22`) + `handleThreadModelChange` (`L103-120`). Clone the handler, drop the `useKeyGate` wrap (`L125-130`) — pass the handler DIRECTLY to the picker.

Add `persona: string | null` to the `Thread` interface beside `model` (L21). Handler (`L103-120`) verbatim minus the gate:
```tsx
const handleThreadPersonaChange = useCallback(async (personaId: string) => {
  if (!activeThreadId) return
  setThreads(prev => prev.map(t => t.id === activeThreadId ? { ...t, persona: personaId } : t))   // optimistic
  try {
    await apiFetch(`/api/threads/${activeThreadId}`, {
      method: 'PATCH', body: JSON.stringify({ persona: personaId }),
    })
  } catch (err) {
    Sentry.captureException(err)
    showToast("Couldn't update the persona for this chat. Try again.", 'error')
  }
}, [activeThreadId, showToast])
```

---

### `frontend/src/components/ChatContainer.tsx` + `frontend/src/pages/SettingsPage.tsx` — render the pickers (presentation)

**ChatContainer analog:** the per-thread model selector row (`ChatContainer.tsx:91-116`). Render `PersonaSelector` beside `ModelSelector` in the same `activeThreadId !== null` shrink-0 header row:
```tsx
<ModelSelector value={threadModel} onSelect={onThreadModelChange} placeholder={...} extraOption={{...}} models={models} />
// ↑ add a sibling <PersonaSelector value={threadPersona} onSelect={onThreadPersonaChange} /> in the same row
```
**SettingsPage analog:** wherever `DefaultModelSelector` is placed (research §L167-171). Add `<DefaultPersonaSelector value={defaultPersona} onChange={...} />` alongside it, seeded from `GET /api/preferences.default_persona`.

---

### Tests (unit — Wave 0 RED scaffolds)

| New test | Analog (clone the harness) | Key contract |
|----------|---------------------------|--------------|
| `backend/tests/test_persona_resolution.py` | `test_key_model_resolution.py` — `_db_with_key_row` MagicMock chain (L44-90), `.table().select().eq().maybe_single().execute().data` | Null pin + null default → `board_game_expert` (PERS-03); unknown id → default (D-10); two back-to-back resolves with different pins never cross (PERS-06) |
| `backend/tests/test_thread_persona_patch.py` | `test_thread_model_patch.py` — `_mock_db(owned)`, `dependency_overrides[get_user_id]`, `patch("routers.threads.get_supabase")` (L26-42) | PATCH `{persona}` scoped by `id`+`user_id`; persona-only body does NOT clobber model; 404 on non-owned |
| `backend/tests/test_personas_api.py` | `test_models_api.py` — `dependency_overrides[get_user_id] = lambda: "user-uuid"` (L96), TestClient (L84-101) | Auth-gated; returns `[{id,label,is_default}]`; exactly one `is_default` |
| extend `backend/tests/test_preferences_api.py` | its own `favorite_models` block | `default_persona` roundtrips PUT→GET; theme-only PUT doesn't clobber it |
| extend `backend/tests/test_config.py` | its `system_prompt` assertions | base still carries citation guidance; NO longer carries KB-first bias |
| `frontend/src/components/PersonaSelector.test.tsx` + `DefaultPersonaSelector.test.tsx` | `DefaultModelSelector.test.tsx` — `vi.mock('../lib/api', () => makeApiMock())` (L10), `renderWithProviders` (L56) | Select → PATCH/PUT with `{persona}`/`{default_persona}`. **DROP the `useKeyStatus` gate mock (L16-21)** — persona has no gate |

> **Keep GREEN:** `test_web_search.py::test_system_prompt_citation_guidance` — citation guidance MUST stay in the operational base (D-02).

---

## Shared Patterns

### 3-tier nullable resolution (thread pin → user default → system default)
**Source:** `backend/routers/chat.py:144-171` (`_safe_thread_model` / `_safe_user_default_model`) + `L246-252` (tier chain).
**Apply to:** the persona resolver. Each tier tolerates an absent column (reads off the SELECT-* row = absent-KEY → None; the `user_preferences` query is wrapped in `try/except` for pre-migration 42P01). **The persona resolver has NO key/mode/demo/free-guard branches** — those are model-only (`_resolve_key_and_model` L254-295 is NOT cloned).

### Per-request no-bleed resolution (PERS-06)
**Source:** `backend/routers/chat.py:890-901` — resolver is a plain module function called ONCE inside `event_generator`, explicitly NOT `@lru_cache`'d (L229 comment). `PERSONAS` is a module constant (same for all users — fine); only the per-user *pinned id* is read fresh per turn.
**Apply to:** `_resolve_persona` (same scope, same non-cached property).

### Own-row RLS covers new columns (no new policy)
**Source:** `supabase/migrations/20240301000032_...sql:34-62` — own-row policies on `user_preferences`; `threads` own-row RLS pre-existing. A `ADD COLUMN` inherits the row's policies.
**Apply to:** migration `035` — add NO policies.

### Auth-gated router
**Source:** `backend/routers/models.py:34-38` — every route is `Depends(get_user_id)`. `PATCH /api/threads/{id}` re-checks ownership `.eq("id",tid).eq("user_id",uid)` (`threads.py:70-79`); `PUT /api/preferences` binds `user_id` from JWT never body (`preferences.py:76`).
**Apply to:** `personas.py`, and the persona additions to `threads.py`/`preferences.py`.

### `response_model` field-declaration (Pitfall 1)
**Source:** `backend/models/schemas.py:97-102` — the `usage` field comment documents that FastAPI strips any undeclared field even when `select('*')` returns it.
**Apply to:** declare `persona` on `ThreadResponse` and `default_persona` on `PreferencesResponse` BEFORE wiring read paths.

### Optimistic-update + fire-and-forget persist (frontend house style)
**Source:** `frontend/src/pages/ChatPage.tsx:103-120` (optimistic setThreads then PATCH, toast on failure) and `frontend/src/components/DefaultModelSelector.tsx:43-46` (`void apiFetch(...).catch(() => {})`).
**Apply to:** `handleThreadPersonaChange` and `DefaultPersonaSelector.onSelect` — but WITHOUT the `useKeyGate` wrapper both model paths carry.

---

## No Analog Found

None. Every file has a working v1.2 model-pin analog. The single novel behavior (system-prompt base/voice split, Pattern A) has a partial analog — the composition seam already exists at `llm_service.py:90-92`; only the "split one constant into two" edit is new, and its shape is fully specified in RESEARCH Pattern 1.

## Files that do NOT need changes (verify-and-skip)

| File | Why no change |
|------|---------------|
| `frontend/src/hooks/useChat.ts` | Send body carries only `content` + optional `use_demo` (`useChat.ts:164`). Model is NOT sent in the body — it rides the thread pin (PATCH → `threads.model` → resolver reads `thread_row`). Persona follows the identical path, so useChat needs NO change for the primary per-thread path (A4: `body.persona` override deferred). |
| `frontend/src/lib/api.ts` | `apiFetch` is already generic (used verbatim by the persona PATCH/PUT handlers). No persona-specific change. |
| `backend/services/llm_service.py` source_hint/scope_hint blocks (L94-123) | Unchanged — only the `system_content` seed line + new `persona_voice` param compose. |
| `TOOL_SELECTION_GUIDE` + its append (`chat.py:634`, `L1080`) | Unchanged (D-04) — appended for ALL personas; guarantees full tool access. |
| `backend/services/subagent_service.py`, `explorer_service` | OUT OF SCOPE — sub-agents keep their own prompts (`config.py:142,151`); persona threads into `stream_chat_completion` only. |

---

## Metadata

**Analog search scope:** `backend/routers/`, `backend/services/`, `backend/models/`, `backend/tests/`, `supabase/migrations/`, `frontend/src/components/`, `frontend/src/pages/`, `frontend/src/hooks/`, `frontend/src/lib/`
**Files read for extraction:** `config.py`, `llm_service.py`, `models.py`, `main.py`, `chat.py` (L140-300, 880-909, 1070-1100), `threads.py`, `preferences.py`, `schemas.py`, `migration 032`, `DefaultModelSelector.tsx`, `api.ts`, `ChatPage.tsx`, `ChatContainer.tsx`, `ModelSelector.tsx` (L1-75), `useChat.ts` (grep), `test_thread_model_patch.py`, `test_models_api.py`, `test_key_model_resolution.py` (L1-90), `DefaultModelSelector.test.tsx`
**Migration head verified:** `034` (last in `supabase/migrations/`) → next = `035`
**Pattern extraction date:** 2026-07-12
