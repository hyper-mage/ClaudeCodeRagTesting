import { useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Shield,
} from 'lucide-react'
import { useDraggable, useDroppable } from '@dnd-kit/react'
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
  onExternalFileDrop?: (file: File, folderId: string) => void
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
  onExternalFileDrop,
}: Props) {
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0
  const isPublic = node.visibility === 'public'
  const isRenaming = renamingId === node.id && !isPublic
  const isCreatingUnder = creatingUnderId === node.id

  // @dnd-kit droppable -- public folders are non-drop targets (we still render
  // the ref so isDropTarget reports correctly, but the onDragEnd handler in
  // DocumentsPage checks visibility and ignores public targets).
  const { ref: dropRef, isDropTarget } = useDroppable({
    id: `folder-${node.id}`,
    disabled: isPublic,
  })

  // @dnd-kit draggable -- private folders are draggable sources. Public
  // folders skip the draggable entirely.
  const { ref: dragRef, isDragging } = useDraggable({
    id: `folder-${node.id}`,
    disabled: isPublic,
  })

  // Compose dnd-kit drop + drag refs onto the same row element.
  const setRowRef = (el: HTMLDivElement | null) => {
    dropRef(el)
    dragRef(el)
  }

  // Native external file drag state (separate from @dnd-kit, detected via
  // dataTransfer.types containing 'Files').
  const [externalDragOver, setExternalDragOver] = useState(false)

  const handleNativeDragOver = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes('Files')) return
    e.preventDefault()
    if (isPublic) {
      e.dataTransfer.dropEffect = 'none'
      return
    }
    e.dataTransfer.dropEffect = 'copy'
    if (!externalDragOver) setExternalDragOver(true)
  }

  const handleNativeDragLeave = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes('Files')) return
    setExternalDragOver(false)
  }

  const handleNativeDrop = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes('Files')) return
    e.preventDefault()
    setExternalDragOver(false)
    if (isPublic) return
    const file = e.dataTransfer.files?.[0]
    if (file) onExternalFileDrop?.(file, node.id)
  }

  // Drop-target visual styles (internal dnd-kit OR external file drag).
  const showDropHighlight = (isDropTarget || externalDragOver) && !isPublic
  const showInvalidTarget = (isDropTarget || externalDragOver) && isPublic

  const rowClasses = [
    'flex items-center py-1.5 pr-2 cursor-pointer group',
    isSelected ? 'bg-gray-800 text-white' : 'hover:bg-gray-800',
    isDragging ? 'opacity-50' : '',
    showDropHighlight ? 'border-2 border-blue-500 bg-blue-500/10' : '',
    showInvalidTarget ? 'cursor-not-allowed opacity-50' : '',
  ]
    .filter(Boolean)
    .join(' ')

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
        ref={setRowRef}
        className={rowClasses}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelect(node.id)}
        onContextMenu={e => onContextMenu?.(e, node)}
        onDragOver={handleNativeDragOver}
        onDragLeave={handleNativeDragLeave}
        onDrop={handleNativeDrop}
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
                onExternalFileDrop={onExternalFileDrop}
              />
            ))}
        </div>
      )}
    </div>
  )
}
