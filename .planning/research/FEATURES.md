# Feature Research

**Domain:** Board Game Knowledge Base with Claude Code-style Agent Tooling
**Researched:** 2026-04-07
**Confidence:** MEDIUM-HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Default board game KB (10 games pre-seeded) | Ludomentor, Boardside, Rulepop all ship with game content ready to query. Empty KB on first login = "why would I use this?" | MEDIUM | Requires seed script, folder structure in Supabase Storage + DB, and RLS allowing all users to read default KB. 10 games is the right number: enough variety without bloating storage. Pick classics with freely-available rulebooks (Catan, Ticket to Ride, Pandemic, Codenames, Azul, 7 Wonders, Wingspan, Splendor, Carcassonne, Dominion). |
| Folder hierarchy for documents | Every file manager and document app uses folders. Users with 20+ game rulebooks need organization. Rulepop organizes by game with linked sub-rules. | MEDIUM | Needs `folders` table with parent_id self-reference, path field for Supabase Storage mapping, and document FK. Must handle default KB folders (read-only) vs user folders (read-write). |
| File manager UI | Users expect drag-drop, breadcrumb navigation, create/rename/delete folders. This is a solved UX pattern -- anything less feels broken. | HIGH | Most complex frontend feature. Tree sidebar + main content area + context menus. Libraries like react-arborist or dnd-kit for tree/drag-drop. Must distinguish default KB (read-only, visually distinct) from user uploads. |
| Transparent tool calls in chat | Claude Code, ChatGPT, Perplexity all show "Searching...", "Reading file..." indicators. Users expect to see what the agent is doing, not just wait for a response. Already partially built (Module 7 tool event streaming). | LOW | Extend existing tool event streaming. Add tool-specific icons and labels (magnifying glass for grep, folder for ls, tree icon for tree). Show tool arguments and brief results. |
| Context-aware source selection | When a user asks "How does Catan trading work?", the agent should search the default KB. When they ask "What's in my uploaded files?", it should search private docs. Forcing manual scope selection is friction. | MEDIUM | Agent decides based on query intent using system prompt instructions. Needs a `list_sources` or `describe_kb` tool so the agent knows what's available. Fall back to searching both when ambiguous. |
| Image OCR for game content | Board game enthusiasts photograph rule cards, reference sheets, and game boards. Ludomentor supports built-in PDF viewing. Not supporting images means users must manually transcribe. | MEDIUM | Docling supports image extraction from PDFs already. For standalone images (PNG/JPG), use Tesseract via pytesseract or a vision model API. Store extracted text as chunks like any other document. |
| XLSX ingestion | Score sheets, game trackers, comparison spreadsheets are common in the board game community. Already have multi-format support; XLSX is a gap. | LOW | Docling handles XLSX. Add MIME type to allowed uploads, ensure parsing_service routes to Docling correctly. Table data should be converted to markdown tables for chunking. |
| Smart chunking with token budget | Board game manuals are 20-50 pages. Without budget management, a single query can consume the entire context window. Research shows quality degrades past ~2,500 assembled context tokens, with 8K as practical ceiling. | MEDIUM | Track token count per chunk. When assembling context for the LLM, enforce a budget (e.g., 6-8K tokens). Prioritize by relevance score. Existing retrieval_service needs a token accumulator that stops adding chunks when budget is hit. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| KB navigation tools (ls, tree, grep, glob, read) | No board game app or RAG product gives the agent filesystem-like tools to navigate a knowledge base. This is the core differentiator -- the agent can explore structure, not just do vector search. Mirrors Claude Code's approach where the right tool is picked for the task. | HIGH | 5 distinct tools, each querying Supabase. `ls`: list folder contents (query folders + documents table). `tree`: recursive folder structure (recursive CTE or app-side recursion). `grep`: regex search across chunk content (pg `~` operator or app-side). `glob`: pattern match on file paths/names. `read`: fetch full document or line range from chunks. Each needs tool schema for the LLM and backend endpoint. |
| Explorer sub-agent | Dedicated agent for deep multi-step KB traversal. Can summarize folders, discover cross-references between games (e.g., "games with worker placement"), and do side-by-side comparisons. Runs in its own context, keeping the main chat clean. | HIGH | Build on existing subagent_service. Explorer gets read-only tools (ls, tree, grep, glob, read). Needs its own system prompt optimized for exploration. Must return structured results to parent agent. Key differentiator over Ludomentor/Boardside which are single-turn Q&A. |
| Cross-reference discovery | "Find all games with deck-building mechanics" or "Which games support 2 players?" -- queries that span the entire KB. No competitor does this well because they lack structured metadata + full-text search combined. | MEDIUM | Leverages existing text-to-SQL (Module 7) for metadata queries + grep/vector search for content queries. Explorer sub-agent orchestrates multi-step searches. Depends on good metadata extraction during ingestion. |
| User-controllable search scope | Power users want to narrow searches: "Search only in Catan folder" or "Only my uploaded games". Manual override for when the agent's automatic selection isn't what you want. | LOW | Add optional `scope` parameter to search tools. UI: folder picker or dropdown in chat input. Backend: filter queries by folder_id or source (default/user). |
| Game comparison and recommendations | "Compare Catan vs Ticket to Ride for beginners" or "Recommend a game like Wingspan for 4 players". Goes beyond rules lookup into reasoning across the KB. | MEDIUM | Mostly prompt engineering + explorer sub-agent. Agent retrieves relevant chunks from multiple games, then reasons. No special infrastructure needed beyond the tools and sub-agent. |
| Folder summarization | "What's in the Strategy Games folder?" -- agent reads folder contents and generates a summary. Useful for orientation in large KBs. | LOW | Explorer sub-agent uses `ls` + `read` on key files, then summarizes. Primarily a prompt/tool-use pattern, not new infrastructure. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automated web scraping of board game rules | "Just pull rules from BGG/publisher sites automatically" | Copyright issues, scraping fragility, inconsistent formatting, violates project constraint (manual upload only). Ludomentor and Boardside only use licensed/official content. | Pre-seed a curated default KB with freely-available rulebooks. Let users upload their own purchased PDFs. |
| Real-time collaborative KB editing | "Multiple users editing the same KB" | Massive complexity (OT/CRDT), not the core value prop, turns a knowledge base into Google Docs. | Single-user KB with read-only default content. Share via export if needed later. |
| Game state tracking / scoring | "Track my Catan game score while playing" | Completely different product (game manager vs knowledge base). Each game has unique scoring rules. Enormous surface area. | Stay focused on knowledge retrieval. Link out to dedicated scoring apps if asked. |
| Natural language folder creation | "Organize my games by player count automatically" | AI-driven organization is unreliable and surprising. Users want control over their folder structure. | Let users create folders manually. Agent can suggest organization but not execute it autonomously. |
| Full-text indexing of every chunk for grep | "Make grep search the raw text of every chunk in real-time" | Postgres full-text search on large chunk tables is slow without proper indexing. Regex across millions of rows is expensive. | Use existing hybrid search (vector + keyword) for most queries. Reserve grep for targeted folder-scoped searches with LIMIT. Add GIN/GiST indexes. |
| Admin UI for managing default KB | Seems necessary for maintaining game content | Adds an entire RBAC layer, admin routes, admin frontend. Seed script is sufficient for a pre-defined set of 10 games. | Use a seed script (Python or SQL) that runs on deploy. Update by modifying seed data and re-running. |
| Chat-based file management | "Delete my Catan folder" via chat | Destructive operations via natural language are dangerous. Misinterpretation = data loss. | File management only through the file manager UI with explicit confirmation dialogs. Agent is read-only for KB structure. |

