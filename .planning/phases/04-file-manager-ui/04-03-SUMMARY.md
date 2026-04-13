---
phase: 04-file-manager-ui
plan: 03
subsystem: frontend-file-manager-interactions
tags: [frontend, react, context-menu, rename, confirm-dialog, folder-picker, portal]
requirements:
  completed: [FMGR-02, FMGR-03, FMGR-04, FMGR-06]
dependency_graph:
  requires:
    - frontend/src/hooks/useFolderTree.ts (from Plan 04-02)
    - frontend/src/components/FolderTree.tsx (from Plan 04-02)
    - frontend/src/components/FolderTreeItem.tsx (from Plan 04-02)
    - frontend/src/components/FileListRow.tsx (from Plan 04-02)
    - frontend/src/components/FileListView.tsx (from Plan 04-02)
    - /api/folders (POST/PATCH/DELETE) from Plan 04-01
    - /api/documents/{id} (PATCH rename, /move) from Plan 04-01
  provides:
    - useContextMenu hook (ContextTarget discriminated union; open/close state)
    - ContextMenu component (portal, viewport-bounds flipping)
    - ContextMenuItem (default + destructive variants)
    - InlineRename (rename mode with select-all + create mode with placeholder)
    - ConfirmDialog (portal modal, Escape + backdrop dismissal)
    - FolderPicker (private-only mini tree with excludeFolderId + root option)
    - useFolderTree CRUD mutations (create/rename/delete/move for folders + docs)
  affects:
    - frontend/src/pages/DocumentsPage.tsx (context menu + modal orchestration)
    - frontend/src/components/FileListView.tsx (toolbar New Folder + inline create row + rename forwarding)
    - frontend/src/components/FolderTreeItem.tsx (double-click rename, inline create pseudo-child)
    - frontend/src/components/FolderTree.tsx (root-level inline create row)
    - frontend/src/components/FileListRow.tsx (double-click rename)
tech_stack:
  added: []
  patterns:
    - "Portal-based overlays (createPortal to document.body) for context menu, confirm dialog, folder picker"
    - "Ref-callback measurement for context menu viewport-bounds flipping (avoids setState-in-effect)"
    - "Discriminated union ContextTarget { type: 'folder' | 'file' } for type-safe menu rendering"
    - "Virtual-root sentinel mapping: ROOT_PRIVATE_ID coerced to null parent_id in mutation helpers"
    - "Inline rename component doubles as inline create (empty defaultValue + placeholder)"
    - "Double-click-to-rename on private items only; context menu suppressed on public (Board Games) items"
key_files:
  created:
    - frontend/src/hooks/useContextMenu.ts
    - frontend/src/components/ContextMenu.tsx
    - frontend/src/components/ContextMenuItem.tsx
    - frontend/src/components/InlineRename.tsx
    - frontend/src/components/ConfirmDialog.tsx
    - frontend/src/components/FolderPicker.tsx
  modified:
    - frontend/src/hooks/useFolderTree.ts
    - frontend/src/components/FolderTree.tsx
    - frontend/src/components/FolderTreeItem.tsx
    - frontend/src/components/FileListRow.tsx
    - frontend/src/components/FileListView.tsx
    - frontend/src/pages/DocumentsPage.tsx
decisions:
  - "Context menu viewport flipping uses ref callback instead of useLayoutEffect+setState to satisfy react-hooks/set-state-in-effect"
  - "Single renamingId / creatingUnderId state lives in DocumentsPage and is passed down; hook handles id-vs-folder dispatch at the callback site"
  - "FolderPicker returns null for ROOT_PRIVATE_ID sentinel so caller always receives real folder id or null (no virtual ids leak to backend)"
  - "Trash-icon click on FileListRow now routes through ConfirmDialog instead of silently deleting"
  - "New subfolder context menu action auto-expands the parent folder so the inline input is visible"
metrics:
  duration_seconds: 900
  tasks: 3
  files_created: 6
  files_modified: 6
  tests_added: 0
  commits: 4
  completed_at: "2026-04-13T15:35:00Z"
---

# Phase 04 Plan 03: Context Menus, Inline Rename, Confirm & Folder Picker Summary

Wires right-click context menus, inline rename (double-click + menu), inline folder creation (root + subfolder + toolbar), delete confirmation dialogs, and a folder-picker mini-tree for Move operations into the file manager UI. Replaces any `window.prompt` with styled inline/modal UX per UI-SPEC.

## What Was Built

