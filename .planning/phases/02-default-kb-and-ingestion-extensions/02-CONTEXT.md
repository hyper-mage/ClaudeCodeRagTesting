# Phase 2: Default KB and Ingestion Extensions - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a pre-seeded board game knowledge base (10 popular games) and extends the ingestion pipeline to support image OCR (JPG/PNG) and XLSX uploads. No file manager UI, no folder selection UI, no KB navigation tools -- those are Phases 3-4.

</domain>

<decisions>
## Implementation Decisions

### Game Selection & Content
- **D-01:** Pre-seed 10 board games with rules-focused content: rules overview, setup instructions, turn structure, win conditions, component list.
- **D-02:** Game selection is a mix -- user will provide some must-have picks, Claude fills remaining slots with popular classics (e.g., Catan, Ticket to Ride, Pandemic).
- **D-03:** One subfolder per game under the Board Games/ root folder (e.g., Board Games/Catan/, Board Games/Pandemic/).

### Seeding Mechanism
- **D-04:** Check in markdown (.md) files per game in the repo (e.g., `data/default-kb/catan.md`). A Python seed script reads these files and ingests them through the existing ingestion pipeline as the system user. Rerunnable and version-controlled.
- **D-05:** The seed script creates subfolders under the Board Games root folder (UUID `a0000000-0000-0000-0000-000000000001` from Phase 1) and inserts documents with `visibility='public'` and `user_id='00000000-0000-0000-0000-000000000000'` (system user).

### OCR Approach
- **D-06:** Use Docling's image pipeline for JPG/PNG OCR. Docling already supports image input formats (uses EasyOCR under the hood). Keeps the parsing pipeline unified -- one library for all formats, no new dependency.
- **D-07:** Add image MIME types (image/jpeg, image/png) to the upload router's mime_map and to parsing_service.py's format handling.

### XLSX Support
- **D-08:** Use Docling for XLSX parsing to produce searchable markdown. Add the XLSX MIME type to the upload router and parsing service.

### Folder Selection on Upload
- **D-09:** Backend-only for Phase 2: add `folder_id` parameter to the upload API endpoint. Frontend does not expose folder selection yet -- uploads default to root (folder_id=NULL). Phase 4 adds the UI folder picker.
- **D-10:** The ingestion pipeline must propagate `folder_id` and `visibility` when creating document records in the database.

### Claude's Discretion
- Exact seed script location and invocation method (CLI command, management script, etc.)
- How to handle seed script idempotency (skip if games already exist, or upsert)
- Docling configuration for image OCR quality (resolution, preprocessing)
- XLSX-to-markdown formatting decisions (table layout, sheet handling)
- Chunk size tuning for game rules content

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database Schema (from Phase 1)
- `supabase/migrations/017_create_system_user.sql` -- System user UUID and auth setup
- `supabase/migrations/018_create_folders_table.sql` -- Folders table, Board Games root folder (UUID `a0000000-0000-0000-0000-000000000001`)
- `supabase/migrations/019_add_visibility_and_folder.sql` -- visibility/folder_id columns, sync triggers
- `supabase/migrations/020_update_rls_policies.sql` -- Mixed-visibility RLS policies
- `supabase/migrations/021_update_search_rpcs.sql` -- Visibility-aware search RPCs

### Backend Integration Points
- `backend/services/parsing_service.py` -- Docling-based parser (needs image + XLSX support)
- `backend/services/ingestion_service.py` -- Document processing pipeline (needs folder_id/visibility propagation)
- `backend/routers/documents.py` -- Upload endpoint (needs new MIME types + folder_id param)
- `backend/services/embedding_service.py` -- Embedding generation (used by seed script)
- `backend/services/record_manager.py` -- Deduplication (seed script needs idempotency)
- `backend/database.py` -- Supabase client (service role key for system user operations)

### Frontend Integration Points
- `frontend/src/components/FileUpload.tsx` -- File upload component (needs accepted types updated)
- `frontend/src/hooks/useDocuments.ts` -- Document listing hook

### Project Constraints
- `CLAUDE.md` -- Docling required for all document extraction; no LangChain

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `parsing_service.py`: Lazy-initialized Docling `DocumentConverter` with PDF pipeline options. Extend for image and XLSX formats.
- `ingestion_service.py`: `process_document()` handles full pipeline (fetch file -> extract text -> chunk -> embed -> store). Seed script can reuse this.
- `record_manager.py`: Content-addressed hashing for deduplication. Seed script can use `check_duplicate()` for idempotency.
- `embedding_service.py`: `get_embeddings()` for batch embedding generation.

### Established Patterns
- MIME type mapping in upload router (`mime_map` dict keyed by extension)
- File-based vs string-based parsing split in `parsing_service.py` (`_FILE_BASED` and `_STRING_BASED` dicts)
- Storage path convention: `{user_id}/{doc_id}/{filename}`
- Document record creation: INSERT into `documents` table, then `process_document()` for chunking/embedding

### Integration Points
- Upload router needs: new MIME types, optional `folder_id` form field
- `process_document()` needs: pass `folder_id` and `visibility` through to document record
- Seed script needs: Supabase service role client, system user UUID, Board Games folder UUID
- Frontend `FileUpload.tsx` / `ACCEPTED_TYPES`: add `.jpg`, `.png`, `.xlsx` extensions

</code_context>

<specifics>
## Specific Ideas

- Game content should be written as clean markdown with consistent structure (## Setup, ## Turn Structure, ## Win Conditions, ## Components) so chunking produces coherent pieces
- Seed script should log progress (which games seeded, which skipped as duplicates)
- Consider adding a "seeded_at" or "source" metadata field so seeded content is distinguishable from user uploads

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 02-default-kb-and-ingestion-extensions*
*Context gathered: 2026-04-08*
