# Phase 17: Agent Personas - Research

**Researched:** 2026-07-12
**Domain:** Additive per-thread/per-user preference feature on an existing FastAPI + Supabase + React stack (system-prompt composition refactor + a new pin dimension mirroring the shipped v1.2 model-pin infrastructure)
**Confidence:** HIGH (all findings verified against the working codebase — this phase reuses a proven, tested pattern end-to-end)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Prompt composition (the core decision)**
- **D-01:** Persona system prompts are built as **shared operational base + per-persona voice overlay** — NOT a full standalone prompt per persona. Extract the persona-agnostic operational rules into a shared base block applied for every persona; each persona contributes only a short voice/role block.
- **D-02:** The **shared operational base** contains only persona-agnostic rules: web-source **citation format** (inline markdown link at point-of-use + trailing "Sources:" list), **tool-error handling** ("briefly tell the user it couldn't be reached, then answer best-effort"), **markdown tables for DB query results**, and the **`analyze_document`-by-name** guidance.
- **D-03:** The current `settings.system_prompt` "**prefer the knowledge base for game rules/mechanics; use web_search only for external facts**" source-routing bias is **Board-Game Expert voice**, NOT operational base. It moves into the Expert's voice block. The General Assistant does not carry this KB-first bias.
- **D-04:** `TOOL_SELECTION_GUIDE` (chat.py) continues to be appended for **all** personas (unchanged mechanism at `llm_service.stream_chat_completion`). Tool access is preserved by construction for every persona.

**Persona catalog**
- **D-05:** Ship **exactly 2** personas in v1.3: **Board-Game Expert** (`is_default = true`) and **General Assistant**.

**General Assistant behavior (PERS-02)**
- **D-06:** General Assistant is a **truly general** assistant — plain helpful-assistant voice, no board-game framing and no KB-first source bias. All tools (KB search, `web_search`, SQL, `analyze_document`) remain callable; the shared operational base still governs HOW a tool is cited / how errors are handled.

**Persona storage / source of truth**
- **D-07:** Persona definitions (`id`, `label`, `voice_block`, `is_default`) live in a **backend Python registry constant**, exposed via a small **`GET /api/personas`** endpoint the pickers fetch. No migration/seed for the catalog. Frontend fetches the list (do NOT hardcode the FE list).

**Pin storage + resolution (mirror the v1.2 model pattern)**
- **D-08:** Add pin columns mirroring migration `032`: a nullable **`threads.persona`** column (per-thread pin) and a **`user_preferences.default_persona`** column (per-user default). Both nullable; null resolves through the tier chain. Additive migration, no backfill. Reuse existing own-row RLS — no new policies.
- **D-09:** Persona resolves in the **same per-turn resolver** as key/model in `chat.py` (~line 233), guaranteeing no cross-user/thread bleed by the same mechanism (PERS-06). Tier chain, each tolerant of an absent column: `thread_row.persona? → user_preferences.default_persona? → system default (Board-Game Expert)`. (Optional `body.persona` per-message override may be threaded in the same shape as `body.model`, but per-thread pin is the primary UI path.)
- **D-10:** **Unknown/removed persona id** falls back to the system default (Board-Game Expert). The resolver validates the pinned id against the registry; the `/api/personas`-fed picker also prevents sending an invalid id. No persisted "notice" row required.
- **D-11:** Persona switching is **per-request / next-turn** — inherited automatically from the per-request resolution seam.

**UI attribution**
- **D-12:** **Picker-only, no per-message persona badge.** Chat picker mirrors `ModelSelector.tsx`; settings picker mirrors `DefaultModelSelector.tsx`. No `messages` schema change.

