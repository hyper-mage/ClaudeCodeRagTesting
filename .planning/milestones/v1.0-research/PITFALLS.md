# Pitfalls Research

**Domain:** Board game knowledge base RAG with hierarchical KB management, Claude Code-style agent tools, and mixed-visibility content
**Researched:** 2026-04-07
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: RLS Policy Collision Between Default KB and Private Documents

**What goes wrong:**
The existing codebase uses `service_role_key` to bypass RLS entirely (see `database.py`), with RLS policies that filter by `user_id`. Adding a default KB (shared, no `user_id`) alongside private user documents creates a fundamental visibility conflict. The current `search_documents` function passes `user_id` as a filter -- default KB rows with a different or null `user_id` would be invisible to users. Developers typically either (a) bypass RLS for default content and accidentally expose private data, or (b) enforce strict user scoping and make the default KB invisible.

**Why it happens:**
The existing RLS model is binary: "users only see their own data." Adding a third visibility tier (shared/default) requires restructuring this assumption. Supabase evaluates multiple RLS policies with OR logic, which is counterintuitive -- a "public read" policy combined with a "user's own data" policy means BOTH apply, potentially over-exposing data if not carefully scoped.

**How to avoid:**
- Add a `visibility` column (`'default'` | `'private'`) to `documents` and `document_chunks` tables
- Use a dedicated "system" user_id (e.g., a UUID constant like `00000000-0000-0000-0000-000000000000`) for all default KB content
- Write RLS policies as: `(user_id = auth.uid()) OR (visibility = 'default')` for SELECT
- Write INSERT/UPDATE/DELETE policies as: `user_id = auth.uid()` only (prevent users from modifying default KB)
- Update ALL existing RPC functions (`match_document_chunks`, `keyword_search_chunks`) to accept an optional visibility filter parameter
- Test: verify a user can search across both default and private, but cannot delete/modify default KB entries

**Warning signs:**
- Default KB content not appearing in search results
- Users seeing other users' private documents after adding the "public read" policy
- Search results mixing default and private content inconsistently depending on search mode (vector vs keyword)

**Phase to address:**
Phase 1 (Default KB + Folder Structure) -- must be the foundation before any tools or agents are built on top.

---

### Pitfall 2: Storage Path and Database Folder Hierarchy Desynchronization

**What goes wrong:**
Supabase Storage uses flat object paths (e.g., `board-games/catan/rules.pdf`) -- there are no real "folders," just path prefixes. The project needs a parallel folder hierarchy in the database for the agent tools (`ls`, `tree`) to query. These two representations drift apart: a file is moved in storage but the DB record's `folder_path` is not updated (or vice versa), breaking tool outputs. The `ls` tool returns files that do not exist, or storage has files the tools cannot find.

**Why it happens:**
Supabase Storage has no concept of folder metadata, parent IDs, or hierarchy -- it is purely path-based. Developers must maintain a separate `folders` table in Postgres. Every storage operation (upload, move, rename, delete) must update BOTH storage AND the database atomically. Without a transaction boundary across storage + DB, partial failures leave the system inconsistent.

**How to avoid:**
- Make the database the source of truth for hierarchy, not storage paths
- Store the folder path in a `folders` table with `id`, `name`, `parent_id`, `user_id`, `visibility` columns
- Use a materialized path column (e.g., `/board-games/catan/`) for efficient prefix queries
- Wrap all file operations in a service function that updates DB first, then storage -- if storage fails, roll back the DB change
- Agent tools (`ls`, `tree`, `glob`) query ONLY the database, never storage directly
- Add a consistency check endpoint or script that reconciles storage vs DB on demand

**Warning signs:**
- `ls` tool returns empty for a folder that visibly has files in the frontend
- Moving a file in the file manager UI does not update what the agent sees
- Orphaned storage objects with no corresponding DB record accumulating over time

**Phase to address:**
Phase 1 (Folder Structure) -- the data model must be right before building tools or the file manager UI.

---

### Pitfall 3: Agent Tool Overuse Blowing Context Window

**What goes wrong:**
With 5+ KB navigation tools available, the LLM agent calls tools excessively for simple queries. A question like "What are the rules of Catan?" triggers: `tree` (to see the structure), `ls /board-games/catan/` (to list files), `read catan-rules.md` (to get content), `grep "victory points" catan-rules.md` (for specifics) -- consuming 4 tool calls and potentially 50K+ tokens of context before even generating an answer. The current architecture stores full tool outputs in `current_messages` (see `chat.py` line 287-290), meaning each tool result stays in context for ALL subsequent LLM calls in the loop.

