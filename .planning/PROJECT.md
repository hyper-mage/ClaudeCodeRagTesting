# Board Game Knowledge Base RAG

## What This Is

An agentic RAG application specialized for board games. It combines a pre-seeded default knowledge base of popular board games with user-uploaded private collections, providing intelligent chat that can search, compare, and recommend across the entire library. The agent uses Claude Code-inspired tooling (ls, tree, grep, glob, read) with transparent tool calls to navigate a hierarchical folder-based knowledge base stored in Supabase.

## Core Value

The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.

## Requirements

### Validated

- ✓ User authentication with email/password via Supabase Auth — Module 1
- ✓ Chat with SSE streaming and stateless completions — Modules 1-2
- ✓ Thread management (create, list, switch) — Module 1
- ✓ Document upload with processing pipeline — Module 2
- ✓ Vector search (pgvector embeddings) — Module 2
- ✓ Realtime ingestion status updates via Supabase Realtime — Module 2
- ✓ Content-addressed deduplication and incremental updates — Module 3
- ✓ LLM-powered metadata extraction on ingestion — Module 4
- ✓ Multi-format document support via Docling (PDF, DOCX, HTML, MD, TXT) — Module 5
- ✓ Hybrid search with RRF fusion (vector + keyword) — Module 6
- ✓ LLM and API reranking — Module 6
- ✓ Text-to-SQL for document metadata queries — Module 7
- ✓ Web search via Tavily — Module 7
- ✓ Tool event streaming with frontend indicators — Module 7
- ✓ Sub-agent for full-document analysis — Module 8
- ✓ Markdown rendering with attribution in chat — Module 7
- ✓ RLS on all tables (users only see their own data) — Module 2
- ✓ LangSmith observability — Module 1
- ✓ Default board game knowledge base (10 popular games, pre-seeded) — Validated in Phase 2
- ✓ Image ingestion with OCR (game board photos, rule cards) — Validated in Phase 2
- ✓ XLSX ingestion support (score sheets, game trackers) — Validated in Phase 2
- ✓ Mixed-visibility RLS (public default KB + private user docs) — Validated in Phase 1
- ✓ Explorer sub-agent for deep KB traversal and analysis — Validated in Phase 5
- ✓ Explorer sub-agent: folder summarization — Validated in Phase 5
- ✓ Explorer sub-agent: cross-reference discovery (games with similar mechanics) — Validated in Phase 5
- ✓ Explorer sub-agent: game recommendations based on context — Validated in Phase 5
- ✓ Explorer sub-agent: streaming progress in chat UI — Validated in Phase 5
- ✓ Explorer budget enforcement (iterations, tool calls, summary chars) — Validated in Phase 5
- ✓ Context-aware source selection (agent decides default KB vs private docs vs both) — Validated in Phase 6
- ✓ Smart chunking with automatic token budget management — Validated in Phase 6
- ✓ User-controllable search scope (narrow to specific folders/games) — Validated in Phase 6
- ✓ Update existing sub-agent system for consistency with new explorer agent — Validated in Phase 6

### Active

- [x] Context-aware source selection (agent decides default KB vs private docs vs both) — Validated in Phase 6
- [x] File manager-style folder/subfolder UI for organizing documents — Validated in Phase 4
- [x] Hierarchical folder structure in Supabase storage and DB — Validated in Phase 1 (schema) + Phase 4 (UI)
- [ ] KB navigation tools: ls (list files in folder)
- [ ] KB navigation tools: tree (hierarchical structure view)
- [ ] KB navigation tools: grep (regex content search across chunks)
- [ ] KB navigation tools: glob (file pattern matching)
- [ ] KB navigation tools: read (full file or line-range extraction)
- [ ] KB structure tool: extract tree structure for agent orientation
- [ ] Transparent tool calls in chat UI (show what agent is doing, like Claude Code)
- [x] Smart chunking with automatic token budget management — Validated in Phase 6
- [x] User-controllable search scope (narrow to specific folders/games) — Validated in Phase 6
- [x] Update existing sub-agent system for consistency with new explorer agent — Validated in Phase 6

### Out of Scope

- Automated ingestion pipelines or connectors — manual upload only (project constraint)
- LangChain/LangGraph — raw SDK calls only (project constraint)
- Admin UI for managing default KB — seed script or pre-deploy only
- Social features (sharing collections, public reviews) — not part of this milestone
- Mobile app — web-only for now
- Game state tracking or scoring — this is a knowledge base, not a game manager

## Context

**Existing Codebase:** 8 modules complete. Full agentic RAG pipeline operational with tool-use loop, hybrid search, sub-agents, and multi-format ingestion. Built with React+Vite frontend, Python FastAPI backend, Supabase for everything (DB, auth, storage, realtime).

**Board Game Focus:** The app is pivoting from a generic RAG tool to a board game knowledge base. The default KB provides immediate value (users can ask about popular games without uploading anything), while private uploads let enthusiasts add their own collection.

**Claude Code Inspiration:** The agent tooling mirrors Claude Code's approach — multiple specialized tools (ls, tree, grep, glob, read) that the agent selects based on the task. Tool calls are shown transparently in the UI. An explorer sub-agent handles complex multi-step searches.

**Context Window Concern:** Board game manuals can be lengthy. Smart chunking and user-controllable scope are essential to prevent the KB from consuming the entire context window. The agent must be efficient about what it pulls in.

**Storage Architecture:** All documents live in Supabase (Storage buckets for originals, `document_chunks` table for processed text). Folder hierarchy must be represented in both storage paths and DB records. Tools query the DB, not the filesystem.

## Constraints

- **Tech Stack**: React+Vite+Tailwind frontend, Python+FastAPI backend, Supabase — established, no changes
- **No LangChain**: Raw OpenAI SDK calls only — project rule
- **Supabase-Only Storage**: All KB tools must work against Supabase tables/storage, not local filesystem
- **Docling Required**: PDF/DOCX/XLSX extraction must go through Docling to produce searchable markdown
- **RLS Enforced**: Default KB visible to all users, private uploads scoped by user_id
- **Context Budget**: Agent must manage context window carefully — smart chunking + scope controls

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Pre-seed 10 default board games on deploy | Quick to seed, covers top classics, gives immediate value without user uploads | — Pending |
| Context-aware source selection (agent decides) | More natural than manual toggles — agent picks sources based on query intent | ✓ Phase 6 |
| File manager-style folder UI | Full drag-drop, tree sidebar, right-click menus — richest interaction model for organizing many files | — Pending |
| Transparent tool calls (like Claude Code) | Users see what the agent is doing — builds trust and understanding | — Pending |
| All KB tools query Supabase (not filesystem) | Documents already stored in Supabase — tools should use the same data layer | — Pending |
| Explorer sub-agent for deep traversal | Complex multi-step KB searches need isolated context — mirrors Claude Code's explorer agent pattern | ✓ Phase 5 |
| Smart chunking + user scope controls | Both needed — automatic budget management plus manual override for power users | ✓ Phase 6 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-22 after Phase 6 completion*
