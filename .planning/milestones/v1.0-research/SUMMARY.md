# Project Research Summary

**Project:** Board Game Knowledge Base with Claude Code-style Agent Tooling
**Domain:** RAG application with hierarchical document management and agentic navigation tools
**Researched:** 2026-04-07
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project extends an existing RAG chat application (React + FastAPI + Supabase) into a board game knowledge base with Claude Code-inspired agent tools. The core idea is novel in the board game space: instead of single-turn Q&A (like competitors Ludomentor, Boardside, Rulepop), the agent gets filesystem-like tools (ls, tree, grep, glob, read) to explore a hierarchical knowledge base, plus an explorer sub-agent for multi-step traversal. The existing codebase already has chat with tool calling, SSE streaming, sub-agents, and document ingestion -- the new work builds on these foundations rather than replacing them.

The recommended approach is to build in strict dependency order: data model first (folders table, RLS for mixed-visibility content, source_type columns), then folder management and default KB seeding, then KB navigation tools, then the explorer sub-agent. The existing stack handles most needs -- the only new backend dependencies are tiktoken for token counting and Docling OCR extras for image support. On the frontend, a shadcn-compatible tree view component (ggoggam/shadcn-treeview with @dnd-kit/react) provides the file manager UI. Database extensions ltree and pg_trgm (both built into Supabase) handle hierarchical path queries and regex search respectively.

The dominant risk is the RLS policy transition from single-user to mixed-visibility content. The current model is "users only see their own data" -- adding a shared default KB requires careful policy restructuring to avoid either hiding default content from users or leaking private data between users. Secondary risks include context window blowout from excessive tool use (the agent has 10+ tools and no token budget enforcement), storage/database desync for folder operations, and OCR quality on stylized board game imagery. All of these are preventable with the patterns identified in the architecture and pitfalls research.

## Key Findings

### Recommended Stack

The existing stack (FastAPI, React/Vite, Supabase, OpenAI SDK, Docling) covers most needs. New additions are minimal and targeted.

**Core additions:**
- **Docling OCR extras** (EasyOCR engine): Image ingestion for board game photos/cards -- already in the stack, just needs `pip install docling[ocr]` and pipeline configuration
- **tiktoken 0.12.0**: Exact token counting for context budget management -- critical for preventing context window blowout with 10+ tools
- **ltree + pg_trgm** (Postgres extensions): Materialized path hierarchy queries and trigram-indexed regex search -- both built into Supabase, zero external dependencies
- **ggoggam/shadcn-treeview**: File manager tree UI with drag-drop -- shadcn registry component matching the existing design system, uses @dnd-kit/react (pre-1.0, isolated risk)
- **openpyxl 3.1.5** (contingency only): XLSX fallback if Docling spreadsheet conversion is insufficient for complex score sheets

### Expected Features

**Must have (table stakes):**
- Default board game KB with 10 pre-seeded classics (Catan, Pandemic, Wingspan, etc.) -- empty KB on first login is a dealbreaker
- Folder hierarchy for document organization -- every file/document app has this
- File manager UI with tree navigation and upload-to-folder
- KB navigation tools: ls, tree, read (minimum viable tool set)
- Context-aware source selection (default KB vs private docs)
- Transparent tool calls in chat UI (extend existing Module 7 streaming)
- Smart chunking with token budget to prevent context window exhaustion

**Should have (differentiators):**
- KB tools: grep, glob -- completes the Claude Code-style tool set
- Explorer sub-agent for multi-step KB traversal -- genuine differentiator vs single-turn competitors
- Image OCR for photographed rule cards
- XLSX support for score sheets
- User-controllable search scope
- Cross-reference discovery across games

**Defer (v2+):**
- Folder summarization, game comparison/recommendations, advanced file manager features (drag-drop reorder, bulk operations, right-click menus)

### Architecture Approach

The architecture extends the existing tool-calling chat loop with new KB navigation tools that are thin Python wrappers over Supabase RPCs (Postgres functions). The database is the single source of truth for folder hierarchy -- not storage paths. A source router classifies each query to determine scope (default KB, private, both) before tool execution. The explorer sub-agent reuses the existing sub-agent pattern (tool-using while-loop with its own context) but scoped to KB tools only.

**Major components:**
1. **KB Navigation Service** (kb_service.py) -- implements ls, tree, grep, glob, read against Supabase tables via RPCs
2. **Source Router** (source_router.py) -- classifies queries to determine data source scope before tool dispatch
3. **Explorer Sub-Agent** (explorer_service.py) -- multi-step KB traversal in isolated context with token budget
4. **Folder Service** (folder_service.py) -- CRUD for folder hierarchy, used by both REST API and KB tools
5. **Seed Script** (seed_default_kb.py) -- idempotent population of 10 default board games through the existing ingestion pipeline

### Critical Pitfalls