**Why it happens:**
LLMs with many tools tend to "explore" rather than act decisively. The existing tool-use loop (`while True` in `chat.py`) keeps looping until no more tool calls are made, with no token budget enforcement. Each tool output is appended to `current_messages` in full, with no truncation or summarization. Board game manuals can be 50+ pages, and `read` on a full document could inject 100K+ characters into context.

**How to avoid:**
- Implement a **token budget tracker** that counts approximate tokens across `current_messages` and refuses/truncates tool outputs when budget is exceeded
- Use the **Memory Pointer Pattern**: store large tool outputs (especially `read` results) in a side-channel dict, and inject only a summary + reference into the LLM context. Full content is available if the agent asks for more detail
- Cap `read` tool output to a configurable max (e.g., 8K tokens) with line-range support so the agent can request specific sections
- Set a **max tool iterations** limit (e.g., 5 per turn) to prevent infinite exploration loops
- Make tool descriptions explicitly guide the agent: "Use `search_documents` for most queries. Only use `ls`/`tree` when the user asks about KB structure. Use `read` only for specific files."
- Consider observation masking: after a tool result is consumed by the next LLM call, replace it with a short summary in the message history

**Warning signs:**
- Single user messages triggering 6+ tool calls
- LLM responses becoming incoherent or ignoring early tool results (context rot -- attention degrades in the middle of long contexts)
- API costs spiking disproportionately to query volume
- Chat responses taking 15+ seconds for simple questions

**Phase to address:**
Phase 2 (KB Navigation Tools) for basic limits; Phase 3 (Explorer Sub-Agent) for memory pointer pattern and observation masking.

---

### Pitfall 4: Explorer Sub-Agent Context Isolation Failure

**What goes wrong:**
The explorer sub-agent is designed for deep multi-step KB traversal, but its results must flow back to the parent agent's context. Two failure modes: (a) the sub-agent returns too much data, overwhelming the parent context, or (b) the sub-agent's isolated context lacks enough information about the user's question, causing it to explore irrelevant paths. The existing `subagent_service.py` already has a `subagent_max_context_chars` limit (100K), but this is applied to the INPUT document, not the OUTPUT -- nothing limits how much the sub-agent returns.

**Why it happens:**
The current sub-agent pattern (`run_document_analysis`) does a single non-streaming LLM call with the full document text. The new explorer sub-agent needs multiple tool calls (ls, tree, read, grep) in its own tool loop -- it is an agent within an agent. Without output budgets, a "compare Catan vs Ticket to Ride" query could have the explorer reading both full rulebooks and returning a 10K+ token comparison, which then gets injected into the parent's already-growing context.

**How to avoid:**
- Set a hard `max_output_tokens` on the explorer sub-agent's final response (e.g., 2K tokens)
- Give the explorer its own independent tool loop with its own token budget tracker
- Pass a focused task description from the parent agent, not the full conversation history
- Return structured results (not free-form text) -- e.g., `{"summary": "...", "key_findings": [...], "sources": [...]}` -- so the parent agent can selectively use parts
- Stream sub-agent tool events to the frontend for transparency, but do NOT add them to the parent's LLM context

**Warning signs:**
- Explorer sub-agent calls exceeding 30 seconds consistently
- Parent agent ignoring or contradicting explorer results (sign of context overload)
- Explorer exploring folders unrelated to the query (insufficient task scoping)

**Phase to address:**
Phase 3 (Explorer Sub-Agent) -- must be designed with budget constraints from the start.

---

### Pitfall 5: Image OCR Producing Unsearchable Garbage for Board Game Content

**What goes wrong:**
Board game content includes photos of game boards, cards with stylized fonts, rule cards with complex layouts (multi-column, sidebars, icons), and scoring reference sheets. Docling's OCR (EasyOCR/Tesseract) produces garbled text from these inputs -- stylized fonts are misread, icons are interpreted as random characters, multi-column layouts merge columns, and game-specific terminology gets mangled. This garbage text gets embedded and pollutes search results, causing irrelevant or confusing retrieval.

