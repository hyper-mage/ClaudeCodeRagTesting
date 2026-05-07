# Architecture Research

**Domain:** Board Game Knowledge Base with Claude Code-style Agent Tooling
**Researched:** 2026-04-07
**Confidence:** HIGH

## System Overview

```
+================================================================+
|                        FRONTEND (React)                         |
|  +------------+  +-------------+  +------------+  +----------+ |
|  | ChatUI     |  | ToolEvents  |  | FileManager|  | Explorer | |
|  | (existing) |  | (existing)  |  | (new)      |  | Panel    | |
|  +-----+------+  +------+------+  +-----+------+  +----+-----+ |
|        |                |               |              |        |
+========|================|===============|==============|========+
         |   SSE stream   |   REST        |   REST       |
+========|================|===============|==============|========+
|                      BACKEND (FastAPI)                          |
|                                                                 |
|  +-----------------------------------------------------------+ |
|  |              TOOL ROUTER (chat.py - extended)              | |
|  |  Dispatches: search_documents, query_database, web_search, | |
|  |  analyze_document, kb_ls, kb_tree, kb_grep, kb_glob,      | |
|  |  kb_read, explore_kb                                       | |
|  +-----+----+----+----+----+----+----+----+----+----+--------+ |
|        |    |    |    |    |    |    |    |    |    |           |
|  +-----+--+ | +-+--+ | +-+--+ | +-+--+ | +-+----+ +-+------+ |
|  |retrieve | | |sql | | |web | | |sub | | |kb_svc| |explorer| |
|  |_service | | |_svc| | |_svc| | |agt | | |(new) | |_agent  | |
|  |(exist.) | | |(ex)| | |(ex)| | |(ex)| | |      | |(new)   | |
|  +----+----+ | +---+  | +---+  | +---+  | +--+---+ +---+----+ |
|       |      |   |     |  |     |  |     |    |         |      |
|  +----+------+---+-----+--+-----+--+-----+----+---------+----+ |
|  |              SOURCE ROUTER (new)                           | |
|  |  Decides: default_kb | private_docs | both | web           | |
|  +----+---------------------------------------------------+---+ |
|       |                                                   |     |
+===================================================================+
         |                                                   |
+========|===================================================|====+
|                       SUPABASE                                   |
|  +-------------+  +----------------+  +-------------------+      |
|  | documents   |  | document_chunks|  | folders (new)     |      |
|  | + folder_id |  | + source_type  |  | id, parent_id,    |      |
|  | + source    |  | + folder_path  |  | name, path,       |      |
|  |   _type     |  |                |  | user_id, source   |      |
|  +-------------+  +----------------+  +-------------------+      |
|                                                                  |
|  +-------------------+  +-------------------+                    |
|  | Storage Bucket    |  | default_kb_config |                    |
|  | documents/        |  | (seed metadata)   |                    |
|  | + user/{id}/...   |  |                   |                    |
|  | + default_kb/...  |  |                   |                    |
|  +-------------------+  +-------------------+                    |
+==================================================================+
```

## Component Responsibilities

| Component | Responsibility | Existing/New |
|-----------|----------------|--------------|
| **Tool Router** (chat.py) | Dispatches tool calls from LLM to service functions. Currently handles 4 tools, will grow to ~10. | Extend |
| **KB Navigation Service** | Implements ls, tree, grep, glob, read against Supabase tables. Stateless functions querying `documents`, `document_chunks`, and `folders`. | **New** |
| **Explorer Sub-Agent** | Multi-step KB traversal in isolated context. Receives a goal, uses KB tools iteratively, returns synthesized answer. Same pattern as existing `subagent_service`. | **New** |
| **Source Router** | Classifies queries to determine source scope: default KB, private docs, both, or web. Runs before tool execution. | **New** |
| **Folder Service** | CRUD for folder hierarchy. Creates, moves, lists folders. Used by both API endpoints and KB tools. | **New** |
| **Seed Script** | One-time script to populate default KB with 10 board games. Runs on deploy. | **New** |
| **FileManager UI** | Tree sidebar + file grid for organizing documents into folders. | **New** |
| **Retrieval Service** | Hybrid search with RRF + reranking. Needs scope parameter (default_kb / private / both). | Extend |
| **Ingestion Service** | Document processing pipeline. Needs folder assignment + source_type tagging. | Extend |

