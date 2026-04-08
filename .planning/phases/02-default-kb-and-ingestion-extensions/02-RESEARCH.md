# Phase 2: Default KB and Ingestion Extensions - Research

**Researched:** 2026-04-08
**Domain:** Document ingestion pipeline (Docling OCR/XLSX), database seeding, Supabase Storage
**Confidence:** HIGH

## Summary

This phase extends the existing ingestion pipeline in three ways: (1) pre-seed 10 board games as public knowledge base content, (2) add image OCR support via Docling's IMAGE format, and (3) add XLSX parsing via Docling's XLSX format. The backend also needs `folder_id` and `visibility` propagation through the upload/ingestion flow.

The technical risk is LOW. Docling 2.82.0 (already installed) natively supports `InputFormat.IMAGE` and `InputFormat.XLSX` -- both verified working on the local environment. The seed script reuses the existing ingestion pipeline (`process_document`) with the system user context. The main work is content creation (10 game markdown files), extending MIME type maps, updating the `DocumentConverter` initialization, and wiring `folder_id`/`visibility` through the upload endpoint and ingestion service.

**Primary recommendation:** Extend the existing `_get_converter()` to include IMAGE and XLSX formats, add MIME types to both backend and frontend, write a seed script that reuses `process_document()`, and propagate `folder_id`/`visibility` through the document insert path.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Pre-seed 10 board games with rules-focused content: rules overview, setup instructions, turn structure, win conditions, component list.
- **D-02:** Game selection is a mix -- user will provide some must-have picks, Claude fills remaining slots with popular classics (e.g., Catan, Ticket to Ride, Pandemic).
- **D-03:** One subfolder per game under the Board Games/ root folder (e.g., Board Games/Catan/, Board Games/Pandemic/).
- **D-04:** Check in markdown (.md) files per game in the repo (e.g., `data/default-kb/catan.md`). A Python seed script reads these files and ingests them through the existing ingestion pipeline as the system user. Rerunnable and version-controlled.
- **D-05:** The seed script creates subfolders under the Board Games root folder (UUID `a0000000-0000-0000-0000-000000000001`) and inserts documents with `visibility='public'` and `user_id='00000000-0000-0000-0000-000000000000'` (system user).
- **D-06:** Use Docling's image pipeline for JPG/PNG OCR. Docling already supports image input formats (uses EasyOCR under the hood). Keeps the parsing pipeline unified.
- **D-07:** Add image MIME types (image/jpeg, image/png) to the upload router's mime_map and to parsing_service.py's format handling.
- **D-08:** Use Docling for XLSX parsing to produce searchable markdown. Add the XLSX MIME type to the upload router and parsing service.
- **D-09:** Backend-only for Phase 2: add `folder_id` parameter to the upload API endpoint. Frontend does not expose folder selection yet -- uploads default to root (folder_id=NULL). Phase 4 adds the UI folder picker.
- **D-10:** The ingestion pipeline must propagate `folder_id` and `visibility` when creating document records in the database.

### Claude's Discretion
- Exact seed script location and invocation method (CLI command, management script, etc.)
- How to handle seed script idempotency (skip if games already exist, or upsert)
- Docling configuration for image OCR quality (resolution, preprocessing)
- XLSX-to-markdown formatting decisions (table layout, sheet handling)
- Chunk size tuning for game rules content

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-04 | Default board game KB ships with 10 pre-seeded popular games organized in folders | Seed script reuses `process_document()` pipeline; system user UUID and Board Games folder UUID already exist in DB from Phase 1 migrations |
| DATA-08 | User can upload images (JPG, PNG) which are processed with OCR to extract text | Docling 2.82.0 supports `InputFormat.IMAGE` with `ImageFormatOption`; verified working locally |
| DATA-09 | User can upload XLSX files which are parsed into searchable markdown content | Docling 2.82.0 supports `InputFormat.XLSX` with `ExcelFormatOption`; verified working locally |
| DATA-10 | Uploaded files are placed into the user's selected folder in Supabase Storage | Add `folder_id` Form parameter to upload endpoint; propagate through document INSERT; `documents.folder_id` column exists from migration 019 |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| docling | 2.82.0 | Document parsing (PDF, DOCX, IMAGE, XLSX) | Already installed; project constraint requires Docling for all extraction |
| supabase | 2.13.0 | Database client (service role for seed script) | Already used throughout backend |
| openai | 1.74.0 | Embedding generation for seeded content | Already used by embedding_service |
| fastapi | 0.115.12 | Upload endpoint with Form fields | Already used for all API routes |

