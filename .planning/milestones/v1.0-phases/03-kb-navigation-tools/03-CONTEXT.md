# Phase 3: KB Navigation Tools - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers 5 KB navigation tools (ls, tree, read, grep, glob) that query Supabase, plus a new collapsible card UI for displaying ALL tool calls transparently in chat. The agent gets a tool selection guide in its system prompt. No file manager UI (Phase 4), no explorer sub-agent (Phase 5), no context budget management (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Tool Output Transparency (TOOL-07, TOOL-08)
- **D-01:** All tool calls (both existing 4 and new 5 KB tools) display as collapsible cards in the chat UI. Cards show tool name + icon, arguments, and collapsible output section.
- **D-02:** Cards are collapsed by default — user clicks to expand and see full tool output.
- **D-03:** SSE protocol uses separate `tool_start` and `tool_result` events. `tool_start` fires when tool begins (shows card with spinner), `tool_result` fires on completion (populates output). This replaces the current pill-badge-only display.

### Path Conventions
- **D-04:** All KB tools use human-readable paths as arguments (e.g., `"Board Games/Catan/rules.md"`). Backend resolves paths to internal folder IDs and document IDs. No UUIDs exposed to agent or user.
- **D-05:** Private user documents appear under a `"My Documents/"` prefix. Agent sees two top-level roots: `"Board Games/"` (default KB, public) and `"My Documents/"` (user uploads, private).
- **D-06:** Path resolution uses the `folders` table (ltree paths from Phase 1) and `documents` table (filename + folder_id).

### Coexistence with Existing Tools
- **D-07:** All 4 existing tools remain: `search_documents` (semantic/vector search), `query_database` (SQL), `web_search` (Tavily), `analyze_document` (sub-agent analysis). Total: 9 tools.
- **D-08:** KB tools complement existing tools — `kb_grep` does regex/keyword text search while `search_documents` does semantic similarity search. `kb_read` returns raw text while `analyze_document` returns LLM-analyzed insights.

### Tool Selection Guide
- **D-09:** System prompt includes a concise tool selection guide categorized by purpose:
  - **Orientation:** kb_tree first to understand KB structure
  - **Find files:** kb_glob for patterns, kb_ls for folder contents
  - **Find content:** kb_grep for exact text, search_documents for semantic meaning
  - **Read content:** kb_read for full text, analyze_document for LLM insights
  - **External:** web_search for info not in KB, query_database for metadata/stats

### KB Tool Designs

#### kb_ls
- **D-10:** Lists files and subfolders in a specified folder path. Returns filenames with sizes.

#### kb_tree
- **D-11:** Shows hierarchical tree structure with a `depth` parameter (default: 2). Depth=1 shows folders only, depth=2 shows folders + immediate files. Agent can increase depth for deeper exploration.

#### kb_read
- **D-12:** Returns full reassembled document content (all chunks joined in order). Supports optional `lines` parameter for line-range extraction (e.g., `lines="10-25"`).
- **D-13:** Auto-truncates at ~200 lines with a hint: `[Truncated at line 200 of 350. Use lines="201-350" to continue reading.]`. Prevents accidental context window blowup.

#### kb_grep
- **D-14:** Supports two modes via a `mode` parameter: `"regex"` for PostgreSQL regex matching (~* operator) and `"keyword"` for full-text search (ts_vector). Agent picks mode based on query type.
- **D-15:** Results show matched lines with 1-2 lines of surrounding context, plus file path and line number. Ripgrep-style output format.

#### kb_glob
- **D-16:** Finds files matching glob patterns across the KB (e.g., `"Board Games/*/rules.md"`). Returns matched file paths.