## Recommended Project Structure

New and modified files only:

```
backend/
  services/
    kb_service.py            # ls, tree, grep, glob, read implementations
    explorer_service.py      # Explorer sub-agent (multi-step KB traversal)
    source_router.py         # Query classification -> source scope
    folder_service.py        # Folder CRUD operations
  routers/
    folders.py               # REST endpoints for folder management
    chat.py                  # Extended with new tool definitions
  scripts/
    seed_default_kb.py       # Populate default board game KB

frontend/src/
  components/
    FileManager/
      FolderTree.tsx         # Sidebar tree navigation
      FileGrid.tsx           # File listing in selected folder
      FolderActions.tsx       # Create, rename, move, delete
    ExplorerPanel.tsx         # Shows explorer agent progress
    ToolCallDisplay.tsx       # Enhanced tool event rendering

supabase/migrations/
  016_create_folders.sql      # folders table + RLS
  017_add_folder_to_documents.sql   # folder_id FK on documents
  018_add_source_type.sql     # source_type enum on documents + chunks
  019_default_kb_rls.sql      # RLS policies for shared default KB
  020_kb_navigation_rpcs.sql  # Postgres functions for efficient KB queries
```

### Structure Rationale

- **kb_service.py**: Single module for all 5 KB navigation tools. They share the same data access patterns (querying folders/documents/chunks by path) so co-location reduces import sprawl.
- **explorer_service.py**: Separate from kb_service because the explorer is an agent loop (LLM calls + tool execution), not a data query. Same isolation pattern as existing `subagent_service.py`.
- **source_router.py**: Lightweight classifier that runs once per user message. Kept separate because it may use LLM classification or heuristics -- implementation can change without touching tool dispatch.
- **folder_service.py**: Decoupled from KB tools because the folder CRUD is also used by REST endpoints for the FileManager UI.

## Architectural Patterns

### Pattern 1: KB Tools as Thin Wrappers over Supabase RPCs

**What:** Each KB tool (ls, tree, grep, glob, read) is a Python function that calls a Supabase RPC (Postgres function), formats the result, and returns a string. The heavy lifting happens in Postgres.

**When to use:** Always for KB navigation. The data lives in Postgres; doing joins/filters in Python means pulling too much data over the wire.

**Trade-offs:** Postgres functions are harder to debug than Python, but much faster for hierarchical queries. Since the folder tree is a classic adjacency list, recursive CTEs in Postgres are the natural fit.

**Example:**
```python
# kb_service.py
def kb_ls(user_id: str, path: str, source_scope: str) -> str:
    db = get_supabase()
    result = db.rpc("kb_list_path", {
        "target_path": path,
        "filter_user_id": user_id,
        "source_scope": source_scope,  # 'default' | 'private' | 'all'
    }).execute()
    # Format as file listing
    lines = []
    for item in result.data:
        icon = "DIR" if item["is_folder"] else item["mime_type"]
        lines.append(f"  {icon}  {item['name']}")
    return "\n".join(lines) or "(empty)"
```

### Pattern 2: Explorer Agent as Tool-Using Loop (Existing Pattern)

**What:** The explorer sub-agent gets its own system prompt, message history, and tool definitions. It runs a while-loop calling the LLM until it produces a final text response (no more tool calls). This is identical to how the main chat loop works but scoped to KB tools only.

**When to use:** When the user's question requires multiple navigation steps -- e.g., "Compare the setup rules for Catan and Ticket to Ride."

**Trade-offs:** Each explorer invocation burns tokens (its own system prompt + accumulated tool results). Must enforce a max iteration count and token budget to prevent runaway loops.

