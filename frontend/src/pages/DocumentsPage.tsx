import { useMemo, useState } from 'react'
import { Plus, Pencil, FolderInput, Trash2 } from 'lucide-react'
import { DragDropProvider } from '@dnd-kit/react'
import type { DragEndEvent } from '@dnd-kit/react'
import { useDocuments } from '../hooks/useDocuments'
import {
  useFolderTree,
  ROOT_PUBLIC_ID,
  ROOT_PRIVATE_ID,
} from '../hooks/useFolderTree'
import FolderTree from '../components/FolderTree'
import FileListView from '../components/FileListView'
import Breadcrumb from '../components/Breadcrumb'
import FileUpload from '../components/FileUpload'
import { useContextMenu } from '../hooks/useContextMenu'
import ContextMenu from '../components/ContextMenu'
import ContextMenuItem from '../components/ContextMenuItem'
import ConfirmDialog from '../components/ConfirmDialog'
import FolderPicker from '../components/FolderPicker'
import { useSelection } from '../hooks/useSelection'
import type { FolderNode } from '../hooks/useFolderTree'
import type { Document } from '../hooks/useDocuments'

type DeleteTarget =
  | { type: 'folder'; id: string; name: string; fileCount: number; subfolderCount: number }
  | { type: 'file'; id: string; name: string }
  | { type: 'bulk'; ids: string[] }

type MoveTarget =
  | { type: 'folder'; id: string; currentParentId: string | null }
  | { type: 'file'; id: string; currentFolderId: string | null }
  | { type: 'bulk'; ids: string[]; currentFolderId: string | null }

// Parse a prefixed dnd-kit id back into its (kind, uuid) parts.
function parseDndId(id: string | number | undefined | null):
  | { kind: 'file' | 'folder'; uuid: string }
  | null {
  if (typeof id !== 'string') return null
  if (id.startsWith('file-')) return { kind: 'file', uuid: id.slice(5) }
  if (id.startsWith('folder-')) return { kind: 'folder', uuid: id.slice(7) }
  return null
}