**Why it happens:**
Docling's OCR is optimized for standard document layouts (single-column, standard fonts). Board game materials are designed for visual appeal, not machine readability. Additionally, Docling does not generate image descriptions for images -- it only extracts OCR text, meaning game board photos with minimal text produce nearly empty chunks.

**How to avoid:**
- Add a **quality gate** after OCR: check character-level confidence scores, reject chunks below a threshold
- For image-heavy content, offer a "manual description" field in the upload UI where users can add their own text description of what the image shows
- Consider a separate vision-model pipeline for images (e.g., GPT-4o vision to describe board game images) rather than relying on OCR alone
- Mark image-sourced chunks with `source_type: "ocr"` metadata so the agent can weight them lower in retrieval
- Set user expectations in the UI: "Image uploads work best with clear text. Photos of game boards may have limited searchability."

**Warning signs:**
- Search results returning chunks of garbled characters
- Users uploading images and getting no useful results from them
- Embedding similarity scores being unexpectedly low for image-derived chunks

**Phase to address:**
Phase 1 or 2 (when adding image ingestion support) -- quality gate must exist before users start uploading images.

---

### Pitfall 6: XLSX Parsing Losing Structural Context

**What goes wrong:**
Board game score sheets and trackers are heavily structured -- column headers define meaning (Player, Score, Round), and cell values are meaningless without their headers. Docling converts XLSX to markdown tables, but chunking then splits tables across chunk boundaries, producing chunks like `| 42 | 38 | 15 |` with no column headers. These chunks are useless for retrieval and confusing to the LLM.

**Why it happens:**
Standard text chunking (split by character count with overlap) does not understand table structure. A 100-row spreadsheet converted to markdown might be 5K tokens, which gets split into 5 chunks. Only the first chunk has the header row.

**How to avoid:**
- Implement **table-aware chunking**: detect markdown table blocks and keep each table as a single chunk (or chunk by row groups, always prepending the header row)
- Add the filename and sheet name as metadata prefix to every chunk: `"From score_tracker.xlsx, Sheet 'Game Log': | Player | Score | Round | ..."`
- Set a higher chunk size limit for table content specifically
- If a table exceeds the chunk size, split by row groups but always include the header row in each chunk

**Warning signs:**
- XLSX search results returning rows of numbers with no context
- Agent responses saying "I found some data but I'm not sure what the columns represent"
- Users uploading spreadsheets and getting no useful answers

**Phase to address:**
Phase 1 (XLSX ingestion support) -- chunking strategy must handle tables before users upload spreadsheets.

---

### Pitfall 7: File Manager UI State Desync with Backend

**What goes wrong:**
The drag-drop file manager shows a folder tree that is out of sync with the actual database state. User drags a file to a new folder, the UI updates optimistically, but the backend call fails (e.g., RLS violation, network error). Now the UI shows the file in the new location while the DB still has it in the old location. The agent's `ls` and `tree` tools report the old state, contradicting what the user sees.

**Why it happens:**
Drag-drop UIs almost always use optimistic updates for responsiveness. But folder operations involve multiple backend calls (update folder_id on document, move file in storage, update chunk paths). Any partial failure leaves an inconsistent state. React state management for trees is notoriously complex -- nested state updates, maintaining expansion state, handling concurrent moves.

**How to avoid:**
- Do NOT use optimistic updates for move/rename/delete operations. Show a loading spinner instead. These operations are infrequent enough that a 200ms delay is acceptable
- Use Supabase Realtime subscriptions on the `documents` and `folders` tables to push server state to the frontend -- the UI always reflects confirmed DB state
- Wrap multi-step operations (move file = update DB + move storage) in a single backend endpoint that handles rollback on partial failure
- Use a dedicated tree state library (react-complex-tree) rather than building custom nested state management
- Disable drag-drop during pending operations to prevent race conditions

**Warning signs:**
- Files appearing in two folders simultaneously
- "File not found" errors when the agent tries to read a file that the UI shows as present
- Frontend console errors about invalid tree state after drag operations

**Phase to address:**
Phase 4 (File Manager UI) -- must be built with pessimistic updates and realtime sync from the start.

---

### Pitfall 8: Default KB Seed Script Fragility

**What goes wrong:**
The seed script that pre-loads 10 board games runs once on deploy. If it fails partway through (e.g., network timeout on game 6), the KB is partially seeded. Re-running the script either duplicates games 1-5 or fails on constraint violations. There is no way to know which games were successfully seeded without manual inspection.

