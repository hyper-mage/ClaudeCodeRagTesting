# Stack Research

**Domain:** Board game knowledge base with agent tooling (additions to existing RAG app)
**Researched:** 2026-04-07
**Confidence:** MEDIUM-HIGH

## Existing Stack (Already In Place - Not Re-Researched)

| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.115.12 | Backend API |
| React | 19.2.4 | Frontend |
| Vite | 6.4.1 | Build tool |
| Tailwind CSS | 4.2.2 | Styling |
| Supabase JS | 2.99.3 | Client SDK |
| Docling | (unpinned) | Document conversion (PDF, DOCX, HTML, MD, TXT) |
| OpenAI SDK | 1.74.0 | LLM calls |
| pgvector | (Supabase) | Vector search |

## Recommended Additions

### Image OCR (Backend - Python)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docling (existing) | latest | Image ingestion (PNG, JPEG, TIFF, BMP, WEBP) | Already in the stack. Docling natively supports image formats with OCR. No new library needed -- just configure the OCR pipeline options. **Confidence: HIGH** |
| EasyOCR (via Docling) | (bundled) | OCR engine for image text extraction | Docling auto-selects EasyOCR when GPU is available, Tesseract otherwise. EasyOCR has better accuracy for varied fonts and game card text. Install via `pip install docling[ocr]` or ensure EasyOCR is available. **Confidence: HIGH** |

**Key insight:** Docling already handles images (PNG, JPEG, TIFF, BMP, WEBP) as input formats. The project constraint says "Docling Required" so image OCR goes through Docling's pipeline, not a separate library. Configure via `PipelineOptions` with `do_ocr=True` and `force_full_page_ocr=True` for game card images.