### Supporting
No new dependencies needed. All required functionality exists in the installed stack.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Docling for OCR | pytesseract / EasyOCR directly | Would add a second parsing path; Docling already wraps OCR engines internally |
| Docling for XLSX | openpyxl + manual markdown | Would need custom table-to-markdown logic; Docling handles it with `export_to_markdown()` |
| Seed script | SQL INSERT with pre-computed embeddings | Would bypass chunking/embedding pipeline; harder to maintain content |

## Architecture Patterns

### Recommended Project Structure
```
data/
  default-kb/
    catan.md
    ticket-to-ride.md
    pandemic.md
    ... (7 more games)
backend/
  scripts/
    seed_default_kb.py      # Seed script entry point
  services/
    parsing_service.py       # Extended with IMAGE + XLSX
    ingestion_service.py     # Extended with folder_id/visibility
  routers/
    documents.py             # Extended with folder_id Form param + new MIME types
frontend/
  src/
    components/
      FileUpload.tsx         # Updated ACCEPTED_TYPES + accept attribute
```

### Pattern 1: Seed Script via Existing Pipeline
**What:** A standalone Python script that reads markdown files from `data/default-kb/`, creates folder records in Supabase, uploads files to Storage, and calls `process_document()` for each game.
**When to use:** One-time seeding of default content; rerunnable for updates.
**Example:**
```python
# backend/scripts/seed_default_kb.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import get_supabase
from services.ingestion_service import process_document
from services.record_manager import hash_content, check_duplicate

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"
BOARD_GAMES_FOLDER_ID = "a0000000-0000-0000-0000-000000000001"

def seed_game(db, game_name: str, content: bytes, filename: str):
    """Seed a single game into the default KB."""
    content_hash = hash_content(content)

    # Idempotency: skip if this exact content already exists for system user
    existing = check_duplicate(SYSTEM_USER_ID, content_hash)
    if existing:
        print(f"  Skipping {game_name} (already seeded)")
        return

    # Create subfolder under Board Games
    folder_id = create_game_folder(db, game_name)

    # Upload to storage + create document record
    doc_id = str(uuid.uuid4())
    storage_path = f"{SYSTEM_USER_ID}/{doc_id}/{filename}"
    db.storage.from_("documents").upload(path=storage_path, file=content, ...)

    db.table("documents").insert({
        "id": doc_id,
        "user_id": SYSTEM_USER_ID,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": len(content),
        "mime_type": "text/markdown",
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": folder_id,
        "visibility": "public",
    }).execute()

    process_document(doc_id, SYSTEM_USER_ID)
    print(f"  Seeded {game_name}")
```

### Pattern 2: Extending DocumentConverter for New Formats
**What:** Modify `_get_converter()` in `parsing_service.py` to include IMAGE and XLSX format support.
**When to use:** Adding any new Docling-supported format.
**Example:**
```python
# In parsing_service.py - updated _get_converter()
def _get_converter():
    global _converter
    if _converter is None:
        from docling.document_converter import (
            DocumentConverter, PdfFormatOption, ImageFormatOption, ExcelFormatOption
        )
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat

        pdf_options = PdfPipelineOptions()
        if _MODELS_DIR.exists():
            pdf_options.artifacts_path = _MODELS_DIR

        _converter = DocumentConverter(
            allowed_formats=[
                InputFormat.PDF, InputFormat.DOCX, InputFormat.HTML,
                InputFormat.MD, InputFormat.IMAGE, InputFormat.XLSX,
            ],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.IMAGE: ImageFormatOption(),
                InputFormat.XLSX: ExcelFormatOption(),
            }
        )
    return _converter
```

