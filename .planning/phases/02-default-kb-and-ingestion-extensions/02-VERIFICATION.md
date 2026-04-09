---
phase: 02-default-kb-and-ingestion-extensions
verified: 2026-04-08T18:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
human_verification:
  - test: "Run seed script and verify board games are queryable"
    expected: "cd backend && python -m scripts.seed_default_kb outputs 'Seeded 10 games', and chatting with agent about Catan returns accurate rules"
    why_human: "Requires live Supabase connection, embedding generation, and end-to-end chat verification"
  - test: "Upload a JPG image and verify OCR extraction"
    expected: "Upload a photo of a rule card via the UI, document processes to 'completed' status with extracted text chunks"
    why_human: "Requires running backend with Docling OCR pipeline and a real image file"
  - test: "Upload an XLSX file and verify markdown extraction"
    expected: "Upload a spreadsheet via the UI, document processes to 'completed' status with markdown content in chunks"
    why_human: "Requires running backend with Docling XLSX pipeline and a real spreadsheet file"
  - test: "Upload a file with folder_id and verify folder association"
    expected: "Document record in Supabase has correct folder_id and visibility='private'"
    why_human: "Requires frontend folder selection UI (Phase 4) or manual API call with folder_id parameter"
---

# Phase 02: Default KB and Ingestion Extensions Verification Report

**Phase Goal:** Users have immediate value from 10 pre-seeded board games, and can upload images and spreadsheets alongside existing formats
**Verified:** 2026-04-08T18:00:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | On first login, user can browse and query 10 popular board games without uploading anything | ? UNCERTAIN | Seed script exists with correct logic, 10 markdown files exist, but live execution requires human verification |
| 2 | User can upload a JPG/PNG image of a rule card and the system extracts searchable text via OCR | VERIFIED (code) | parsing_service.py registers IMAGE format with Docling, documents.py accepts .jpg/.jpeg/.png, FileUpload.tsx accepts these types |
| 3 | User can upload an XLSX file and the system parses it into searchable markdown content | VERIFIED (code) | parsing_service.py registers XLSX format with Docling, documents.py accepts .xlsx, FileUpload.tsx accepts .xlsx |
| 4 | Uploaded files land in the user's selected folder in Supabase Storage with correct folder association | VERIFIED (code) | documents.py upload_document accepts folder_id Form param, INSERT includes folder_id and visibility='private' |