**OCR engine recommendation:** Use EasyOCR (Docling's default with GPU) for board game cards/boards. Game components have varied fonts, stylized text, and mixed layouts that benefit from EasyOCR's neural network approach over Tesseract's traditional OCR. If running CPU-only, Tesseract is the automatic fallback and still adequate.

### XLSX Parsing (Backend - Python)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Docling (existing) | latest | XLSX to markdown conversion | Docling supports XLSX natively -- converts spreadsheet content to markdown with table structures preserved. Handles multi-sheet files. **Confidence: HIGH** |
| openpyxl | 3.1.5 | Supplementary XLSX reading (if Docling's output needs enrichment) | Only needed if Docling's XLSX-to-markdown is insufficient for complex score sheets. Provides cell-level access, formulas, formatting. Use as fallback, not primary. **Confidence: MEDIUM** |

**Key insight:** Docling handles XLSX conversion to markdown, including multi-sheet files. The limitation is that `export_to_markdown()` aggregates all sheets into one output, but the `DoclingDocument.tables` attribute contains separate `TableItem` objects per sheet. For board game score sheets and trackers, Docling's output should be sufficient. Keep openpyxl as a contingency if per-sheet metadata extraction is needed.

### Hierarchical Folder Structure (Backend - Supabase/Postgres)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| ltree (Postgres extension) | (Supabase built-in) | Materialized path tree queries | Available in Supabase, purpose-built for hierarchical data. Supports ancestor/descendant queries, pattern matching (e.g., `games.catan.*`), and GiST indexing. Perfect for folder path queries like "all documents under /games/catan/". **Confidence: HIGH** |

**Schema pattern:** Use materialized paths with ltree, not adjacency lists (parent_id). Rationale:

1. **Query efficiency**: `WHERE path <@ 'games.catan'` finds all descendants in one indexed query vs recursive CTEs with adjacency lists
2. **Path display**: Materialized paths map directly to the UI breadcrumb/tree display
3. **Supabase compatibility**: ltree is a supported Supabase extension, enable with `CREATE EXTENSION IF NOT EXISTS ltree WITH SCHEMA extensions;`
4. **RLS friendly**: Path-based policies are straightforward -- default KB paths start with `default.`, user paths start with `user_{id}.`

**Recommended DB schema addition:**

```sql
-- folders table
CREATE TABLE folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users,
  name TEXT NOT NULL,
  path ltree NOT NULL,
  is_default BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT unique_path_per_user UNIQUE (user_id, path)
);

CREATE INDEX idx_folders_path ON folders USING GIST (path);

-- Add folder_id to existing documents table
ALTER TABLE documents ADD COLUMN folder_id UUID REFERENCES folders(id);
```

### Regex Search Over Document Chunks (Backend - Postgres)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pg_trgm (Postgres extension) | (Supabase built-in) | Trigram-indexed regex search | Supabase includes pg_trgm. Enables GIN/GiST indexes that accelerate `~` (regex) and `LIKE/ILIKE` operators. Without it, regex search on document_chunks is a full table scan. **Confidence: HIGH** |

**Implementation for grep tool:**

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

-- Add trigram index on chunk content
CREATE INDEX idx_chunks_content_trgm ON document_chunks USING GIN (content gin_trgm_ops);

-- Grep query (used by the agent's grep tool)
SELECT id, document_id, content, chunk_index
FROM document_chunks
WHERE content ~ 'dice.*roll'  -- regex pattern
  AND user_id = $1
ORDER BY document_id, chunk_index;
```

The trigram index extracts trigrams from regex patterns and uses the index for acceleration. Not all regex patterns benefit (very short patterns or `.* ` heavy patterns), but typical grep-style searches will be fast.

### Tree View UI (Frontend - React)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| ggoggam/shadcn-treeview | latest (registry) | File manager tree view with drag-drop | Built for React 19 + shadcn/ui (matches our stack exactly). Uses @dnd-kit/react for drag-drop. Supports lazy loading, multi-selection, cross-tree DnD, keyboard navigation. Install as shadcn registry component, not npm package. **Confidence: MEDIUM** |
| @dnd-kit/react | 0.3.2 | Drag-and-drop primitives (dependency of treeview) | Modern DnD toolkit for React. Lightweight, accessible, extensible. Required by the shadcn-treeview component. **Confidence: MEDIUM** |

**Why this over alternatives:**

- **ggoggam/shadcn-treeview** over **MrLightful/shadcn-tree-view**: ggoggam uses @dnd-kit/react (newer React 19-native API) vs MrLightful which may use older @dnd-kit/core. ggoggam also supports cross-tree DnD and lazy loading, both needed for moving files between folders.
- **shadcn registry component** over **npm package**: Aligns with the project's shadcn/ui approach -- copy component code into project, full customization control.
- **@dnd-kit/react** over **react-beautiful-dnd**: react-beautiful-dnd is deprecated/unmaintained. @dnd-kit is the modern successor.

**Installation:**
```bash
npx shadcn@latest add https://ggoggam.github.io/shadcn-treeview/r/tree-view.json
```

**Risk note:** @dnd-kit/react is at 0.3.2 (pre-1.0). The API may change. The shadcn-treeview wraps it, so changes are isolated. Monitor for breaking changes. If stability is critical, building a custom tree with @dnd-kit/core (stable, widely used) is the fallback.

### Context Window Management (Backend - Python)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| tiktoken | 0.12.0 | Token counting for context budget management | OpenAI's official BPE tokenizer. 3-6x faster than alternatives. Needed to count tokens before assembling context windows. Supports o200k_base encoding for latest models. **Confidence: HIGH** |

**Context budget strategy for board game KB:**

The agent must manage a token budget across: system prompt (~2K), conversation history (~4-8K), retrieved KB content (variable), and response buffer (~4K). For a 128K context window:

1. **Budget allocation**: System (2K) + History (8K) + KB Content (up to 80K) + Response (4K) = ~94K safe maximum
2. **Chunk-level counting**: Use tiktoken to count tokens per chunk before including in context
3. **Progressive retrieval**: Start with summaries/metadata, drill into full chunks only when needed (mirrors Claude Code's read tool -- get line ranges, not full files)
4. **Scope narrowing**: User-controllable folder scope reduces the search space before retrieval
5. **Smart truncation**: When budget is exceeded, truncate oldest/lowest-relevance chunks first

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | latest | Image preprocessing before OCR | Only if images need resizing/rotation/enhancement before Docling processes them. Docling handles most cases internally. Add only if OCR accuracy is poor on raw uploads. |
| lucide-react | (existing) | Icons for tree view, file types, folders | Already in frontend dependencies. Use for folder/file/document-type icons in the tree UI. |

## Installation

### Backend (Python)

```bash
# OCR support (if not already installed with docling)
pip install "docling[ocr]"

# Token counting
pip install tiktoken==0.12.0

# XLSX fallback (only if Docling XLSX output is insufficient)
# pip install openpyxl==3.1.5
```

### Frontend (Node)

```bash
# Tree view component (shadcn registry)
npx shadcn@latest add https://ggoggam.github.io/shadcn-treeview/r/tree-view.json

# dnd-kit (installed automatically as dependency of treeview)
# npm install @dnd-kit/react  -- usually pulled in by the registry component
```

### Database (Supabase SQL)

```sql
-- Enable extensions (run in Supabase SQL editor)
CREATE EXTENSION IF NOT EXISTS ltree WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;
```

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Docling OCR (EasyOCR engine) | pytesseract standalone | Docling already handles the full pipeline (image -> structured content -> markdown). Adding pytesseract separately duplicates effort and bypasses Docling's layout analysis. |
| Docling for XLSX | openpyxl as primary | Project constraint requires Docling for document conversion. openpyxl adds complexity with a parallel processing path. Keep as fallback only. |
| ltree materialized paths | Adjacency list (parent_id) | Adjacency lists require recursive CTEs for tree queries, which are slower and harder to index. ltree gives single-query ancestor/descendant lookups with GiST indexes. |
| ltree materialized paths | Nested sets | Nested sets are fast for reads but very expensive for inserts/moves (must renumber). Folder reorganization (drag-drop) would be painful. |
| ggoggam/shadcn-treeview | rc-tree / react-arborist | rc-tree doesn't match shadcn styling. react-arborist is heavier and doesn't integrate with shadcn/ui. The shadcn-treeview is a copy-paste component that matches the existing design system. |
| @dnd-kit/react | react-beautiful-dnd | react-beautiful-dnd is unmaintained (Atlassian stopped development). @dnd-kit is the actively maintained modern alternative. |
| tiktoken | Manual token estimation | Character-count heuristics (chars/4) are inaccurate by 20-30%. tiktoken gives exact counts, critical for budget management near context limits. |
| pg_trgm for regex | Application-level regex (Python re) | Pulling all chunks to Python for regex matching defeats the purpose of having a database. pg_trgm indexes accelerate regex queries in Postgres directly. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pytesseract (standalone) | Duplicates Docling's OCR pipeline, loses layout analysis | Docling with EasyOCR/Tesseract engine |
| LangChain document loaders | Project constraint: no LangChain | Docling for all document processing |
| react-beautiful-dnd | Unmaintained, incompatible with React 19 | @dnd-kit/react |
| Manual parent_id tree queries | Recursive CTEs are slow, complex, hard to optimize | Postgres ltree extension |
| pandas for XLSX | Massive dependency for simple spreadsheet reading, overkill | Docling (primary) or openpyxl (fallback) |
| Elasticsearch for regex search | Adds external dependency when Postgres pg_trgm handles the use case | pg_trgm extension in existing Supabase Postgres |

## Stack Patterns by Variant

**If Docling XLSX output is insufficient for complex score sheets:**
- Add openpyxl 3.1.5 as a pre-processor
- Parse XLSX with openpyxl, convert to markdown manually, then feed into the existing chunk pipeline
- This adds a parallel ingestion path -- only do this if Docling can't handle the specific XLSX formats

**If OCR accuracy is poor on game cards with stylized fonts:**
- Add Pillow for image preprocessing (contrast enhancement, deskewing, resizing)
- Consider using `force_full_page_ocr=True` in Docling pipeline options
- If still poor, evaluate docling-ocr package (LLM-based OCR) as a premium alternative

**If @dnd-kit/react 0.x stability is a concern:**
- Build custom tree view using @dnd-kit/core (stable, 5.x) + @dnd-kit/sortable (stable, 7.x)
- More work but fully stable APIs
- The shadcn-treeview component isolates the @dnd-kit/react dependency, so this is only needed if bugs surface

**If ltree path updates become a bottleneck (frequent folder moves):**
- ltree path updates require updating all descendant paths
- For deep trees with many descendants, batch the updates in a transaction
- In practice, board game folder structures are shallow (2-4 levels), so this is unlikely to be an issue

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Docling (latest) | Python 3.10+ | OCR extras may require additional system dependencies (Tesseract binary for TesseractCliOcrOptions) |
| tiktoken 0.12.0 | Python 3.9+ | Uses o200k_base encoding for GPT-4o models |
| openpyxl 3.1.5 | Python 3.8+ | No conflicts with existing deps |
| ggoggam/shadcn-treeview | React 19, TypeScript | Built specifically for React 19. Requires shadcn/ui setup (already in project). |
| @dnd-kit/react 0.3.2 | React 19 | Pre-1.0 -- API may change. Isolated behind shadcn-treeview wrapper. |
| ltree | PostgreSQL 12+ (Supabase) | Core extension, always available. Enable in extensions schema. |
| pg_trgm | PostgreSQL 12+ (Supabase) | Core extension, always available. Enable in extensions schema. |

## Sources

- [Docling Supported Formats](https://docling-project.github.io/docling/usage/supported_formats/) -- confirmed image (PNG, JPEG, TIFF, BMP, WEBP) and XLSX support. HIGH confidence.
- [Docling Pipeline Options](https://docling-project.github.io/docling/reference/pipeline_options/) -- OCR engine configuration (EasyOCR, Tesseract, RapidOCR). HIGH confidence.
- [Docling XLSX Multi-sheet Issue #1292](https://github.com/docling-project/docling/issues/1292) -- confirmed XLSX works but aggregates sheets in markdown export. MEDIUM confidence.
- [PostgreSQL ltree Documentation](https://www.postgresql.org/docs/current/ltree.html) -- materialized path data type. HIGH confidence.
- [PostgreSQL pg_trgm Documentation](https://www.postgresql.org/docs/current/pgtrgm.html) -- trigram indexing for regex. HIGH confidence.
- [Supabase Extensions](https://supabase.com/docs/guides/database/extensions) -- ltree and pg_trgm available. HIGH confidence.
- [Supabase Storage Hierarchical RLS](https://supabase.com/docs/guides/troubleshooting/supabase-storage-inefficient-folder-operations-and-hierarchical-rls-challenges-b05a4d) -- folder hierarchy patterns. MEDIUM confidence.
- [ggoggam/shadcn-treeview](https://github.com/ggoggam/shadcn-treeview) -- React 19 tree component with DnD. MEDIUM confidence (pre-1.0 dependency).
- [tiktoken on PyPI](https://pypi.org/project/tiktoken/) -- v0.12.0, Oct 2025. HIGH confidence.
- [openpyxl on PyPI](https://pypi.org/project/openpyxl/) -- v3.1.5. HIGH confidence.
- [@dnd-kit/react on npm](https://www.npmjs.com/package/@dnd-kit/react) -- v0.3.2. MEDIUM confidence (pre-1.0).

---
*Stack research for: Board game knowledge base with agent tooling*
*Researched: 2026-04-07*