## Feature Dependencies

```
[Folder hierarchy (DB + Storage)]
    +--requires--> [File manager UI]
    +--requires--> [KB navigation tools (ls, tree, glob)]
    +--requires--> [Default board game KB seeding]
    +--requires--> [User-controllable search scope]

[KB navigation tools (ls, tree, grep, glob, read)]
    +--requires--> [Explorer sub-agent]
    +--requires--> [Context-aware source selection]

[Default board game KB]
    +--requires--> [Context-aware source selection]
    +--requires--> [Cross-reference discovery]

[Smart chunking / token budget]
    +--enhances--> [KB navigation tools (read)]
    +--enhances--> [Explorer sub-agent]

[Image OCR]
    +--independent-- (extends existing ingestion pipeline)

[XLSX support]
    +--independent-- (extends existing ingestion pipeline)

[Transparent tool calls]
    +--enhances--> [KB navigation tools]
    +--enhances--> [Explorer sub-agent]
    (extends existing Module 7 tool event streaming)

[Explorer sub-agent]
    +--requires--> [KB navigation tools]
    +--enhances--> [Cross-reference discovery]
    +--enhances--> [Game comparison / recommendations]
    +--enhances--> [Folder summarization]
```

### Dependency Notes

- **Folder hierarchy is the foundation:** Almost everything depends on folders existing in the DB. This must be built first. Without it, ls/tree/glob have nothing to navigate, the file manager has nothing to display, and the default KB has nowhere to live.
- **KB tools before explorer sub-agent:** The explorer agent needs tools to work with. Build the 5 tools first, then wire them into a sub-agent.
- **Default KB seeding depends on folder hierarchy:** The seed script needs the folder structure to exist so it can place games in the right folders.
- **Image OCR and XLSX are independent:** These extend the existing ingestion pipeline and can be built in parallel with other work. No dependencies on new features.
- **Transparent tool calls extend existing infrastructure:** Module 7 already streams tool events. New tools just need to emit the same event format.
- **Smart chunking enhances but doesn't block:** The system works without it (just less efficiently). Can be added as an optimization pass.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what's needed to validate the "board game KB with agent tools" concept.