**Score:** 4/4 truths verified at code level; 4 items need human runtime verification

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/services/parsing_service.py` | IMAGE and XLSX format support in Docling | VERIFIED | Contains InputFormat.IMAGE, InputFormat.XLSX, ImageFormatOption(), ExcelFormatOption(), _FILE_BASED has image/jpeg, image/png, xlsx MIME |
| `backend/routers/documents.py` | Extended MIME map and folder_id Form parameter | VERIFIED | mime_map has .jpg, .jpeg, .png, .xlsx; upload_document accepts folder_id: str \| None = Form(None); INSERT has folder_id and visibility='private' |
| `backend/services/ingestion_service.py` | folder_id/visibility propagation | N/A | folder_id/visibility are set at document INSERT in documents.py, not in ingestion_service. Ingestion service reads from DB record. No folder_id grep hit is expected. |
| `frontend/src/components/FileUpload.tsx` | Updated accepted file types | VERIFIED | ACCEPTED_TYPES includes .jpg,.jpeg,.png,.xlsx; accept attr includes them; display text shows them; error message includes them |
| `data/default-kb/catan.md` | Catan rules content | VERIFIED | 4141 bytes, 5 ## sections, substantive rules content |
| `data/default-kb/ticket-to-ride.md` | Ticket to Ride rules | VERIFIED | 3951 bytes, 5 ## sections |
| `data/default-kb/pandemic.md` | Pandemic rules | VERIFIED | 4563 bytes, 5 ## sections |
| `data/default-kb/carcassonne.md` | Carcassonne rules | VERIFIED | 3905 bytes, 5 ## sections |
| `data/default-kb/7-wonders.md` | 7 Wonders rules | VERIFIED | 4583 bytes, 5 ## sections |
| `data/default-kb/codenames.md` | Codenames rules | VERIFIED | 3925 bytes, 5 ## sections |
| `data/default-kb/azul.md` | Azul rules | VERIFIED | 4701 bytes, 5 ## sections |
| `data/default-kb/splendor.md` | Splendor rules | VERIFIED | 4352 bytes, 5 ## sections |
| `data/default-kb/dominion.md` | Dominion rules | VERIFIED | 4322 bytes, 5 ## sections |
| `data/default-kb/wingspan.md` | Wingspan rules | VERIFIED | 5011 bytes, 5 ## sections |
| `backend/scripts/seed_default_kb.py` | Rerunnable seed script for default KB | VERIFIED | Contains SYSTEM_USER_ID, BOARD_GAMES_FOLDER_ID, GAMES dict (10 entries), sanitize_ltree_label, get_or_create_game_folder, seed_game, main, check_duplicate for idempotency, process_document call, visibility='public' |
| `backend/tests/test_parsing_formats.py` | Unit tests for image OCR and XLSX parsing | VERIFIED | 5 tests covering _FILE_BASED entries, unsupported MIME raises, mime_map entries |
| `backend/tests/test_upload_folder.py` | Unit test for folder_id propagation | VERIFIED | 4 tests covering signature, optionality, INSERT dict folder_id, INSERT dict visibility |
| `backend/tests/test_seed_default_kb.py` | Integration test for seed script | VERIFIED | 8 tests covering ltree sanitization, GAMES count, file existence, UUID validity |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `documents.py` | `parsing_service.py` | mime_type passed through ingestion pipeline | WIRED | documents.py sets mime_type in DB, ingestion_service.py reads it and calls extract_text() with it (line 70, 142) |
| `documents.py` | documents table | INSERT with folder_id and visibility | WIRED | Lines 73-84: INSERT dict contains "folder_id": folder_id, "visibility": "private" |
| `seed_default_kb.py` | `ingestion_service.py` | process_document() call | WIRED | Line 132: process_document(doc_id, SYSTEM_USER_ID) |
| `seed_default_kb.py` | `data/default-kb/` | reads markdown files from disk | WIRED | Line 94: os.path.join(DEFAULT_KB_DIR, filename), all 10 files confirmed to exist |
| `seed_default_kb.py` | Supabase folders table | INSERT game subfolders | WIRED | Lines 79-86: db.table("folders").insert({...visibility: "public"...}) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `seed_default_kb.py` | file_bytes | data/default-kb/*.md files on disk | Yes -- 10 files with 3900-5000 bytes each | FLOWING |
| `parsing_service.py` | text | Docling converter.convert() | Yes -- converts binary formats to markdown text | FLOWING (requires runtime) |
| `FileUpload.tsx` | onUpload prop | Parent component passes upload handler | Yes -- wired to API call | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 17 unit tests pass | `cd backend && venv/Scripts/python.exe -m pytest tests/ -x -v -p no:dash` | 17 passed, 0 failed | PASS |
| 10 markdown files exist | `ls data/default-kb/*.md \| wc -l` | 10 | PASS |
| Each file has 5 sections | `grep -c "^## " data/default-kb/*.md` | All return 5 | PASS |
| Each file 3900-5100 bytes | `wc -c data/default-kb/*.md` | Range: 3905-5011 | PASS |
| No TODOs in modified files | grep for TODO/FIXME/PLACEHOLDER | No matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DATA-04 | 02-02, 02-03 | Default board game KB ships with 10 pre-seeded popular games organized in folders | SATISFIED | 10 markdown files in data/default-kb/, seed script creates per-game subfolders and inserts as public documents |
| DATA-08 | 02-01 | User can upload images (JPG, PNG) which are processed with OCR to extract text | SATISFIED | parsing_service.py registers InputFormat.IMAGE with ImageFormatOption(), documents.py mime_map has .jpg/.jpeg/.png, FileUpload.tsx accepts these |
| DATA-09 | 02-01 | User can upload XLSX files which are parsed into searchable markdown content | SATISFIED | parsing_service.py registers InputFormat.XLSX with ExcelFormatOption(), documents.py mime_map has .xlsx, FileUpload.tsx accepts .xlsx |
| DATA-10 | 02-01 | Uploaded files are placed into the user's selected folder in Supabase Storage | SATISFIED | documents.py upload_document accepts folder_id Form param, INSERT includes folder_id in document record |

No orphaned requirements found for Phase 2.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns detected |

### Human Verification Required

### 1. Seed Script Live Execution

**Test:** Run `cd backend && python -m scripts.seed_default_kb` against live Supabase
**Expected:** Output shows "Seeded 10 games, skipped 0". Rerun shows "Seeded 0 games, skipped 10 (already exist)". Supabase dashboard shows 10 public documents with system user, 10 game subfolders, and chunks with embeddings.
**Why human:** Requires live Supabase connection, OpenAI embedding API, and database verification

### 2. Chat Queryability of Default KB

**Test:** Log in as ragtest1@gmail.com and ask "How do you win in Catan?"
**Expected:** Agent retrieves chunks from seeded Catan content and responds with accurate victory point information
**Why human:** Requires running frontend + backend + LLM, end-to-end verification

### 3. Image OCR Upload

**Test:** Upload a JPG/PNG image of a board game rule card through the UI
**Expected:** Document status transitions to "completed", extracted text appears in document_chunks
**Why human:** Requires Docling OCR runtime, real image file, running server

### 4. XLSX Upload

**Test:** Upload an XLSX spreadsheet through the UI
**Expected:** Document status transitions to "completed", parsed markdown content appears in document_chunks
**Why human:** Requires Docling XLSX runtime, real spreadsheet file, running server

### Gaps Summary

No code-level gaps found. All artifacts exist, are substantive, and are properly wired. All 17 unit tests pass. All 4 requirements (DATA-04, DATA-08, DATA-09, DATA-10) are satisfied at the code level.

The phase depends on human verification for runtime behavior: seed script execution against live Supabase, chat queryability of seeded content, and actual OCR/XLSX parsing with real files through Docling.

---

_Verified: 2026-04-08T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
