# Phase 4: File Manager UI - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a file manager-style UI for the Documents page: tree sidebar with folder hierarchy, folder CRUD operations, drag-and-drop file/folder management, right-click context menus, bulk selection, and breadcrumb navigation. Covers requirements FMGR-01 through FMGR-10 plus DATA-02. No agent intelligence changes (Phase 6), no explorer sub-agent (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Tree Sidebar Layout
- **D-01:** Replace the current flat `DocumentList` sidebar with a folder tree component. Same two-column layout: tree sidebar on left (w-64), content panel on right.
- **D-02:** Two top-level roots in the tree: "Board Games" (default KB, public) and "My Documents" (user uploads, private). Both expandable/collapsible.
- **D-03:** Board Games folders appear with a lock/shield icon and muted text color. Read-only — no rename, delete, move, upload, or folder creation allowed within the Board Games tree.
- **D-04:** Clicking a folder in the tree shows its contents in the right panel as a list view with breadcrumb navigation (FMGR-10).
- **D-05:** Right panel shows folder contents as a table-style list: filename, status badge, type, size. Upload button in toolbar + drop-to-upload within the file list area.
- **D-06:** When no folder is selected (initial page load), the right panel shows the existing FileUpload drop zone. Uploads go to My Documents root.

### Drag-and-Drop
- **D-07:** Full drag-and-drop: move files between folders, move folders within the tree, drop external files onto a folder in the tree to upload into that folder (FMGR-09).
- **D-08:** Drag-drop works in both the tree sidebar (folders as drop targets) and the right panel file list (drag sources for files, drop target for uploads).
- **D-09:** Visual feedback: valid drop targets get a blue highlight border, dragged items show a semi-transparent ghost, invalid targets (Board Games folders) show a "not allowed" cursor.

### Context Menus & Interactions
- **D-10:** Custom right-click context menu on tree items and file list rows. Overrides browser default. Styled dropdown with actions: Rename, Delete, Move to..., New subfolder (on folders only).
- **D-11:** Bulk selection via checkboxes + shift-click for range select. Toolbar appears with bulk actions (delete, move to folder) when items are selected (FMGR-07).
- **D-12:** Inline rename: double-click or context menu "Rename" turns name into an editable text input in-place. Enter to confirm, Escape to cancel.

### Folder CRUD Backend
- **D-13:** New backend API endpoints for folder operations: create, rename, delete, move. Add to a new `folders.py` router or extend `documents.py`.
- **D-14:** Cascade delete: deleting a folder deletes all contained documents, their chunks, and storage files. Confirmation dialog on frontend lists folder contents before proceeding.
- **D-15:** Move operations update only the `folder_id` in the documents table (and ltree path for folders). Storage paths stay as-is — they're keyed by `user_id/doc_id`, not folder path.
- **D-16:** Board Games tree is entirely read-only for users. Backend enforces this — reject create/rename/delete/move operations targeting public-visibility folders.

### Claude's Discretion
- Tree component library choice (custom implementation vs lightweight library)
- Context menu component implementation (custom or library)
- Drag-and-drop library selection (HTML5 drag API vs react-dnd vs @dnd-kit)
- Folder API endpoint structure and naming
- How to handle ltree path updates on folder move (recursive update strategy)
- Loading states and animations for tree expansion
- Keyboard navigation within the tree (accessibility)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Database Schema (from Phase 1)
- `supabase/migrations/018_create_folders_table.sql` -- Folders table with ltree paths, Board Games root folder, My Documents creation
- `supabase/migrations/019_add_visibility_and_folder.sql` -- visibility/folder_id columns on documents, sync triggers
- `supabase/migrations/020_update_rls_policies.sql` -- Mixed-visibility RLS policies (enforces read-only for public content)

### Current Frontend (to be modified)
- `frontend/src/pages/DocumentsPage.tsx` -- Current two-column layout (DocumentList + FileUpload)
- `frontend/src/components/DocumentList.tsx` -- Flat file list with status badges and delete (to be replaced by tree)
- `frontend/src/components/FileUpload.tsx` -- Drag-drop upload component (reuse/integrate)
- `frontend/src/hooks/useDocuments.ts` -- Document CRUD hook with Realtime subscription (extend for folders)
- `frontend/src/components/IconSidebar.tsx` -- App-level nav sidebar (unchanged, for layout reference)
- `frontend/src/App.tsx` -- Route definitions and AuthenticatedLayout wrapper

### Backend (to be extended)
- `backend/routers/documents.py` -- Document upload/list/delete endpoints (folder_id already accepted on upload)
- `backend/database.py` -- Supabase service role client
- `backend/auth.py` -- JWT auth middleware (get_user_id dependency)

### Prior Phase Context
- `.planning/phases/01-data-foundation-and-schema/01-CONTEXT.md` -- D-05 through D-09: folder schema decisions, ltree, system user
- `.planning/phases/03-kb-navigation-tools/03-CONTEXT.md` -- D-04/D-05: path conventions (Board Games/ and My Documents/ roots)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FileUpload.tsx`: Drag-drop upload with file type validation — integrate into folder content view
- `DocumentList.tsx`: Status badge styling (`STATUS_STYLES` map) — reuse in new file list view
- `useDocuments.ts`: Supabase Realtime subscription pattern — extend for folder changes
- `useAuth` / `AuthContext`: Auth state for API calls
- Lucide icons (`lucide-react`): Folder, FolderOpen, File, Lock, Trash2, Pencil, Plus, Move, etc.

### Established Patterns
- Two-column layout in `DocumentsPage.tsx` (sidebar w-64 + flex-1 main area)
- `useCallback` + `useState` hooks for CRUD operations
- Backend `Depends(get_user_id)` for auth on all endpoints
- Tailwind dark theme: bg-gray-950/900/800, text-gray-200/300/500, border-gray-800
- No component library (no shadcn/ui directory) — all components are hand-written

### Integration Points
- `DocumentsPage.tsx`: Replace `DocumentList` with tree component, make right panel context-sensitive
- `useDocuments.ts`: Add folder fetching, folder CRUD, file move operations
- `documents.py` router: `folder_id` param already wired on upload — extend list endpoint to filter by folder
- New router needed: folder CRUD endpoints (create, rename, delete, move)
- `folders` table: ltree paths need updating on folder move (recursive)

</code_context>

<specifics>
## Specific Ideas

- Tree should feel like a lightweight desktop file manager (VS Code sidebar inspiration)
- Board Games lock icon should be subtle, not obtrusive — muted text + small icon is enough
- Breadcrumb should be clickable to navigate up the hierarchy (each segment is a link)
- Upload zone as default right panel gives existing users a familiar starting point before they explore folders

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 04-file-manager-ui*
*Context gathered: 2026-04-10*
