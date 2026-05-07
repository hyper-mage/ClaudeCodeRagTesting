---
phase: 04-file-manager-ui
plan: 04
subsystem: frontend-file-manager-dnd-bulk
tags: [frontend, react, dnd-kit, drag-drop, bulk-actions, selection, toast]
requirements:
  completed: [FMGR-05, FMGR-07, FMGR-09]
dependency_graph:
  requires:
    - frontend/src/hooks/useFolderTree.ts (from Plan 04-02)
    - frontend/src/hooks/useDocuments.ts (from earlier phases)
    - frontend/src/components/FolderTree.tsx (from Plans 04-02, 04-03)
    - frontend/src/components/FolderTreeItem.tsx (from Plans 04-02, 04-03)
    - frontend/src/components/FileListRow.tsx (from Plan 04-02)
    - frontend/src/components/FileListView.tsx (from Plans 04-02, 04-03)
    - frontend/src/pages/DocumentsPage.tsx (from Plan 04-03)
    - POST /api/documents/bulk-delete, /api/documents/bulk-move (from Plan 04-01)
  provides:
    - useSelection hook (shift-click range select, derived pruning of stale ids)
    - BulkActionBar component (fixed toolbar with Delete/Move when selection > 0)
    - Drag-and-drop moves for files (file row -> private folder) via @dnd-kit/react
    - Drag-and-drop moves for folders (private tree item -> private folder)
    - External file drop zones (tree folder + file list area) for direct-to-folder upload
    - ToastProvider / useToast (lightweight toast system, auto-dismiss)
  affects:
    - frontend/src/App.tsx (ToastProvider wrap)
    - frontend/src/pages/DocumentsPage.tsx (DragDropProvider, selection, bulk ops, upload refresh, toasts)
    - frontend/src/components/FolderTree.tsx (suppressRootCreate to avoid duplicate inline input)
    - frontend/src/components/FolderTreeItem.tsx (useDraggable + useDroppable + native file drop)
    - frontend/src/components/FileListRow.tsx (useDraggable + checkbox + shift-click toggle)
    - frontend/src/components/FileListView.tsx (BulkActionBar slot, external drop zone)
tech_stack:
  added:
    - "@dnd-kit/react ^0.3.2 (pre-1.0; DragDropProvider, useDraggable, useDroppable APIs)"
  patterns:
    - "Prefixed dnd ids ('file-{uuid}', 'folder-{uuid}') parsed in onDragEnd to route to moveDocument vs moveFolder"
    - "Dual drop-target detection: @dnd-kit isDropTarget for internal DnD, dataTransfer.types.includes('Files') for external OS drags"
    - "Target visibility enforcement at the handler layer (public folders rejected in onDragEnd, not just disabled hook)"
    - "Selection hook derives live Set by filtering against items prop, pruning ids that no longer exist"
    - "Bulk operations validate the entire batch before any storage/DB mutation (atomic rejection)"
    - "Single inline-create input via suppressRootCreate prop to avoid focus-stealing onBlur cancellation when two inputs render at once"
    - "Toast system via context + auto-dismiss timers; surfaces backend duplicate responses and upload status"
key_files:
  created:
    - frontend/src/hooks/useSelection.ts
    - frontend/src/components/BulkActionBar.tsx
    - frontend/src/contexts/ToastContext.tsx
  modified:
    - frontend/package.json
    - frontend/src/App.tsx
    - frontend/src/pages/DocumentsPage.tsx
    - frontend/src/components/FolderTree.tsx
    - frontend/src/components/FolderTreeItem.tsx
    - frontend/src/components/FileListRow.tsx
    - frontend/src/components/FileListView.tsx
