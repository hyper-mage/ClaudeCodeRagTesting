import { Plus, Folder } from 'lucide-react'
import type { FolderNode } from '../hooks/useFolderTree'
import { ROOT_PUBLIC_ID, ROOT_PRIVATE_ID } from '../hooks/useFolderTree'
import FolderTreeItem from './FolderTreeItem'
import InlineRename from './InlineRename'

interface Props {
  folders: FolderNode[]
  selectedFolderId: string | null
  expandedIds: Set<string>
  onSelect: (id: string | null) => void
  onToggleExpand: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, node: FolderNode) => void
  renamingId?: string | null
  onStartRename?: (id: string) => void
  onConfirmRename?: (id: string, newName: string) => void
  onCancelRename?: () => void
  creatingUnderId?: string | null
  onStartCreate?: (parentId: string) => void
  onConfirmCreate?: (parentId: string | null, name: string) => void
  onCancelCreate?: () => void
  onExternalFileDrop?: (file: File, folderId: string) => void
  // When true, FileListView will render the root-level create input;
  // suppress the duplicate render here to avoid focus-stealing/onBlur cancel.
  suppressRootCreate?: boolean
}

export default function FolderTree({
  folders,
  selectedFolderId,
  expandedIds,
  onSelect,
  onToggleExpand,
  onContextMenu,
  renamingId,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  creatingUnderId,
  onStartCreate,
  onConfirmCreate,
  onCancelCreate,
  onExternalFileDrop,
  suppressRootCreate,
}: Props) {
  const publicRoot = folders.find(f => f.id === ROOT_PUBLIC_ID)
  const privateRoot = folders.find(f => f.id === ROOT_PRIVATE_ID)

  const creatingAtPrivateRoot =
    creatingUnderId === ROOT_PRIVATE_ID && !suppressRootCreate

  return (
    <div className="flex-1 overflow-y-auto py-2">
      {/* BOARD GAMES section */}
      <div className="mb-2">
        <div
          className="text-xs uppercase tracking-wider text-gray-400 px-2 py-2 cursor-pointer hover:text-gray-300"
          onClick={() => onSelect(ROOT_PUBLIC_ID)}
        >
          BOARD GAMES
        </div>
        {publicRoot?.children.map(node => (
          <FolderTreeItem
            key={node.id}
            node={node}
            depth={0}
            selectedId={selectedFolderId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onToggleExpand={onToggleExpand}
            onContextMenu={onContextMenu}
            onExternalFileDrop={onExternalFileDrop}
          />
        ))}
      </div>

      {/* MY DOCUMENTS section */}
      <div>
        <div className="flex items-center justify-between px-2 py-2">
          <span
            className="text-xs uppercase tracking-wider text-gray-400 cursor-pointer hover:text-gray-300 flex-1"
            onClick={() => onSelect(ROOT_PRIVATE_ID)}
          >
            MY DOCUMENTS
          </span>
          <button
            type="button"
            onClick={() => onStartCreate?.(ROOT_PRIVATE_ID)}
            className="text-gray-500 hover:text-gray-200 shrink-0"
            aria-label="New folder"
            title="New folder"
          >
            <Plus size={14} />
          </button>
        </div>
        {creatingAtPrivateRoot && (
          <div
            className="flex items-center py-1.5 pr-2"
            style={{ paddingLeft: '8px' }}
          >
            <div className="shrink-0 w-4 h-4" />
            <span className="shrink-0 ml-0.5 text-gray-400">
              <Folder size={14} />
            </span>
            <span className="ml-1.5 flex-1">
              <InlineRename
                placeholder="New folder name"
                onConfirm={name => onConfirmCreate?.(null, name)}
                onCancel={() => onCancelCreate?.()}
              />
            </span>
          </div>
        )}
        {privateRoot?.children.map(node => (
          <FolderTreeItem
            key={node.id}
            node={node}
            depth={0}
            selectedId={selectedFolderId}
            expandedIds={expandedIds}
            onSelect={onSelect}
            onToggleExpand={onToggleExpand}
            onContextMenu={onContextMenu}
            renamingId={renamingId}
            onStartRename={onStartRename}
            onConfirmRename={onConfirmRename}
            onCancelRename={onCancelRename}
            creatingUnderId={creatingUnderId}
            onConfirmCreate={onConfirmCreate}
            onCancelCreate={onCancelCreate}
            onExternalFileDrop={onExternalFileDrop}
          />
        ))}
      </div>
    </div>
  )
}