### Pattern 3: folder_id/visibility Propagation in Upload
**What:** Add optional `folder_id` Form field to upload endpoint; pass `folder_id` and `visibility` into the document INSERT.
**When to use:** Every document upload (defaults to NULL folder, "private" visibility for user uploads).
**Example:**
```python
# In documents.py upload_document()
from fastapi import Form

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    folder_id: str | None = Form(None),
    user_id: str = Depends(get_user_id),
):
    # ... existing logic ...
    doc = db.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
        "file_size": file_size,
        "mime_type": mime_type,
        "status": "pending",
        "content_hash": content_hash,
        "folder_id": folder_id,       # NEW: nullable, Phase 4 adds UI
        "visibility": "private",       # User uploads always private
    }).execute()
```

### Anti-Patterns to Avoid
- **Separate OCR library:** Do not add pytesseract or EasyOCR as a direct dependency. Docling handles OCR internally.
- **Embedding pre-computation in seed data:** Do not store pre-computed embeddings in the repo. Use the existing pipeline to generate them at seed time. This ensures consistency with the configured embedding model.
- **Hardcoded game content in Python:** Keep game content in markdown files under `data/default-kb/`, not embedded as Python strings.
- **Non-idempotent seed script:** The seed script must be safely rerunnable. Use `check_duplicate()` or filename matching to skip already-seeded games.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Image OCR | Custom OCR pipeline with pytesseract | `InputFormat.IMAGE` + `ImageFormatOption` in Docling | Docling already wraps EasyOCR/Tesseract; unified parsing pipeline |
| XLSX to markdown | openpyxl reader + custom table formatter | `InputFormat.XLSX` + `ExcelFormatOption` in Docling | Docling handles multi-sheet, table structure, export to markdown |
| Content deduplication for seed | Custom hash comparison | Existing `record_manager.check_duplicate()` | Already implements SHA-256 content-addressed deduplication |
| Chunk visibility sync | Manual UPDATE on chunks after insert | DB trigger `trg_set_chunk_visibility` (migration 019) | Trigger auto-sets chunk visibility from parent document on INSERT |
| Folder path computation | Manual ltree path string building | Query parent folder path and append | ltree paths must be consistent with parent hierarchy |

**Key insight:** The Phase 1 database triggers handle visibility propagation from documents to chunks automatically. The seed script and upload endpoint only need to set `visibility` on the document record; chunks inherit it via the BEFORE INSERT trigger.

## Common Pitfalls

### Pitfall 1: Docling IMAGE Format Needs File-Based Conversion
**What goes wrong:** Trying to use `convert_string()` with image bytes fails. Images are binary and must use `convert()` with a file path.
**Why it happens:** The existing code splits formats into `_FILE_BASED` and `_STRING_BASED` dicts. IMAGE must go in `_FILE_BASED`.
**How to avoid:** Add `"image/jpeg": ".jpg"` and `"image/png": ".png"` to the `_FILE_BASED` dict in `parsing_service.py`. Same temp file pattern as PDF/DOCX.
**Warning signs:** `ValueError: Unsupported MIME type` or garbled output from image files.

### Pitfall 2: XLSX Also Needs File-Based Conversion
**What goes wrong:** Trying to decode XLSX bytes as UTF-8 string fails -- XLSX is a binary (ZIP-based) format.
**Why it happens:** Developer might assume spreadsheet is text-like and put it in `_STRING_BASED`.
**How to avoid:** Add XLSX MIME type to `_FILE_BASED` dict: `"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx"`.
**Warning signs:** `UnicodeDecodeError` or `ValueError` during parsing.