**Example:**
```python
# explorer_service.py
def run_exploration(user_id: str, goal: str, source_scope: str) -> dict:
    """Multi-step KB traversal to answer a complex question."""
    KB_TOOLS = [KB_LS_TOOL, KB_TREE_TOOL, KB_GREP_TOOL, KB_GLOB_TOOL, KB_READ_TOOL]
    messages = [
        {"role": "system", "content": EXPLORER_SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]
    for _ in range(MAX_EXPLORER_STEPS):
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=KB_TOOLS,
        )
        if response.choices[0].finish_reason == "stop":
            return {"result": response.choices[0].message.content}
        # Execute tool calls, append results, continue loop
        ...
    return {"result": "Explorer reached step limit", "partial": True}
```

### Pattern 3: Source Routing via Intent Classification

**What:** Before the main agent selects tools, a lightweight classification step determines which data sources are relevant. This sets the `source_scope` parameter that all KB tools and retrieval use.

**When to use:** Every chat message. The classification can be a simple heuristic (keyword matching) initially, upgraded to LLM classification later.

**Trade-offs:** Adds latency if using LLM classification (~200ms). Heuristic approach is faster but less accurate. Recommendation: start with heuristics, add LLM fallback for ambiguous queries.

**Implementation approach:**
```python
# source_router.py
def classify_source(query: str, user_has_private_docs: bool) -> str:
    """Returns 'default' | 'private' | 'both' | 'web'"""
    # Phase 1: Heuristic
    query_lower = query.lower()
    # Explicit scope mentions
    if "my documents" in query_lower or "my files" in query_lower:
        return "private"
    if any(game in query_lower for game in DEFAULT_GAME_NAMES):
        return "default" if not user_has_private_docs else "both"
    # Default: search both
    return "both"
```

### Pattern 4: Materialized Path for Folder Hierarchy

**What:** Each folder stores its full path as a text column (e.g., `/Board Games/Catan/Rules`). This is in addition to the `parent_id` adjacency list. The path column enables fast prefix matching for tree operations without recursive queries.

**When to use:** Always. The dual representation (parent_id for structural integrity, path for fast queries) is the standard approach for hierarchies that need both mutation and fast reads.

**Trade-offs:** Path must be updated on folder rename/move (cascading update to all descendants). This is acceptable because folder mutations are rare compared to reads.

```sql
-- 016_create_folders.sql
CREATE TABLE folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),  -- NULL for default KB
    parent_id UUID REFERENCES folders(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    path TEXT NOT NULL,  -- materialized path: '/Games/Catan/Rules'
    source_type TEXT NOT NULL DEFAULT 'private'
        CHECK (source_type IN ('default', 'private')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_folders_path ON folders USING btree (path text_pattern_ops);
CREATE INDEX idx_folders_user_source ON folders (user_id, source_type);
```

## Data Flow

### Chat with KB Tools (Primary Flow)

```
User sends message
    |
    v
POST /api/threads/{id}/messages
    |
    v
Load message history from Supabase
    |
    v
Source Router classifies query -> source_scope
    |
    v
Build tool list (include KB tools + search + existing tools)
    |
    v
stream_chat_completion() with tools
    |
    +---> LLM returns text_delta -> SSE to frontend
    |
    +---> LLM calls kb_ls/tree/grep/glob/read
    |         |
    |         v
    |     kb_service dispatches to Supabase RPC
    |     (passes source_scope to filter default/private/both)
    |         |
    |         v
    |     Result appended to messages, loop continues
    |
    +---> LLM calls explore_kb (complex multi-step question)
    |         |
    |         v
    |     explorer_service.run_exploration()
    |         |
    |         +---> Inner tool loop (kb_ls, kb_grep, kb_read...)
    |         |     Each step: LLM decides next tool -> execute -> append
    |         |
    |         v
    |     Synthesized answer returned to main agent
    |
    +---> LLM produces final response -> SSE to frontend
    |
    v
Store assistant message in Supabase
```

### Document Upload with Folder Assignment

