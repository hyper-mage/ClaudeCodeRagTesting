---
phase: 04-file-manager-ui
plan: 02
subsystem: frontend-file-manager-ui
tags: [frontend, react, file-manager, tree, breadcrumb, tailwind]
requirements:
  completed: [DATA-02, FMGR-01, FMGR-08, FMGR-10]
dependency_graph:
  requires:
    - /api/folders (GET)
    - /api/folders/{id}/contents (GET)
    - /api/documents (GET)
    - /api/documents/upload (POST, with folder_id)
  provides:
    - useFolderTree hook (tree state, fetching, breadcrumbs)
    - FolderTree sidebar (two-root structure with section headers)
    - FolderTreeItem recursive tree node
    - FileListView right-panel content + toolbar
    - FileListRow file row
    - Breadcrumb navigation
  affects:
    - frontend/src/pages/DocumentsPage.tsx (full rewrite, DocumentList removed)
    - frontend/src/components/FileUpload.tsx (folderId prop)
    - frontend/src/hooks/useDocuments.ts (folder_id in uploadDocument)
tech_stack:
  added: []
  patterns:
    - "Two virtual root nodes (root-public, root-private) overlay flat folder API response"
    - "buildTree(): O(n) map-based nesting of flat folder rows"
    - "useMemo for tree derivation and breadcrumb computation"
    - "Private root view reuses /api/documents (root-level docs where folder_id is null)"
    - "Public folders visually muted (text-gray-500 + Shield icon) per D-03/FMGR-08"
key_files:
  created:
    - frontend/src/hooks/useFolderTree.ts
    - frontend/src/components/FolderTree.tsx
    - frontend/src/components/FolderTreeItem.tsx
    - frontend/src/components/FileListView.tsx
    - frontend/src/components/FileListRow.tsx
    - frontend/src/components/Breadcrumb.tsx
  modified:
    - frontend/src/pages/DocumentsPage.tsx
    - frontend/src/components/FileUpload.tsx
    - frontend/src/hooks/useDocuments.ts
decisions:
  - "Two virtual root folder nodes (root-public/root-private) materialized in hook rather than on server"
  - "Root-level 'My Documents' pulls via /api/documents and filters for folder_id == null (documents without a folder)"
  - "STATUS_STYLES inlined in FileListRow (kept private to satisfy react-refresh/only-export-components)"
  - "renderIcon helper returns JSX directly to avoid dynamic component tag (react-hooks/static-components)"
metrics:
  duration_seconds: 420
  tasks: 2
  files_created: 6
  files_modified: 3
  tests_added: 0
  commits: 2
  completed_at: "2026-04-13T15:18:05Z"
---

# Phase 04 Plan 02: File Manager UI — Tree Sidebar + Content Panel Summary

Delivers the two-column file manager layout: tree sidebar with BOARD GAMES (public, muted, Shield) and MY DOCUMENTS roots, right-panel content with breadcrumb + file list + toolbar, and the existing FileUpload drop zone when no folder is selected.

## What Was Built

- **`frontend/src/hooks/useFolderTree.ts`** — Fetches `/api/folders`, builds tree via `buildTree()`, wraps with two virtual roots, tracks `selectedFolderId`, `expandedIds` (initially both roots expanded), `folderContents`, and derives `breadcrumbs` by walking the parent chain.
- **`frontend/src/components/FolderTree.tsx`** — Sidebar with two section headers ("BOARD GAMES", "MY DOCUMENTS") using `text-xs uppercase tracking-wider text-gray-400`, plus `+` button next to My Documents for creating a root-level folder.
- **`frontend/src/components/FolderTreeItem.tsx`** — Recursive tree row with chevron (ChevronRight / ChevronDown), Folder / FolderOpen icon, Shield icon + `text-gray-500` styling for public folders, 16px-per-depth indent, selected/hover states.
- **`frontend/src/components/Breadcrumb.tsx`** — Clickable segments (`text-xs text-gray-400 hover:text-gray-200`), `/` separators in `text-gray-600`, last segment unclickable (`text-gray-200`).
- **`frontend/src/components/FileListRow.tsx`** — Columns: checkbox placeholder, mime-based icon, filename, status badge (reusing status color map), type (uppercase extension), human-readable size, hover-revealed Trash2 delete.
- **`frontend/src/components/FileListView.tsx`** — Toolbar with "Upload File" + "New Folder" (hidden when `isReadOnly`), subfolder rows + FileListRow list, empty states ("This folder is empty" / "No documents in this folder yet."), loading state.
- **`frontend/src/pages/DocumentsPage.tsx`** — Rewritten: w-64 tree sidebar + flex-1 content panel. When `selectedFolderId` is null, renders centered FileUpload; otherwise Breadcrumb + FileListView.
- **`frontend/src/components/FileUpload.tsx`** — Accepts `folderId` prop and forwards to `onUpload(file, folderId)`.
- **`frontend/src/hooks/useDocuments.ts`** — `uploadDocument(file, folderId?)` appends `folder_id` to FormData when provided.

