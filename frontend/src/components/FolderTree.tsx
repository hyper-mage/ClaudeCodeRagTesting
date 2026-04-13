import { Plus } from 'lucide-react'
import type { FolderNode } from '../hooks/useFolderTree'
import { ROOT_PUBLIC_ID, ROOT_PRIVATE_ID } from '../hooks/useFolderTree'
import FolderTreeItem from './FolderTreeItem'

interface Props {
  folders: FolderNode[]
  selectedFolderId: string | null
  expandedIds: Set<string>
  onSelect: (id: string | null) => void
  onToggleExpand: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, node: FolderNode) => void
  onCreateRootFolder?: () => void
}

export default function FolderTree({
  folders,
  selectedFolderId,
  expandedIds,
  onSelect,
  onToggleExpand,
  onContextMenu,
  onCreateRootFolder,
}: Props) {
  const publicRoot = folders.find(f => f.id === ROOT_PUBLIC_ID)
  const privateRoot = folders.find(f => f.id === ROOT_PRIVATE_ID)

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
            onClick={() => onCreateRootFolder?.()}
            className="text-gray-500 hover:text-gray-200 shrink-0"
            aria-label="New folder"
            title="New folder"
          >
            <Plus size={14} />
          </button>
        </div>
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
          />
        ))}
      </div>
    </div>
  )
}