1. **RLS policy collision between default KB and private docs** -- Add a visibility/source_type column, write policies as `(user_id = auth.uid()) OR (source_type = 'default')` for SELECT, restrict writes to owner only. Test exhaustively before building anything on top.
2. **Storage path and DB folder hierarchy desync** -- Make the database the source of truth. Agent tools query ONLY the database. Wrap move/rename operations in single backend endpoints with rollback on partial failure.
3. **Agent tool overuse blowing context window** -- Implement a token budget tracker (tiktoken), cap read output to 8K tokens with line-range support, limit to 5 tool iterations per turn, use the Memory Pointer Pattern for large results.
4. **Explorer sub-agent context isolation failure** -- Hard limit of 8-10 steps, max_output_tokens on final response (2K), pass focused task description not full conversation history, return structured results.
5. **Default KB seed script fragility** -- Make idempotent via content hash checks, use the existing ingestion pipeline, track progress, support re-running without duplicates.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Data Foundation and Schema
**Rationale:** Everything depends on the folder hierarchy and mixed-visibility data model. RLS must be restructured before any features are built on top. This is the highest-risk phase and must be solid.
**Delivers:** folders table with ltree/materialized paths, source_type columns on documents and chunks, RLS policies for mixed visibility, pg_trgm extension enabled, folder CRUD service
**Addresses:** Folder hierarchy (P1), foundation for all subsequent features
**Avoids:** RLS policy collision (Pitfall 1), Storage/DB desync (Pitfall 2)

### Phase 2: Default KB and Ingestion Extensions
**Rationale:** The default KB provides test data for all subsequent tool development and gives immediate user value. Image OCR and XLSX support extend the existing ingestion pipeline with minimal risk.
**Delivers:** Idempotent seed script for 10 board games, image OCR via Docling, XLSX ingestion with table-aware chunking, source_type tagging on all ingested content
**Addresses:** Default board game KB (P1), Image OCR (P2), XLSX support (P2)
**Avoids:** Seed script fragility (Pitfall 8), OCR garbage (Pitfall 5), XLSX structural context loss (Pitfall 6)

### Phase 3: KB Navigation Tools
**Rationale:** Tools are the core differentiator. They need the folder structure (Phase 1) and default KB data (Phase 2) to test against. Build ls, tree, read first (minimum viable), then grep and glob.
**Delivers:** 5 KB tools as Supabase RPCs with Python wrappers, token budget tracker, tool definitions in chat.py, source routing (heuristic v1)
**Addresses:** KB tools ls/tree/read (P1), grep/glob (P2), context-aware source selection (P1), smart chunking with token budget (P1)
**Avoids:** Agent tool overuse (Pitfall 3), Source selection confusion (Pitfall 9)

### Phase 4: File Manager UI
**Rationale:** Users need to see and organize their documents. Depends on folder CRUD (Phase 1) and benefits from having default KB visible (Phase 2). Build with pessimistic updates and Realtime sync.
**Delivers:** Tree sidebar with ggoggam/shadcn-treeview, file grid, folder create/rename/delete, upload to folder, visual distinction between default KB and private docs
**Addresses:** File manager UI (P1), transparent tool calls enhancement
**Avoids:** File manager state desync (Pitfall 7)

### Phase 5: Explorer Sub-Agent
**Rationale:** The most complex component. Requires stable KB tools (Phase 3) as its toolkit. Must be designed with strict budget constraints from the start.
**Delivers:** Multi-step KB traversal agent, token budget enforcement, structured output, streaming progress to frontend, explore_kb tool for parent agent
**Addresses:** Explorer sub-agent (P2), cross-reference discovery (P2), game comparison (P3)
**Avoids:** Explorer context isolation failure (Pitfall 4)

### Phase 6: Polish and Scope Controls
**Rationale:** Refinements that improve usability once core features work. Lower risk, standard patterns.
**Delivers:** User-controllable search scope UI, enhanced tool call display with human-friendly labels, observation masking for context efficiency, folder summarization
**Addresses:** User-controllable scope (P2), transparent tool calls polish, folder summarization (P3)

### Phase Ordering Rationale

- **Schema before features:** The folder table and RLS restructuring is a hard dependency for every subsequent phase. Getting this wrong creates cascading bugs across all features.
- **Default KB before tools:** KB tools need real data to test against. Building tools against an empty database leads to untested edge cases.
- **Tools before explorer:** The explorer is an agent that uses tools. Building the agent before the tools are stable means debugging two systems simultaneously.
- **File manager in parallel-ish with tools:** The file manager depends on Phase 1 (folders) but not on Phase 3 (tools). It could be built in parallel with Phase 3 if resources allow, but sequentially it makes sense after tools because the tools validate the data model.
- **Explorer last among core features:** It is the highest-complexity, highest-token-cost component. Every other piece should be stable before tackling it.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** RLS policy design needs careful testing -- the interaction between multiple OR-combined policies in Supabase is subtle. Research the exact policy evaluation semantics.
- **Phase 4:** The shadcn-treeview component is pre-1.0 (@dnd-kit/react 0.3.2). Validate it works with React 19 and the project shadcn setup before committing to the approach. Have a fallback plan using @dnd-kit/core (stable).
- **Phase 5:** Explorer sub-agent token budget management and the Memory Pointer Pattern need prototyping. No off-the-shelf solution exists.