## Task Timeline

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | useFolderTree hook + FolderTree + FolderTreeItem | `f5235ed` | `frontend/src/hooks/useFolderTree.ts`, `frontend/src/components/FolderTree.tsx`, `frontend/src/components/FolderTreeItem.tsx` |
| 2 | Breadcrumb, FileListRow, FileListView, DocumentsPage rewrite, FileUpload folderId, useDocuments folder_id | `f0304e2` | `frontend/src/components/Breadcrumb.tsx`, `frontend/src/components/FileListRow.tsx`, `frontend/src/components/FileListView.tsx`, `frontend/src/pages/DocumentsPage.tsx`, `frontend/src/components/FileUpload.tsx`, `frontend/src/hooks/useDocuments.ts` |

## Verification Results

- `cd frontend && npx tsc --noEmit` — PASS (no errors)
- `cd frontend && npm run lint` — 3 pre-existing errors remain (FileUpload `any`, AuthContext non-component export, ChatPage setState-in-effect). No new lint errors introduced by this plan. Pre-existing errors are out of scope for Plan 04-02.

## Must-Haves Verification

All 6 must-have truths from the plan:

- [x] User sees a tree sidebar with two roots: BOARD GAMES (public, read-only) and MY DOCUMENTS (private) — `FolderTree.tsx` section headers
- [x] Clicking a folder shows contents in right panel as file list table — `selectFolder` -> `loadContents` -> `FileListView`
- [x] Board Games folders display with Shield icon and muted `text-gray-500` styling — `FolderTreeItem.tsx` `isPublic` branch
- [x] Breadcrumb shows clickable path segments for current folder — `Breadcrumb.tsx` + `useFolderTree.breadcrumbs`
- [x] When no folder selected, right panel shows the existing FileUpload drop zone — `DocumentsPage.tsx` ternary
- [x] File list shows filename, status badge, type, and size columns — `FileListRow.tsx`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `renderIcon` helper instead of dynamic component tag**
- **Found during:** Task 2 lint
- **Issue:** `const Icon = iconForMime(...)` followed by `<Icon ... />` triggered `react-hooks/static-components` lint error (component created during render).
- **Fix:** Replaced with `renderIcon(mime)` function returning JSX directly.
- **Files modified:** `frontend/src/components/FileListRow.tsx`
- **Commit:** `f0304e2`

**2. [Rule 1 — Bug] `STATUS_STYLES` not re-exported**
- **Found during:** Task 2 lint
- **Issue:** Exporting a const alongside default-exported component triggers `react-refresh/only-export-components`.
- **Fix:** Kept `STATUS_STYLES` as module-local const (matches values from original `DocumentList`).
- **Files modified:** `frontend/src/components/FileListRow.tsx`
- **Commit:** `f0304e2`

**3. [Rule 1 — Bug] Replaced `any` in new component props with `unknown` / union types**
- **Found during:** Task 2 lint
- **Issue:** `any` in new `FileListView` `Props` (`onUpload`, `onContextMenu`) triggered `@typescript-eslint/no-explicit-any`.
- **Fix:** `Promise<unknown>` for onUpload; `FolderNode | Document` for context menu target.
- **Files modified:** `frontend/src/components/FileListView.tsx`
- **Commit:** `f0304e2`

## Known Stubs

- **`FolderTree.onCreateRootFolder` / `FileListView.onNewFolder` buttons** — wired to optional callbacks but no handler provided yet from `DocumentsPage`. Plan 04-03 (context menus, rename, create) will attach these.
- **`onContextMenu` in tree/list components** — optional prop, not consumed by `DocumentsPage` yet. Plan 04-03 will attach it.
- **Checkbox placeholder div in FileListRow / FileListView subfolder rows** — reserves 16px width for Plan 04-04 bulk selection.

These are intentional scaffolding points for subsequent plans in this phase, not missing functionality for Plan 04-02's goal.

## Follow-up

- Plan 04-03: context menus, inline rename, new folder, move dialog — will connect `onContextMenu`, `onCreateRootFolder`, `onNewFolder` callbacks.
- Plan 04-04: drag-and-drop and bulk selection — will use the checkbox placeholder slot.

## Self-Check: PASSED

- `frontend/src/hooks/useFolderTree.ts` — FOUND
- `frontend/src/components/FolderTree.tsx` — FOUND
- `frontend/src/components/FolderTreeItem.tsx` — FOUND
- `frontend/src/components/FileListView.tsx` — FOUND
- `frontend/src/components/FileListRow.tsx` — FOUND
- `frontend/src/components/Breadcrumb.tsx` — FOUND
- `frontend/src/pages/DocumentsPage.tsx` — MODIFIED (FolderTree + Breadcrumb + FileListView; no DocumentList)
- `frontend/src/components/FileUpload.tsx` — MODIFIED (folderId prop)
- `frontend/src/hooks/useDocuments.ts` — MODIFIED (folder_id FormData)
- Commit `f5235ed` — FOUND
- Commit `f0304e2` — FOUND