- [ ] Folder hierarchy in DB and Supabase Storage -- foundation for everything
- [ ] Default board game KB (10 games seeded) -- immediate value without uploads
- [ ] KB navigation tools: ls, tree, read -- minimum tool set for structured navigation
- [ ] Context-aware source selection -- agent picks default KB vs user docs
- [ ] Transparent tool calls in chat UI -- users see what the agent does
- [ ] Smart chunking with token budget -- prevents context window blowout on long manuals
- [ ] File manager UI (basic: tree view, breadcrumbs, upload to folder) -- users need to see and organize their docs

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] KB tools: grep, glob -- complete the tool set after ls/tree/read prove the pattern
- [ ] Explorer sub-agent -- once tools are stable, add the deep-traversal agent
- [ ] Image OCR -- when users request it (photos of rule cards)
- [ ] XLSX support -- when users request it (score sheets)
- [ ] User-controllable search scope -- once the KB grows large enough to need it
- [ ] Cross-reference discovery -- once explorer sub-agent is working

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Folder summarization -- nice-to-have, not core
- [ ] Game comparison/recommendations -- impressive but requires solid KB + tools first
- [ ] Advanced file manager (drag-drop reorder, bulk operations, right-click menus) -- polish after basics work
- [ ] Side-by-side rule comparison view in UI -- specialized UI component, low priority

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Folder hierarchy (DB/Storage) | HIGH | MEDIUM | P1 |
| Default board game KB (10 games) | HIGH | MEDIUM | P1 |
| KB tools: ls, tree, read | HIGH | MEDIUM | P1 |
| Context-aware source selection | HIGH | MEDIUM | P1 |
| Transparent tool calls | HIGH | LOW | P1 |
| Smart chunking / token budget | HIGH | MEDIUM | P1 |
| File manager UI (basic) | HIGH | HIGH | P1 |
| KB tools: grep, glob | MEDIUM | MEDIUM | P2 |
| Explorer sub-agent | HIGH | HIGH | P2 |
| Image OCR | MEDIUM | MEDIUM | P2 |
| XLSX support | LOW | LOW | P2 |
| User-controllable scope | MEDIUM | LOW | P2 |
| Cross-reference discovery | MEDIUM | MEDIUM | P2 |
| Folder summarization | LOW | LOW | P3 |
| Game comparison/recommendations | MEDIUM | MEDIUM | P3 |
| Advanced file manager features | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch -- validates the core concept
- P2: Should have, add when core is stable
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Ludomentor | Rulepop | Boardside (BGG) | Our Approach |
|---------|------------|---------|------------------|--------------|
| Pre-loaded game rules | Yes (curated library) | Yes (publisher partnerships) | Yes (official rulebooks only) | Yes (10 pre-seeded classics) |
| AI Q&A about rules | Yes (core feature) | No (static reference) | Yes (AI chatbot) | Yes, plus multi-step reasoning via tools |
| Cross-game queries | No (single-game context) | No (single-game reference) | No (single-game chatbot) | Yes -- grep/vector search across entire KB |
| User uploads | No | No | No | Yes -- private document uploads with folders |
| Folder organization | N/A (flat game list) | N/A (per-game site) | N/A (per-game thread) | Yes -- hierarchical folders in file manager |
| Image/OCR support | No (text-only) | No (digital rules only) | No | Yes -- OCR for photographed rule cards |
| Transparent agent actions | No (black box) | N/A (not AI) | No (black box) | Yes -- Claude Code-style tool visibility |
| Offline support | Yes (PWA) | Yes (PWA) | No | No (web app, not PWA -- out of scope) |
| Multi-step exploration | No (single-turn) | No (static) | No (single-turn) | Yes -- explorer sub-agent with tool loop |

**Key competitive insight:** Existing board game rule apps are either static references (Rulepop) or single-turn AI Q&A (Ludomentor, Boardside). None offer multi-step agent exploration, cross-game queries, user uploads, or transparent tool use. The combination of structured KB navigation tools + explorer sub-agent + user uploads is genuinely novel in this space.

## Sources

- [Ludomentor - Board Game AI](https://play.google.com/store/apps/details?id=com.awakenrealms.ludomentor) - Competitor: AI rules Q&A app
- [Rulepop](https://rulepop.com/) - Competitor: Digital rulebook platform with linked rules
- [Boardside AI on BGG](https://boardgamegeek.com/thread/3631492/boardside-ai-app-for-board-game-rules) - Competitor: AI chatbot for board game rules
- [Claude Code Tools Reference](https://www.vtrivedy.com/posts/claudecode-tools-reference) - Tool design patterns
- [Claude Code System Prompts (Piebald-AI)](https://github.com/Piebald-AI/claude-code-system-prompts) - Explore agent architecture
- [Claude Code Sub-agents Docs](https://code.claude.com/docs/en/sub-agents) - Sub-agent patterns
- [RAG Chunking Strategies 2026 Benchmark](https://blog.premai.io/rag-chunking-strategies-the-2026-benchmark-guide/) - Chunking best practices
- [Context Window Chunk Strategy Guide 2026](https://markaicode.com/rag-context-window-chunk-strategy/) - Token budget management
- [Board Game App Companions Market Report](https://dataintelo.com/report/board-game-app-companions-market/amp) - Market size ($1.18B in 2024)
- [Agentic RAG Survey](https://arxiv.org/abs/2501.09136) - Transparency and tool-use patterns

---
*Feature research for: Board Game Knowledge Base with Claude Code-style Agent Tooling*
*Researched: 2026-04-07*