### Claude's Discretion
- Exact tool function names (kb_ls vs kb-ls vs list_folder, etc.)
- PostgreSQL implementation details for regex and glob matching
- How to efficiently reassemble chunks for kb_read (query ordering, joining strategy)
- Line number tracking across chunks (store line offsets or compute on the fly)
- SSE event field names and exact JSON structure for tool_start/tool_result
- Glob pattern matching implementation (SQL LIKE, regex conversion, or application-level)
- How many context lines to show around grep matches (1-2 suggested, exact count flexible)
- Default truncation threshold for kb_read (200 lines suggested, exact number flexible)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Tool Infrastructure
- `backend/routers/chat.py` -- Current tool definitions (RETRIEVAL_TOOL, SQL_TOOL, WEB_SEARCH_TOOL, ANALYZE_DOCUMENT_TOOL), execute_tool() dispatcher, SSE event_generator()
- `backend/services/retrieval_service.py` -- Existing search pipeline (vector + keyword + rerank)
- `backend/services/subagent_service.py` -- analyze_document implementation (reassembles chunks for full-doc analysis)
- `backend/services/sql_service.py` -- execute_readonly_query integration
- `backend/services/web_search_service.py` -- Tavily web search

### Frontend Tool Display
- `frontend/src/components/MessageBubble.tsx` -- Current ToolEvent interface, TOOL_LABELS map, pill-badge rendering (to be replaced with collapsible cards)
- `frontend/src/hooks/useChat.ts` -- SSE event parsing, tool_call event handling
- `frontend/src/components/ChatContainer.tsx` -- Chat message rendering

### Database Schema (from Phase 1)
- `supabase/migrations/018_create_folders_table.sql` -- Folders table with ltree paths, Board Games root folder
- `supabase/migrations/019_add_visibility_and_folder.sql` -- visibility/folder_id columns on documents/chunks
- `supabase/migrations/020_update_rls_policies.sql` -- Mixed-visibility RLS policies
- `supabase/migrations/021_update_search_rpcs.sql` -- Visibility-aware search RPCs
- `supabase/migrations/014_keyword_search_function.sql` -- keyword_search_chunks RPC (grep keyword mode can leverage)

### Backend Patterns
- `backend/config.py` -- Settings singleton pattern
- `backend/database.py` -- Supabase service role client
- `backend/services/llm_service.py` -- System prompt construction, tool-use loop

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `execute_tool()` dispatcher in `chat.py`: extensible switch statement — add new tool handlers following the same pattern
- `subagent_service.py`: already reassembles chunks into full document text — reusable logic for kb_read
- `keyword_search_chunks` RPC: existing full-text search — can power kb_grep keyword mode
- `ToolEvent` interface in `MessageBubble.tsx`: needs extension for output data but provides the base structure
- `useChat.ts` SSE parsing: already handles `tool_call` events — extend for `tool_start`/`tool_result`

### Established Patterns
- Tool definitions as OpenAI function-calling JSON schemas (dict constants in `chat.py`)
- Tool results returned as JSON strings from `execute_tool()`
- SSE events yielded from `event_generator()` async generator
- TOOL_LABELS map for display names in frontend
- Service role client bypasses RLS — all KB tools should use this for reads, then filter by visibility in queries

### Integration Points
- `chat.py`: Add 5 new tool constants, extend `execute_tool()`, update system prompt builder, add tool_start/tool_result SSE events
- `MessageBubble.tsx`: Replace pill badges with collapsible card component, extend TOOL_LABELS for KB tools
- `useChat.ts`: Parse new SSE event types (tool_start, tool_result), track tool call state
- New service file(s): KB tool logic (path resolution, folder queries, chunk reassembly, regex search)
- Possible new RPC functions: for regex search across chunks, glob pattern matching

</code_context>

<specifics>
## Specific Ideas

- Tool output in collapsible cards should use monospace font for file listings and grep results (terminal-like feel)
- kb_tree output should use tree-drawing characters (├── └── etc.) for visual hierarchy
- Grep results should show line numbers and matched text highlighted, similar to ripgrep format
- The tool selection guide in the system prompt should be concise (not a wall of text) — categorized by purpose as shown in D-09

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 03-kb-navigation-tools*
*Context gathered: 2026-04-08*
