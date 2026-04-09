# Phase 3: KB Navigation Tools - Research

**Researched:** 2026-04-09
**Domain:** Backend tool implementation (Python/FastAPI + Supabase), Frontend SSE + collapsible card UI (React)
**Confidence:** HIGH

## Summary

Phase 3 adds 5 KB navigation tools (kb_ls, kb_tree, kb_read, kb_grep, kb_glob) to the existing agentic chat loop, plus replaces the current pill-badge tool display with collapsible card UI. The backend work is primarily a new service module that queries Supabase's `folders` and `document_chunks` tables using ltree paths, regex, and full-text search. The frontend work involves a new ToolCallCard component, updated SSE event parsing (tool_start/tool_result), and updates to MessageBubble.

The existing codebase provides strong foundations: `execute_tool()` dispatcher is an extensible switch, `subagent_service.py` already reassembles chunks into full text (reusable for kb_read), `keyword_search_chunks` RPC provides full-text search infrastructure (reusable for kb_grep keyword mode), and the SSE event_generator pattern is straightforward to extend. The folders table uses ltree with GiST indexes for efficient tree traversal.

**Primary recommendation:** Create a single new `backend/services/kb_tools_service.py` containing all 5 tool functions plus a shared path-resolution utility. Add new Supabase RPC functions for regex search and glob matching. Extend the existing SSE protocol with `tool_start`/`tool_result` events for all tools (not just new ones).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** All tool calls (both existing 4 and new 5 KB tools) display as collapsible cards in the chat UI. Cards show tool name + icon, arguments, and collapsible output section.
- **D-02:** Cards are collapsed by default -- user clicks to expand and see full tool output.
- **D-03:** SSE protocol uses separate `tool_start` and `tool_result` events. `tool_start` fires when tool begins (shows card with spinner), `tool_result` fires on completion (populates output). This replaces the current pill-badge-only display.
- **D-04:** All KB tools use human-readable paths as arguments (e.g., `"Board Games/Catan/rules.md"`). Backend resolves paths to internal folder IDs and document IDs. No UUIDs exposed to agent or user.
- **D-05:** Private user documents appear under a `"My Documents/"` prefix. Agent sees two top-level roots: `"Board Games/"` (default KB, public) and `"My Documents/"` (user uploads, private).
- **D-06:** Path resolution uses the `folders` table (ltree paths from Phase 1) and `documents` table (filename + folder_id).
- **D-07:** All 4 existing tools remain: `search_documents` (semantic/vector search), `query_database` (SQL), `web_search` (Tavily), `analyze_document` (sub-agent analysis). Total: 9 tools.
- **D-08:** KB tools complement existing tools -- `kb_grep` does regex/keyword text search while `search_documents` does semantic similarity search. `kb_read` returns raw text while `analyze_document` returns LLM-analyzed insights.
- **D-09:** System prompt includes a concise tool selection guide categorized by purpose.
- **D-10:** kb_ls lists files and subfolders in a specified folder path. Returns filenames with sizes.
- **D-11:** kb_tree shows hierarchical tree structure with a `depth` parameter (default: 2).
- **D-12:** kb_read returns full reassembled document content. Supports optional `lines` parameter.
- **D-13:** Auto-truncates at ~200 lines with a hint for continuation.
- **D-14:** kb_grep supports two modes: `"regex"` for PostgreSQL regex matching (~* operator) and `"keyword"` for full-text search (ts_vector).
- **D-15:** Results show matched lines with 1-2 lines of surrounding context, plus file path and line number. Ripgrep-style output format.
- **D-16:** kb_glob finds files matching glob patterns across the KB.

