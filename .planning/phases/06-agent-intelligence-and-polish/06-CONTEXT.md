# Phase 6: Agent Intelligence and Polish - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers four capabilities: (1) LLM-inferred source routing so the agent picks default KB vs private docs vs both, (2) token budget management with model-aware limits and oldest-first truncation, (3) natural language scope controls for narrowing searches, and (4) sub-agent pattern alignment between analyze_document and explore_kb. No new tools, no UI changes beyond scope indicator in tool cards, no new sub-agents.

</domain>

<decisions>
## Implementation Decisions

### Source Routing (AGNT-01)
- **D-01:** Agent uses LLM-inferred source routing — analyzes query intent to pick sources automatically. "What are Catan rules?" routes to default KB. "Summarize my uploaded doc" routes to private docs. No user action needed.
- **D-02:** When source intent is ambiguous, agent defaults to searching both default KB and private docs. No clarification questions — just search everything.
- **D-03:** Source scope is visible in tool cards via an indicator (e.g., "scope: default KB" or "scope: both"). Uses existing tool card args_preview pattern — no new UI component needed.

### Token Budget Management (AGNT-02, AGNT-03)
- **D-04:** Track token usage across system prompt, chat history, tool results, and reserve space for response. Truncate oldest tool results first when approaching budget limit.
- **D-05:** Budget limits derived via model-aware auto-detection. Query model context window from OpenRouter API or config, compute budget dynamically. Supports varying limits across different OpenRouter models.
- **D-06:** Truncation strategy: oldest tool results removed first. Recent tool results and chat history preserved. This maintains natural conversation flow.
- **D-07:** Token counting should use a lightweight method (character-based estimation or tiktoken) — exact accuracy less important than preventing context window exhaustion.

### Scope Controls (AGNT-04)
- **D-08:** Users narrow search scope via natural language in their message. "Only search Catan" or "look in my uploads only" — agent parses intent and scopes tool calls accordingly. No special syntax or commands.
- **D-09:** Scope persistence is Claude's discretion — implementation can choose per-message or sticky based on what works best.

### Sub-Agent Consistency (AGNT-05)
- **D-10:** Align analyze_document (Module 8) and explore_kb (Phase 5) patterns: shared SSE event format, consistent budget tracking, similar error handling. Both remain as separate tools.
- **D-11:** analyze_document stays focused on single-document analysis. No KB tool access — cross-referencing is explorer's job. Clear separation of concerns.
- **D-12:** Both sub-agents should use consistent SSE sub_event format (explore_kb already emits sub_event types; align analyze_document to match).

### Claude's Discretion
- Token counting method (tiktoken vs character estimation vs API-reported usage)
- Model context window detection strategy (OpenRouter API headers, model registry, or config fallback)
- How source routing hints are passed to tool calls (system prompt injection vs tool parameter)
- Scope persistence approach (per-message vs sticky)
- Exact budget allocation ratios (system prompt vs history vs tool results vs response reserve)
- How to align analyze_document SSE events with explorer pattern (refactor vs adapter)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Chat Loop and Tool Infrastructure
- `backend/routers/chat.py` -- Tool definitions (all 10), execute_tool() dispatcher, event_generator() with SSE, tool_start/tool_result events, explore_kb inline handling
- `backend/services/llm_service.py` -- stream_chat_completion(), system prompt construction, no current token management
- `backend/config.py` -- Settings class with all env vars, system_prompt, explorer budget settings, timeouts

### Sub-Agent Services
- `backend/services/explorer_service.py` -- run_exploration() sync generator, SUBAGENT_TOOL_RESULT_CLIP_CHARS=4000, SUBAGENT_SSE_OUTPUT_CLIP_CHARS=1000, MODE_HINTS, budget enforcement
- `backend/services/subagent_service.py` -- run_document_analysis(), different pattern from explorer (non-streaming, no tool loop)

### KB Tools
- `backend/services/kb_tools_service.py` -- kb_ls, kb_tree, kb_read, kb_grep, kb_glob implementations
- `backend/services/retrieval_service.py` -- search_documents (vector + keyword + rerank)

### Frontend Tool Display
- `frontend/src/components/ToolCallCard.tsx` -- Tool card rendering with sub-events (args_preview already displayed)
- `frontend/src/hooks/useChat.ts` -- SSE event parsing for tool_start/tool_result/sub_event

### Database Schema
- `supabase/migrations/018_create_folders_table.sql` -- Folders with ltree paths, visibility
- `supabase/migrations/019_add_visibility_and_folder.sql` -- visibility column on documents
- `supabase/migrations/020_update_rls_policies.sql` -- Mixed-visibility RLS

### Models
- `backend/models/schemas.py` -- ExplorerResult, other Pydantic models

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `explorer_service.py` budget pattern: max_iterations, max_tool_calls, max_summary_chars — extend similar approach for parent agent token budget
- `_build_args_preview()` in chat.py: already builds display string for tool cards — extend with scope indicator
- `TOOL_SELECTION_GUIDE` constant: system prompt already has tool guidance — extend with source routing hints
- `SUBAGENT_TOOL_RESULT_CLIP_CHARS` pattern: explorer already clips tool results — generalize for parent agent

### Established Patterns
- Settings via pydantic-settings with env vars and @lru_cache singleton
- Tool results as JSON strings from execute_tool()
- SSE events: tool_start → sub_event (for sub-agents) → tool_result
- Explorer uses is_subagent flag for unified tagging

### Integration Points
- `llm_service.py`: Add token counting and budget management before calling OpenAI API
- `chat.py event_generator()`: Add token tracking around the while-loop, truncate old tool results when budget tight
- `chat.py`: Add source routing logic — modify tool list or system prompt per-query based on inferred intent
- `config.py`: Add budget-related settings (response_reserve_tokens, etc.) and model context window config
- `subagent_service.py`: Align SSE event format with explorer pattern

</code_context>

<specifics>
## Specific Ideas

- Source routing should feel invisible — user shouldn't notice it working, just get better results
- Token budget should be a safety net, not something users interact with — it just prevents crashes
- Scope controls via natural language means the system prompt needs guidance on parsing scope hints
- Sub-agent alignment is mostly backend refactoring — minimal user-visible changes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-agent-intelligence-and-polish*
*Context gathered: 2026-04-21*