decisions:
  - "@dnd-kit/react (0.3.2, pre-1.0) chosen over @dnd-kit/core for its simpler hook-based API; prefixed ids decode source/target kind at drop time"
  - "External file drops detected via dataTransfer.types.includes('Files') to disambiguate from internal @dnd-kit drags on the same element"
  - "Bulk action bar surfaces above file list (not floating) and is keyboard-dismissible via Escape"
  - "Post-upload refresh calls useFolderTree.refreshTree() instead of optimistic insert so dedup/metadata come from the authoritative server state"
  - "Toast system built in-house (no new dep) — context + timers — matching project preference against unnecessary libraries"
  - "Root-level create input rendered only in FileListView when My Documents virtual root is selected; tree input suppressed to prevent focus-stealing"
metrics:
  duration_min: 60
  completed: 2026-04-15
  tasks: 2
  files_touched: 10
---

# Phase 04 Plan 04: DnD + Bulk Actions + Checkpoint Fixes Summary

Drag-and-drop reorganization (via `@dnd-kit/react` for internal moves, native `dataTransfer` for external file drops), multi-select with shift-click range selection, bulk delete/move operations, and a new toast system that surfaces backend duplicate-upload responses. Three post-checkpoint bug fixes applied for root-folder creation, silent duplicate uploads, and stale file list after upload.

## One-liner

Full drag-drop/bulk-select file manager with @dnd-kit, ToastContext for duplicate-upload feedback, and post-upload auto-refresh via `refreshTree()`.

## What Shipped

- **@dnd-kit/react integration** — `DragDropProvider` wraps `DocumentsPage`; `FolderTreeItem` uses `useDroppable` + `useDraggable` (disabled on public folders); `FileListRow` uses `useDraggable`. Prefixed ids (`file-{uuid}`, `folder-{uuid}`) decoded in `onDragEnd` to dispatch to `moveDocument` vs `moveFolder`.
- **External file drop** — native `onDragOver`/`onDrop` on tree folder rows and the file list content area. `dataTransfer.types.includes('Files')` distinguishes OS drags from internal `@dnd-kit` drags. Read-only (public) folders show `cursor-not-allowed` / `dropEffect='none'`.
- **useSelection hook** — `Set<string>` of selected ids, `toggle(id, shiftKey)` with range select from the last-clicked index, `selectAll`/`clearSelection`. Derived pruning keeps the live view in sync when items disappear.
- **BulkActionBar** — appears above the file list when `selected.size > 0`. Shows count, `Delete {N} Items` (routed through `ConfirmDialog` with bulk copy), `Move to...` (routed through `FolderPicker`), and dismisses on `Escape`.
- **Post-checkpoint fixes (see Deviations)** — root-level folder create, duplicate-upload toast, post-upload list refresh.

## Verification Results

- `cd frontend && npx tsc --noEmit` — clean, no errors
- `cd backend && python -m pytest tests/test_folders_api.py -x -q` — 20/20 passing
- ESLint on touched files: one pre-existing `react-refresh/only-export-components` warning in `ToastContext.tsx` matching the existing pattern in `AuthContext.tsx` (out of scope per scope-boundary rule)
- Manual walkthrough checkpoint is now unblocked: the 3 user-reported bugs are fixed

## Deviations from Plan

The plan Task 1 executed as specified and was committed at `e500994`. During the Task 2 human-verify checkpoint, the user reported three bugs that were fixed before closing the plan.

### Auto-fixed Issues

**1. [Rule 1 - Bug] Root-level folder creation silently cancelled**
- **Found during:** Task 2 human verification
- **Issue:** Clicking the `+` in the MY DOCUMENTS tree header, or the "New Folder" toolbar button while the virtual My Documents root was selected, appeared to do nothing. Root cause: when `selectedFolderId === ROOT_PRIVATE_ID`, both `FolderTree` and `FileListView` rendered an `InlineRename` input for the same create-under-root state. The second input to mount stole focus, fired `onBlur` on the first, which called the empty-value-cancel branch of `commit()` and unmounted both.
- **Fix:** Added `suppressRootCreate?: boolean` to `FolderTree`; `DocumentsPage` sets it to `selectedFolderId === ROOT_PRIVATE_ID`. Now exactly one input is rendered at a time: `FolderTree` owns it when no folder (or a real folder) is selected, `FileListView` owns it when the private root is selected.
- **Files modified:** `frontend/src/components/FolderTree.tsx`, `frontend/src/pages/DocumentsPage.tsx`
- **Commit:** `5991075`

