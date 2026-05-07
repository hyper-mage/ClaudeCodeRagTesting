# Phase 4: File Manager UI - Research

**Researched:** 2026-04-10
**Domain:** React file manager UI with tree sidebar, drag-and-drop, context menus, folder CRUD backend
**Confidence:** HIGH

## Summary

Phase 4 replaces the flat DocumentList sidebar with a full file-manager-style interface: recursive tree sidebar with two roots (Board Games read-only, My Documents editable), right-panel file list with breadcrumbs, drag-and-drop for reorganizing files and folders, right-click context menus, bulk selection, and inline rename. The backend needs new folder CRUD endpoints plus modifications to the existing documents list endpoint to filter by folder and include public Board Games content.

The existing codebase uses hand-written Tailwind components with no component library (no shadcn/ui). The tree component should be custom-built with recursion -- this is the standard approach for folder trees in React and avoids adding heavyweight dependencies for what amounts to ~150 lines of recursive rendering. For drag-and-drop, @dnd-kit is the standard choice: lightweight (10kB core), accessible, touch/keyboard-ready, and well-suited for hierarchical structures. The native HTML5 drag-and-drop API is too limited for tree-based interactions (no touch, no keyboard, inconsistent cross-browser behavior for nested drop targets).

**Primary recommendation:** Use @dnd-kit/react (0.3.2) for drag-and-drop interactions, hand-build the tree and context menu components with Tailwind, and create a new `folders.py` backend router with CRUD + move endpoints that enforce read-only constraints on public folders.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Replace current flat DocumentList sidebar with folder tree component. Same two-column layout: tree sidebar on left (w-64), content panel on right.
- D-02: Two top-level roots in the tree: "Board Games" (default KB, public) and "My Documents" (user uploads, private). Both expandable/collapsible.
- D-03: Board Games folders appear with a lock/shield icon and muted text color. Read-only -- no rename, delete, move, upload, or folder creation allowed within the Board Games tree.
- D-04: Clicking a folder in the tree shows its contents in the right panel as a list view with breadcrumb navigation (FMGR-10).
- D-05: Right panel shows folder contents as a table-style list: filename, status badge, type, size. Upload button in toolbar + drop-to-upload within the file list area.
- D-06: When no folder is selected (initial page load), the right panel shows the existing FileUpload drop zone. Uploads go to My Documents root.
- D-07: Full drag-and-drop: move files between folders, move folders within the tree, drop external files onto a folder in the tree to upload into that folder (FMGR-09).
- D-08: Drag-drop works in both the tree sidebar (folders as drop targets) and the right panel file list (drag sources for files, drop target for uploads).
- D-09: Visual feedback: valid drop targets get a blue highlight border, dragged items show a semi-transparent ghost, invalid targets (Board Games folders) show a "not allowed" cursor.
- D-10: Custom right-click context menu on tree items and file list rows. Overrides browser default. Styled dropdown with actions: Rename, Delete, Move to..., New subfolder (on folders only).
- D-11: Bulk selection via checkboxes + shift-click for range select. Toolbar appears with bulk actions (delete, move to folder) when items are selected (FMGR-07).
- D-12: Inline rename: double-click or context menu "Rename" turns name into an editable text input in-place. Enter to confirm, Escape to cancel.
- D-13: New backend API endpoints for folder operations: create, rename, delete, move. Add to a new folders.py router or extend documents.py.
- D-14: Cascade delete: deleting a folder deletes all contained documents, their chunks, and storage files. Confirmation dialog on frontend lists folder contents before proceeding.
- D-15: Move operations update only the folder_id in the documents table (and ltree path for folders). Storage paths stay as-is -- they're keyed by user_id/doc_id, not folder path.
- D-16: Board Games tree is entirely read-only for users. Backend enforces this -- reject create/rename/delete/move operations targeting public-visibility folders.