**Why it happens:**
Seed scripts are treated as one-off throw-away code. Developers do not build idempotency, progress tracking, or partial-failure recovery into them. The existing `record_manager.py` has content-addressed deduplication, but the seed script may bypass this if it uses a different ingestion path.

**How to avoid:**
- Make the seed script idempotent: check for existing documents by content hash before inserting
- Use the existing ingestion pipeline (not raw SQL inserts) so content hashing, chunking, embedding, and metadata extraction all run properly
- Add a `source` metadata field (`'default_kb'`) to distinguish seeded content from user uploads
- Track seed progress in a simple status table or file: which games have been seeded, their document IDs, completion status
- Provide a `--force` flag to re-seed a specific game (delete + re-ingest) without affecting others
- Test the seed script in CI by running it twice and verifying no duplicates

**Warning signs:**
- Some default games appearing in search but not others
- Duplicate chunks for the same game inflating search results
- Seed script taking 30+ minutes (suggests it is re-processing already-seeded content)

**Phase to address:**
Phase 1 (Default KB) -- the seed script is the first thing built and must be robust.

---

### Pitfall 9: Agent Source Selection Confusion

**What goes wrong:**
The agent must decide whether to search the default KB, the user's private docs, or both. Without explicit scoping, the agent guesses wrong: a user asks "What are Catan's rules?" and the agent searches only the user's private docs (which do not have Catan), returning "I couldn't find anything." Or a user asks about their private game notes but gets results from the default KB instead.

**Why it happens:**
The current `search_documents` tool has no source scoping parameter. The agent relies on the system prompt to decide, which is unreliable. Metadata filters exist (`document_type`, `topic`) but nothing for source/visibility. Without explicit tooling, the LLM cannot reliably distinguish between "search everything" vs "search only my docs" vs "search only the default KB."

**How to avoid:**
- Add a `scope` parameter to the search tool: `"all"` (default), `"default_kb"`, `"private"`
- Include the user's document list and the default KB game list in the system prompt context so the agent knows what exists where
- Use the `tree` tool output to orient the agent: default KB lives under `/default/` and private docs under `/my-docs/`
- Add a "scope" UI control that users can set to narrow searches, which gets passed as context to the agent
- In the system prompt, explicitly instruct: "When the user asks about a well-known board game, search the default KB first. When they reference 'my' documents or specific uploads, search private docs."

**Warning signs:**
- Agent consistently returning "I don't have information about that" for games that ARE in the default KB
- Users confused about whether the agent is searching their docs or the shared KB
- Agent mixing default KB and private doc results without indicating which is which