**2. [Rule 2 - Missing feedback] Duplicate upload had no user-visible signal**
- **Found during:** Task 2 human verification
- **Issue:** Backend `/api/documents/upload` already returns `{...existing, duplicate: true, message: "This file has already been uploaded"}` for a duplicate content hash, but only the standalone `<FileUpload>` surface (shown when no folder is selected) rendered the inline `info` message. The `FileListView` toolbar upload path and the external-drop-on-tree path swallowed the response silently.
- **Fix:** Added `frontend/src/contexts/ToastContext.tsx` (context + provider + `useToast` hook, auto-dismiss after 4s, variants: info/success/warning/error). Wrapped `App.tsx` with `ToastProvider`. `DocumentsPage.handleUpload` and `handleExternalFileDrop` now inspect the upload result and call `showToast(result.message, 'warning')` for duplicates or `'success'` for new uploads. Errors also raise a toast.
- **Files modified:** `frontend/src/contexts/ToastContext.tsx` (new), `frontend/src/App.tsx`, `frontend/src/pages/DocumentsPage.tsx`
- **Commit:** `5991075`

**3. [Rule 1 - Bug] File list not refreshed after upload**
- **Found during:** Task 2 human verification
- **Issue:** `FileListView.documents` is sourced from `folderContents.documents` on the `useFolderTree` hook, not from `useDocuments.documents`. The Supabase Realtime subscription in `useDocuments` updated that hook's internal `documents` state, but nothing re-fetched `/api/folders/{id}/contents` (or the root-level document list), so the user had to reload to see newly uploaded files.
- **Fix:** Both `handleUpload` and `handleExternalFileDrop` in `DocumentsPage` now `await refreshTree()` after the upload call, which reloads both the folder list and the active folder's contents.
- **Files modified:** `frontend/src/pages/DocumentsPage.tsx`
- **Commit:** `5991075`

All three fixes landed in a single commit (`5991075`) since they share overlapping edits in `DocumentsPage.tsx` (unified toast-aware `handleUpload`/`handleExternalFileDrop` plus the `suppressRootCreate` wire-up).

## Key Files

**Created:**
- `frontend/src/hooks/useSelection.ts` — selection state with shift-range select
- `frontend/src/components/BulkActionBar.tsx` — fixed bar with Delete/Move buttons
- `frontend/src/contexts/ToastContext.tsx` — toast provider + `useToast` hook

**Modified:**
- `frontend/package.json` — `@dnd-kit/react` added
- `frontend/src/App.tsx` — wrapped routes with `ToastProvider`
- `frontend/src/pages/DocumentsPage.tsx` — `DragDropProvider`, selection, bulk, upload refresh, toasts, `suppressRootCreate`
- `frontend/src/components/FolderTree.tsx` — `suppressRootCreate` prop
- `frontend/src/components/FolderTreeItem.tsx` — droppable + draggable + native file drop
- `frontend/src/components/FileListRow.tsx` — draggable + checkbox + shift-click
- `frontend/src/components/FileListView.tsx` — BulkActionBar slot + external drop zone

## Commits

| Hash      | Message                                                             |
| --------- | ------------------------------------------------------------------- |
| `e500994` | feat(04-04): add drag-and-drop, bulk selection, and bulk action bar |
| `5991075` | fix(04-04): address three checkpoint issues in file manager UI      |

## Known Stubs

None. All data is live from the backend; duplicate/error states flow through toasts; new uploads refresh via `refreshTree()`.

## Self-Check: PASSED

- `frontend/src/hooks/useSelection.ts` — FOUND
- `frontend/src/components/BulkActionBar.tsx` — FOUND
- `frontend/src/contexts/ToastContext.tsx` — FOUND
- Commit `e500994` — FOUND
- Commit `5991075` — FOUND
- `npx tsc --noEmit` — clean
- `pytest tests/test_folders_api.py` — 20/20 passing