### Claude's Discretion
- Tree component library choice (custom implementation vs lightweight library)
- Context menu component implementation (custom or library)
- Drag-and-drop library selection (HTML5 drag API vs react-dnd vs @dnd-kit)
- Folder API endpoint structure and naming
- How to handle ltree path updates on folder move (recursive update strategy)
- Loading states and animations for tree expansion
- Keyboard navigation within the tree (accessibility)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-02 | User can see a hierarchical folder structure in the ingestion interface | Tree sidebar component with recursive rendering, folder fetch API, Supabase RLS provides mixed visibility |
| FMGR-01 | Ingestion interface displays a tree sidebar showing folder hierarchy | FolderTree + FolderTreeItem recursive components, folder list API endpoint |
| FMGR-02 | User can create new folders and subfolders via the UI | Backend POST /api/folders with parent_id, ltree path construction |
| FMGR-03 | User can rename folders and files | InlineRename component, PATCH /api/folders/:id and PATCH /api/documents/:id |
| FMGR-04 | User can delete folders (with confirmation) and files | ConfirmDialog component, cascade delete on backend (folder + docs + chunks + storage) |
| FMGR-05 | User can drag and drop files and folders to move/reorder them | @dnd-kit/react for drag-drop, PATCH /api/folders/:id/move and PATCH /api/documents/:id/move |
| FMGR-06 | Right-click context menus provide folder/file operations | Custom ContextMenu component with portal rendering |
| FMGR-07 | User can select multiple files for bulk move or delete operations | BulkActionBar with checkbox state management and shift-click range selection |
| FMGR-08 | Default KB folders are visually distinct (read-only indicator) | Shield icon + text-gray-500 muted styling + backend rejects mutations on public folders |
| FMGR-09 | User can upload files by dropping them into a specific folder in the tree | @dnd-kit drop target on tree folders combined with native File drag detection |
| FMGR-10 | Breadcrumb navigation shows current folder path | Breadcrumb component built from folder ancestry chain |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **No LangChain, no LangGraph** -- raw SDK calls only
- **Python backend must use venv** -- all Python deps in backend/venv/
- **Use Pydantic for structured outputs** -- applies to new folder API models
- **All tables need Row-Level Security** -- folders table already has RLS (migration 018)
- **Supabase-Only Storage** -- no local filesystem
- **No component library detected** -- all components are hand-written Tailwind (no shadcn/ui)
- **TypeScript strict mode** -- noUnusedLocals, noUnusedParameters enabled
- **ESLint enforced** -- react-hooks, react-refresh plugins active
- **GSD Workflow Enforcement** -- use GSD commands for execution

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @dnd-kit/react | 0.3.2 | Drag-and-drop for tree items, file rows, external file upload | Modern, lightweight (10kB), accessible, touch/keyboard support, designed for React |
| lucide-react | ^0.577.0 (existing) | Icons for folders, files, actions | Already installed and used throughout the project |
| react | ^19.2.4 (existing) | UI framework | Already installed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Custom FolderTree | N/A | Recursive tree component | Hand-written -- ~150 lines of recursive rendering with Tailwind |
| Custom ContextMenu | N/A | Right-click menu | Hand-written -- portal-based floating div, ~80 lines |
| Custom ConfirmDialog | N/A | Destructive action confirmation | Hand-written modal with backdrop |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @dnd-kit/react | HTML5 native drag API | Native API lacks touch support, keyboard DnD, and has inconsistent nested drop target behavior. Not suitable for tree structures. |
| @dnd-kit/react | react-dnd | react-dnd is built on HTML5 backend by default. Heavier API surface. react-beautiful-dnd is deprecated. |
| @dnd-kit/react | @dnd-kit/core (legacy) | @dnd-kit/react (0.3.2) is the newer React-specific package. Use it over @dnd-kit/core for new React projects. |
| Custom tree | react-arborist | Full tree library but adds 30kB+ dependency for something achievable with recursion. Overkill for this use case. |
| Custom context menu | @radix-ui/react-context-menu | Adds Radix dependency chain. This project has zero UI libraries -- keep it consistent. |