### Claude's Discretion
- Exact voice-block wording for each persona (Expert must encode D-03's KB-first bias; General Assistant reads as non-board-game-specialized per D-06).
- The precise refactor seam for splitting `settings.system_prompt` into base + Expert voice (e.g. a base-prompt constant + a `voice_block` per registry entry, composed in `stream_chat_completion`).
- Whether a `body.persona` per-message override param is added now or left as a future seam.
- Picker component structure/placement details (reuse vs. adapt `ModelSelector`).

### Deferred Ideas (OUT OF SCOPE)
- **User-editable custom persona prompts** (CRUD, storage, prompt-injection review) — PERS-F1.
- **Per-persona tool allowlists** — PERS-F2. All v1.3 personas retain full tool access.
- **Curated set of 3-4 personas** — ship exactly 2 now (D-05).
- **Per-message persona badge on assistant bubbles** — picker-only for v1.3 (D-12).
- **`body.persona` per-message override** — optional seam; per-thread pin is the primary path.
- Sub-agent prompts (`subagent_system_prompt`, `explorer_system_prompt`) are NOT in scope — personas apply to the **main chat loop only**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PERS-01 | Select an agent persona for a thread from a predefined set via a chat-UI picker (mirrors the model picker) | New `PersonaSelector` in `ChatContainer` header row (§Frontend); `PATCH /api/threads/{id}` extended with `persona` (§Backend Routes); catalog from `GET /api/personas` |
| PERS-02 | "General Assistant" persona behaves as a vanilla model while retaining full tool access | Prompt composition split (§Pattern 1); tools list is persona-independent in `chat.py` `_traced_turn` (lines 963-980) — persona never gates `tools=` (§Don't Hand-Roll, Pitfall 3) |
| PERS-03 | Board-game-expert persona preserved as the default | Registry `is_default=true` on Board-Game Expert; system-default fallback in resolver (D-09); existing threads (null pin) resolve to it (§Pattern 3) |
| PERS-04 | Set default persona (applied to new threads) on the settings page | `user_preferences.default_persona` column (migration 035); `PUT /api/preferences {default_persona}`; `DefaultPersonaSelector` in `SettingsPage` (§Frontend) — mirrors `DefaultModelSelector` |
| PERS-05 | A thread's persona selection persists across sessions and is restored | `threads.persona` column rides `select('*')` on thread read (threads list + `GET /api/threads/{id}`); picker seeds from `activeThread.persona` (§Pattern 4) |
| PERS-06 | Selected persona's system prompt resolved per chat request (no cross-user/thread bleed) | Per-request resolver in `chat.py` `event_generator` (not `@lru_cache`'d, called once per turn); mirror `test_no_cross_user_bleed` (§Validation) |
</phase_requirements>

## Summary

Phase 17 is an **additive feature that clones a fully-shipped, fully-tested pattern** — the v1.2 model pin (migration `032`, Phases 11–15). Every architectural question is already answered by working code: the 3-tier nullable resolution (`thread → user_preferences → system default`), the per-request no-bleed resolver in `chat.py`, the additive nullable-column migration with own-row RLS, the `GET` catalog endpoint (`models.py`), and the per-thread/settings picker pair (`ModelSelector` / `DefaultModelSelector`). The work is to mirror each of these for a `persona` dimension, plus one genuinely new piece: **splitting the monolithic `settings.system_prompt` into a persona-agnostic operational base + per-persona voice overlays** composed in `stream_chat_completion`.

The single most important simplification versus the model pin: **persona has no key/cost/demo dimension.** The model pin is entangled with BYOK key resolution, the demo free-guard (`_demo_model_for`), deprecated-pin fallback, and the `useKeyGate` UI interception. **None of that applies to persona.** A keyless user can freely pick a persona; there is no gate, no cost, no `model_cache` validation — only registry-id validation. This means the persona picker is dramatically simpler than the 560-line `ModelSelector` combobox, and the persona resolver is a clean 3-tier read with no fail-closed branching.

**Primary recommendation:** Repurpose `settings.system_prompt` to hold **only** the operational base (D-02); put a `persona_service.py` registry (`PERSONAS` + `resolve_persona_id()` + `get_persona_voice()`) and a thin `routers/personas.py` (`GET /api/personas`); add `_resolve_persona()` beside `_resolve_key_and_model()` in `chat.py` (same per-request scope, called once per turn); thread the resolved voice string into `stream_chat_completion(..., persona_voice=...)`; add migration `035` with two nullable TEXT columns; extend `PATCH /api/threads/{id}` and `PUT /api/preferences` with a `persona`/`default_persona` field via `exclude_unset`; and build dedicated lightweight `PersonaSelector` / `DefaultPersonaSelector` components (do NOT reuse `ModelSelector` — its `ModelResponse` shape and key gate do not fit).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persona catalog (source of truth) | API/Backend (Python registry constant) | — | D-07: prompt text versions with code like `system_prompt`/`TOOL_SELECTION_GUIDE`; served read-only to the client |
| Persona pin storage | Database (`threads.persona`, `user_preferences.default_persona`) | — | D-08: user-scoped, own-row RLS; mirrors `threads.model`/`user_preferences.default_model` |
| Persona resolution (per request) | API/Backend (`chat.py` resolver) | — | D-09/PERS-06: no-bleed comes from per-request resolution, never cached; runs server-side only |
| System-prompt composition (base + voice) | API/Backend (`llm_service.stream_chat_completion`) | — | D-01/D-02/D-03: the LLM system message is assembled server-side; the voice_block never crosses to the client |
| Persona persistence writes | API/Backend routes (`threads.py` PATCH, `preferences.py` PUT) | Browser (fire-and-forget call) | Mirrors model-pin write paths; ownership re-check + JWT-bound user_id |
| Persona picker UI | Browser/Client (React) | API (reads `GET /api/personas`) | D-12: presentation only; picker fetches the list, never hardcodes it |

## Standard Stack

This phase adds **zero new dependencies.** Everything is already installed and in use. Versions below are **[VERIFIED: file read]** from `backend/requirements.txt` and `frontend/package.json` on 2026-07-12.

### Core (already present — no install)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.12 | Router + `Depends(get_user_id)` auth + Pydantic response models | Existing app framework (CLAUDE.md) |
| Pydantic | 2.11.1 | `PersonaResponse`, extend `PreferencesUpdate`/`ThreadUpdate` | CLAUDE.md: "Use Pydantic for structured LLM outputs" and request/response models |
| pydantic-settings | 2.9.1 | `Settings` (holds the operational base prompt) | Existing config pattern (`backend/config.py`) |
| supabase (py) | 2.13.0 | Service-role client for pin reads/writes | Existing DB access (`backend/database.py`) |
| openai | 1.74.0 | Raw SDK chat completions (persona voice enters the system message) | CLAUDE.md: raw SDK only, NO LangChain |
| React | 19.2.4 | `PersonaSelector` / `DefaultPersonaSelector` components | Existing frontend |
| lucide-react | 0.577.0 | Icons (Check/ChevronDown) for the picker | Already used by `ModelSelector` |

### Supporting (test tooling — already present)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.4.2 | Backend resolver/registry/route tests | Wave 0 RED scaffolds (mirror `test_key_model_resolution.py`) |
| pytest-asyncio | 0.23.8 | Async route tests (`asyncio_mode = auto`) | Already configured in `pytest.ini` |
| vitest | 4.1.9 | Frontend picker component tests | Mirror `DefaultModelSelector.test.tsx` |
| @testing-library/react | 16.3.2 | Render + `userEvent` picker interaction | Existing pattern; `renderWithProviders` in `src/test/utils.tsx` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dedicated `PersonaSelector` | Reuse `ModelSelector.tsx` | ✗ Reject: `ModelSelector` is hard-typed to `ModelResponse` (is_free/pricing/popularity/favorites/search) and wraps every pick in `useKeyGate`. Persona has none of those. Faking `ModelResponse` shapes for 2 items is worse than a 40-line dedicated dropdown. |
| Registry in `services/persona_service.py` | Registry constant inline in `chat.py` | Prefer a service module: both `chat.py` (resolver) and `routers/personas.py` (endpoint) import it; mirrors `models.py` ↔ `model_catalog_service.py` split. Inline-in-chat.py is acceptable but couples the endpoint to the chat router. |
| Repurpose `settings.system_prompt` as the base | Add a new `persona_base_prompt` field, leave `system_prompt` dead | Repurpose is the CONTEXT-intended path (D-03 "moves into the Expert's voice block"). New-field avoids the `SYSTEM_PROMPT` env-shadow (Pitfall 6) but leaves dead config. Recommend repurpose + delete any `SYSTEM_PROMPT` from `.env`/`.env.prod`. |

**Installation:** None. `npm install` / `pip install` add nothing this phase.

**Version verification:** Confirmed via `backend/requirements.txt` and `frontend/package.json` (read 2026-07-12). No registry lookup needed — no new packages. `[VERIFIED: file read backend/requirements.txt, frontend/package.json]`

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────── BROWSER (React) ───────────────────────┐
                          │                                                                 │
  GET /api/personas ◀─────┤  ChatContainer header:  [Persona ▾]  (PersonaSelector)          │
   (id,label,is_default)  │  SettingsPage:          [Default persona ▾] (DefaultPersonaSel) │
                          │        │ select                     │ select                      │
                          │        ▼                            ▼                             │
   PATCH /api/threads/{id}│  {persona: "board_game_expert"}   PUT /api/preferences           │
        {persona} ◀───────┤  (ChatPage.handleThreadPersonaChange)  {default_persona} ◀───────┤
                          │        (optimistic local update, NO key gate)                    │
                          └─────────────────────────────────────────────────────────────────┘
                                       │                              │
                                       ▼ (writes)                     ▼ (writes)
        ┌──────────────────────────────────────────────────────────────────────────┐
        │  SUPABASE (Postgres, own-row RLS)                                          │
        │    threads.persona  (nullable TEXT)      user_preferences.default_persona  │
        └──────────────────────────────────────────────────────────────────────────┘
                                       │ read on next send()          │
   POST /api/threads/{id}/messages     ▼                              │
        │                    ┌──────────────────────── BACKEND (FastAPI) ───────────┐
        │  send_message()    │ thread = select('*')  → thread.data["persona"]        │
        ▼                    │                                                        │
   event_generator()  ──────▶│ _resolve_key_and_model(...)  (existing: api_key,model)│
   (per request, NOT cached) │ _resolve_persona(db,user,thread,body)  ◀── NEW        │
                             │    tier: thread.persona? → prefs.default_persona?      │
                             │          → system default (Board-Game Expert)          │
                             │    validate id vs persona_service.PERSONAS (D-10)      │
                             │    voice = get_persona_voice(resolved_id)              │
                             └───────────────┬────────────────────────────────────────┘
                                             │ persona_voice=voice
                                             ▼
        ┌──────────── llm_service.stream_chat_completion(...) ────────────┐
        │  system_content = settings.system_prompt   (operational BASE)   │
        │               + "\n\n" + persona_voice      (◀── NEW overlay)    │
        │               + "\n\n" + TOOL_SELECTION_GUIDE (unchanged, D-04)  │
        │               + source-routing hints (unchanged)                │
        │  tools = [ ...all tools... ]  ← INDEPENDENT of persona (PERS-02) │
        └─────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼  OpenAI SDK (raw) → OpenRouter
```

Sub-agents (`analyze_document` → `subagent_service`, `explore_kb` → `explorer_service`) keep their own dedicated system prompts and are **out of scope** — persona threads into `stream_chat_completion` ONLY.

### Component Responsibilities

| File | Change | Responsibility |
|------|--------|----------------|
| `backend/config.py` (~L95 `system_prompt`) | Edit | Repurpose to hold ONLY the operational base (strip "You are…" opener + KB-first bias) |
| `backend/services/persona_service.py` | **New** | `PERSONAS` registry (id/label/voice_block/is_default) + `list_personas()`, `resolve_persona_id(pinned)` (D-10 validate/fallback), `get_persona_voice(id)` |
| `backend/routers/personas.py` | **New** | `GET /api/personas` → `list[PersonaResponse]`, `Depends(get_user_id)` gated |
| `backend/main.py` (L9, L64-71) | Edit | Import + `app.include_router(personas.router)` |
| `backend/routers/chat.py` (~L145-296 resolver, ~L890-901 event_generator, ~L1077-1086 stream call) | Edit | Add `_safe_thread_persona`/`_safe_user_default_persona`/`_resolve_persona`; call it once per turn; pass `persona_voice` into `stream_chat_completion` |
| `backend/services/llm_service.py` (~L62-92) | Edit | Add `persona_voice: str \| None = None` param; compose `system_content = base + voice + tool_guide + hints` |
| `backend/routers/threads.py` (L58-89 PATCH) | Edit | Extend to accept `persona`; write via `exclude_unset` partial update |
| `backend/routers/preferences.py` (GET L37-60, PUT L63-96) | Edit | Add `default_persona` to select + response + upsert path (mirror `favorite_models`) |
| `backend/models/schemas.py` | Edit | `PersonaResponse`; add `persona` to `ThreadResponse` + rename/extend `ThreadModelUpdate`→`ThreadUpdate`; add `default_persona` to `PreferencesResponse`/`PreferencesUpdate` |
| `supabase/migrations/20240301000035_add_persona_columns.sql` | **New** | `ALTER TABLE threads ADD COLUMN persona TEXT;` + `ALTER TABLE user_preferences ADD COLUMN default_persona TEXT;` |
| `frontend/src/components/PersonaSelector.tsx` + `DefaultPersonaSelector.tsx` | **New** | Lightweight dropdowns over `GET /api/personas` |
| `frontend/src/pages/ChatPage.tsx` (L15-22 Thread, L100-120 handler, L206-217 render) | Edit | `persona` on `Thread`; `handleThreadPersonaChange` (PATCH, no gate); pass to `ChatContainer` |
| `frontend/src/components/ChatContainer.tsx` (L91-116 header row) | Edit | Render `PersonaSelector` beside the model selector |
| `frontend/src/pages/SettingsPage.tsx` (L167-171) | Edit | Add `DefaultPersonaSelector` |

### Recommended Project Structure (new/changed files)
```
backend/
├── services/persona_service.py     # NEW — registry + resolution helpers
├── routers/personas.py             # NEW — GET /api/personas
├── routers/chat.py                 # EDIT — _resolve_persona + thread voice into stream call
├── routers/threads.py              # EDIT — PATCH accepts persona (exclude_unset)
├── routers/preferences.py          # EDIT — default_persona in GET/PUT
├── services/llm_service.py         # EDIT — persona_voice param + compose
├── config.py                       # EDIT — system_prompt → operational base only
└── models/schemas.py               # EDIT — PersonaResponse + field additions
supabase/migrations/
└── 20240301000035_add_persona_columns.sql   # NEW
frontend/src/
├── components/PersonaSelector.tsx           # NEW
├── components/DefaultPersonaSelector.tsx     # NEW
├── components/ChatContainer.tsx              # EDIT — render PersonaSelector
├── pages/ChatPage.tsx                        # EDIT — persona state + PATCH handler
└── pages/SettingsPage.tsx                    # EDIT — render DefaultPersonaSelector
```

### Pattern 1: Split system prompt into operational base + persona voice overlay (D-01/D-02/D-03)

**What:** `settings.system_prompt` today bundles a generic opener + KB-first bias (Expert voice) + operational rules (citation/error/tables/analyze). Strip it to operational-rules-only; each persona voice_block supplies its own "You are…" opener + any voice-specific bias.

**When to use:** The one novel change in this phase. Everything else is a clone.

**Current code** (`backend/config.py:95-109`):
```python
system_prompt: str = (
    "You are a helpful assistant with access to tools. Answer questions clearly and concisely. "  # ← opener: DROP (each voice supplies its own)
    "Prefer the knowledge base for game rules and mechanics; use web_search only for current or "  # ← KB-first bias: MOVE to Expert voice (D-03)
    "external facts the knowledge base cannot answer (prices, availability, upcoming expansions, "
    "BGG rankings, designer/publisher news). "
    "When you use web search results, cite each source as an inline markdown link ..."             # ← citation: KEEP in base (D-02)
    "If a tool returns an error, briefly tell the user it couldn't be reached ..."                  # ← tool-error: KEEP in base (D-02)
    "When showing database query results, format them as markdown tables when appropriate. "        # ← tables: KEEP in base (D-02)
    "When a user asks about a specific document by name ... use the analyze_document tool ..."       # ← analyze_document: KEEP in base (D-02)
)
```

**Recommended shape:**
```python
# config.py — system_prompt becomes the PERSONA-AGNOSTIC operational base (D-02).
# NOTE: any SYSTEM_PROMPT value in .env/.env.prod SHADOWS this default (Pitfall 6) — remove it.
system_prompt: str = (
    "When you use web search results, cite each source as an inline markdown link at the point the "
    "fact is used (e.g. [BGG](https://boardgamegeek.com/...)), and end your answer with a short "
    "\"Sources:\" list of the links you relied on. "
    "If a tool returns an error, briefly tell the user it couldn't be reached, then answer "
    "best-effort from the knowledge base or your own knowledge. "
    "When showing database query results, format them as markdown tables when appropriate. "
    "When a user asks about a specific document by name ... use the analyze_document tool "
    "instead of search_documents."
)

# persona_service.py — voice blocks (Claude's discretion on exact wording).
PERSONAS = [
    {
        "id": "board_game_expert",
        "label": "Board-Game Expert",
        "is_default": True,
        "voice_block": (
            "You are a board-game expert with access to tools. Answer questions clearly and "
            "concisely. Prefer the knowledge base for game rules and mechanics; use web_search "
            "only for current or external facts the knowledge base cannot answer (prices, "
            "availability, upcoming expansions, BGG rankings, designer/publisher news)."
        ),
    },
    {
        "id": "general_assistant",
        "label": "General Assistant",
        "is_default": False,
        "voice_block": (
            "You are a helpful, general-purpose assistant with access to tools. Answer questions "
            "clearly and concisely across any topic. Use the tools available when they help, but "
            "do not assume the user's question is about board games."
        ),
    },
]
```

**Composition** (`backend/services/llm_service.py:90`, replacing the single line):
```python
system_content = settings.system_prompt          # operational BASE (D-02)
if persona_voice:                                 # NEW param, default None → base-only (back-compat)
    system_content = persona_voice + "\n\n" + system_content   # voice FIRST (role framing leads), base after
if tool_guide:
    system_content += "\n\n" + tool_guide         # UNCHANGED (D-04) — appended for ALL personas
# ... existing source_hint / scope_hint blocks unchanged ...
```
`// Source: backend/services/llm_service.py:62-92 (verified) + backend/config.py:95-109 (verified)`

### Pattern 2: Per-request persona resolution (D-09 / PERS-06) — clone the model tier chain

**What:** A module-level function (NOT a `Settings` method, NOT `@lru_cache`'d) called once per turn inside `event_generator`. No-bleed is guaranteed by the same mechanism as `_resolve_key_and_model`.

**When to use:** Every chat turn, right beside the existing key/model resolution.

**Recommended (a sibling helper, not a 5-tuple change to `_resolve_key_and_model`):**
```python
# chat.py — mirror _safe_thread_model (L144) / _safe_user_default_model (L153).
def _safe_thread_persona(thread_row: dict | None) -> str | None:
    return thread_row.get("persona") if thread_row else None

def _safe_user_default_persona(db, user_id: str) -> str | None:
    try:
        r = (db.table("user_preferences").select("default_persona")
             .eq("user_id", user_id).maybe_single().execute())
        return r.data.get("default_persona") if r and r.data else None
    except Exception as e:                      # 42P01 pre-migration tolerance (mirrors model helper)
        logger.debug(f"user_preferences not available: {scrub_secrets(str(e))}")
        return None

def _resolve_persona(db, user_id: str, thread_row: dict | None, body) -> str:
    """Resolve the per-request persona VOICE string. Not cached (Pitfall 8 no-bleed)."""
    pinned = (
        getattr(body, "persona", None)                 # optional future override (D-09) — or omit
        or _safe_thread_persona(thread_row)            # per-thread pin
        or _safe_user_default_persona(db, user_id)     # user default
    )
    resolved_id = resolve_persona_id(pinned)           # persona_service: validates vs registry, else default (D-10)
    return get_persona_voice(resolved_id)
```

Called in `event_generator` (`chat.py:898-901`), immediately after the existing resolve:
```python
api_key, model, mode, is_user_key = _resolve_key_and_model(db, user_id, thread.data, body)
persona_voice = _resolve_persona(db, user_id, thread.data, body)   # NEW — same per-request scope
```
And passed into the stream call (`chat.py:1077-1086`):
```python
for event in stream_chat_completion(
    current_messages, tools=tools,
    tool_guide=TOOL_SELECTION_GUIDE if tools else None,
    source_hint=source_scope, scope_hint=scope_hint if scope_hint else None,
    api_key=api_key, model=model, trace=(not is_user_key),
    persona_voice=persona_voice,                                  # NEW
):
```
`// Source: backend/routers/chat.py:144-296, 898-901, 1077-1086 (verified)`

> **Design note on D-09 "same resolver function":** Extending `_resolve_key_and_model`'s return tuple from 4 to 5 elements would break ~15 existing tests that unpack exactly `api_key, model, mode, is_user_key`. A **sibling `_resolve_persona` in the same module, called in the same per-request scope**, satisfies the *locked intent* (no-bleed via per-request, non-cached resolution — PERS-06) without disturbing the heavily-tested key/model contract. Persona also has none of key/model's concerns (mode, is_user_key, demo free-guard). This is the recommended interpretation; the alternative (widen the tuple + migrate all resolver tests) is available if the planner prefers literal co-location.

### Pattern 3: Additive nullable-column migration (D-08) — verbatim clone of migration 032/033

**What:** Two `ALTER TABLE ... ADD COLUMN ... TEXT` (nullable, no DEFAULT, no backfill). No new RLS — own-row policies from migration 032 cover the whole row.

**Recommended** (`supabase/migrations/20240301000035_add_persona_columns.sql`):
```sql
-- Phase 17 — persona pin columns (additive, mirrors migration 032/033).
-- Nullable, no backfill: existing threads/rows resolve to the system default
-- (Board-Game Expert) via the resolver tier chain (D-08). NOT a CHECK/FK — a removed
-- persona id must resolve to default (D-10), never raise (same rationale as default_model).
-- RLS: the own-row policies on threads (existing) and user_preferences (migration 032)
-- cover the whole row — add NO policies here.
ALTER TABLE threads ADD COLUMN persona TEXT;
ALTER TABLE user_preferences ADD COLUMN default_persona TEXT;
```
`// Source: supabase/migrations/20240301000032_...sql:57-62 (verified) + 033 (verified). Current head = 034 → next = 035.`

### Pattern 4: Extend PATCH/PUT with a partial (`exclude_unset`) write

**What:** The thread PATCH currently hardcodes `{"model": body.model}`. To accept `persona` without a persona-only PATCH clobbering `model` (and vice-versa), switch to `body.model_dump(exclude_unset=True)` — the exact mechanism `PUT /api/preferences` already uses for `favorite_models` (`preferences.py:75`). A `{model: null}` body still clears (explicitly set → included); a persona-only body only touches persona.

**Recommended** (`backend/routers/threads.py`, replacing L81-89):
```python
patch = body.model_dump(exclude_unset=True)     # {"persona": "..."} OR {"model": None} etc.
updated = (db.table("threads").update(patch)
           .eq("id", thread_id).eq("user_id", user_id).execute())   # ownership re-check kept
return updated.data[0]
```
Rename `ThreadModelUpdate` → `ThreadUpdate` with both `model: str | None = None` and `persona: str | None = None`. Existing `test_thread_model_patch.py` stays green (a `{model:"x/y"}` body → `exclude_unset` → `{"model":"x/y"}`; `{model:null}` → `{"model":None}`).
`// Source: backend/routers/threads.py:58-89 (verified) + backend/routers/preferences.py:63-96 (verified) + backend/models/schemas.py:56-81 (verified)`

### Pattern 5: `GET /api/personas` endpoint (D-07) — clone `models.py`

```python
# backend/routers/personas.py
from fastapi import APIRouter, Depends
from auth import get_user_id
from models.schemas import PersonaResponse
from services.persona_service import list_personas

router = APIRouter(prefix="/api/personas", tags=["personas"])

@router.get("", response_model=list[PersonaResponse])
def get_personas(user_id: str = Depends(get_user_id)) -> list[dict]:
    return list_personas()   # [{id, label, is_default}] — voice_block NOT sent to the client
```
`PersonaResponse` = `{id: str, label: str, is_default: bool}` (do NOT expose `voice_block` — the client only renders id+label+default marker). Register in `main.py` alongside the other routers.
`// Source: backend/routers/models.py:24-53 (verified) + backend/main.py:9,64-71 (verified)`

### Anti-Patterns to Avoid
- **Hardcoding the persona list in the frontend** — D-07 forbids it (FE/BE drift). The picker fetches `GET /api/personas`.
- **Routing the persona picker through `useKeyGate`** — persona has no key/cost. A keyless user must be able to pick a persona. The model picker's gate does NOT apply.
- **Gating tools by persona** — PERS-02/D-04: the `tools=[...]` list in `_traced_turn` (chat.py:963-980) is built from doc/web availability, NEVER from persona. The persona only changes the system message.
- **Threading persona into sub-agents** — `subagent_service`/`explorer_service` keep their own prompts; out of scope.
- **Adding a CHECK constraint / FK on the persona columns** — a removed persona id must fall back to default (D-10), not raise.
- **Composing base + voice with two "You are…" openers** — strip the opener from the base so exactly one role sentence (the voice) leads.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-request no-bleed resolution | A cached/global persona lookup | The existing non-cached resolver seam in `event_generator` | `@lru_cache` would bleed one user's persona into another (Pitfall 8, proven in `_resolve_key_and_model`) |
| 3-tier nullable pin | A new resolution scheme | Clone `_safe_thread_model`/`_safe_user_default_model` + tier chain | Proven, tested (`test_key_model_resolution.py`), tolerant of pre-migration schema |
| Additive migration | A custom migration shape | Verbatim clone migration 032/033 | Own-row RLS already covers the row; no backfill needed |
| Catalog endpoint | A bespoke route pattern | Clone `routers/models.py` (auth-gated GET + Pydantic response) | Consistent auth + response_model conventions |
| Settings default picker | New settings plumbing | Clone `DefaultModelSelector` self-PUT + `SettingsPage` seed | Fire-and-forget PUT + optimistic `onChange` already established |
| Partial PATCH/PUT | Manual field-merge logic | `body.model_dump(exclude_unset=True)` (already used by preferences PUT) | Avoids clobbering sibling fields; handles explicit-null clear correctly |
| Persona picker combobox | Reuse the 560-line `ModelSelector` | A dedicated ~40-line dropdown over 2 items | `ModelResponse` shape + key gate + favorites/search don't apply |

**Key insight:** This phase's risk is not "how" (every pattern exists) but "did we clone all of it" — the migration, the schema fields, the resolver helper, the endpoint registration in `main.py`, the response_model field additions (Pitfall 1), and the two frontend read paths. A checklist against the model-pin phase (13) is the highest-value planning artifact.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `threads.persona` + `user_preferences.default_persona` are **NEW** nullable columns. No existing rows carry persona data. Existing threads (null pin) resolve to Board-Game Expert via the tier chain (D-08). | Code edit only — **no data migration / no backfill**. |
| Live service config | None. Persona catalog is code (registry constant), not stored in any external service UI/DB. | None — verified: D-07 keeps the catalog in Python, no seed/migration. |
| OS-registered state | None — no schedulers, no OS registrations touched. | None. |
| Secrets/env vars | `SYSTEM_PROMPT` env var (if present in `.env`/`.env.prod`) **shadows** the repurposed base prompt (STATE.md Phase 16 note). No new secrets. | Remove `SYSTEM_PROMPT` from `.env`/`.env.prod` so the new operational base reaches the app (Pitfall 6). |
| Build artifacts | None — no package rename, no compiled artifacts. | None. |

**The canonical question — after every file is updated, what runtime state still holds an old value?** Only two: (1) a stale `SYSTEM_PROMPT` in `.env` shadowing the new base, and (2) the two new DB columns must exist in **both** the dev and prod Supabase projects (`.env` = dev, `.env.prod` = prod — MEMORY: dual Supabase envs). The prod migration is deferred to deploy per the project's dual-env discipline.

## Common Pitfalls

### Pitfall 1: `response_model` strips the new field on read
**What goes wrong:** Adding `persona` to the DB and returning it from the route, but the picker never sees it after reload.
**Why it happens:** FastAPI's `response_model` (`ThreadResponse`, `PreferencesResponse`) **strips any field not declared on the model**, even when `select('*')` returns it. This exact bug is documented at `schemas.py:97-102` (the `usage` field).
**How to avoid:** Add `persona: str | None = None` to `ThreadResponse` and `default_persona: str | None = None` to `PreferencesResponse` **before** wiring the read paths.
**Warning signs:** PATCH succeeds, DB has the value, but `GET /api/threads/{id}` / thread list omits `persona`.

### Pitfall 2: Prompt composition ordering / double opener
**What goes wrong:** Two "You are…" sentences, or operational rules appearing before the role.
**Why it happens:** The base still contains the old opener, and the voice adds another.
**How to avoid:** Strip the opener from the base (Pattern 1); compose **voice first, then base, then tool_guide**.
**Warning signs:** The model's tone is muddled, or the General Assistant still references board games (KB-first bias leaked into base instead of Expert voice — D-03).

### Pitfall 3: Persona accidentally gates tools (breaks PERS-02)
**What goes wrong:** General Assistant loses tool access.
**Why it happens:** Someone conditions the `tools=[...]` list on persona.
**How to avoid:** Leave `_traced_turn`'s tool assembly (chat.py:963-980) **exactly as-is** — it keys on document/web availability only. Persona changes only the system message. Add a test asserting `tools` is identical across personas (§Validation PERS-02).
**Warning signs:** A test that a General-Assistant turn still passes `web_search`/`search_documents` in `tools` fails.

### Pitfall 4: Module-level caching bleeds persona across users (breaks PERS-06)
**What goes wrong:** User B's turn uses User A's persona.
**Why it happens:** `@lru_cache` or a module-global on the persona lookup.
**How to avoid:** `_resolve_persona` is a plain function called once per turn inside `event_generator` (mirrors `_resolve_key_and_model`, chat.py:230 comment "NOT @lru_cache'd"). Registry `PERSONAS` is a constant read (fine to be module-level — it is the same for all users; only the *pinned id* is per-user and is read fresh from the request/DB each turn).
**Warning signs:** `test_no_cross_user_bleed`-style test fails under two back-to-back resolutions with different pins.

### Pitfall 5: Unknown/removed persona id crashes or injects (D-10)
**What goes wrong:** A pin no longer in the registry raises, or a raw string reaches the LLM.
**Why it happens:** `get_persona_voice` assumes the id exists; resolver skips validation.
**How to avoid:** `resolve_persona_id(pinned)` returns the pinned id **only if** it maps to a registry entry, else the default id — then `get_persona_voice` is always called with a valid id. Only registry `voice_block` strings ever reach the prompt (never user input — predefined-only, PERS-F1 deferred).
**Warning signs:** A crafted `PATCH {persona:"__nonsense__"}` followed by a send throws, or changes the system prompt to attacker text.

### Pitfall 6: `SYSTEM_PROMPT` env var shadows the new base
**What goes wrong:** The refactored operational base never reaches the running app; all personas share a stale prompt.
**Why it happens:** `pydantic-settings` env override — `SYSTEM_PROMPT` in `.env`/`.env.prod` wins over the code default (already flagged in Phase 16 SUMMARY / STATE.md).
**How to avoid:** Remove `SYSTEM_PROMPT` from `.env` and `.env.prod`. Verify with the running app, not just the unit default.
**Warning signs:** `Settings().system_prompt` (unit) shows the new base, but a live turn still uses the old bundled prompt.

### Pitfall 7: `db push` replays old migrations / "already exists"
**What goes wrong:** Applying migration 035 errors on earlier migrations.
**Why it happens:** Supabase migration-history drift (MEMORY: "db push replays old migrations / 'already exists'").
**How to avoid:** `supabase migration repair --status applied` for the prior range first, then `db push`. Apply to **both** dev (`.env`) and prod (`.env.prod`) projects; prod is deferred to deploy per dual-env discipline.
**Warning signs:** `db push` fails on a migration < 035 with "relation already exists".

### Pitfall 8: Extending `_resolve_key_and_model`'s tuple breaks the resolver suite
**What goes wrong:** ~15 tests in `test_key_model_resolution.py` unpack exactly 4 values and fail.
**Why it happens:** Adding persona to that function's return.
**How to avoid:** Use a sibling `_resolve_persona` (Pattern 2). If the planner insists on literal co-location, budget a task to migrate every unpack site + assertion.

## Code Examples

### Registry + resolution helpers (`persona_service.py`)
```python
# backend/services/persona_service.py
DEFAULT_PERSONA_ID = "board_game_expert"

def list_personas() -> list[dict]:
    """Public catalog for GET /api/personas — id/label/is_default only (no voice_block)."""
    return [{"id": p["id"], "label": p["label"], "is_default": p["is_default"]} for p in PERSONAS]

def resolve_persona_id(pinned: str | None) -> str:
    """D-10: a pin that maps to a registry entry wins; anything else → the system default."""
    ids = {p["id"] for p in PERSONAS}
    return pinned if (pinned in ids) else DEFAULT_PERSONA_ID

def get_persona_voice(persona_id: str) -> str:
    by_id = {p["id"]: p for p in PERSONAS}
    return by_id.get(persona_id, by_id[DEFAULT_PERSONA_ID])["voice_block"]
```
`// Pattern source: backend/services/model_catalog_service.py split + backend/config.py constants`

### Frontend per-thread PATCH handler (no key gate — mirror, minus the gate)
```tsx
// ChatPage.tsx — mirrors handleThreadModelChange (L103-120) but with NO useKeyGate wrap.
const handleThreadPersonaChange = useCallback(async (personaId: string) => {
  if (!activeThreadId) return
  setThreads(prev => prev.map(t => t.id === activeThreadId ? { ...t, persona: personaId } : t))  // optimistic
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
`// Source: frontend/src/pages/ChatPage.tsx:100-120 (verified) — pass handleThreadPersonaChange DIRECTLY to the picker (no guardedSelect)`

### Frontend settings default (mirror `DefaultModelSelector`, no gate)
```tsx
// DefaultPersonaSelector.tsx — self-PUT, optimistic onChange (mirrors DefaultModelSelector L30-60).
function onSelect(personaId: string) {
  onChange?.(personaId)
  void apiFetch('/api/preferences', {
    method: 'PUT', body: JSON.stringify({ default_persona: personaId }),
  }).catch(() => {})     // fire-and-forget, house style
}
```
`// Source: frontend/src/components/DefaultModelSelector.tsx:30-60 (verified)`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single bundled `system_prompt` (voice + rules) | Operational base + per-persona voice overlay | This phase | Adding a persona later is pure registry data (no code) — D-05 |
| Model pin only (`threads.model`) | Parallel `persona` pin dimension | This phase | Same tier chain, same picker pattern, minus key/cost concerns |

**Deprecated/outdated:** Nothing deprecated. This phase does not touch LangChain (never used — CLAUDE.md), and stays on the raw OpenAI SDK. No library version moves.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Repurposing `settings.system_prompt` as the operational base (vs. a new `persona_base_prompt` field) is the CONTEXT-intended split | Pattern 1 | Low — both work; new-field avoids the env-shadow but leaves dead config. Planner/discuss can pick. |
| A2 | A sibling `_resolve_persona` (not widening `_resolve_key_and_model`'s tuple) satisfies D-09's "same resolver function" intent | Pattern 2 | Low — both satisfy PERS-06 no-bleed; sibling avoids breaking ~15 tests. Flag for planner confirmation. |
| A3 | The chat header persona picker lists the 2 personas and pins on select; whether to also offer an explicit "follow my default" clear row is a UX choice | §Open Questions | Low — cosmetic; default resolution already handles null pins server-side. |
| A4 | `body.persona` per-message override is NOT added this phase (per-thread pin is primary; resolver reads `thread_row.persona` and the next send re-fetches the thread) | Pattern 2 / D-09 | Low — D-09 marks it optional ("planner may stub or skip"). |
| A5 | `PersonaResponse` sends `{id, label, is_default}` only (not `voice_block`) | Pattern 5 | Low — picker needs only id+label+default; keeps prompts server-side. |

**These A-tags map to real forks the planner or `/gsd-discuss-phase` should confirm — none block planning, all have a clear recommended default.**

## Open Questions (RESOLVED)

All three have a clear recommended default that the plans implement — none leave an implementation fork undecided.

1. **Chat-header persona picker: offer an explicit "use my default" row, or just the 2 personas?**
   - What we know: the model picker offers a `extraOption` "Use my default model" (clears the pin to null). Persona has only 2 options and a system default.
   - What's unclear: with 2 personas, a 3rd "follow default" row may confuse more than help.
   - RESOLVED: **Just list the 2 personas**; selecting one pins it. New-thread default resolution (server-side) already covers the "no pin" case. Revisit only if UX feedback wants an explicit "follow default." → implemented by plan 17-09.

2. **Registry location: `services/persona_service.py` vs. inline constant in `chat.py`?**
   - What we know: `chat.py` already holds tool schemas + `TOOL_SELECTION_GUIDE`; `models.py` delegates to `model_catalog_service.py`.
   - RESOLVED: **`services/persona_service.py`** — both the resolver (chat.py) and the endpoint (personas.py) import it; avoids coupling the endpoint to the chat router. → implemented by plan 17-04.

3. **Does the General Assistant voice need explicit "you may still search the board-game KB" language?**
   - What we know: tools stay available (D-04); the base governs *how* tools are cited.
   - What's unclear: whether the General voice should mention the KB at all.
   - RESOLVED: keep the General voice board-game-agnostic (D-06) but non-prohibitive ("use tools when helpful"); do NOT forbid KB tools. Exact wording is Claude's discretion. → implemented by plan 17-04/1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python venv + FastAPI | Backend routes/resolver | ✓ | FastAPI 0.115.12 | — |
| pytest / pytest-asyncio | Backend tests | ✓ | 8.4.2 / 0.23.8 | — |
| Node + vitest | Frontend picker tests | ✓ | vitest 4.1.9 | — |
| Supabase CLI (`db push` / `migration repair`) | Apply migration 035 | ✓ (project uses it) | — | Apply SQL via Supabase dashboard SQL editor |
| Supabase dev project (`.env`) | Column creation + RLS | ✓ | — | — |
| Supabase prod project (`.env.prod`) | Prod column creation | ✓ (deferred to deploy) | — | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Supabase CLI migration path can fall back to the dashboard SQL editor if `db push` history drift blocks (Pitfall 7).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | pytest 8.4.2 + pytest-asyncio 0.23.8 (`asyncio_mode = auto`) |
| Framework (frontend) | vitest 4.1.9 + @testing-library/react 16.3.2 + jsdom |
| Config file | `backend/pytest.ini` ; `frontend/vitest.config.ts` (setup `src/test/setup.ts`) |
| Quick run (backend) | `cd backend && python -m pytest tests/test_persona_resolution.py -x` |
| Quick run (frontend) | `cd frontend && npx vitest run src/components/PersonaSelector.test.tsx` |
| Full suite (backend) | `cd backend && python -m pytest` |
| Full suite (frontend) | `cd frontend && npm test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERS-01 | Chat picker lists personas; select PATCHes `{persona}` | unit (FE) | `npx vitest run src/components/PersonaSelector.test.tsx` | ❌ Wave 0 |
| PERS-01/05 | `PATCH /api/threads/{id} {persona}` writes scoped by id+user_id; persona-only doesn't clobber model | unit (BE) | `pytest tests/test_thread_persona_patch.py -x` | ❌ Wave 0 (mirror `test_thread_model_patch.py`) |
| PERS-02 | Composed prompt has NO board-game framing for General; tools identical across personas | unit (BE) | `pytest tests/test_persona_prompt.py -x` | ❌ Wave 0 |
| PERS-03 | Null pin + null default → `board_game_expert`; registry `is_default` = Expert | unit (BE) | `pytest tests/test_persona_resolution.py -x` | ❌ Wave 0 (mirror `test_key_model_resolution.py`) |
| PERS-04 | `default_persona` roundtrips via `PUT`/`GET /api/preferences`; theme-only PUT doesn't clobber it | unit (BE) | `pytest tests/test_preferences_api.py -k persona` | ⚠️ extend existing |
| PERS-04 | Settings picker PUTs `{default_persona}` | unit (FE) | `npx vitest run src/components/DefaultPersonaSelector.test.tsx` | ❌ Wave 0 |
| PERS-06 | Two back-to-back resolutions with different pins never cross | unit (BE) | `pytest tests/test_persona_resolution.py -k bleed` | ❌ Wave 0 (mirror `test_no_cross_user_bleed`) |
| PERS-10/D-10 | Unknown/removed persona id → default (no crash, no injection) | unit (BE) | `pytest tests/test_persona_resolution.py -k unknown` | ❌ Wave 0 |
| `GET /api/personas` | Auth-gated; returns `[{id,label,is_default}]`; exactly one default | unit (BE) | `pytest tests/test_personas_api.py -x` | ❌ Wave 0 (mirror `test_models_api.py`) |
| migration 035 | Columns nullable, additive | manual/CI | `supabase db push` (dev) | n/a |

### Sampling Rate
- **Per task commit:** the task's targeted quick-run command above.
- **Per wave merge:** `cd backend && python -m pytest` + `cd frontend && npm test`.
- **Phase gate:** both full suites green before `/gsd-verify-work`. Confirm `test_web_search.py::test_system_prompt_citation_guidance` stays GREEN (citation guidance MUST remain in the operational base — D-02).

### Wave 0 Gaps
- [ ] `backend/tests/test_persona_resolution.py` — PERS-03/06/D-10 (mirror `test_key_model_resolution.py`: MagicMock db chain, `_db_with_persona_row` helper, no-bleed, unknown-id fallback, tier order)
- [ ] `backend/tests/test_persona_prompt.py` — PERS-02 (composed system_content per persona; tools list identical across personas)
- [ ] `backend/tests/test_personas_api.py` — `GET /api/personas` (mirror `test_models_api.py`: `dependency_overrides[get_user_id]`, patch `routers.personas.get_supabase` if used)
- [ ] `backend/tests/test_thread_persona_patch.py` — PERS-01/05 (mirror `test_thread_model_patch.py`: sets, no-clobber-model, 404 non-owned)
- [ ] Extend `backend/tests/test_preferences_api.py` — `default_persona` roundtrip + no-clobber (mirror the `favorite_models` block)
- [ ] `frontend/src/components/PersonaSelector.test.tsx` + `DefaultPersonaSelector.test.tsx` — mirror `DefaultModelSelector.test.tsx` (mock `../lib/api` via `makeApiMock`, `renderWithProviders`); note: NO `useKeyStatus`/gate mock needed (persona has no gate)
- [ ] Config default check: extend `backend/tests/test_config.py` — assert `system_prompt` (base) still carries citation guidance and no longer carries the KB-first bias

*(Existing infra covers the harness — no framework install needed; all new files slot into `backend/tests/` and `frontend/src/**`.)*

## Security Domain

Config has no explicit `security_enforcement` key → treated as **enabled**. This phase is low-surface (no new secrets, no crypto, no auth change).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Unchanged — `Depends(get_user_id)` (JWT) on all new/edited routes |
| V3 Session Management | no | Unchanged |
| V4 Access Control | **yes** | Own-row RLS on `threads`/`user_preferences` covers the new columns (D-08, no new policies); `PATCH /api/threads/{id}` re-checks ownership (`.eq id .eq user_id`); `PUT /api/preferences` binds `user_id` from the JWT, never the body |
| V5 Input Validation | **yes** | The pinned persona id is validated against the code registry (`resolve_persona_id`, D-10); only registry `voice_block` strings reach the LLM system message. **Predefined-only** (PERS-F1 deferred) means there is NO user-authored-prompt injection surface |
| V6 Cryptography | no | Not touched |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Crafted `{persona:"..."}` in PATCH body or a stale DB pin not in the registry | Tampering | `resolve_persona_id` falls back to the default id (D-10); the raw string never reaches the prompt |
| Setting another user's thread persona (IDOR) | Elevation of Privilege | PATCH ownership re-check `.eq("id",tid).eq("user_id",uid)` → 404 on non-owned (mirrors `test_thread_model_patch.py::test_patch_404_non_owned`) |
| Reading another user's default persona | Info Disclosure | Own-row RLS on `user_preferences`; `user_id` bound from JWT in the preferences router |
| Persona voice_block leakage to client | Info Disclosure | `PersonaResponse` omits `voice_block` (non-secret, but no reason to ship prompt text) |
| Persona used to bypass tool restrictions | — | N/A this phase — all personas retain full tool access by construction (D-04); allowlists are PERS-F2 (deferred) |

## Project Constraints (from CLAUDE.md)

Directives that constrain this phase (planner must not contradict):
- **No LangChain / no LangGraph — raw SDK calls only.** Persona voice enters the raw OpenAI SDK system message; no framework.
- **Use Pydantic for structured outputs / request+response models.** `PersonaResponse` + field additions are Pydantic.
- **All tables need RLS — users only see their own data.** New columns inherit own-row RLS (D-08); no new policies, no exposure.
- **Python backend must use a `venv`.** Run tests inside `backend/venv`.
- **Module 2+ uses stateless completions.** Persona is resolved fresh per request; nothing persisted in the LLM beyond the composed system message. No cross-turn persona state.
- **Naming conventions:** `snake_case.py` services (`persona_service.py`), resource-named router (`personas.py`), `PascalCase.tsx` components (`PersonaSelector.tsx`), `test_{module}.py` tests.
- **Plans saved to `.agent/plans/`** with `{sequence}.{name}.md` naming + complexity indicator + per-task validation test (this is a GSD-planned phase; reconcile with the GSD plan location if both apply).
- **GSD workflow enforcement:** edits go through a GSD command; this research feeds `/gsd-plan-phase`.

## Sources

### Primary (HIGH confidence — read this session)
- `backend/config.py:95-109` — `system_prompt` (the D-01/D-02/D-03 split surface) + `subagent_system_prompt`/`explorer_system_prompt` (out of scope)
- `backend/services/llm_service.py:62-132` — `stream_chat_completion` system_content assembly (composition seam)
- `backend/routers/chat.py:144-296` (resolver helpers + `_resolve_key_and_model`), `805-901` (`send_message` + `event_generator`), `963-980` (persona-independent tools list), `1077-1086` (stream call), `634-661` (`TOOL_SELECTION_GUIDE`)
- `backend/routers/threads.py:58-89` — `PATCH` model pin (extend for persona)
- `backend/routers/preferences.py:37-96` — GET/PUT (extend for `default_persona`)
- `backend/routers/models.py:24-53` — `GET` catalog pattern for `GET /api/personas`
- `backend/main.py:9,64-71` — router registration
- `backend/models/schemas.py:25-102` — `ThreadResponse`/`PreferencesResponse`/`ThreadModelUpdate`/`PreferencesUpdate` (+ the `usage`-field `response_model` stripping note, Pitfall 1)
- `supabase/migrations/20240301000032_...sql` + `...033_add_favorite_models.sql` + `...034_create_app_settings.sql` — additive-migration pattern; current head = 034
- `backend/tests/test_key_model_resolution.py`, `test_thread_model_patch.py`, `test_preferences_api.py`, `test_config.py`, `test_models_api.py`, `backend/tests/conftest.py`, `backend/pytest.ini` — backend test patterns
- `frontend/src/components/ModelSelector.tsx`, `DefaultModelSelector.tsx`, `ChatContainer.tsx`; `frontend/src/pages/ChatPage.tsx`, `SettingsPage.tsx`; `frontend/src/hooks/useChat.ts`; `frontend/src/lib/api.ts`; `frontend/src/test/utils.tsx`, `setup.ts`; `frontend/vitest.config.ts`; `frontend/src/components/DefaultModelSelector.test.tsx` — frontend picker + test patterns
- `.planning/phases/17-agent-personas/17-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `CLAUDE.md`, MEMORY (dual Supabase envs; migration-history repair)
- `backend/requirements.txt`, `frontend/package.json` — version verification

### Secondary / Tertiary
- None required — this phase reuses in-repo patterns; no external docs or WebSearch were needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all versions read from lockfiles.
- Architecture: HIGH — every pattern is a clone of shipped, tested code (model pin, Phases 11–15).
- Pitfalls: HIGH — six of eight are documented in the codebase itself (response_model stripping, non-cached resolver, env-shadow, migration-history repair) or by requirement (tool gating, unknown-id fallback).
- The one MEDIUM area is exact voice-block wording (Claude's discretion) and the two design forks (A1/A2) — both have clear recommended defaults and are flagged for planner/discuss confirmation.

**Research date:** 2026-07-12
**Valid until:** 2026-08-11 (stable — internal patterns; only invalidated by a refactor of the model-pin resolver or the migration head advancing past 034 before this phase lands)
