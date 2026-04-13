import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Shield,
} from 'lucide-react'
import type { FolderNode } from '../hooks/useFolderTree'
import InlineRename from './InlineRename'

interface Props {
  node: FolderNode
  depth: number
  selectedId: string | null
  expandedIds: Set<string>
  onSelect: (id: string) => void
  onToggleExpand: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, node: FolderNode) => void
  renamingId?: string | null
  onStartRename?: (id: string) => void
  onConfirmRename?: (id: string, newName: string) => void
  onCancelRename?: () => void
  creatingUnderId?: string | null
  onConfirmCreate?: (parentId: string | null, name: string) => void
  onCancelCreate?: () => void
}

export default function FolderTreeItem({
  node,
  depth,
  selectedId,
  expandedIds,
  onSelect,
  onToggleExpand,
  onContextMenu,
  renamingId,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  creatingUnderId,
  onConfirmCreate,
  onCancelCreate,
}: Props) {
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0
  const isPublic = node.visibility === 'public'
  const isRenaming = renamingId === node.id && !isPublic
  const isCreatingUnder = creatingUnderId === node.id

  const rowClasses = [
    'flex items-center py-1.5 pr-2 cursor-pointer group',
    isSelected ? 'bg-gray-800 text-white' : 'hover:bg-gray-800',
  ].join(' ')

  const nameClasses = [
    'text-sm truncate ml-1.5',
    isPublic ? 'text-gray-500' : 'text-gray-200',
  ].join(' ')

  // When creating-under this folder, we want to show the input as a pseudo-child.
  // Force-expand visual so the input is visible.
  const showChildren = isExpanded || isCreatingUnder

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
            if (hasChildren || isCreatingUnder) onToggleExpand(node.id)
          }}
          className="shrink-0 w-4 h-4 flex items-center justify-center text-gray-500 hover:text-gray-300"
          aria-label={isExpanded ? 'Collapse' : 'Expand'}
        >
          {hasChildren || isCreatingUnder ? (
            showChildren ? (
              <ChevronDown size={14} />
            ) : (
              <ChevronRight size={14} />
            )
          ) : null}
        </button>
        <span className="shrink-0 ml-0.5 text-gray-400">
          {showChildren && (hasChildren || isCreatingUnder) ? (
            <FolderOpen size={14} />
          ) : (
            <Folder size={14} />
          )}
        </span>
        {isRenaming ? (
          <span className="ml-1.5 flex-1" onClick={e => e.stopPropagation()}>
            <InlineRename
              currentName={node.name}
              onConfirm={name => onConfirmRename?.(node.id, name)}
              onCancel={() => onCancelRename?.()}
            />
          </span>
        ) : (
          <span
            className={nameClasses}
            onDoubleClick={e => {
              e.stopPropagation()
              if (!isPublic) onStartRename?.(node.id)
            }}
          >
            {node.name}
          </span>
        )}
        {isPublic && (
          <Shield size={12} className="ml-1 text-gray-500 shrink-0" />
        )}
      </div>
      {showChildren && (
        <div>
          {isCreatingUnder && (
            <div
              className="flex items-center py-1.5 pr-2"
              style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
              onClick={e => e.stopPropagation()}
            >
              <div className="shrink-0 w-4 h-4" />
              <span className="shrink-0 ml-0.5 text-gray-400">
                <Folder size={14} />
              </span>
              <span className="ml-1.5 flex-1">
                <InlineRename
                  placeholder="New folder name"
                  onConfirm={name => onConfirmCreate?.(node.id, name)}
                  onCancel={() => onCancelCreate?.()}
                />
              </span>
            </div>
          )}
          {hasChildren &&
            node.children.map(child => (
              <FolderTreeItem
                key={child.id}
                node={child}
                depth={depth + 1}
                selectedId={selectedId}
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
              />
            ))}
        </div>
      )}
    </div>
  )
}