```
User uploads file (via FileManager UI or existing upload)
    |
    v
POST /api/documents/upload  (extended with folder_id param)
    |
    v
Deduplication check (existing)
    |
    v
Upload to Supabase Storage: {user_id}/{folder_path}/{filename}
    |
    v
Create document record (with folder_id, source_type='private')
    |
    v
Ingestion pipeline (existing: parse -> chunk -> embed -> store)
    |
    v
Each chunk gets: folder_path, source_type in metadata
    |
    v
Realtime status update (existing)
```

### Default KB Seeding

```
seed_default_kb.py (run once on deploy)
    |
    v
For each of 10 games:
    |
    +---> Create folder: /Board Games/{Game Name}/
    |     Create subfolders: /Rules, /Reference, etc.
    |
    +---> Upload markdown files to Supabase Storage
    |     Path: default_kb/{game}/{filename}
    |
    +---> Create document records
    |     source_type='default', user_id=NULL (or system user)
    |
    +---> Run ingestion pipeline
          Chunks tagged with source_type='default'
```

### Key Data Flows

1. **Source-scoped search:** All retrieval and KB tool queries accept a `source_scope` parameter. Supabase RPCs filter by `source_type` column. Default KB has `user_id=NULL` and `source_type='default'`; RLS policies grant SELECT to all authenticated users on default rows.

2. **Token budget management:** The explorer agent tracks cumulative token count of tool results. When approaching budget limit, it switches from `kb_read` (full content) to `kb_grep` (targeted excerpts). The budget is configurable via `Settings.explorer_max_context_tokens`.

3. **Folder path resolution:** KB tools accept human-readable paths (e.g., `/Catan/Rules`). The `kb_service` resolves these against the `folders.path` column using prefix matching. Ambiguous paths return disambiguation options.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-100 users | Current architecture is fine. Default KB shared across all users. Single Supabase instance handles everything. |
| 100-1k users | Index optimization: ensure `folders.path` and `document_chunks.source_type` are indexed. Consider caching default KB tree structure (it rarely changes). |
| 1k+ users | Cache frequently accessed default KB chunks in Redis/memory. Explorer agent results for common questions (e.g., "Catan rules") could be cached. |

### Scaling Priorities

1. **First bottleneck:** Explorer agent token costs. Each exploration is 3-8 LLM calls. Mitigation: cache results for identical goals against default KB, enforce step limits.
2. **Second bottleneck:** Supabase RPC latency for tree operations on large folder hierarchies. Mitigation: materialized path index makes this O(log n) not O(n).

## Anti-Patterns

### Anti-Pattern 1: KB Tools Querying Storage Bucket Directly

**What people do:** Implement `kb_ls` by listing files in Supabase Storage bucket.
**Why it's wrong:** Storage bucket listings don't have metadata, source_type filtering, or RLS integration. You'd need separate queries for folder structure anyway. Two sources of truth = drift.
**Do this instead:** All KB tools query the `folders` and `documents` tables. Storage bucket is only for raw file retrieval during ingestion.

### Anti-Pattern 2: Explorer Agent with Unlimited Steps

**What people do:** Let the explorer loop until it produces a final answer.
**Why it's wrong:** Complex queries can cause infinite loops or consume entire context window. A "compare all 10 games" query would pull every document.
**Do this instead:** Hard limit of 8-10 steps. Token budget cap. Explorer must synthesize partial results if it hits the limit.

### Anti-Pattern 3: Separate Tool Definitions for Default vs Private KB

**What people do:** Create `kb_ls_default` and `kb_ls_private` as separate tools.
**Why it's wrong:** Doubles the tool count, confuses the LLM, and prevents the agent from naturally searching across both scopes. The source router should handle scoping transparently.
**Do this instead:** Single `kb_ls` tool. Source scope is determined by the source router and passed as a parameter, invisible to the LLM's tool choice.

### Anti-Pattern 4: Storing Folder Hierarchy Only in Storage Paths

