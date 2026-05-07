---
phase: 02-default-kb-and-ingestion-extensions
plan: 01
subsystem: api, ingestion, ui
tags: [docling, ocr, xlsx, image-parsing, fastapi, react, file-upload]

requires:
  - phase: 01-rls-and-folder-schema
    provides: folder_id and visibility columns on documents table

provides:
  - IMAGE (JPG/PNG) and XLSX format support in Docling parsing pipeline
  - folder_id and visibility propagation in upload endpoint
  - Extended frontend file picker accepting image and spreadsheet types

affects: [02-02-kb-schema-and-folder-ui, 02-03-seed-default-kb]

tech-stack:
  added: [pytest, ImageFormatOption, ExcelFormatOption]
  patterns: [module-level mime_map dict for testability, TDD with AST-based test assertions]

key-files:
  created:
    - backend/tests/test_parsing_formats.py
    - backend/tests/test_upload_folder.py
    - backend/tests/__init__.py
  modified:
    - backend/services/parsing_service.py
    - backend/routers/documents.py
    - backend/requirements.txt
    - frontend/src/components/FileUpload.tsx

key-decisions:
  - "Moved mime_map to module-level constant in documents.py for direct import in tests"
  - "Used AST inspection for folder_id/visibility tests to avoid needing full Supabase mocking"

patterns-established:
  - "Module-level mime_map: extracting inline dicts to module scope for testability"
  - "AST-based testing: inspecting function source AST to verify dict contents without runtime dependencies"

requirements-completed: [DATA-08, DATA-09, DATA-10]

duration: 6min
completed: 2026-04-08
---

# Phase 02 Plan 01: Ingestion Format Extensions Summary

**IMAGE OCR and XLSX parsing via Docling with folder_id/visibility propagation in upload endpoint**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-08T17:16:06Z
- **Completed:** 2026-04-08T17:22:30Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Extended Docling converter with ImageFormatOption and ExcelFormatOption for JPG/PNG OCR and XLSX parsing
- Added folder_id (optional) and visibility=private fields to document upload INSERT
- Updated frontend FileUpload component to accept .jpg, .jpeg, .png, .xlsx file types
- Created 9 passing tests covering format registration, MIME map entries, and folder_id propagation

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for IMAGE/XLSX and folder_id** - `4ee0e03` (test)
2. **Task 1 GREEN: Extend parsing and upload router** - `69816b5` (feat)
3. **Task 2: Update frontend FileUpload** - `6f5efc8` (feat)

## Files Created/Modified
- `backend/services/parsing_service.py` - Added IMAGE/XLSX to _FILE_BASED dict and Docling converter format options
- `backend/routers/documents.py` - Extended mime_map, added folder_id Form param, added visibility=private to INSERT
- `backend/requirements.txt` - Added pytest dependency
- `frontend/src/components/FileUpload.tsx` - Updated ACCEPTED_TYPES, accept attr, display text, error message
- `backend/tests/test_parsing_formats.py` - Tests for format registration and MIME map entries
- `backend/tests/test_upload_folder.py` - Tests for folder_id signature and INSERT dict contents
- `backend/tests/__init__.py` - Package marker for test discovery

## Decisions Made
- Moved mime_map from inline local variable to module-level constant for direct test import
- Used AST inspection in test_upload_folder.py to verify INSERT dict contents without requiring Supabase mocking

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- IMAGE and XLSX formats ready for ingestion pipeline use in seed script (Plan 03)
- folder_id parameter ready for folder-aware uploads (Plan 02)
- Frontend accepts new file types for user uploads

---
## Self-Check: PASSED

All 6 files verified present. All 3 commits verified in git log.

---
*Phase: 02-default-kb-and-ingestion-extensions*
*Completed: 2026-04-08*