**Phase to address:**
Phase 2 (KB Navigation Tools + Search Integration) -- must be addressed when tools are connected to the dual-source architecture.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using service_role_key for all backend DB calls (bypassing RLS) | Simple -- no need to pass user JWTs to backend | RLS policies are never exercised by backend, bugs in policies go undetected until frontend tries direct DB access | During initial development only; migrate to per-user JWT-scoped clients for tool operations before launch |
| Storing folder hierarchy only in storage paths (no DB table) | One less table to manage | Tools cannot efficiently query folder structure; `ls` requires listing storage objects with prefix filtering which is slow | Never -- DB folder table is required for agent tools |
| Embedding full tool outputs in chat messages without truncation | Simple implementation, agent sees everything | Context window exhaustion on complex queries, increasing API costs per message | Acceptable for MVP with simple queries; must add truncation before explorer sub-agent is built |
| Hardcoding 10 default games in seed script | Quick to ship | Adding/updating default games requires code changes and redeployment | Acceptable for initial release; add a config-driven approach if the game list needs to change frequently |
| Using `subagent_max_context_chars` as the only budget control | One setting to configure | Does not account for tool result sizes, multiple tool calls, or the difference between input and output budgets | Never sufficient once the explorer sub-agent has its own tool loop |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Supabase Storage + DB | Moving a file in storage without updating the DB `folder_path` | Always update DB first, then storage. Single backend endpoint handles both atomically |
| Supabase Realtime + File Manager | Subscribing to entire `documents` table changes | Subscribe only to the user's documents with RLS-filtered channel. Otherwise Realtime broadcasts all changes to all clients |
| Docling XLSX conversion | Assuming XLSX produces clean markdown automatically | Pre-process: strip empty rows/columns, detect header rows, tag sheets. Post-process: validate markdown table structure before chunking |
| OpenRouter + tool calling | Assuming all OpenRouter models support tool_calls equally | Some models return malformed tool call JSON or ignore tools entirely. Pin to a model known to support structured tool output (e.g., GPT-4o, Claude 3.5+) and test tool calling specifically |
| Supabase RPC functions | Adding a `visibility` parameter to RPC but forgetting to update the function's SECURITY DEFINER context | RPC functions with SECURITY DEFINER run as the function creator, bypassing RLS. If the function accepts user input for filtering, it MUST validate inputs to prevent injection |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unindexed `folder_path` queries | `ls` and `tree` tool calls taking 500ms+ | Add a GIN index on the materialized path column and a B-tree index on `parent_id` | 1000+ documents across 50+ folders |
| Full document reassembly for `read` tool | `get_full_document_text` loads ALL chunks for a document into memory | Add pagination to chunk retrieval; support line-range reads that map to chunk ranges | Documents with 200+ chunks (50+ page manuals) |
| RLS policy joins on every query | Adding folder-based RLS that JOINs `folders` table on every `document_chunks` query | Cache the user's accessible folder IDs in a session-scoped temporary table, or use a denormalized `visibility` column directly on `document_chunks` | 10K+ chunks across 100+ documents |
| Embedding generation during seed | Seeding 10 games synchronously blocks deployment for 10+ minutes | Run seed as a background job; or pre-compute embeddings and store them in the seed data | Always -- 10 full game manuals = thousands of chunks to embed |
| Frontend tree rendering with large hierarchies | File manager becomes sluggish with 100+ visible nodes | Use virtualized tree rendering (react-complex-tree supports this). Lazy-load folder contents on expand | 200+ files/folders visible simultaneously |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Default KB modification via API | Users could potentially update/delete default KB content if RLS policies have INSERT/UPDATE/DELETE for the "public read" visibility tier | Ensure write policies ONLY match `user_id = auth.uid()` and the system user_id is never a valid auth user |
| Folder traversal in agent tools | Agent `read` tool could be manipulated via prompt injection to read files outside the user's scope | All tool implementations must filter by `user_id` (and `visibility = 'default'`). Never construct file paths from user/LLM input without validation |
| SQL injection via text-to-SQL + new tables | Adding `folders` and new columns to the queryable schema exposes them to the existing `query_database` tool. Malicious SQL could probe folder structures | Ensure the SQL tool's RLS policies cover all new tables. Audit `get_queryable_schema()` to only expose safe columns |
| Storage bucket permissions for default KB | Default KB files in a public bucket could be downloaded directly without authentication | Use a separate private bucket for default KB content. Serve files through authenticated API endpoints only |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visual distinction between default KB and private docs | Users confused about what they uploaded vs what came pre-loaded | Use different icons/colors for default vs private content. Label default KB games clearly as "Included" |
| Tool call transparency showing raw tool names | Users see "Calling ls..." or "Calling grep..." which means nothing to non-developers | Translate tool calls to human language: "Browsing the knowledge base...", "Searching for relevant rules...", "Reading the Catan rulebook..." |
| Explorer sub-agent with no progress indication | Sub-agent takes 10-20 seconds with no feedback, users think it is frozen | Stream sub-agent tool events to the UI in real-time, similar to the existing `tool_event` SSE pattern. Show a step-by-step progress list |
| Scope controls hidden or absent | Users cannot tell what the agent is searching, leading to frustration when results come from unexpected sources | Add a visible "Search scope" indicator/toggle in the chat input area: "Searching: All / Default KB / My Documents" |
| Drag-drop with no undo | User accidentally drags a file to the wrong folder, no way to reverse it | Add an undo toast notification after move operations (store the previous location and offer a 5-second undo window) |

## "Looks Done But Isn't" Checklist