**Installation:**
```bash
cd frontend && npm install @dnd-kit/react
```

**Version verification:** @dnd-kit/react 0.3.2 confirmed via `npm view` on 2026-04-10. Note: this is pre-1.0 but actively maintained and the recommended React package from dnd-kit.

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
  components/
    FolderTree.tsx          # Recursive tree sidebar
    FolderTreeItem.tsx      # Single tree node with expand/collapse/drag/drop
    FileListView.tsx        # Right panel file table
    FileListRow.tsx         # Single file row with checkbox/drag/actions
    Breadcrumb.tsx          # Clickable path navigation
    ContextMenu.tsx         # Floating right-click menu (portal)
    ContextMenuItem.tsx     # Single menu item
    InlineRename.tsx        # Inline editable text input
    BulkActionBar.tsx       # Selection toolbar
    ConfirmDialog.tsx       # Modal confirmation
    FolderPicker.tsx        # Mini tree for "Move to..." dialog
    FileUpload.tsx          # (existing, modified to accept folderId)
    DocumentList.tsx        # (deprecated, replaced by FolderTree)
  hooks/
    useDocuments.ts         # (existing, extended with folder ops)
    useFolderTree.ts        # NEW: folder CRUD, tree state, expand/collapse
    useContextMenu.ts       # NEW: position tracking, open/close state
    useSelection.ts         # NEW: checkbox state, shift-click range select
  pages/
    DocumentsPage.tsx       # (existing, rewritten for new layout)
backend/
  routers/
    folders.py              # NEW: folder CRUD + move endpoints
    documents.py            # (existing, extended: list by folder, rename, move)
  models/
    folder_models.py        # NEW: Pydantic models for folder requests/responses
```

### Pattern 1: Recursive Tree Rendering
**What:** A FolderTree component renders root-level folders, each FolderTreeItem renders its children recursively.
**When to use:** Any hierarchical data display with expand/collapse.
**Example:**
```typescript
// FolderTreeItem.tsx
interface FolderNode {
  id: string
  name: string
  path: string
  visibility: 'public' | 'private'
  parent_id: string | null
  children: FolderNode[]
  document_count?: number
}