### Claude's Discretion
- Exact tool function names (kb_ls vs kb-ls vs list_folder, etc.)
- PostgreSQL implementation details for regex and glob matching
- How to efficiently reassemble chunks for kb_read (query ordering, joining strategy)
- Line number tracking across chunks (store line offsets or compute on the fly)
- SSE event field names and exact JSON structure for tool_start/tool_result
- Glob pattern matching implementation (SQL LIKE, regex conversion, or application-level)
- How many context lines to show around grep matches (1-2 suggested, exact count flexible)
- Default truncation threshold for kb_read (200 lines suggested, exact number flexible)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | Agent can list files and subfolders in a specific folder (ls tool) | kb_ls queries `folders` table (ltree descendant `<@` operator for children) + `documents` table (folder_id join). Path resolution via shared utility. |
| TOOL-02 | Agent can view the full hierarchical tree structure of the KB (tree tool) | kb_tree uses ltree `<@` with nlevel() depth filtering. Recursive CTE or ltree descendant query with depth limit. |
| TOOL-03 | Agent can read a full document or specific line range from document chunks (read tool) | kb_read reuses `get_full_document_text()` from subagent_service.py, adds line splitting, range extraction, and truncation logic. |
| TOOL-04 | Agent can search document content using regex patterns (grep tool) | kb_grep regex mode: new RPC with `~*` operator. Keyword mode: leverages existing `keyword_search_chunks` RPC (updated in migration 021). |
| TOOL-05 | Agent can find files matching glob patterns across the KB (glob tool) | kb_glob converts glob patterns to SQL LIKE or regex, queries `documents` joined with `folders` for path construction. |
| TOOL-06 | All KB tools query Supabase tables and respect RLS visibility | Service role client bypasses RLS but all queries explicitly filter: `(user_id = X OR visibility = 'public')`. Matches existing pattern from migration 021. |
| TOOL-07 | Agent tool calls displayed transparently with tool-specific icons and labels | New ToolCallCard component per UI-SPEC. SSE `tool_start` event triggers card creation. TOOL_LABELS and icon map extended for 5 new tools. |
| TOOL-08 | Tool results show arguments and brief output summaries in collapsible sections | SSE `tool_result` event populates card output. Collapsed by default per D-02. Monospace font for terminal-like output per UI-SPEC. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.12 | Backend API framework | Already installed, tool routes extend existing router |
| supabase-py | 2.13.0 | Database client | Already installed, service role client for KB queries |
| openai | 1.74.0 | LLM tool-calling | Already installed, tool definitions as function-calling schemas |
| sse-starlette | 2.2.1 | SSE streaming | Already installed, extend event_generator for tool_start/tool_result |
| React | ^19.2.4 | Frontend UI | Already installed |
| lucide-react | ^0.577.0 | Tool icons | Already installed, provides FolderOpen, GitBranch, FileText, Search, Globe, Database, Brain |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PostgreSQL ltree | built-in | Hierarchical path queries | Already enabled (migration 016), used for tree traversal and path resolution |
| PostgreSQL tsvector | built-in | Full-text search for kb_grep keyword mode | Already configured (migration 013), GIN-indexed |

No new dependencies required. Everything needed is already in the project.

## Architecture Patterns

### Recommended Project Structure
```
backend/
  services/
    kb_tools_service.py     # NEW: All 5 KB tool functions + path resolution
  routers/
    chat.py                 # MODIFIED: 5 new tool constants, execute_tool dispatch, SSE events, system prompt
supabase/
  migrations/
    022_kb_grep_regex_rpc.sql  # NEW: RPC for regex search across chunks
    023_kb_glob_rpc.sql        # NEW: RPC for glob pattern matching (or handled in Python)
frontend/
  src/
    components/
      ToolCallCard.tsx      # NEW: Collapsible tool card component
      MessageBubble.tsx     # MODIFIED: Replace pill badges with ToolCallCard
    hooks/
      useChat.ts            # MODIFIED: Parse tool_start/tool_result SSE events
```

### Pattern 1: Path Resolution (Critical Shared Utility)
**What:** Convert human-readable paths like `"Board Games/Catan/rules.md"` to folder_id + document lookup.
**When to use:** Every KB tool call requires this.
**Implementation approach:**

