# Phase 17: Agent Personas - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Let users switch the chat agent's **persona per-thread** and set a **user-level default persona**, choosing between the **Board-Game Expert (default)** and a **General Assistant** — both retaining full tool access. The selected persona's system prompt is resolved **per chat request** with no cross-user or cross-thread bleed (PERS-01..06).

This mirrors the shipped v1.2 per-thread model-pin infrastructure (migration `032`: `user_preferences` per-user default row + a nullable `threads` column, resolved through a 3-tier chain at the per-request seam). This is an additive feature built on a proven pattern — not a greenfield subsystem.

**Predefined personas only** — no user-editable free-text prompts (deferred PERS-F1). **All personas keep full tool access** — no per-persona tool allowlists (deferred PERS-F2). Provider/model switching is out of scope (already shipped v1.2).

</domain>

<decisions>
## Implementation Decisions

### Prompt composition (the core decision)
- **D-01:** Persona system prompts are built as **shared operational base + per-persona voice overlay** — NOT a full standalone prompt per persona. Extract the persona-agnostic operational rules into a shared base block that is **always applied for every persona**; each persona contributes only a short voice/role block. Rules live in one place; General Assistant retains correct tool behavior by construction.
- **D-02:** The **shared operational base** contains only persona-agnostic rules: web-source **citation format** (inline markdown link at point-of-use + trailing "Sources:" list), **tool-error handling** ("briefly tell the user it couldn't be reached, then answer best-effort"), **markdown tables for DB query results**, and the **`analyze_document`-by-name** guidance. These are HOW-to-use-tools rules, independent of persona voice.
- **D-03:** The current `settings.system_prompt` "**prefer the knowledge base for game rules/mechanics; use web_search only for external facts**" source-routing bias is **Board-Game Expert voice**, NOT operational base. It moves into the Expert's voice block. The General Assistant does not carry this KB-first bias.
- **D-04:** `TOOL_SELECTION_GUIDE` (chat.py) continues to be appended for **all** personas (unchanged mechanism at `llm_service.stream_chat_completion`). Tool access is preserved by construction for every persona — the persona voice never gates which tools are passed.

### Persona catalog
- **D-05:** Ship **exactly 2** personas in v1.3: **Board-Game Expert** (`is_default = true`) and **General Assistant**. Satisfies PERS-02/PERS-03 exactly; smallest surface. More personas can be added later as pure registry data (no new code) since they are just voice blocks.

### General Assistant behavior (PERS-02)
- **D-06:** General Assistant is a **truly general** assistant — plain helpful-assistant voice, **no board-game framing** and **no KB-first source bias**. All tools (KB search, `web_search`, SQL, `analyze_document`) remain callable, and the shared operational base (D-02) still governs HOW a tool is cited / how errors are handled when a tool IS used. It simply won't lead with board-game context or bias toward the KB. Matches "behaves like a vanilla model while retaining full tool access."

### Persona storage / source of truth
- **D-07:** Persona definitions (`id`, `label`, `voice_block`, `is_default`) live in a **backend Python registry constant**, exposed via a small **`GET /api/personas`** endpoint the chat/settings pickers fetch. No migration or seed for the catalog — persona prompt text versions with code (like `system_prompt` / `TOOL_SELECTION_GUIDE` today). The **pin columns are still DB** (see D-08). Frontend fetches the list from the endpoint (do NOT hardcode the FE list) to avoid FE/BE drift.

### Pin storage + resolution (mirror the v1.2 model pattern)
- **D-08:** Add the pin columns mirroring migration `032`: a nullable **`threads.persona`** column (per-thread pin) and a **`user_preferences.default_persona`** column (per-user default). Both nullable; null resolves through the tier chain. Additive migration, no backfill (existing threads/rows resolve to the system default). Reuse the existing own-row RLS on both tables — no new policies needed.
- **D-09:** Persona resolves in the **same per-turn resolver function** as key/model in `chat.py` (~line 233), guaranteeing no cross-user/thread bleed by the same mechanism (PERS-06). Tier chain, each tolerant of an absent column:
  `thread_row.persona? → user_preferences.default_persona? → system default (Board-Game Expert)`.
  (Optional `body.persona` per-message override may be threaded in the same shape as `body.model`, but per-thread pin is the primary UI path.)
- **D-10:** **Unknown / removed persona id** (a pin that no longer maps to a registry entry) **falls back to the system default (Board-Game Expert)** — mirrors the deprecated-model-pin fallback intent. The resolver validates the pinned id against the registry; the `/api/personas`-fed picker also prevents sending an invalid id. No persisted "notice" row is required (persona has no cost/deprecation surface like models do).
- **D-11:** Persona switching is **per-request / next-turn** (a mid-thread switch applies to subsequent turns, not retroactively) — inherited automatically from the per-request resolution seam (D-09), same as the model pin.

### UI attribution
- **D-12:** **Picker-only, no per-message persona badge.** The chat picker (mirrors `ModelSelector.tsx`) shows the thread's current persona; the settings page (mirrors `DefaultModelSelector.tsx`) sets the user default. Assistant bubbles get **no** per-message persona label and **no** `messages` schema change — consistent with how per-thread model works today (no per-message model badge exists).