function FolderTreeItem({ node, depth, selectedId, onSelect }: Props) {
  const [expanded, setExpanded] = useState(false)
  const isReadOnly = node.visibility === 'public'
  
  return (
    <div>
      <div
        className={`flex items-center py-1.5 px-2 cursor-pointer hover:bg-gray-800 ${
          selectedId === node.id ? 'bg-gray-800 text-white' : 'text-gray-300'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.id)}
      >
        <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        {expanded ? <FolderOpen size={14} /> : <Folder size={14} />}
        <span className="ml-1.5 text-sm truncate">{node.name}</span>
        {isReadOnly && <Shield size={12} className="ml-1 text-gray-500" />}
      </div>
      {expanded && node.children.map(child => (
        <FolderTreeItem key={child.id} node={child} depth={depth + 1} ... />
      ))}
    </div>
  )
}
```

### Pattern 2: Context Menu via Portal
**What:** Right-click spawns a floating menu at cursor position, rendered via React portal to avoid overflow clipping.
**When to use:** Any custom right-click menu.
**Example:**
```typescript
// useContextMenu.ts
function useContextMenu() {
  const [menu, setMenu] = useState<{ x: number; y: number; target: ContextTarget } | null>(null)

  const openMenu = useCallback((e: React.MouseEvent, target: ContextTarget) => {
    e.preventDefault()
    setMenu({ x: e.clientX, y: e.clientY, target })
  }, [])

  const closeMenu = useCallback(() => setMenu(null), [])

  // Close on click outside or Escape
  useEffect(() => {
    if (!menu) return
    const handler = () => closeMenu()
    const keyHandler = (e: KeyboardEvent) => { if (e.key === 'Escape') closeMenu() }
    document.addEventListener('click', handler)
    document.addEventListener('keydown', keyHandler)
    return () => {
      document.removeEventListener('click', handler)
      document.removeEventListener('keydown', keyHandler)
    }
  }, [menu, closeMenu])

  return { menu, openMenu, closeMenu }
}
```

### Pattern 3: Backend Folder CRUD with ltree
**What:** Folder operations maintain ltree paths for efficient tree queries.
**When to use:** All folder create/rename/move/delete operations.
**Example:**
```python
# folders.py router
@router.post("")
async def create_folder(
    body: FolderCreate,
    user_id: str = Depends(get_user_id),
):
    db = get_supabase()
    folder_id = str(uuid.uuid4())
    
    # Build ltree path from parent
    if body.parent_id:
        parent = db.table("folders").select("path, visibility").eq("id", body.parent_id).single().execute()
        if not parent.data:
            raise HTTPException(404, "Parent folder not found")
        if parent.data["visibility"] == "public":
            raise HTTPException(403, "Cannot create folders in read-only areas")
        path = f"{parent.data['path']}.{_sanitize_label(body.name)}"
    else:
        # Root-level folder under "My Documents"
        path = f"my_documents.{_sanitize_label(body.name)}"
    
    result = db.table("folders").insert({
        "id": folder_id,
        "user_id": user_id,
        "name": body.name,
        "path": path,
        "parent_id": body.parent_id,
        "visibility": "private",
    }).execute()
    
    return result.data[0]
```

### Pattern 4: ltree Path Update on Folder Move
**What:** When a folder moves, all descendant folder paths must be updated recursively.
**When to use:** Folder move/rename operations.
**Example:**
```python
# Recursive ltree path update for folder move
def move_folder_paths(db, folder_id: str, old_path: str, new_path: str, user_id: str):
    """Update the moved folder's path and all descendant paths."""
    # Update the folder itself
    db.table("folders").update({"path": new_path}).eq("id", folder_id).execute()
    
    # Find all descendants whose path starts with old_path
    # Use ltree descendant operator: path <@ old_path (but excluding self)
    descendants = (
        db.table("folders")
        .select("id, path")
        .eq("user_id", user_id)
        .like("path", f"{old_path}.%")
        .execute()
    )
    
    for desc in descendants.data:
        # Replace prefix: old_path.child -> new_path.child
        updated_path = new_path + desc["path"][len(old_path):]
        db.table("folders").update({"path": updated_path}).eq("id", desc["id"]).execute()
```

### Anti-Patterns to Avoid
- **Storing folder path in storage_path:** Storage paths are keyed by `user_id/doc_id/filename` per D-15. Never change storage paths on move -- only update `folder_id`.
- **Fetching tree one level at a time:** Fetch the entire folder tree in one query (it's small, ~50 folders max). Lazy loading adds network roundtrips for no benefit.
- **Using HTML5 drag API for tree DnD:** Nested drop targets have inconsistent behavior across browsers with native DnD. Use @dnd-kit which handles this correctly.
- **Allowing mutations on public folders from frontend only:** Backend MUST enforce read-only on public/Board Games folders. Frontend checks are UX, not security.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Drag-and-drop | Custom mouse/touch event handlers | @dnd-kit/react | Edge cases: touch delays, scroll during drag, accessibility, drop target detection in nested trees |
| File type detection for icons | Manual extension parsing | Utility function with map | Simple but DRY -- used in both tree and file list |
| Portal rendering | Manual DOM manipulation | React createPortal | Standard React pattern for context menus and modals |
| Tree data transformation | Nested loops | Single-pass flat-to-tree builder | Common pattern: flat DB rows -> nested tree structure. O(n) with a map. |

**Key insight:** The tree component itself is simple enough to hand-write (recursion + Tailwind), but drag-and-drop interactions in a tree have dozens of edge cases that @dnd-kit handles out of the box.

## Common Pitfalls

### Pitfall 1: ltree Label Sanitization
**What goes wrong:** ltree labels can only contain alphanumeric characters and underscores. Folder names with spaces, hyphens, or special characters break ltree operations.
**Why it happens:** User-created folder names naturally contain spaces and special chars.
**How to avoid:** Sanitize folder names into valid ltree labels: replace non-alphanumeric with underscores, collapse multiple underscores, lowercase. Keep the display name separate from the path label.
**Warning signs:** Postgres errors on INSERT with path containing invalid ltree characters.

### Pitfall 2: Context Menu Positioning at Screen Edges
**What goes wrong:** Context menu renders off-screen when right-clicking near window edges.
**Why it happens:** Menu is positioned at cursor coordinates without bounds checking.
**How to avoid:** After rendering, check if the menu overflows the viewport and flip its position (render above instead of below, or to the left instead of right).
**Warning signs:** Menu cut off at bottom or right edge of screen.

### Pitfall 3: Drag-and-Drop + External File Upload Conflict
**What goes wrong:** @dnd-kit internal drag events interfere with native file drop events (dropping files from the OS).
**Why it happens:** Both @dnd-kit and native drag events fire on the same drop targets.
**How to avoid:** Detect the drag source type: if `dataTransfer.types` includes 'Files', treat it as an external file upload rather than an internal move. Handle file drops with native event handlers outside @dnd-kit's DndContext, or use @dnd-kit's sensor system to differentiate.
**Warning signs:** Dropping a file from desktop either triggers a move operation or doesn't trigger upload.

### Pitfall 4: Stale Tree State After Mutation
**What goes wrong:** After creating/deleting/moving a folder, the tree sidebar doesn't reflect the change.
**Why it happens:** Tree data is fetched once and mutations don't trigger a refetch or optimistic update.
**How to avoid:** Either (a) optimistically update the local tree state after each mutation, or (b) refetch the full tree after mutations. Given the tree is small, refetch is simpler and more reliable.
**Warning signs:** User creates a folder but it doesn't appear until page refresh.

### Pitfall 5: Cascade Delete Missing Storage Cleanup
**What goes wrong:** Deleting a folder removes DB rows but leaves orphaned files in Supabase Storage.
**Why it happens:** `ON DELETE CASCADE` only handles DB foreign keys, not storage files.
**How to avoid:** Before deleting a folder, query all documents in it (and descendants), collect their `storage_path` values, delete from storage, then delete the folder (which cascades to documents and chunks).
**Warning signs:** Storage bucket grows indefinitely, storage costs increase.

### Pitfall 6: "My Documents" Root Folder
**What goes wrong:** Unlike "Board Games" which has a seeded root folder, there's no seeded "My Documents" folder -- it needs to be created per-user or represented as a virtual root.
**Why it happens:** The schema seeds Board Games but not per-user roots. Documents with `folder_id = NULL` belong to the user's root.
**How to avoid:** Treat "My Documents" as a virtual root in the frontend. Documents with `folder_id = NULL` and folders with `parent_id = NULL` (private visibility) are shown under it. No actual DB row needed for the "My Documents" root.
**Warning signs:** User's root-level documents don't appear in the tree.

## Code Examples

### Flat-to-Tree Transformation
```typescript
// Transform flat folder array from API into nested tree
interface FolderRow {
  id: string
  name: string
  path: string
  parent_id: string | null
  visibility: 'public' | 'private'
}

interface FolderNode extends FolderRow {
  children: FolderNode[]
}

function buildTree(folders: FolderRow[]): FolderNode[] {
  const map = new Map<string, FolderNode>()
  const roots: FolderNode[] = []

  // First pass: create nodes
  for (const f of folders) {
    map.set(f.id, { ...f, children: [] })
  }

  // Second pass: link parents
  for (const f of folders) {
    const node = map.get(f.id)!
    if (f.parent_id && map.has(f.parent_id)) {
      map.get(f.parent_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}
```

### Backend Folder API Models (Pydantic)
```python
from pydantic import BaseModel

class FolderCreate(BaseModel):
    name: str
    parent_id: str | None = None

class FolderRename(BaseModel):
    name: str

class FolderMove(BaseModel):
    new_parent_id: str | None  # None = move to root

class FolderResponse(BaseModel):
    id: str
    name: str
    path: str
    parent_id: str | None
    visibility: str
    created_at: str
    updated_at: str

class FolderContents(BaseModel):
    folder: FolderResponse | None
    subfolders: list[FolderResponse]
    documents: list[dict]  # Reuse existing document shape
```

### Backend Folder Router Endpoints
```python
# Recommended endpoint structure for folders.py
router = APIRouter(prefix="/api/folders", tags=["folders"])

GET    /api/folders              # List all folders (tree data) for user + public
POST   /api/folders              # Create folder (name, parent_id)
GET    /api/folders/{id}/contents  # Get folder contents (subfolders + documents)
PATCH  /api/folders/{id}         # Rename folder
PATCH  /api/folders/{id}/move    # Move folder to new parent
DELETE /api/folders/{id}         # Delete folder (cascade)

# Extended document endpoints
PATCH  /api/documents/{id}/move  # Move document to folder
PATCH  /api/documents/{id}       # Rename document
POST   /api/documents/bulk-delete  # Bulk delete documents
POST   /api/documents/bulk-move    # Bulk move documents to folder
```

### Shift-Click Range Selection
```typescript
function useSelection(items: { id: string }[]) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [lastClicked, setLastClicked] = useState<string | null>(null)

  const toggle = useCallback((id: string, shiftKey: boolean) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (shiftKey && lastClicked) {
        // Range select
        const ids = items.map(i => i.id)
        const start = ids.indexOf(lastClicked)
        const end = ids.indexOf(id)
        const [lo, hi] = start < end ? [start, end] : [end, start]
        for (let i = lo; i <= hi; i++) {
          next.add(ids[i])
        }
      } else {
        if (next.has(id)) next.delete(id)
        else next.add(id)
      }
      return next
    })
    setLastClicked(id)
  }, [items, lastClicked])

  const selectAll = useCallback(() => {
    setSelected(new Set(items.map(i => i.id)))
  }, [items])

  const clearSelection = useCallback(() => {
    setSelected(new Set())
    setLastClicked(null)
  }, [])

  return { selected, toggle, selectAll, clearSelection }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| @dnd-kit/core + @dnd-kit/sortable | @dnd-kit/react (unified) | 2024-2025 | New React-specific package, simpler API, same maintainer |
| react-beautiful-dnd | @dnd-kit/react or pragmatic-drag-and-drop | 2023 (deprecated) | react-beautiful-dnd is no longer maintained |
| react-dnd | @dnd-kit/react | Gradual shift | @dnd-kit is lighter, more modern API, better tree support |

**Deprecated/outdated:**
- react-beautiful-dnd: Deprecated by Atlassian, replaced by pragmatic-drag-and-drop (but that's Atlassian-specific)
- react-sortable-tree: Unmaintained since 2021

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend) |
| Config file | none (default pytest discovery) |
| Quick run command | `cd backend && python -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FMGR-01 | Tree sidebar shows folder hierarchy | manual (UI) | N/A | N/A |
| FMGR-02 | Create folders via UI | unit (backend) | `pytest tests/test_folders_api.py::test_create_folder -x` | Wave 0 |
| FMGR-03 | Rename folders and files | unit (backend) | `pytest tests/test_folders_api.py::test_rename_folder -x` | Wave 0 |
| FMGR-04 | Delete folders with cascade | unit (backend) | `pytest tests/test_folders_api.py::test_delete_folder_cascade -x` | Wave 0 |
| FMGR-05 | Drag-drop move files/folders | manual (UI) | N/A | N/A |
| FMGR-06 | Context menu operations | manual (UI) | N/A | N/A |
| FMGR-07 | Bulk select and operate | manual (UI) | N/A | N/A |
| FMGR-08 | Board Games read-only styling | manual (UI) | N/A | N/A |
| FMGR-09 | Upload by dropping onto folder | manual (UI) | N/A | N/A |
| FMGR-10 | Breadcrumb navigation | manual (UI) | N/A | N/A |
| DATA-02 | Hierarchical folder display | manual (UI) | N/A | N/A |
| -- | Backend rejects public folder mutations | unit (backend) | `pytest tests/test_folders_api.py::test_reject_public_mutation -x` | Wave 0 |
| -- | ltree path update on move | unit (backend) | `pytest tests/test_folders_api.py::test_move_updates_paths -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v`
- **Phase gate:** Full suite green + manual UI walkthrough

### Wave 0 Gaps
- [ ] `backend/tests/test_folders_api.py` -- covers folder CRUD, move, cascade delete, read-only enforcement
- [ ] `backend/routers/folders.py` -- the router being tested
- [ ] `backend/models/folder_models.py` -- Pydantic models for folder operations
- No frontend test framework detected -- UI testing is manual via browser

## Open Questions

1. **@dnd-kit/react external file detection**
   - What we know: @dnd-kit handles internal drag-drop. External file drops (from OS) use native browser events.
   - What's unclear: Whether @dnd-kit 0.3.2 has built-in support for detecting external file drops or if we need to handle them separately with native onDrop handlers.
   - Recommendation: Use native `onDrop`/`onDragOver` handlers on tree folder items for external file uploads, alongside @dnd-kit for internal moves. Test both paths during implementation.

2. **"My Documents" auto-creation**
   - What we know: Board Games root is seeded in migration 018. Per-user root folders are not seeded.
   - What's unclear: Whether to create a "My Documents" folder record per-user on first login, or treat it as a virtual node.
   - Recommendation: Virtual node in frontend (no DB row). Private root-level folders and documents with `folder_id = NULL` belong to "My Documents". Simpler, no migration needed.

3. **Supabase .like() for ltree descendant queries**
   - What we know: The Supabase JS/Python client doesn't have native ltree operators (`<@`, `@>`).
   - What's unclear: Whether `.like("path", "prefix.%")` works reliably for ltree columns, or if we need an RPC function.
   - Recommendation: Use SQL `.like()` for path prefix matching in the Python client (it works on ltree cast to text). If performance matters later, add an RPC function.

## Sources

### Primary (HIGH confidence)
- Existing codebase: migrations 016-020 (ltree, folders, RLS), documents.py, useDocuments.ts, DocumentsPage.tsx
- npm registry: @dnd-kit/react 0.3.2 verified via `npm view`
- UI-SPEC.md: Complete design contract for Phase 4

### Secondary (MEDIUM confidence)
- dnd-kit official docs (https://dndkit.com/react/quickstart) -- API patterns
- DEV Community article on dnd-kit tree implementation (https://dev.to/fupeng_wang/react-dnd-kit-implement-tree-list-drag-and-drop-sortable-225l)
- Puck blog comparison of React DnD libraries (https://puckeditor.com/blog/top-5-drag-and-drop-libraries-for-react)

### Tertiary (LOW confidence)
- @dnd-kit/react 0.3.2 stability claims (pre-1.0, noted in STATE.md as needing validation)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- @dnd-kit is the clear ecosystem winner, hand-written tree is standard for this scope
- Architecture: HIGH -- patterns well-established, existing codebase patterns clear
- Pitfalls: HIGH -- ltree sanitization and cascade delete are well-known issues; DnD + external file conflict is documented

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable domain, @dnd-kit may release new versions)