The `folders` table stores ltree paths using underscored labels (e.g., `board_games` for "Board Games"). Path resolution must:
1. Parse the human-readable path into segments
2. Convert segments to ltree labels (lowercase, underscores)
3. Query `folders` table by ltree path
4. For document paths, split off the filename and resolve folder + document separately
5. Handle the `"My Documents/"` virtual prefix by mapping to user's private folders

```python
def resolve_path(user_id: str, path: str) -> dict:
    """Resolve human-readable path to folder_id and/or document_id.
    
    Returns:
      {"type": "folder", "folder_id": uuid, "folder_path": ltree_str}
      {"type": "document", "document_id": uuid, "folder_id": uuid}
      {"type": "error", "message": str}
    """
    db = get_supabase()
    
    # Split path into folder part and potential filename
    parts = path.strip("/").split("/")
    
    if parts[0] == "My Documents":
        # User's private docs -- query folders with user_id filter
        folder_parts = parts[1:]  # skip "My Documents" prefix
        visibility_filter = "private"
        owner_filter = user_id
    elif parts[0] == "Board Games":
        # Public KB
        ltree_path = ".".join(p.lower().replace(" ", "_") for p in parts)
        visibility_filter = "public"
        owner_filter = None  # system user
    
    # Query folders table by ltree path
    # Then check if last segment is a document filename
```

**Key insight:** The ltree paths in the `folders` table use underscored labels (`board_games.catan`), but the agent sees human-readable names (`Board Games/Catan`). The path resolver must map between these two representations. The `name` column on `folders` stores the human-readable name.

### Pattern 2: Tool Definition as OpenAI Function-Calling Schema
**What:** Each tool is a dict constant in `chat.py` following the existing pattern.
**When to use:** All 5 new tools.
**Example:**
```python
KB_LS_TOOL = {
    "type": "function",
    "function": {
        "name": "kb_ls",
        "description": "List files and subfolders in a KB folder.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": 'Folder path, e.g. "Board Games/Catan/"',
                },
            },
            "required": ["path"],
        },
    },
}
```

### Pattern 3: SSE Event Protocol Extension
**What:** Replace single `tool_event` with `tool_start` + `tool_result` pair.
**When to use:** All 9 tools (not just new KB tools).
**Example:**
```python
# In event_generator(), before executing each tool:
yield {
    "event": "tool_event",
    "data": json.dumps({
        "tool_event": True,
        "type": "tool_start",
        "tool": fn_name,
        "call_id": tc["id"],
        "args_preview": build_args_preview(fn_name, fn_args),
    }),
}

# After tool execution:
yield {
    "event": "tool_event",
    "data": json.dumps({
        "tool_event": True,
        "type": "tool_result",
        "tool": fn_name,
        "call_id": tc["id"],
        "output": truncate_output(tool_result, max_chars=2000),
    }),
}
```

### Pattern 4: Backend Service Role Client with Manual Visibility Filter
**What:** The backend uses the service role key (bypasses RLS), so visibility must be enforced in queries.
**When to use:** All KB tool queries.
**Pattern:**
```python
# Always include visibility filter in WHERE clause
result = db.table("folders").select("*").or_(
    f"user_id.eq.{user_id},visibility.eq.public"
).execute()
```

### Anti-Patterns to Avoid
- **Exposing UUIDs to the agent:** Per D-04, all tool arguments use human-readable paths. The agent never sees folder IDs or document IDs.
- **Querying with RLS-enabled client:** The backend uses service role (no RLS). Must manually filter by `user_id` OR `visibility='public'` in every query.
- **Loading entire KB in kb_tree:** Always respect the `depth` parameter. Use `nlevel()` in PostgreSQL to limit tree depth.
- **Unbounded kb_read output:** Must auto-truncate at ~200 lines per D-13. Never return full document without limit.
- **Building ltree paths from user input without sanitization:** ltree labels must be alphanumeric + underscores. Sanitize user path segments before constructing ltree queries.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Full-text search | Custom text scanning | Existing `keyword_search_chunks` RPC (migration 014/021) | Already GIN-indexed, visibility-aware, ranked |
| Regex search across chunks | Python-side regex on all chunks | PostgreSQL `~*` operator in an RPC | Server-side regex is orders of magnitude faster than fetching all chunks to Python |
| Tree traversal | Recursive Python queries | ltree `<@` operator with `nlevel()` | Single query vs N+1 recursive queries |
| Document reassembly | New chunk-joining code | Adapt `get_full_document_text()` from subagent_service.py | Already handles chunk ordering by chunk_index |
| tsvector indexing | Manual text indexing | Existing trigger `trg_document_chunks_tsv` (migration 013) | Auto-populates on INSERT/UPDATE |