### Pitfall 3: Seed Script Must Use Service Role Client (Not RLS-Restricted)
**What goes wrong:** Seed script inserts fail because RLS policies restrict writes to `auth.uid()`.
**Why it happens:** The system user UUID doesn't have a real Supabase Auth session.
**How to avoid:** The existing `database.py` already uses the service role key, which bypasses RLS. The seed script should use `get_supabase()` directly -- this is already the pattern.
**Warning signs:** `new row violates row-level security policy` errors.

### Pitfall 4: Folder Creation for Game Subfolders Must Use Correct ltree Paths
**What goes wrong:** Game subfolders have wrong ltree paths, breaking tree traversal queries.
**Why it happens:** ltree path must be parent_path.child_label format (e.g., `board_games.catan`). Labels can only contain alphanumeric + underscore.
**How to avoid:** Sanitize game names for ltree labels: lowercase, replace spaces/special chars with underscores, strip non-alphanumeric. Set `parent_id` to the Board Games folder UUID.
**Warning signs:** ltree syntax errors, folders not appearing in tree queries.

### Pitfall 5: Frontend ACCEPTED_TYPES and accept Attribute Must Both Be Updated
**What goes wrong:** User sees the new file types in the drop zone text but the file picker doesn't show them (or vice versa).
**Why it happens:** The `ACCEPTED_TYPES` array (for validation) and the `<input accept="...">` attribute (for file picker filtering) are separate.
**How to avoid:** Update both in `FileUpload.tsx`: add `.jpg`, `.jpeg`, `.png`, `.xlsx` to both `ACCEPTED_TYPES` and the `accept` attribute.
**Warning signs:** "Unsupported file type" error on valid images/spreadsheets.

### Pitfall 6: check_duplicate Scopes by user_id -- Seed Script Uses System User
**What goes wrong:** `check_duplicate()` uses `user_id` as scope. If the seed script passes the wrong user_id, dedup won't find existing seeded content.
**Why it happens:** The function signature requires `user_id` parameter.
**How to avoid:** Always pass `SYSTEM_USER_ID` ("00000000-0000-0000-0000-000000000000") when checking/inserting seed content.
**Warning signs:** Duplicate seeded documents after re-running the script.

## Code Examples

### Extending _FILE_BASED and _STRING_BASED Dicts
```python
# parsing_service.py additions
_FILE_BASED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
```

### Upload Router MIME Map Extension
```python
# documents.py additions to mime_map
mime_map = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".htm": "text/html",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
```

### Sanitizing Game Names for ltree Labels
```python
import re

def sanitize_ltree_label(name: str) -> str:
    """Convert a game name to a valid ltree label."""
    label = name.lower().replace(" ", "_")
    label = re.sub(r"[^a-z0-9_]", "", label)
    label = re.sub(r"_+", "_", label).strip("_")
    return label

# Example: "Ticket to Ride" -> "ticket_to_ride"
# Example: "7 Wonders" -> "7_wonders"
```