Phases with standard patterns (skip research-phase):
- **Phase 2:** Document ingestion extensions (OCR, XLSX) follow Docling documented pipeline. Well-covered by official docs.
- **Phase 3:** KB tools are straightforward Supabase RPCs. The pattern (Python function calls Postgres function, formats result) is standard.
- **Phase 6:** UI polish is standard React development with no architectural risk.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Existing stack is proven. New additions (tiktoken, ltree, pg_trgm) are well-documented. Tree view component is pre-1.0 -- only area of uncertainty. |
| Features | MEDIUM-HIGH | Competitor analysis is solid, feature prioritization is clear. The Claude Code-style tools differentiator is genuinely novel in this space. |
| Architecture | HIGH | Builds directly on existing codebase patterns (tool loop, sub-agents, Supabase RPCs). No new architectural paradigms needed. |
| Pitfalls | HIGH | Pitfalls are specific, codebase-grounded, and have concrete prevention strategies. RLS and context window risks are well-understood. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **ltree vs materialized path text column:** STACK.md recommends ltree extension, ARCHITECTURE.md uses a plain text path column with B-tree index. The roadmapper should pick one approach. Recommendation: use ltree for the folders table (it is purpose-built for this), but keep a plain text folder_path on documents/chunks for fast prefix matching without joins.
- **Tree view component stability:** @dnd-kit/react 0.3.2 is pre-1.0. Build a spike/prototype early in Phase 4 to validate. If unstable, fall back to @dnd-kit/core (stable, 5.x) with a custom tree implementation.
- **OCR quality for board game content:** Docling OCR is optimized for standard documents, not stylized game cards. A vision-model pipeline (GPT-4o vision) may be needed as a premium fallback. Defer this decision until Phase 2 testing reveals actual OCR quality.
- **Explorer sub-agent token costs:** Each exploration is 3-8 LLM calls. No caching strategy has been designed yet. Phase 5 planning should include cost modeling and caching for common queries against the default KB.
- **Service role key usage:** The existing backend bypasses RLS via service_role_key for all DB calls. This should migrate to per-user JWT-scoped clients for KB tool operations to ensure RLS is actually exercised. Plan this migration as part of Phase 1.

## Sources

### Primary (HIGH confidence)
- [PostgreSQL ltree Documentation](https://www.postgresql.org/docs/current/ltree.html) -- hierarchical path queries
- [PostgreSQL pg_trgm Documentation](https://www.postgresql.org/docs/current/pgtrgm.html) -- trigram-indexed regex
- [Supabase Extensions](https://supabase.com/docs/guides/database/extensions) -- ltree and pg_trgm availability
- [Supabase RLS Documentation](https://supabase.com/docs/guides/database/postgres/row-level-security) -- policy evaluation semantics
- [Docling Supported Formats](https://docling-project.github.io/docling/usage/supported_formats/) -- image and XLSX support
- [Docling Pipeline Options](https://docling-project.github.io/docling/reference/pipeline_options/) -- OCR engine configuration
- [tiktoken on PyPI](https://pypi.org/project/tiktoken/) -- v0.12.0 token counting
- [Effective Context Engineering for AI Agents - Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### Secondary (MEDIUM confidence)
- [ggoggam/shadcn-treeview](https://github.com/ggoggam/shadcn-treeview) -- React 19 tree component (pre-1.0 dependency)
- [Docling XLSX Multi-sheet Issue 1292](https://github.com/docling-project/docling/issues/1292) -- XLSX aggregation behavior
- [Claude Code System Prompts (Piebald-AI)](https://github.com/Piebald-AI/claude-code-system-prompts) -- tool design patterns
- [RAG Chunking Strategies 2026 Benchmark](https://blog.premai.io/rag-chunking-strategies-the-2026-benchmark-guide/) -- chunking best practices
- [Agentic RAG Survey](https://arxiv.org/abs/2501.09136) -- transparency and tool-use patterns
- [Board Game App Companions Market Report](https://dataintelo.com/report/board-game-app-companions-market/amp) -- market context ($1.18B in 2024)

### Tertiary (LOW confidence)
- [Docling GitHub Issues: Image OCR Limitations](https://github.com/docling-project/docling/issues/2446) -- OCR quality concerns for non-standard layouts, needs validation with actual board game content
- [@dnd-kit/react on npm](https://www.npmjs.com/package/@dnd-kit/react) -- v0.3.2 pre-1.0, API stability uncertain

---
*Research completed: 2026-04-07*
*Ready for roadmap: yes*