**Key insight:** PostgreSQL's ltree, tsvector, and regex operators handle the heavy lifting server-side. The Python service layer should be thin -- build queries, format output.

## Common Pitfalls

### Pitfall 1: ltree Path Label Format Mismatch
**What goes wrong:** Human-readable folder names like "Board Games" don't match ltree labels like `board_games`. Queries return empty results.
**Why it happens:** ltree labels are restricted to alphanumeric + underscores. The `folders.name` column stores the display name, `folders.path` stores the ltree path.
**How to avoid:** Path resolution must query `folders` by `name` (case-insensitive) level-by-level, or maintain a name-to-ltree mapping. Do NOT try to derive ltree paths from display names with simple string replacement -- folder names may contain special characters.
**Warning signs:** KB tools return "folder not found" for folders that clearly exist.

**Recommended approach:** Query folders by walking the path segments top-down using `name` matching and `parent_id` chain, rather than constructing ltree strings from display names.

### Pitfall 2: Chunk Boundary Issues in Line Numbering
**What goes wrong:** kb_read and kb_grep need line numbers, but chunks split mid-document. Line 50 might be in chunk 2 or chunk 3 depending on chunk sizes.
**Why it happens:** Chunks are created by text splitter with overlap. Lines don't align to chunk boundaries.
**How to avoid:** For line-range operations, reassemble full text first (join all chunks by chunk_index), then split into lines. Compute line numbers on the assembled text, not per-chunk.
**Warning signs:** Line ranges return wrong content; grep line numbers don't match kb_read line numbers.

