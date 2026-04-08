# Requirements: Board Game Knowledge Base RAG

**Defined:** 2026-04-07
**Core Value:** The agent can intelligently search and reason across a structured board game knowledge base — finding rules, comparing mechanics, and recommending games — using the right tool for the job, transparently.

## v1 Requirements

### Data Foundation

- [x] **DATA-01**: User can create folders and subfolders to organize their documents
- [ ] **DATA-02**: User can see a hierarchical folder structure in the ingestion interface
- [x] **DATA-03**: System stores folder hierarchy in Supabase with materialized paths for efficient tree queries
- [ ] **DATA-04**: Default board game KB ships with 10 pre-seeded popular games organized in folders
- [x] **DATA-05**: All authenticated users can read the default KB content (shared visibility)
- [x] **DATA-06**: User's uploaded documents remain private (only visible to that user)
- [x] **DATA-07**: RLS policies enforce mixed visibility (default KB readable by all, private docs per-user)
- [ ] **DATA-08**: User can upload images (JPG, PNG) which are processed with OCR to extract text
- [ ] **DATA-09**: User can upload XLSX files which are parsed into searchable markdown content
- [ ] **DATA-10**: Uploaded files are placed into the user's selected folder in Supabase Storage

### KB Navigation Tools

- [ ] **TOOL-01**: Agent can list files and subfolders in a specific folder (ls tool)
- [ ] **TOOL-02**: Agent can view the full hierarchical tree structure of the KB (tree tool)
- [ ] **TOOL-03**: Agent can read a full document or specific line range from document chunks (read tool)
- [ ] **TOOL-04**: Agent can search document content using regex patterns (grep tool)
- [ ] **TOOL-05**: Agent can find files matching glob patterns across the KB (glob tool)
- [ ] **TOOL-06**: All KB tools query Supabase tables (not filesystem) and respect RLS visibility
- [ ] **TOOL-07**: Agent tool calls are displayed transparently in the chat UI with tool-specific icons and labels
- [ ] **TOOL-08**: Tool results show arguments used and brief output summaries in collapsible sections

### Agent Intelligence

- [ ] **AGNT-01**: Agent automatically selects appropriate sources (default KB, private docs, or both) based on query intent
- [ ] **AGNT-02**: Agent manages a token budget when assembling context, preventing context window exhaustion
- [ ] **AGNT-03**: Token budget tracks usage across system prompt, chat history, tool results, and reserves space for response
- [ ] **AGNT-04**: User can manually narrow search scope to specific folders or games via the chat interface
- [ ] **AGNT-05**: Agent uses the existing sub-agent pattern to update for consistency with new tool set

### Explorer Sub-Agent

- [ ] **EXPL-01**: Explorer sub-agent can perform multi-step KB traversal using all navigation tools (ls, tree, read, grep, glob)
- [ ] **EXPL-02**: Explorer sub-agent can generate summaries of folder contents on request
- [ ] **EXPL-03**: Explorer sub-agent can discover cross-references between games (e.g., games with similar mechanics)
- [ ] **EXPL-04**: Explorer sub-agent can recommend related games based on the current conversation context
- [ ] **EXPL-05**: Explorer sub-agent has output budget limits to prevent returning excessive content to the parent agent
- [ ] **EXPL-06**: Explorer sub-agent progress is streamed to the frontend via SSE events

### File Manager UI

- [ ] **FMGR-01**: Ingestion interface displays a tree sidebar showing folder hierarchy
- [ ] **FMGR-02**: User can create new folders and subfolders via the UI
- [ ] **FMGR-03**: User can rename folders and files
- [ ] **FMGR-04**: User can delete folders (with confirmation) and files
- [ ] **FMGR-05**: User can drag and drop files and folders to move/reorder them
- [ ] **FMGR-06**: Right-click context menus provide folder/file operations (rename, delete, move, new subfolder)
- [ ] **FMGR-07**: User can select multiple files for bulk move or delete operations
- [ ] **FMGR-08**: Default KB folders are visually distinct (read-only indicator, different styling)
- [ ] **FMGR-09**: User can upload files by dropping them into a specific folder in the tree
- [ ] **FMGR-10**: Breadcrumb navigation shows current folder path

## v2 Requirements

### Explorer Capabilities

- **EXPL-07**: Explorer sub-agent can perform side-by-side comparison of rules/mechanics across games
- **EXPL-08**: Explorer sub-agent can build game profiles from ingested content for quick reference

### Advanced File Management

- **FMGR-11**: User can search/filter within the file tree
- **FMGR-12**: User can view file previews (first page/section) without opening

### Advanced Ingestion

- **INGS-01**: System detects and handles multi-sheet XLSX files as separate documents
- **INGS-02**: OCR quality gate warns user when extracted text confidence is low

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automated web scraping of rulebooks | Copyright issues, fragile, violates manual-upload-only constraint |
| Real-time collaborative KB editing | Massive complexity (CRDT), not core value prop |
| Game state tracking / scoring | Different product entirely — this is a knowledge base |
| Natural language folder creation | AI-driven organization is unreliable; users want control |
| Chat-based file management (delete via chat) | Destructive ops via NL are dangerous; use explicit UI |
| Admin UI for default KB management | Seed script is sufficient for 10 games |
| Mobile app / PWA | Web-first, defer to later |
| LangChain / LangGraph | Project constraint — raw SDK calls only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 4 | Pending |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 2 | Pending |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 1 | Complete |
| DATA-07 | Phase 1 | Complete |
| DATA-08 | Phase 2 | Pending |
| DATA-09 | Phase 2 | Pending |
| DATA-10 | Phase 2 | Pending |
| TOOL-01 | Phase 3 | Pending |
| TOOL-02 | Phase 3 | Pending |
| TOOL-03 | Phase 3 | Pending |
| TOOL-04 | Phase 3 | Pending |
| TOOL-05 | Phase 3 | Pending |
| TOOL-06 | Phase 3 | Pending |
| TOOL-07 | Phase 3 | Pending |
| TOOL-08 | Phase 3 | Pending |
| AGNT-01 | Phase 6 | Pending |
| AGNT-02 | Phase 6 | Pending |
| AGNT-03 | Phase 6 | Pending |
| AGNT-04 | Phase 6 | Pending |
| AGNT-05 | Phase 6 | Pending |
| EXPL-01 | Phase 5 | Pending |
| EXPL-02 | Phase 5 | Pending |
| EXPL-03 | Phase 5 | Pending |
| EXPL-04 | Phase 5 | Pending |
| EXPL-05 | Phase 5 | Pending |
| EXPL-06 | Phase 5 | Pending |
| FMGR-01 | Phase 4 | Pending |
| FMGR-02 | Phase 4 | Pending |
| FMGR-03 | Phase 4 | Pending |
| FMGR-04 | Phase 4 | Pending |
| FMGR-05 | Phase 4 | Pending |
| FMGR-06 | Phase 4 | Pending |
| FMGR-07 | Phase 4 | Pending |
| FMGR-08 | Phase 4 | Pending |
| FMGR-09 | Phase 4 | Pending |
| FMGR-10 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after roadmap creation*
