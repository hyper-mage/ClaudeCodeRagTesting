import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Shield,
} from 'lucide-react'
import type { FolderNode } from '../hooks/useFolderTree'

interface Props {
  node: FolderNode
  depth: number
  selectedId: string | null
  expandedIds: Set<string>
  onSelect: (id: string) => void
  onToggleExpand: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, node: FolderNode) => void
}

export default function FolderTreeItem({
  node,
  depth,
  selectedId,
  expandedIds,
  onSelect,
  onToggleExpand,
  onContextMenu,
}: Props) {
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0
  const isPublic = node.visibility === 'public'

  const rowClasses = [
    'flex items-center py-1.5 pr-2 cursor-pointer group',
    isSelected ? 'bg-gray-800 text-white' : 'hover:bg-gray-800',
  ].join(' ')

  const nameClasses = [
    'text-sm truncate ml-1.5',
    isPublic ? 'text-gray-500' : 'text-gray-200',
  ].join(' ')

  return (
    <div>
      <div
        className={rowClasses}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.id)}
        onContextMenu={e => onContextMenu?.(e, node)}
      >
        <button
          type="button"
          onClick={e => {
            e.stopPropagation()
            if (hasChildren) onToggleExpand(node.id)
          }}
          className="shrink-0 w-4 h-4 flex items-center justify-center text-gray-500 hover:text-gray-300"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown size={14} />
            ) : (
              <ChevronRight size={14} />
            )
          ) : null}
        </button>
        <span className="shrink-0 ml-0.5 text-gray-400">
          {isExpanded && hasChildren ? (
            <FolderOpen size={14} />
          ) : (
            <Folder size={14} />
          )}
        </span>
        <span className={nameClasses}>{node.name}</span>
        {isPublic && (
          <Shield size={12} className="ml-1 text-gray-500 shrink-0" />
        )}
      </div>
      {isExpanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <FolderTreeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              expandedIds={expandedIds}
              onSelect={onSelect}
              onToggleExpand={onToggleExpand}
              onContextMenu={onContextMenu}
            />
          ))}
        </div>
      )}
    </div>
  )
}