### Game Markdown Content Structure
```markdown
# Catan

## Overview
Catan is a multiplayer board game designed by Klaus Teuber...

## Setup
1. Lay out the hexagonal terrain tiles...
2. Place number tokens...

## Turn Structure
On your turn, you:
1. Roll the dice...
2. Trade resources...
3. Build...

## Win Conditions
The first player to reach 10 victory points wins.

## Components
- 19 terrain hexes
- 6 sea frame pieces
- 9 harbor pieces
- ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate OCR library (pytesseract) | Docling unified parsing (InputFormat.IMAGE) | Docling 2.x (2025) | Single library for all doc types |
| openpyxl manual parsing | Docling XLSX support (InputFormat.XLSX) | Docling 2.x (2025) | Automatic markdown export |

## Open Questions

1. **Image OCR Quality for Rule Cards**
   - What we know: Docling uses EasyOCR by default for IMAGE format. Works for printed text.
   - What's unclear: Quality on photographed rule cards with complex layouts, small text, or colored backgrounds.
   - Recommendation: Accept default Docling settings. If quality is poor, tune OCR engine options (Tesseract vs EasyOCR) in a follow-up.

2. **XLSX Multi-Sheet Handling**
   - What we know: Docling XLSX converts to markdown with table formatting. Multi-sheet handling exists but behavior with `export_to_markdown()` is not fully documented.
   - What's unclear: Whether each sheet becomes a separate section or if only the first sheet is processed.
   - Recommendation: Use defaults. Multi-sheet intelligence is deferred to v2 (INGS-01). For Phase 2, any markdown output from XLSX is acceptable.

3. **Game Content Quality and Length**
   - What we know: Chunk size is 1000 chars with 200 overlap. Game rules content should produce coherent chunks.
   - What's unclear: Optimal content length per game to balance completeness vs chunk quality.
   - Recommendation: Target 2000-4000 chars per game (2-5 chunks each). Use consistent markdown headers (## Setup, ## Turn Structure, etc.) so the recursive splitter breaks on section boundaries.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (not installed -- needs Wave 0 setup) |
| Config file | none -- needs creation |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-04 | 10 games seeded as public docs in Board Games subfolders | integration | `python -m pytest tests/test_seed_default_kb.py -x` | No -- Wave 0 |
| DATA-08 | JPG/PNG uploaded and OCR-extracted to text | unit | `python -m pytest tests/test_parsing_formats.py::test_image_ocr -x` | No -- Wave 0 |
| DATA-09 | XLSX uploaded and parsed to markdown | unit | `python -m pytest tests/test_parsing_formats.py::test_xlsx_parse -x` | No -- Wave 0 |
| DATA-10 | Upload with folder_id stores doc in correct folder | unit | `python -m pytest tests/test_upload_folder.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Install pytest: `pip install pytest && pip freeze | grep pytest >> requirements.txt`
- [ ] `backend/tests/test_parsing_formats.py` -- covers DATA-08, DATA-09 (unit tests for image/xlsx parsing)
- [ ] `backend/tests/test_seed_default_kb.py` -- covers DATA-04 (integration test for seed script idempotency)
- [ ] `backend/tests/test_upload_folder.py` -- covers DATA-10 (unit test for folder_id propagation)

## Project Constraints (from CLAUDE.md)

- **Docling required** for all document extraction (PDF, DOCX, IMAGE, XLSX) -- no alternative parsers
- **No LangChain / LangGraph** -- raw SDK calls only
- **Pydantic** for structured outputs
- **RLS enforced** -- users only see their own data; public KB visible to all
- **Manual file upload only** -- no automated connectors or scrapers
- **Python venv** -- all backend deps in `backend/venv/`
- **Plans in `.agent/plans/`** -- but GSD workflow uses `.planning/phases/`
- **snake_case** for Python files, functions, variables
- **Type hints** on all Python function parameters and return values

## Sources

### Primary (HIGH confidence)
- Docling 2.82.0 installed locally -- `InputFormat.IMAGE` and `InputFormat.XLSX` verified via Python import
- Docling official docs (supported formats) -- https://docling-project.github.io/docling/usage/supported_formats/
- Existing codebase: `parsing_service.py`, `ingestion_service.py`, `documents.py`, `record_manager.py`
- Phase 1 migrations: `017_create_system_user.sql`, `018_create_folders_table.sql`, `019_add_visibility_and_folder.sql`

### Secondary (MEDIUM confidence)
- Docling reference docs -- https://docling-project.github.io/docling/reference/document_converter/
- Docling multi-format example -- https://docling-project.github.io/docling/examples/run_with_formats/

### Tertiary (LOW confidence)
- XLSX multi-sheet behavior -- based on GitHub issue discussions, not official docs (https://github.com/docling-project/docling/issues/2269)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and verified working
- Architecture: HIGH - patterns extend existing code with minimal new abstractions
- Pitfalls: HIGH - identified from reading actual codebase code paths

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (stable -- no fast-moving dependencies)