### Claude's Discretion
- Exact voice-block wording for each persona (as long as Expert encodes D-03's KB-first bias and General Assistant reads as non-board-game-specialized per D-06).
- The precise refactor seam for splitting `settings.system_prompt` into base + Expert voice (planner/researcher decides; e.g., a `PERSONA_BASE_PROMPT` constant + a `voice_block` per registry entry, composed in `stream_chat_completion` where `system_content` is currently assembled at llm_service.py ~line 90).
- Whether a `body.persona` per-message override param is added now or left as a future seam (D-09).
- Picker component structure/placement details (reuse vs. adapt `ModelSelector`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — PERS-01..06 (in scope) + Future (PERS-F1 custom prompts, PERS-F2 per-persona tool allowlists) + Out of Scope table (predefined-only, all personas full tool access)
- `.planning/ROADMAP.md` §"Phase 17: Agent Personas" — goal, depends-on (reuse guidance), 5 success criteria

### The model-pin pattern to mirror (primary template)
- `supabase/migrations/20240301000032_create_user_preferences_and_thread_model.sql` — the EXACT pattern to mirror: `user_preferences` table (own-row RLS) + nullable `threads.model` column, additive, no backfill. Persona adds `user_preferences.default_persona` + `threads.persona` the same way (D-08).
- `backend/routers/chat.py` — per-turn resolver (~line 233): `body.model? → thread_row.model? → user_preferences.default_model? → settings.llm_model`; helpers `_safe_thread_model` (~line 145), `_safe_user_default_model` (~line 153). Persona resolves in the SAME function (D-09). Also `TOOL_SELECTION_GUIDE` (~line 634) and its append (~line 1080) — stays for all personas (D-04).
- `frontend/src/components/ModelSelector.tsx` — chat per-thread picker to mirror for the persona picker (PERS-01).
- `frontend/src/components/DefaultModelSelector.tsx` — settings-page default picker to mirror for the default-persona setting (PERS-04).
- `frontend/src/hooks/useChat.ts` + `frontend/src/lib/api.ts` — where the thread's model is read/sent; persona flows the same path.

### The system-prompt seam (the D-01/D-02/D-03 refactor surface)
- `backend/config.py` — `system_prompt` (~line 95): currently bundles persona voice + operational rules; split per D-01/D-02/D-03. (`subagent_system_prompt` ~line 142 and `explorer_system_prompt` ~line 151 are separate sub-agent prompts — NOT in scope; personas apply to the main chat loop only.)
- `backend/services/llm_service.py` — `stream_chat_completion` (~line 62); `system_content = settings.system_prompt` then `+ tool_guide` + source routing (~lines 90-108). This is where base + persona voice get composed; thread a persona/voice param here alongside `model`/`api_key`.

### Codebase maps
- `.planning/codebase/ARCHITECTURE.md` — agentic tool-use loop + per-request resolution architecture
- `.planning/codebase/INTEGRATIONS.md` — external/LLM integration map

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Migration `032`** — copy the shape verbatim for the persona pin: `user_preferences.default_persona TEXT` (nullable) + `threads.persona TEXT` (nullable), additive, own-row RLS already present.
- **Per-turn resolver in `chat.py`** (~line 233) + `_safe_thread_model` / `_safe_user_default_model` helpers — clone as `_safe_thread_persona` / `_safe_user_default_persona`; add the persona tier chain in the same no-bleed function.
- **`ModelSelector.tsx` / `DefaultModelSelector.tsx`** — the chat picker and settings default picker; the persona pickers mirror these (fetch list, pin per-thread, set default).
- **`TOOL_SELECTION_GUIDE` + tool_guide append** — unchanged; guarantees full tool access for every persona (D-04).

### Established Patterns
- **3-tier nullable resolution** (thread pin → user default → system default), each tier tolerant of an absent column — the project's proven pin pattern (D-09).
- **Definition-in-code + endpoint** — `system_prompt` / `TOOL_SELECTION_GUIDE` live in backend code; the persona registry follows suit, served via `GET /api/personas` (D-07).
- **Per-request resolution seam** — fresh resolution per turn (already used for key/model) gives PERS-06 no-bleed for free (D-09).

### Integration Points
- `backend/config.py` `system_prompt` — split into shared base + Expert voice (D-01/D-02/D-03).
- `backend/services/llm_service.py` `stream_chat_completion` — compose base + persona voice where `system_content` is built (~line 90); add a persona/voice param.
- `backend/routers/chat.py` — persona registry constant + `GET /api/personas` route + persona tier in the per-turn resolver; pass resolved voice into `stream_chat_completion`.
- New migration (next number after `034`) — `threads.persona` + `user_preferences.default_persona`.
- Frontend chat + settings pickers + `useChat.ts` / `api.ts` request payload.

</code_context>

<specifics>
## Specific Ideas

- **Board-Game Expert voice** must carry the KB-first source bias currently in `system_prompt` (D-03): "prefer the KB for game rules/mechanics; use web_search only for current/external facts (prices, availability, upcoming expansions, BGG rankings, designer/publisher news)."
- **General Assistant voice** is a plain, board-game-agnostic helpful assistant; tools remain available but it does not lead with board-game framing (D-06).
- Board-Game Expert is the **system default** — the fallback when no thread pin and no user default exist (D-09), preserving today's behavior for all existing threads (PERS-03).

</specifics>

<deferred>
## Deferred Ideas

- **User-editable custom persona prompts** (CRUD, storage, prompt-injection review) — PERS-F1, future milestone. v1.3 is predefined-only.
- **Per-persona tool allowlists** (restrict which tools a persona may call) — PERS-F2, future milestone. All v1.3 personas retain full tool access.
- **Curated set of 3-4 personas** (e.g. Rules Referee, Game Recommender) — considered, deferred; ship exactly 2 now (D-05). Additive as registry data later.
- **Per-message persona badge on assistant bubbles** — considered, deferred; picker-only for v1.3 (D-12). Would need a `messages` column.
- **`body.persona` per-message override** — optional seam; per-thread pin is the primary path (D-09). Planner may stub or skip.

Discussion stayed within the phase scope (per-thread persona pin + user default + per-request resolution).

</deferred>

---

*Phase: 17-agent-personas*
*Context gathered: 2026-07-12*