**What people do:** Rely on Supabase Storage path conventions (e.g., `user_id/folder/subfolder/file`) without a `folders` table.
**Why it's wrong:** No way to have empty folders, folder metadata, or efficient tree queries. Listing children requires string parsing on every document record.
**Do this instead:** Explicit `folders` table with `parent_id` and materialized `path`. Documents reference `folder_id`. Storage paths are a convenience, not the source of truth.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenRouter LLM | OpenAI-compatible SDK (existing) | Explorer agent uses same client, may want different model for cost control |
| Supabase | Python client + RPCs (existing) | New RPCs needed for KB navigation queries |
| LangSmith | Tracing wrapper (existing) | Add `@traceable` to explorer loops for debugging multi-step traversals |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Tool Router -> KB Service | Direct function call | Same process, no serialization overhead |
| Tool Router -> Explorer Agent | Direct function call (blocking) | Explorer runs synchronously; SSE stream pauses during exploration. Emit `tool_event` with status updates. |
| Source Router -> Tool Router | Function return value | Source router returns scope string; tool router passes it through to every KB/retrieval call |
| Frontend -> Folder API | REST (CRUD) | Standard REST endpoints for folder management |
| Frontend -> Chat SSE | SSE stream (existing) | Extended with new tool event types for KB tools and explorer progress |
| Seed Script -> Ingestion Pipeline | Reuses existing ingestion functions | Seed script calls `process_document()` directly, same as upload endpoint |

## Build Order (Dependencies)

The components have clear dependencies that dictate build order:

```
Phase 1: Data Foundation
    folders table + RLS + source_type columns
    (everything else depends on the schema)
        |
        v
Phase 2: Folder Management
    folder_service.py + REST API + FileManager UI
    (users need to organize docs before KB tools make sense)
        |
        v
Phase 3: Default KB Seeding
    seed script + default KB content
    (needs folders table; provides data for KB tools to navigate)
        |
        v
Phase 4: KB Navigation Tools
    kb_service.py (ls, tree, grep, glob, read)
    Supabase RPCs for efficient queries
    Tool definitions in chat.py
    (needs folders + documents + default KB data to test against)
        |
        v
Phase 5: Source Routing
    source_router.py + integration into chat flow
    (needs KB tools working to be meaningful)
        |
        v
Phase 6: Explorer Sub-Agent
    explorer_service.py with tool loop + token budget
    (needs KB tools as its toolkit; most complex component)
        |
        v
Phase 7: Polish
    Enhanced tool event UI, smart chunking refinement, scope controls
```

**Rationale:** Each phase produces a testable increment. The schema comes first because it is a hard dependency. Folder management is next because it provides the UI for organizing content that the KB tools will navigate. Default KB seeding can happen in parallel with folder UI polish since it only depends on the schema. KB tools are the core new capability. Source routing and the explorer agent build on top.

## RLS Strategy for Default KB

The default KB requires a departure from the current "users only see their own data" RLS model. Recommended approach:

```sql
-- Default KB rows have user_id = NULL and source_type = 'default'
-- All authenticated users can SELECT default rows
-- Only service role can INSERT/UPDATE/DELETE default rows

-- documents table
CREATE POLICY "Users can see default KB"
    ON documents FOR SELECT
    USING (source_type = 'default' OR auth.uid() = user_id);

-- document_chunks table
CREATE POLICY "Users can see default KB chunks"
    ON document_chunks FOR SELECT
    USING (source_type = 'default' OR auth.uid() = user_id);

-- folders table
CREATE POLICY "Users can see default KB folders"
    ON folders FOR SELECT
    USING (source_type = 'default' OR auth.uid() = user_id);
```

This keeps existing RLS intact for private docs while opening default KB to all authenticated users. The seed script runs with the service role key, bypassing RLS for inserts.

## Sources

- Existing codebase analysis (chat.py tool loop, subagent_service.py pattern, retrieval_service.py, database schema)
- Supabase documentation on RLS policies and RPC functions
- Materialized path pattern for hierarchical data in relational databases (standard pattern, well-documented in PostgreSQL literature)
- Claude Code tool design patterns (ls, tree, grep, glob, read tool set)

---
*Architecture research for: Board Game Knowledge Base with Agent Tooling*
*Researched: 2026-04-07*
