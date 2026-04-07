# Roadmap: Board Game Knowledge Base RAG

## Overview

This roadmap transforms the existing agentic RAG application (8 modules complete) into a board game knowledge base with Claude Code-inspired navigation tools. The work progresses from data foundation (folder hierarchy, RLS restructuring) through default KB seeding and ingestion extensions, KB navigation tools, file manager UI, explorer sub-agent, and finally agent intelligence polish. Each phase delivers a coherent, testable capability that builds on the previous.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Foundation and Schema** - Folder hierarchy, mixed-visibility RLS, and schema extensions for the entire knowledge base
- [ ] **Phase 2: Default KB and Ingestion Extensions** - Pre-seeded board game library plus image OCR and XLSX support
- [ ] **Phase 3: KB Navigation Tools** - Agent tools (ls, tree, read, grep, glob) that query the knowledge base through Supabase
- [ ] **Phase 4: File Manager UI** - Tree sidebar, folder operations, drag-drop, and file management in the ingestion interface
- [ ] **Phase 5: Explorer Sub-Agent** - Multi-step KB traversal agent for deep searches, cross-references, and recommendations
- [ ] **Phase 6: Agent Intelligence and Polish** - Token budget management, source routing, scope controls, and sub-agent consistency

## Phase Details

### Phase 1: Data Foundation and Schema
**Goal**: The database supports hierarchical folder organization with mixed-visibility content (shared default KB + private user docs)
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-03, DATA-05, DATA-06, DATA-07
**Success Criteria** (what must be TRUE):
  1. User can create folders and subfolders that persist in the database with materialized paths
  2. Default KB content is readable by all authenticated users without granting access to other users' private documents
  3. A user's uploaded documents are invisible to every other user
  4. RLS policies correctly enforce mixed visibility: shared reads for default content, owner-only for private content
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md -- ltree extension, system user, and folders table with RLS
- [ ] 01-02-PLAN.md -- Visibility columns, RLS policy replacement, and search RPC updates

### Phase 2: Default KB and Ingestion Extensions
**Goal**: Users have immediate value from 10 pre-seeded board games, and can upload images and spreadsheets alongside existing formats
**Depends on**: Phase 1
**Requirements**: DATA-04, DATA-08, DATA-09, DATA-10
**Success Criteria** (what must be TRUE):
  1. On first login, user can browse and query 10 popular board games without uploading anything
  2. User can upload a JPG/PNG image of a rule card and the system extracts searchable text via OCR
  3. User can upload an XLSX file and the system parses it into searchable markdown content
  4. Uploaded files land in the user's selected folder in Supabase Storage with correct folder association
**Plans**: TBD

Plans:
- [ ] 02-01: TBD
- [ ] 02-02: TBD
- [ ] 02-03: TBD

### Phase 3: KB Navigation Tools
**Goal**: The agent can navigate and search the knowledge base using specialized tools that query Supabase, with transparent display in the chat UI
**Depends on**: Phase 1, Phase 2 (needs default KB data for testing)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08
**Success Criteria** (what must be TRUE):
  1. User can ask the agent to list files in a folder and see accurate ls results in the chat
  2. User can ask the agent to show the KB structure and see a hierarchical tree view
  3. User can ask the agent to find specific content and see grep/glob results with matched files
  4. User can ask the agent to read a document and see the content (full or line-range)
  5. Every tool call is displayed transparently in the chat UI with tool name, arguments, and collapsible output
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD
- [ ] 03-03: TBD

### Phase 4: File Manager UI
**Goal**: Users can visually organize their documents and the default KB in a file manager-style interface with full folder operations
**Depends on**: Phase 1 (folder CRUD), Phase 2 (default KB for display)
**Requirements**: DATA-02, FMGR-01, FMGR-02, FMGR-03, FMGR-04, FMGR-05, FMGR-06, FMGR-07, FMGR-08, FMGR-09, FMGR-10
**Success Criteria** (what must be TRUE):
  1. User sees a tree sidebar showing folder hierarchy with their documents and the default KB
  2. User can create, rename, and delete folders and files through the UI
  3. User can drag and drop files/folders to reorganize them
  4. User can right-click for context menus and select multiple files for bulk operations
  5. Default KB folders are visually distinct (read-only styling) from the user's own folders
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD
- [ ] 04-03: TBD
- [ ] 04-04: TBD

### Phase 5: Explorer Sub-Agent
**Goal**: Complex multi-step KB searches are handled by a dedicated explorer agent that traverses, summarizes, cross-references, and recommends
**Depends on**: Phase 3 (needs stable KB tools as its toolkit)
**Requirements**: EXPL-01, EXPL-02, EXPL-03, EXPL-04, EXPL-05, EXPL-06
**Success Criteria** (what must be TRUE):
  1. User can ask a complex question requiring multiple KB lookups and the explorer agent handles it autonomously
  2. User can request a folder summary and receive a coherent synthesis of its contents
  3. User can ask "what games are similar to X" and get cross-reference discoveries with reasoning
  4. Explorer progress is streamed to the frontend so the user sees what it is doing in real time
  5. Explorer output stays within budget limits and does not overwhelm the parent agent's context
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD
- [ ] 05-03: TBD

### Phase 6: Agent Intelligence and Polish
**Goal**: The agent intelligently manages its context budget, routes queries to the right sources, and users can control search scope
**Depends on**: Phase 3, Phase 5
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05
**Success Criteria** (what must be TRUE):
  1. Agent automatically selects default KB, private docs, or both based on what the user is asking about
  2. Agent stays within token budget even when many tool results are returned (no context window exhaustion)
  3. User can narrow search scope to specific folders or games via a chat command and see scoped results
  4. Existing sub-agent (from Module 8) works consistently with the new explorer agent and KB tool set
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Foundation and Schema | 0/2 | Not started | - |
| 2. Default KB and Ingestion Extensions | 0/3 | Not started | - |
| 3. KB Navigation Tools | 0/3 | Not started | - |
| 4. File Manager UI | 0/4 | Not started | - |
| 5. Explorer Sub-Agent | 0/3 | Not started | - |
| 6. Agent Intelligence and Polish | 0/3 | Not started | - |