### Pitfall 3: SSE Event Ordering and State Management
**What goes wrong:** Frontend shows tool cards in wrong state (spinner never stops, output appears before card).
**Why it happens:** Multiple tool calls can happen in a single agent turn. `tool_start` and `tool_result` events for different tools can interleave.
**How to avoid:** Use `call_id` (from OpenAI's tool call ID, e.g., `tc["id"]`) to correlate `tool_start` and `tool_result` events. Frontend must match by `call_id`, not by tool name (agent might call the same tool twice).
**Warning signs:** Cards show wrong output, spinner stays on completed tools.

### Pitfall 4: kb_grep Regex Mode -- PostgreSQL Regex Syntax Differences
**What goes wrong:** Agent sends JavaScript/Python-style regex that PostgreSQL doesn't understand.
**Why it happens:** PostgreSQL POSIX regex has different syntax from PCRE. No `\d`, `\w` shortcuts in basic mode (use `[[:digit:]]`, `[[:alnum:]]` instead). The `~*` operator is case-insensitive POSIX regex.
**How to avoid:** Use `~*` (case-insensitive) by default. Document in the tool description that patterns use POSIX regex. Handle regex compilation errors gracefully (catch and return user-friendly error).
**Warning signs:** "invalid regular expression" errors from PostgreSQL.

### Pitfall 5: Tool Availability Logic
**What goes wrong:** KB tools are always offered even when no KB content exists, or not offered when only default KB exists.
**Why it happens:** Current tool availability checks `doc_check` for user's documents only. KB tools should always be available (default KB always exists).
**How to avoid:** KB navigation tools should always be included in the tools list (the default KB is always there). Keep existing `doc_check` logic only for `search_documents` and `analyze_document`.
**Warning signs:** Agent can't use KB tools when user has no private uploads.

### Pitfall 6: My Documents Virtual Path for Users with No Folders
**What goes wrong:** User has uploaded documents without folders (legacy pre-Phase-1 uploads). These documents have `folder_id = NULL`.
**Why it happens:** Migration 019 added `folder_id` as nullable to preserve existing data.
**How to avoid:** kb_ls for "My Documents/" should include both folder-organized private docs AND unorganized private docs (folder_id IS NULL). Show unorganized docs at the root of "My Documents/".
**Warning signs:** User's uploaded documents disappear from KB tool results.

## Code Examples

### kb_ls Implementation Pattern
```python
def kb_ls(user_id: str, path: str) -> str:
    """List files and subfolders in a KB folder."""
    db = get_supabase()
    
    # Resolve path to folder
    folder = resolve_folder_by_path(user_id, path)
    if not folder:
        return json.dumps({"error": f"Folder not found: {path}"})
    
    # Get immediate child folders
    children = (
        db.table("folders")
        .select("name")
        .eq("parent_id", folder["id"])
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .execute()
    )
    
    # Get documents in this folder
    docs = (
        db.table("documents")
        .select("filename, file_size")
        .eq("folder_id", folder["id"])
        .eq("status", "completed")
        .or_(f"user_id.eq.{user_id},visibility.eq.public")
        .execute()
    )
    
    # Format output
    lines = []
    for child in children.data:
        lines.append(f"{child['name']}/")
    for doc in docs.data:
        size_kb = doc["file_size"] // 1024
        lines.append(f"{doc['filename']}  ({size_kb} KB)")
    
    return "\n".join(lines) if lines else "(empty folder)"
```

### kb_tree Using ltree
```python
def kb_tree(user_id: str, path: str = "", depth: int = 2) -> str:
    """Show hierarchical tree structure with depth limit."""
    db = get_supabase()
    
    # Get root folder (or specified folder)
    if not path or path == "/":
        # Show both roots: Board Games/ and My Documents/
        roots = ["Board Games", "My Documents"]
        # ... build tree from both roots
    else:
        folder = resolve_folder_by_path(user_id, path)
        # Query descendants using ltree
        # nlevel(path) - nlevel(root_path) <= depth
    
    # Use ltree descendant query:
    # SELECT * FROM folders
    # WHERE path <@ 'board_games'  -- descendants of root
    #   AND nlevel(path) - nlevel('board_games') <= depth
    #   AND (user_id = X OR visibility = 'public')
    # ORDER BY path
```

### kb_grep Regex Mode -- New RPC Function
```sql
CREATE OR REPLACE FUNCTION kb_grep_regex(
  pattern TEXT,
  filter_user_id UUID,
  match_limit INT DEFAULT 20
)
RETURNS TABLE (
  document_id UUID,
  chunk_id UUID,
  content TEXT,
  chunk_index INT,
  filename TEXT,
  folder_path TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    dc.document_id,
    dc.id AS chunk_id,
    dc.content,
    dc.chunk_index,
    d.filename,
    f.name AS folder_path
  FROM document_chunks dc
  JOIN documents d ON dc.document_id = d.id
  LEFT JOIN folders f ON d.folder_id = f.id
  WHERE dc.content ~* pattern
    AND (dc.user_id = filter_user_id OR dc.visibility = 'public')
  ORDER BY d.filename, dc.chunk_index
  LIMIT match_limit;
END;
$$;
```

### ToolCallCard Component Structure
```typescript
// frontend/src/components/ToolCallCard.tsx
import { useState } from 'react'
import { ChevronDown, ChevronUp, Check } from 'lucide-react'

interface Props {
  tool: string
  args_preview: string
  output?: string
  status: 'running' | 'complete'
  call_id?: string
}

export default function ToolCallCard({ tool, args_preview, output, status }: Props) {
  const [expanded, setExpanded] = useState(false)
  const Icon = TOOL_ICONS[tool] // map from tool name to lucide icon
  const iconColor = tool.startsWith('kb_') ? 'text-emerald-400' : 'text-gray-400'
  
  return (
    <div className="border border-gray-700 rounded-md overflow-hidden">
      <div 
        className="flex items-center justify-between px-2 py-2 cursor-pointer bg-gray-800/50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-1">
          <Icon className={`w-4 h-4 ${iconColor}`} />
          <span className="text-xs font-semibold">{TOOL_LABELS[tool]}</span>
          <span className="text-xs font-mono text-gray-400 truncate max-w-[200px]">
            {args_preview}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {status === 'running' ? (
            <span className="w-3.5 h-3.5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5 text-gray-500" />
          )}
          {expanded ? <ChevronUp className="w-3.5 h-3.5 text-gray-500" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-500" />}
        </div>
      </div>
      {expanded && output && (
        <div className="border-t border-gray-700 px-4 py-2 bg-gray-800">
          <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
            {output}
          </pre>
        </div>
      )}
    </div>
  )
}
```

### SSE Event Parsing in useChat.ts
```typescript
// In the SSE parsing loop, update tool_event handling:
if (parsed.tool_event === true) {
  if (parsed.type === 'tool_start') {
    // Add new card in running state
    setMessages(prev => prev.map(m => {
      if (m.id !== assistantId) return m
      return {
        ...m,
        toolsUsed: [...(m.toolsUsed || []), {
          tool: parsed.tool,
          args_preview: parsed.args_preview,
          call_id: parsed.call_id,
          status: 'running' as const,
        }],
      }
    }))
  } else if (parsed.type === 'tool_result') {
    // Update existing card with output and complete status
    setMessages(prev => prev.map(m => {
      if (m.id !== assistantId) return m
      return {
        ...m,
        toolsUsed: (m.toolsUsed || []).map(t =>
          t.call_id === parsed.call_id
            ? { ...t, status: 'complete' as const, output: parsed.output }
            : t
        ),
      }
    }))
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pill badges for tool calls | Collapsible cards with output | Phase 3 | All 9 tools get transparent display |
| Single `tool_event` SSE | `tool_start` + `tool_result` pair | Phase 3 | Enables spinner-to-complete animation |
| Search only (vector/keyword) | Search + navigation (ls/tree/read/grep/glob) | Phase 3 | Agent can explore KB structure, not just search |

## Open Questions

1. **Path Resolution Strategy for Deep Nesting**
   - What we know: Folders use ltree paths. The `Board Games` root has ltree path `board_games`. Game subfolders have paths like `board_games.catan`.
   - What's unclear: Are there deeper nesting levels beyond game folders? How many path segments to expect?
   - Recommendation: Build path resolution to handle arbitrary depth (walk segments with parent_id chain). Don't hardcode to 2 levels.

2. **Glob Pattern Implementation**
   - What we know: Need to match patterns like `"Board Games/*/rules.md"` across the KB.
   - What's unclear: Whether to implement glob-to-SQL conversion server-side (RPC) or application-side (Python).
   - Recommendation: Convert glob to SQL LIKE patterns in Python (`*` becomes `%`, `?` becomes `_`), then query `documents` joined with `folders`. Simpler than an RPC and adequate for the expected query volume.

3. **Output Truncation for tool_result SSE**
   - What we know: kb_read truncates at ~200 lines. But tool_result output in SSE should also be bounded.
   - What's unclear: Max output size to send via SSE for display in cards.
   - Recommendation: Truncate tool output for SSE display at ~2000 characters. The full output is always sent to the LLM in the tool result message (which has its own token limits). The SSE output is just for user transparency.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend/tests/ exists) |
| Config file | none -- needs creation in Wave 0 |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | kb_ls returns files and subfolders | unit | `pytest tests/test_kb_tools.py::test_kb_ls -x` | Wave 0 |
| TOOL-02 | kb_tree returns hierarchical structure with depth limit | unit | `pytest tests/test_kb_tools.py::test_kb_tree -x` | Wave 0 |
| TOOL-03 | kb_read returns full doc and line ranges | unit | `pytest tests/test_kb_tools.py::test_kb_read -x` | Wave 0 |
| TOOL-04 | kb_grep finds content via regex and keyword modes | unit | `pytest tests/test_kb_tools.py::test_kb_grep -x` | Wave 0 |
| TOOL-05 | kb_glob matches file patterns | unit | `pytest tests/test_kb_tools.py::test_kb_glob -x` | Wave 0 |
| TOOL-06 | All tools respect visibility (public + user private only) | unit | `pytest tests/test_kb_tools.py::test_visibility -x` | Wave 0 |
| TOOL-07 | SSE emits tool_start events with correct shape | integration | `pytest tests/test_chat_sse.py::test_tool_start -x` | Wave 0 |
| TOOL-08 | SSE emits tool_result events with output | integration | `pytest tests/test_chat_sse.py::test_tool_result -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_kb_tools.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_kb_tools.py` -- unit tests for all 5 KB tools
- [ ] `backend/tests/test_chat_sse.py` -- integration tests for SSE tool events
- [ ] `backend/tests/conftest.py` -- shared fixtures (mock Supabase client, sample folder/document data)
- [ ] Framework install: `pip install pytest` (verify if already in requirements.txt)

## Project Constraints (from CLAUDE.md)

- **Python venv required:** Backend must use `backend/venv/`
- **No LangChain/LangGraph:** Raw SDK calls only -- all tool logic is plain Python + Supabase queries
- **Pydantic for structured outputs:** Use Pydantic models where appropriate for tool result schemas
- **RLS enforced:** Users only see their own data + public KB. Service role client bypasses RLS, so manual visibility filters required in all queries
- **SSE for chat streaming:** Tool events must use SSE (sse-starlette), not WebSocket
- **Supabase Realtime for ingestion status:** Not relevant to Phase 3 (no ingestion changes)
- **No LangChain:** Tool definitions must be raw OpenAI function-calling JSON dicts, not LangChain tool decorators
- **snake_case for Python functions:** `kb_ls`, `kb_tree`, `kb_read`, `kb_grep`, `kb_glob`
- **PascalCase for React components:** `ToolCallCard.tsx`
- **camelCase for hooks:** Updated `useChat.ts`
- **Service file naming:** `kb_tools_service.py` (follows `{domain}_service.py` pattern)

## Sources

### Primary (HIGH confidence)
- `backend/routers/chat.py` -- Existing tool definitions, execute_tool dispatcher, SSE event_generator (lines 1-342)
- `backend/services/subagent_service.py` -- Document reassembly pattern via get_full_document_text() (lines 36-47)
- `backend/services/llm_service.py` -- System prompt injection, stream_chat_completion tool-use loop
- `supabase/migrations/018_create_folders_table.sql` -- Folders table schema with ltree paths, GiST index
- `supabase/migrations/019_add_visibility_and_folder.sql` -- folder_id + visibility on documents/chunks
- `supabase/migrations/013_add_fulltext_search.sql` -- tsvector column + GIN index + auto-populate trigger
- `supabase/migrations/021_update_search_rpcs.sql` -- Visibility-aware keyword_search_chunks RPC
- `frontend/src/components/MessageBubble.tsx` -- Current pill-badge tool display (to be replaced)
- `frontend/src/hooks/useChat.ts` -- Current SSE parsing with tool_event handling
- `.planning/phases/03-kb-navigation-tools/03-CONTEXT.md` -- All locked decisions D-01 through D-16
- `.planning/phases/03-kb-navigation-tools/03-UI-SPEC.md` -- ToolCallCard visual specification

### Secondary (MEDIUM confidence)
- PostgreSQL ltree documentation -- `<@` descendant operator, `nlevel()` function, label format restrictions
- PostgreSQL regex documentation -- `~*` case-insensitive POSIX regex operator

### Tertiary (LOW confidence)
- None -- all findings verified against project source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, everything already installed
- Architecture: HIGH -- extends well-documented existing patterns (tool dispatch, SSE, service role queries)
- Pitfalls: HIGH -- derived from direct code inspection of schema constraints (ltree labels, chunk boundaries, RLS bypass)

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- no external dependency changes expected)