- **`useContextMenu.ts`** -- Portal-friendly state hook returning `{ menu, openMenu, closeMenu }`. `ContextTarget` is a discriminated union (`{ type: 'folder', node }` | `{ type: 'file', doc }`). Installs document-level click + Escape listeners while open.
- **`ContextMenu.tsx`** -- Portal to `document.body`, fixed position, viewport-bounds flipping via ref callback (no setState-in-effect). Stops propagation so inner clicks don't close it.
- **`ContextMenuItem.tsx`** -- 32px-minimum click target, default (`text-gray-300 hover:bg-gray-800`) + destructive (`text-red-400 hover:bg-red-600/20`) variants.
- **`InlineRename.tsx`** -- Dual-purpose input: when `currentName` present, auto-selects; when absent, shows `placeholder`. Enter commits (trimmed, non-empty, different), Escape cancels, onBlur commits.
- **`ConfirmDialog.tsx`** -- Portal modal with `bg-black/50` backdrop, AlertTriangle icon, bg-red-600 confirm button. Escape + backdrop click trigger cancel. Copywriting supplied by caller.
- **`FolderPicker.tsx`** -- Portal modal with private-folder mini tree, "My Documents (root)" option, `excludeFolderId` to prevent moving a folder into itself, expand/collapse on rows, Move Here / Cancel footer.
- **`useFolderTree.ts`** -- Added `createFolder`, `renameFolder`, `deleteFolder`, `moveFolder`, `moveDocument`, `renameDocument`. Virtual-root sentinels (`ROOT_PRIVATE_ID` / `ROOT_PUBLIC_ID`) are coerced to `null` before hitting the API. Deleting the currently-selected folder deselects automatically.
- **`FolderTreeItem.tsx`** -- Double-click on a private folder's name triggers `onStartRename`; renders `InlineRename` when `renamingId` matches. When `creatingUnderId === node.id`, an extra pseudo-child row with `InlineRename` (placeholder "New folder name") is rendered at `depth + 1`. Recursive props propagate to children.
- **`FolderTree.tsx`** -- MY DOCUMENTS "+" button calls `onStartCreate(ROOT_PRIVATE_ID)`. When `creatingUnderId === ROOT_PRIVATE_ID`, renders an inline creation row above the private roots (depth 0).
- **`FileListRow.tsx`** -- Double-click filename triggers `onStartRename(doc.id)`; renders `InlineRename` when `isRenaming`.
- **`FileListView.tsx`** -- Toolbar "New Folder" now calls `onStartCreate()`. When `creatingInCurrentFolder`, an inline creation row (folder icon + InlineRename + FOLDER badge) is prepended to the subfolder list. Rename props forwarded to each FileListRow.
- **`DocumentsPage.tsx`** -- Central state machine: `renamingId`, `creatingUnderId`, `confirmDelete`, `movingItem`. Wires context menu handlers to suppress public folders and virtual roots. Dispatches rename based on whether the id is a folder (found in `rawFolders`) or a document. Trash-icon click in FileListRow now routes through ConfirmDialog.

## Task Timeline

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create interaction primitives (hook + 5 components) | `d443466` | `useContextMenu.ts`, `ContextMenu.tsx`, `ContextMenuItem.tsx`, `InlineRename.tsx`, `ConfirmDialog.tsx`, `FolderPicker.tsx` |
| 2a | Extend useFolderTree with mutations; wire rename/create into tree + row components | `c3e5dc0` | `useFolderTree.ts`, `FolderTreeItem.tsx`, `FolderTree.tsx`, `FileListRow.tsx` |
| 2b | Wire ContextMenu, ConfirmDialog, FolderPicker into DocumentsPage + FileListView | `8fc2831` | `DocumentsPage.tsx`, `FileListView.tsx` |
| 2b.fix | Replace setState-in-effect with ref callback in ContextMenu | `df29b27` | `ContextMenu.tsx` |

## Verification Results

- `cd frontend && npx tsc --noEmit` -- PASS (no errors)
- `cd frontend && npx eslint` (on the 12 files touched by this plan) -- PASS after the Task 2b.fix commit
- `grep -r "window.prompt" frontend/src` -- no matches
- Acceptance criteria checks:
  - `useContextMenu.ts` contains `export type ContextTarget` and `e.preventDefault()` -- OK
  - `ContextMenu.tsx` contains `createPortal` and `bg-gray-900 border border-gray-700` -- OK
  - `ContextMenuItem.tsx` contains `text-red-400` (destructive variant) -- OK
  - `InlineRename.tsx` contains `onConfirm`, `onCancel`, `select()`, `placeholder` -- OK
  - `ConfirmDialog.tsx` contains `createPortal`, `bg-red-600 hover:bg-red-700`, `bg-black/50` -- OK
  - `FolderPicker.tsx` contains `Move to`, `Move Here`, `createPortal` -- OK
  - `DocumentsPage.tsx` contains `useContextMenu`, `<ContextMenu`, `<ConfirmDialog`, `<FolderPicker`, `Delete File`, `Delete Folder`, `setCreatingUnderId` -- OK
  - No `window.prompt` anywhere -- OK