- [ ] **Folder hierarchy:** Often missing recursive delete -- deleting a folder must delete all children (sub-folders, documents, chunks, storage objects)
- [ ] **Default KB seed:** Often missing embedding generation -- seed script inserts documents but skips the chunking/embedding pipeline, making them unsearchable
- [ ] **RLS on new tables:** Often missing policies on the new `folders` table -- it gets created but only `documents` and `document_chunks` have RLS
- [ ] **Agent tool definitions:** Often missing error handling in tool JSON schemas -- the agent sends malformed arguments and the tool crashes instead of returning an error message
- [ ] **Search with scope:** Often missing the update to BOTH vector search AND keyword search RPCs -- hybrid search breaks because only one RPC was updated with visibility filtering
- [ ] **Tree tool:** Often missing depth limiting -- `tree` on the root folder of a 500-document KB returns a massive string that blows context
- [ ] **File manager:** Often missing loading states for folder expansion -- folder contents load asynchronously but the UI shows empty folders briefly, confusing users
- [ ] **Explorer sub-agent:** Often missing timeout -- sub-agent enters an infinite tool loop with no maximum iteration or time limit

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| RLS policy collision (data leak) | HIGH | Audit all exposed data, fix policies, notify affected users, re-test with integration tests covering all visibility scenarios |
| Storage/DB desync | MEDIUM | Run reconciliation script: list all storage objects, compare with DB records, flag orphans and missing entries for manual review |
| Context window blowout | LOW | Add token budget middleware, truncate existing tool results in message history, tune `max_tool_iterations` config |
| Explorer infinite loop | LOW | Add `max_iterations` and `timeout_seconds` config. Kill stuck requests. No data loss -- just wasted tokens |
| Garbled OCR chunks in search index | MEDIUM | Identify OCR-sourced chunks by metadata, delete low-quality ones, re-process with improved pipeline or manual descriptions |
| Partial seed failure | LOW | Re-run idempotent seed script. If not idempotent, manually identify missing games and seed individually |
| File manager state desync | LOW | Force refresh from server state. Add "Refresh" button to file manager. Implement Realtime subscription for auto-sync |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| RLS policy collision | Phase 1 (Default KB + Data Model) | Integration test: user A sees default + own docs, not user B's docs |
| Storage/DB desync | Phase 1 (Folder Structure) | Move a file via API, verify both storage path and DB record updated. Kill backend mid-operation, verify rollback |
| Agent tool overuse | Phase 2 (KB Navigation Tools) | Send 10 diverse queries, verify average tool calls per query is under 4 |
| Explorer context isolation | Phase 3 (Explorer Sub-Agent) | Run a "compare two games" query, verify parent context stays under budget |
| OCR quality | Phase 1 or 2 (Image Ingestion) | Upload 5 board game photos, verify extracted text is meaningful or quality gate rejects them |
| XLSX structural context | Phase 1 (XLSX Support) | Upload a score sheet, search for a player name, verify the result includes column headers |
| File manager desync | Phase 4 (File Manager UI) | Simulate a failed move operation, verify UI reverts to server state |
| Seed script fragility | Phase 1 (Default KB) | Run seed script twice, verify no duplicates. Kill script mid-run, re-run, verify completion |
| Agent source selection | Phase 2 (Tool Integration) | Ask about a default KB game without uploading it, verify the agent finds it |

## Sources

- [Supabase RLS Documentation](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase Storage Hierarchical RLS Challenges](https://supabase.com/docs/guides/troubleshooting/supabase-storage-inefficient-folder-operations-and-hierarchical-rls-challenges-b05a4d)
- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control)
- [Context Window Overflow in AI Agents (arxiv)](https://arxiv.org/html/2511.22729v1)
- [Effective Context Engineering for AI Agents - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [JetBrains Research: Context Management for LLM Agents](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)
- [Redis: Context Window Overflow](https://redis.io/blog/context-window-overflow/)
- [RAG Best Practices: Lessons from 100+ Teams](https://www.kapa.ai/blog/rag-best-practices)
- [Docling GitHub Issues: Image OCR Limitations](https://github.com/docling-project/docling/issues/2446)
- [Sub-Agent Spawning Patterns](https://www.agentic-patterns.com/patterns/sub-agent-spawning/)
- [React Complex Tree Library](https://github.com/lukasbach/react-complex-tree)
- [Supabase RLS Best Practices for Multi-Tenant Apps](https://makerkit.dev/blog/tutorials/supabase-rls-best-practices)
- [Supabase API Keys Documentation](https://supabase.com/docs/guides/api/api-keys)
- Codebase analysis: `backend/database.py`, `backend/routers/chat.py`, `backend/services/subagent_service.py`, `backend/services/retrieval_service.py`, `backend/config.py`

---
*Pitfalls research for: Board Game KB RAG with hierarchical management, agent tools, and mixed visibility*
*Researched: 2026-04-07*
