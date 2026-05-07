# Phase 4: File Manager UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-10
**Phase:** 04-file-manager-ui
**Areas discussed:** Tree sidebar layout, Drag-and-drop scope, Context menus & interactions, Folder CRUD backend

---

## Tree Sidebar Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Replace flat list | Replace DocumentList sidebar with folder tree. Same two-column layout. | Yes |
| Tree + file detail panel | Three-column: tree, file list, details/upload. More complex. | |
| Full-width file manager | Drop upload zone, tree + grid/list with integrated upload. | |

**User's choice:** Replace flat list
**Notes:** Keeps the existing layout structure, just upgrades the left panel.

| Option | Description | Selected |
|--------|-------------|----------|
| Muted with lock icon | Board Games shows lock/shield icon, muted text. No CRUD actions. | Yes |
| Separate section with divider | Two labeled sections with divider line. | |
| Same style, badge only | Minimal distinction, small 'Public' badge. | |

**User's choice:** Muted with lock icon

| Option | Description | Selected |
|--------|-------------|----------|
| Show folder contents | Clicking folder shows files in right panel. Breadcrumb for path. | Yes |
| Tree only for organization | Tree for drag-drop/folder ops only. Right panel always shows upload. | |

**User's choice:** Show folder contents

| Option | Description | Selected |
|--------|-------------|----------|
| List view | Table-style list: filename, status, type, size. Upload in toolbar. | Yes |
| Card grid | Files as cards in a grid. Richer but less dense. | |
| You decide | Claude picks. | |

**User's choice:** List view

| Option | Description | Selected |
|--------|-------------|----------|
| Upload zone | Show FileUpload drop zone as default. Uploads go to My Documents root. | Yes |
| Welcome / overview | Summary with stats. Upload via toolbar only. | |
| Auto-select My Documents | Auto-select root on page load. | |

**User's choice:** Upload zone (default/initial state)

---

## Drag-and-Drop Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full drag-drop | Move files between folders, move folders, drop external files to upload. | Yes |
| Files only, no folder moves | Drag files between folders. Folders can't be moved. | |
| Upload drop only | Only external file drops for upload. Internal moves via context menu. | |

**User's choice:** Full drag-drop

| Option | Description | Selected |
|--------|-------------|----------|
| Both tree and file list | Tree folders as drop targets, file list as drop target for uploads, drag from list to tree. | Yes |
| Tree sidebar only | All drag-drop in tree. File list is view-only. | |
| You decide | Claude picks. | |

**User's choice:** Both tree and file list

| Option | Description | Selected |
|--------|-------------|----------|
| Highlight + ghost | Blue highlight on valid targets, semi-transparent ghost, not-allowed cursor on invalid. | Yes |
| Minimal -- highlight only | Just highlight targets. No ghost. | |
| You decide | Claude picks. | |

**User's choice:** Highlight + ghost

---

## Context Menus & Interactions

| Option | Description | Selected |
|--------|-------------|----------|
| Custom context menu | Override browser right-click. Styled dropdown: Rename, Delete, Move, New subfolder. | Yes |
| Action buttons on hover | Icons on hover (like current delete button). No context menu. | |
| Both | Hover for quick actions + right-click for full menu. | |

**User's choice:** Custom context menu

| Option | Description | Selected |
|--------|-------------|----------|
| Checkbox + shift-click | Checkboxes on hover, shift-click range, toolbar with bulk actions. | Yes |
| Click to select, Ctrl+click | Click/Ctrl/Shift select. No visible checkboxes. Highlighted background. | |
| You decide | Claude picks. | |

**User's choice:** Checkbox + shift-click

| Option | Description | Selected |
|--------|-------------|----------|
| Inline edit | Double-click turns name into text input. Enter/Escape. | Yes |
| Modal dialog | Rename opens modal with pre-filled text field. | |
| You decide | Claude picks. | |

**User's choice:** Inline edit

---

## Folder CRUD Backend

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm, then cascade | Confirmation listing contents. Delete folder + docs + chunks + storage. | Yes |
| Block if not empty | Prevent deletion of non-empty folders. | |
| Move contents to parent | Delete folder, move contents up. | |

**User's choice:** Confirm, then cascade

| Option | Description | Selected |
|--------|-------------|----------|
| DB only | Move updates folder_id only. Storage paths unchanged. | Yes |
| Both DB and Storage | Update folder_id AND rename storage paths. | |

**User's choice:** DB only

| Option | Description | Selected |
|--------|-------------|----------|
| No -- read-only | Board Games entirely read-only for users. Backend enforces. | Yes |
| Yes -- user can add subfolders | Users can create personal subfolders within Board Games. | |

**User's choice:** No -- read-only

---

## Claude's Discretion

- Tree component library choice
- Context menu component implementation
- Drag-and-drop library (HTML5 vs react-dnd vs @dnd-kit)
- Folder API endpoint structure
- ltree path update strategy on folder move
- Loading states and animations
- Keyboard accessibility

## Deferred Ideas

None -- discussion stayed within phase scope