export default function DocumentsPage() {
  const {
    uploadDocument,
    deleteDocument,
    bulkDeleteDocuments,
    bulkMoveDocuments,
  } = useDocuments()
  const {
    folders,
    rawFolders,
    selectedFolderId,
    expandedIds,
    folderContents,
    loadingContents,
    selectFolder,
    toggleExpand,
    breadcrumbs,
    createFolder,
    renameFolder,
    deleteFolder,
    moveFolder,
    moveDocument,
    renameDocument,
    refreshTree,
  } = useFolderTree()

  const { menu, openMenu, closeMenu } = useContextMenu()
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [creatingUnderId, setCreatingUnderId] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<DeleteTarget | null>(null)
  const [movingItem, setMovingItem] = useState<MoveTarget | null>(null)

  // Selection over the current folder's documents.
  const currentDocuments = folderContents?.documents ?? []
  const { selected, toggle, clearSelection } = useSelection(currentDocuments)

  const selectedFolder = useMemo(() => {
    if (!selectedFolderId) return null
    if (selectedFolderId === ROOT_PUBLIC_ID || selectedFolderId === ROOT_PRIVATE_ID) {
      return {
        id: selectedFolderId,
        name: selectedFolderId === ROOT_PUBLIC_ID ? 'Board Games' : 'My Documents',
        visibility: selectedFolderId === ROOT_PUBLIC_ID ? 'public' : 'private',
      }
    }
    const found = rawFolders.find(f => f.id === selectedFolderId)
    return found ?? null
  }, [selectedFolderId, rawFolders])

  const isReadOnly = selectedFolder?.visibility === 'public'

  const handleUpload = async (file: File, overrideFolderId?: string) => {
    let targetFolderId: string | undefined = overrideFolderId
    if (targetFolderId === undefined && selectedFolderId) {
      if (
        selectedFolderId !== ROOT_PUBLIC_ID &&
        selectedFolderId !== ROOT_PRIVATE_ID &&
        !isReadOnly
      ) {
        targetFolderId = selectedFolderId
      }
    }
    return await uploadDocument(file, targetFolderId)
  }

  // External file dropped onto a tree folder -> upload to that folder.
  const handleExternalFileDrop = async (file: File, folderId: string) => {
    try {
      await uploadDocument(file, folderId)
    } catch (err) {
      console.error(err)
    }
  }

  // @dnd-kit drag end: move file-to-folder or folder-to-folder.
  const handleDragEnd = async (event: DragEndEvent) => {
    if (event.canceled) return
    const src = parseDndId(event.operation.source?.id)
    const tgt = parseDndId(event.operation.target?.id)
    if (!src || !tgt || tgt.kind !== 'folder') return

    // Resolve target folder: reject public targets.
    const targetFolder = rawFolders.find(f => f.id === tgt.uuid)
    if (!targetFolder || targetFolder.visibility === 'public') return

    if (src.kind === 'file') {
      try {
        await moveDocument(src.uuid, tgt.uuid)
      } catch (err) {
        console.error(err)
      }
      return
    }

    if (src.kind === 'folder') {
      // Source must be a private folder and not itself.
      if (src.uuid === tgt.uuid) return
      const sourceFolder = rawFolders.find(f => f.id === src.uuid)
      if (!sourceFolder || sourceFolder.visibility === 'public') return
      try {
        await moveFolder(src.uuid, tgt.uuid)
      } catch (err) {
        console.error(err)
      }
    }
  }

  // Folder context-menu: skip public folders (D-10)
  const handleFolderContextMenu = (e: React.MouseEvent, node: FolderNode) => {
    if (node.visibility === 'public') return
    if (node.id === ROOT_PUBLIC_ID || node.id === ROOT_PRIVATE_ID) return
    openMenu(e, { type: 'folder', node })
  }

  // FileListView context menu: target is either a FolderNode (subfolder row) or a Document
  const handleListContextMenu = (
    e: React.MouseEvent,
    target: FolderNode | Document
  ) => {
    if ('visibility' in target) {
      if (target.visibility === 'public') return
      openMenu(e, { type: 'folder', node: target })
    } else {
      // Documents in public (Board Games) folders are read-only
      if (isReadOnly) return
      openMenu(e, { type: 'file', doc: target })
    }
  }

  const handleConfirmRename = async (id: string, name: string) => {
    try {
      const isFolder = rawFolders.some(f => f.id === id)
      if (isFolder) {
        await renameFolder(id, name)
      } else {
        await renameDocument(id, name)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setRenamingId(null)
    }
  }

  const handleConfirmCreate = async (parentId: string | null, name: string) => {
    try {
      await createFolder(name, parentId)
    } catch (err) {
      console.error(err)
    } finally {
      setCreatingUnderId(null)
    }
  }

  const handleConfirmDelete = async () => {
    if (!confirmDelete) return
    try {
      if (confirmDelete.type === 'folder') {
        await deleteFolder(confirmDelete.id)
      } else if (confirmDelete.type === 'file') {
        await deleteDocument(confirmDelete.id)
      } else {
        await bulkDeleteDocuments(confirmDelete.ids)
        clearSelection()
        await refreshTree()
      }
    } catch (err) {
      console.error(err)
    } finally {
      setConfirmDelete(null)
    }
  }

  const handleMoveSelect = async (destinationFolderId: string | null) => {
    if (!movingItem) return
    try {
      if (movingItem.type === 'folder') {
        await moveFolder(movingItem.id, destinationFolderId)
      } else if (movingItem.type === 'file') {
        await moveDocument(movingItem.id, destinationFolderId)
      } else {
        await bulkMoveDocuments(movingItem.ids, destinationFolderId)
        clearSelection()
        await refreshTree()
      }
    } catch (err) {
      console.error(err)
    } finally {
      setMovingItem(null)
    }
  }

  const currentFolderDocCount = folderContents?.documents.length ?? 0

  // Bulk action handlers from BulkActionBar.
  const handleBulkDelete = () => {
    if (selected.size === 0) return
    setConfirmDelete({ type: 'bulk', ids: Array.from(selected) })
  }

  const handleBulkMove = () => {
    if (selected.size === 0) return
    const currentFolderId =
      selectedFolderId === ROOT_PRIVATE_ID ||
      selectedFolderId === ROOT_PUBLIC_ID ||
      selectedFolderId === null
        ? null
        : selectedFolderId
    setMovingItem({
      type: 'bulk',
      ids: Array.from(selected),
      currentFolderId,
    })
  }

  return (
    <DragDropProvider onDragEnd={handleDragEnd}>
      <div className="flex-1 bg-gray-950 text-white flex overflow-hidden">
        {/* Tree Sidebar */}
        <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full overflow-y-auto">
          <FolderTree
            folders={folders}
            selectedFolderId={selectedFolderId}
            expandedIds={expandedIds}
            onSelect={selectFolder}
            onToggleExpand={toggleExpand}
            onContextMenu={handleFolderContextMenu}
            renamingId={renamingId}
            onStartRename={setRenamingId}
            onConfirmRename={handleConfirmRename}
            onCancelRename={() => setRenamingId(null)}
            creatingUnderId={creatingUnderId}
            onStartCreate={setCreatingUnderId}
            onConfirmCreate={handleConfirmCreate}
            onCancelCreate={() => setCreatingUnderId(null)}
            onExternalFileDrop={handleExternalFileDrop}
          />
        </div>

        {/* Content Panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedFolderId ? (
            <>
              <Breadcrumb segments={breadcrumbs} onNavigate={selectFolder} />
              <FileListView
                folder={folderContents?.folder ?? null}
                subfolders={folderContents?.subfolders ?? []}
                documents={folderContents?.documents ?? []}
                loading={loadingContents}
                onDeleteDoc={id => {
                  const doc = folderContents?.documents.find(d => d.id === id)
                  if (doc) {
                    setConfirmDelete({ type: 'file', id: doc.id, name: doc.filename })
                  }
                }}
                onSelectFolder={selectFolder}
                onUpload={handleUpload}
                isReadOnly={!!isReadOnly}
                onContextMenu={handleListContextMenu}
                renamingId={renamingId}
                onStartRename={setRenamingId}
                onConfirmRename={handleConfirmRename}
                onCancelRename={() => setRenamingId(null)}
                creatingInCurrentFolder={
                  creatingUnderId !== null && creatingUnderId === selectedFolderId
                }
                onStartCreate={() => {
                  if (
                    selectedFolderId === ROOT_PRIVATE_ID ||
                    selectedFolderId === null
                  ) {
                    setCreatingUnderId(ROOT_PRIVATE_ID)
                  } else {
                    setCreatingUnderId(selectedFolderId)
                  }
                }}
                onConfirmCreate={async (name: string) => {
                  const parentId =
                    selectedFolderId === ROOT_PRIVATE_ID ||
                    selectedFolderId === null
                      ? null
                      : selectedFolderId
                  await handleConfirmCreate(parentId, name)
                }}
                onCancelCreate={() => setCreatingUnderId(null)}
                selectedIds={selected}
                onToggleSelect={toggle}
                onBulkDelete={handleBulkDelete}
                onBulkMove={handleBulkMove}
                onClearSelection={clearSelection}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <div className="w-full max-w-lg">
                <FileUpload onUpload={handleUpload} />
              </div>
            </div>
          )}
        </div>

        {/* Context Menu */}
        {menu && menu.target.type === 'folder' &&
          menu.target.node.visibility === 'private' && (
            <ContextMenu x={menu.x} y={menu.y}>
              <ContextMenuItem
                icon={<Plus size={14} />}
                label="New subfolder"
                onClick={() => {
                  if (menu.target.type !== 'folder') return
                  setCreatingUnderId(menu.target.node.id)
                  if (!expandedIds.has(menu.target.node.id)) {
                    toggleExpand(menu.target.node.id)
                  }
                  closeMenu()
                }}
              />
              <ContextMenuItem
                icon={<Pencil size={14} />}
                label="Rename"
                onClick={() => {
                  if (menu.target.type !== 'folder') return
                  setRenamingId(menu.target.node.id)
                  closeMenu()
                }}
              />
              <ContextMenuItem
                icon={<FolderInput size={14} />}
                label="Move to..."
                onClick={() => {
                  if (menu.target.type !== 'folder') return
                  setMovingItem({
                    type: 'folder',
                    id: menu.target.node.id,
                    currentParentId: menu.target.node.parent_id,
                  })
                  closeMenu()
                }}
              />
              <ContextMenuItem
                icon={<Trash2 size={14} />}
                label="Delete"
                variant="destructive"
                onClick={() => {
                  if (menu.target.type !== 'folder') return
                  const node = menu.target.node
                  const fileCount =
                    selectedFolderId === node.id ? currentFolderDocCount : 0
                  setConfirmDelete({
                    type: 'folder',
                    id: node.id,
                    name: node.name,
                    fileCount,
                    subfolderCount: node.children.length,
                  })
                  closeMenu()
                }}
              />
            </ContextMenu>
          )}
        {menu && menu.target.type === 'file' && (
          <ContextMenu x={menu.x} y={menu.y}>
            <ContextMenuItem
              icon={<Pencil size={14} />}
              label="Rename"
              onClick={() => {
                if (menu.target.type !== 'file') return
                setRenamingId(menu.target.doc.id)
                closeMenu()
              }}
            />
            <ContextMenuItem
              icon={<FolderInput size={14} />}
              label="Move to..."
              onClick={() => {
                if (menu.target.type !== 'file') return
                const currentFolderId =
                  selectedFolderId === ROOT_PRIVATE_ID ||
                  selectedFolderId === ROOT_PUBLIC_ID
                    ? null
                    : selectedFolderId
                setMovingItem({
                  type: 'file',
                  id: menu.target.doc.id,
                  currentFolderId,
                })
                closeMenu()
              }}
            />
            <ContextMenuItem
              icon={<Trash2 size={14} />}
              label="Delete"
              variant="destructive"
              onClick={() => {
                if (menu.target.type !== 'file') return
                setConfirmDelete({
                  type: 'file',
                  id: menu.target.doc.id,
                  name: menu.target.doc.filename,
                })
                closeMenu()
              }}
            />
          </ContextMenu>
        )}

        {/* Confirm Delete Dialog */}
        {confirmDelete && confirmDelete.type === 'file' && (
          <ConfirmDialog
            heading={`Delete ${confirmDelete.name}?`}
            body={`Are you sure you want to delete ${confirmDelete.name}? This cannot be undone.`}
            confirmLabel="Delete File"
            cancelLabel="Keep File"
            onConfirm={handleConfirmDelete}
            onCancel={() => setConfirmDelete(null)}
          />
        )}
        {confirmDelete && confirmDelete.type === 'folder' && (
          <ConfirmDialog
            heading={`Delete ${confirmDelete.name}?`}
            body={`Delete ${confirmDelete.name} and all its contents? This will permanently remove ${confirmDelete.fileCount} files and ${confirmDelete.subfolderCount} subfolders.`}
            confirmLabel="Delete Folder"
            cancelLabel="Keep Folder"
            onConfirm={handleConfirmDelete}
            onCancel={() => setConfirmDelete(null)}
          />
        )}
        {confirmDelete && confirmDelete.type === 'bulk' && (
          <ConfirmDialog
            heading={`Delete ${confirmDelete.ids.length} items?`}
            body={`Are you sure you want to delete ${confirmDelete.ids.length} selected items? This cannot be undone.`}
            confirmLabel={`Delete ${confirmDelete.ids.length} Items`}
            cancelLabel="Keep Items"
            onConfirm={handleConfirmDelete}
            onCancel={() => setConfirmDelete(null)}
          />
        )}

        {/* Folder Picker for Move */}
        {movingItem && (
          <FolderPicker
            folders={folders}
            currentFolderId={
              movingItem.type === 'folder'
                ? movingItem.currentParentId
                : movingItem.type === 'file'
                  ? movingItem.currentFolderId
                  : movingItem.currentFolderId
            }
            excludeFolderId={movingItem.type === 'folder' ? movingItem.id : null}
            onSelect={handleMoveSelect}
            onCancel={() => setMovingItem(null)}
          />
        )}
      </div>
    </DragDropProvider>
  )
}
