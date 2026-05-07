---
phase: 04-file-manager-ui
plan: 01
subsystem: backend-folder-api
tags: [folders, documents, api, ltree, rls, pydantic]
requirements:
  completed: [FMGR-02, FMGR-03, FMGR-04, FMGR-07, FMGR-08]
dependency_graph:
  requires:
    - supabase/migrations/018_create_folders_table.sql
    - backend/auth.py
    - backend/database.py
  provides:
    - POST/GET/PATCH/DELETE /api/folders endpoints
    - GET /api/folders/{id}/contents endpoint
    - PATCH /api/folders/{id}/move endpoint
    - PATCH /api/documents/{id} rename endpoint
    - PATCH /api/documents/{id}/move endpoint
    - POST /api/documents/bulk-delete endpoint
    - POST /api/documents/bulk-move endpoint
  affects:
    - backend/main.py (registers folders router)
tech_stack:
  added: []
  patterns:
    - "ltree path scheme: my_documents.{sanitized_label} for private roots"
    - "Recursive descendant path update on folder rename/move via LIKE prefix match"
    - "Read-only enforcement: visibility=='public' -> 403 on all mutations"
    - "Storage cleanup before DB delete (FK cascade handles children + chunks)"
    - "FastAPI dependency_overrides + patched get_supabase for router unit tests"
key_files:
  created:
    - backend/models/folder_models.py
    - backend/routers/folders.py
    - backend/tests/test_folders_api.py
  modified:
    - backend/routers/documents.py
    - backend/main.py
decisions:
  - "Kept _sanitize_label inline in folders.py (not extracted to utils) -- only used in this router"
  - "Moved doc to root (folder_id=null) skips target validation -- root has no folder to check"
  - "Bulk ops validate ALL items before any mutation; on any failure, entire batch rejected before storage/DB writes"
  - "Used MagicMock-based chain fakes in tests instead of introducing a Supabase mocking library"
metrics:
  duration_seconds: 251
  tasks: 2
  files_created: 3
  files_modified: 2
  tests_added: 20
  tests_passing: 20
  commits: 2
  completed_at: "2026-04-13T15:11:48Z"
---

# Phase 04 Plan 01: Backend Folder + Document Mutation API Summary

Folder CRUD router (list/create/rename/move/delete/contents) and extended documents router (rename/move/bulk-delete/bulk-move) with ltree path management, read-only enforcement on public folders/documents, cascade storage cleanup, and 20 unit tests — all passing.

## What Was Built

- **`backend/models/folder_models.py`** — Pydantic request models (`FolderCreate`, `FolderRename`, `FolderMove`) plus `FolderResponse`.
- **`backend/routers/folders.py`** — Six endpoints under `/api/folders`:
  - `GET /` — flat list of user-private + public folders (ordered by path)
  - `POST /` — create private folder; uses `my_documents.{label}` for root, `{parent.path}.{label}` otherwise
  - `GET /{id}/contents` — folder + subfolders + documents
  - `PATCH /{id}` — rename; updates label in ltree path and cascades to descendants
  - `PATCH /{id}/move` — move to new parent (or root); updates self + all descendant paths
  - `DELETE /{id}` — cascade delete; removes storage files for all docs in folder + descendants before DB delete
- **`backend/routers/documents.py`** — Added rename (`PATCH /{id}`), move (`PATCH /{id}/move`), bulk-delete (`POST /bulk-delete`), bulk-move (`POST /bulk-move`).
- **`backend/main.py`** — Registered folders router.
- **`backend/tests/test_folders_api.py`** — 20 unit tests using FastAPI `TestClient`, dependency override for auth, and `patch`-based Supabase mocks.

## Task Timeline

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Folder models + folder router + extend documents router + register in main | `a457869` | `backend/models/folder_models.py`, `backend/routers/folders.py`, `backend/routers/documents.py`, `backend/main.py` |
| 2 | 20 unit tests for folder and document mutation endpoints | `329ae3f` | `backend/tests/test_folders_api.py` |

## Verification Results

- `python -c "from models.folder_models import FolderCreate, FolderRename, FolderMove, FolderResponse"` — OK
- `python -c "from routers.folders import router"` — OK
- `python -c "from routers.documents import router"` — OK
- `python -c "from main import app; print([r.path for r in app.routes])"` — includes:
  - `/api/folders`, `/api/folders/{folder_id}`, `/api/folders/{folder_id}/contents`, `/api/folders/{folder_id}/move`
  - `/api/documents/{doc_id}` (PATCH), `/api/documents/{doc_id}/move`, `/api/documents/bulk-delete`, `/api/documents/bulk-move`
- `python -m pytest tests/test_folders_api.py -v` — **20 passed** in 1.72s

## Must-Haves Verification

All 13 must-have truths from the plan are implemented:

- [x] POST /api/folders creates a private folder with correct ltree path (`my_documents.{label}` root; `{parent.path}.{label}` nested)
- [x] PATCH /api/folders/{id} renames a folder and updates ltree path (last segment + descendants)
- [x] PATCH /api/folders/{id}/move moves folder and updates all descendant ltree paths
- [x] DELETE /api/folders/{id} cascade-deletes folder, child folders, documents, chunks, and storage files
- [x] All folder mutation endpoints reject operations on public-visibility folders with 403
- [x] GET /api/folders returns all user-private + public folders as flat list
- [x] GET /api/folders/{id}/contents returns subfolders + documents for a folder
- [x] PATCH /api/documents/{id} renames a private document; public documents rejected with 403
- [x] PATCH /api/documents/{id}/move moves a private document to a target private folder (or root); public targets/sources rejected with 403
- [x] POST /api/documents/bulk-delete deletes multiple owned documents in a single request
- [x] POST /api/documents/bulk-move moves multiple owned documents to a target private folder (or root) in a single request
- [x] Private root folder path uses scheme `my_documents.{sanitized_name}` per RESEARCH Pattern 3

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes, no architectural checkpoints, no auth gates.

## Known Stubs

None. All endpoints wired end-to-end; frontend integration is covered in subsequent plans in this phase.

## Follow-up

- Plan 04-02+ will build the frontend file manager UI against these endpoints.
- Real Supabase integration tests (vs. these mock-based unit tests) can live in a separate e2e suite once auth fixtures are set up.

## Self-Check: PASSED

- `backend/models/folder_models.py` — FOUND
- `backend/routers/folders.py` — FOUND
- `backend/tests/test_folders_api.py` — FOUND
- `backend/routers/documents.py` — MODIFIED (rename/move/bulk endpoints present)
- `backend/main.py` — MODIFIED (folders router registered)
- Commit `a457869` — FOUND
- Commit `329ae3f` — FOUND