## Must-Haves Verification

All 8 must-have truths from the plan:

- [x] Right-clicking a private folder or file shows a context menu with Rename, Delete, Move to options -- `DocumentsPage.tsx` context menu blocks
- [x] Right-clicking a folder also shows New subfolder option -- first menu item for folder target
- [x] No context menu appears on Board Games folders -- `handleFolderContextMenu` / `handleListContextMenu` return early when `visibility === 'public'`
- [x] Selecting Rename enters inline edit mode; Enter confirms, Escape cancels -- `InlineRename.tsx` keydown handler
- [x] Selecting Delete shows a confirmation dialog with folder/file name and content counts -- `ConfirmDialog` body string interpolation
- [x] Selecting Move to opens a folder picker mini-tree to choose destination -- `FolderPicker.tsx`
- [x] User can create new folders via context menu New subfolder (inline row in tree) or toolbar New Folder button (inline row in content panel) -- tree + FileListView inline rows
- [x] Folder creation never uses window.prompt; an inline input row is rendered under the chosen parent -- `grep -r "window.prompt" frontend/src` returns no matches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] setState-in-effect lint error in ContextMenu positioning**
- **Found during:** Final lint sweep after Task 2b
- **Issue:** `useLayoutEffect` + `setPos` pattern triggered `react-hooks/set-state-in-effect` (repo's ESLint 9 config blocks this pattern).
- **Fix:** Replaced with a `useCallback` ref that mutates `el.style.top`/`el.style.left` directly once the menu is measured. Same viewport-bounds behavior, no cascading render.
- **Files modified:** `frontend/src/components/ContextMenu.tsx`
- **Commit:** `df29b27`

**2. [Rule 2 - Missing functionality] Trash-icon click on FileListRow now confirms**
- **Found during:** Wiring delete flow in Task 2b
- **Issue:** The existing hover-revealed `Trash2` button called `onDelete` directly, bypassing the new ConfirmDialog. That would leave two different delete paths with inconsistent UX (dialog from context menu, silent from trash icon).
- **Fix:** `onDeleteDoc` in `DocumentsPage` now routes to `setConfirmDelete({ type: 'file', ... })` instead of calling `deleteDocument` directly. Both entry points go through the dialog.
- **Files modified:** `frontend/src/pages/DocumentsPage.tsx`

**3. [Rule 2 - Missing functionality] Auto-expand parent when "New subfolder" chosen from context menu**
- **Found during:** Wiring context menu
- **Issue:** If the user right-clicked a collapsed folder and selected "New subfolder", the inline input would be rendered as a pseudo-child but hidden because the folder wasn't expanded.
- **Fix:** In the "New subfolder" ContextMenuItem handler, call `toggleExpand(node.id)` if the folder is not already expanded.
- **Files modified:** `frontend/src/pages/DocumentsPage.tsx`

## Known Stubs

None. All interactions (context menu, rename, create, delete, move) are wired end-to-end against the Plan 04-01 backend endpoints.

Scaffolding that remains deliberately unwired (tracked for Plan 04-04):
- Checkbox placeholders in FileListRow / FileListView subfolder rows -- reserved 16px slot for bulk selection.
- Drag-and-drop on tree items / file rows -- not yet attached (Plan 04-04).

## Follow-up

- Plan 04-04: drag-and-drop and bulk selection -- will use the checkbox slot, add drop targets on tree items, and render a BulkActionBar when items are selected.

## Self-Check: PASSED

- `frontend/src/hooks/useContextMenu.ts` -- FOUND
- `frontend/src/components/ContextMenu.tsx` -- FOUND
- `frontend/src/components/ContextMenuItem.tsx` -- FOUND
- `frontend/src/components/InlineRename.tsx` -- FOUND
- `frontend/src/components/ConfirmDialog.tsx` -- FOUND
- `frontend/src/components/FolderPicker.tsx` -- FOUND
- `frontend/src/hooks/useFolderTree.ts` -- MODIFIED (6 new mutations exported)
- `frontend/src/components/FolderTree.tsx` -- MODIFIED (inline create row + rename props)
- `frontend/src/components/FolderTreeItem.tsx` -- MODIFIED (double-click rename, pseudo-child create row)
- `frontend/src/components/FileListRow.tsx` -- MODIFIED (double-click rename)
- `frontend/src/components/FileListView.tsx` -- MODIFIED (toolbar onStartCreate, inline create row, rename forwarding)
- `frontend/src/pages/DocumentsPage.tsx` -- MODIFIED (context menu + modal orchestration)
- Commit `d443466` -- FOUND
- Commit `c3e5dc0` -- FOUND
- Commit `8fc2831` -- FOUND
- Commit `df29b27` -- FOUND
