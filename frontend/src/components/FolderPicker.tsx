import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Folder, FolderOpen, ChevronDown, ChevronRight, Home } from 'lucide-react'
import type { FolderNode } from '../hooks/useFolderTree'
import { ROOT_PRIVATE_ID } from '../hooks/useFolderTree'

interface Props {
  folders: FolderNode[]
  currentFolderId: string | null
  excludeFolderId?: string | null
  onSelect: (folderId: string | null) => void
  onCancel: () => void
}

interface RowProps {
  node: FolderNode
  depth: number
  selectedId: string | null
  excludeId: string | null
  expandedIds: Set<string>
  onPick: (id: string) => void
  onToggle: (id: string) => void
}

function PickerRow({
  node,
  depth,
  selectedId,
  excludeId,
  expandedIds,
  onPick,
  onToggle,
}: RowProps) {
  if (excludeId && node.id === excludeId) return null
  const isExpanded = expandedIds.has(node.id)
  const isSelected = selectedId === node.id
  const hasChildren = node.children.length > 0

  return (
    <div>
      <div
        className={`flex items-center py-1.5 pr-2 cursor-pointer text-sm ${
          isSelected ? 'bg-blue-600/30 text-white' : 'hover:bg-gray-800 text-gray-200'
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onPick(node.id)}
      >
        <button
          type="button"
          onClick={e => {
            e.stopPropagation()
            if (hasChildren) onToggle(node.id)
          }}
          className="shrink-0 w-4 h-4 flex items-center justify-center text-gray-500 hover:text-gray-300"
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
        <span className="ml-1.5 truncate">{node.name}</span>
      </div>
      {isExpanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <PickerRow
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              excludeId={excludeId}
              expandedIds={expandedIds}
              onPick={onPick}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FolderPicker({
  folders,
  currentFolderId,
  excludeFolderId,
  onSelect,
  onCancel,
}: Props) {
  const [chosenId, setChosenId] = useState<string | null>(currentFolderId)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set([ROOT_PRIVATE_ID]))

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onCancel])

  const toggleExpand = (id: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // Filter to private folders only (exclude the virtual public root)
  const privateRoot = folders.find(f => f.id === ROOT_PRIVATE_ID)
  const privateChildren = privateRoot?.children ?? []

  const confirm = () => {
    // null = root, ROOT_PRIVATE_ID sentinel also maps to root (null parent)
    const resolved = chosenId === ROOT_PRIVATE_ID ? null : chosenId
    onSelect(resolved)
  }

  return createPortal(
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onCancel}
    >
      <div
        className="bg-gray-900 border border-gray-700 rounded-lg p-4 max-w-sm w-full mx-4 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        <h2 className="text-sm font-bold text-white mb-3">Move to...</h2>
        <div className="max-h-80 overflow-y-auto border border-gray-800 rounded">
          {/* Root option */}
          <div
            className={`flex items-center py-1.5 pr-2 pl-2 cursor-pointer text-sm ${
              chosenId === null || chosenId === ROOT_PRIVATE_ID
                ? 'bg-blue-600/30 text-white'
                : 'hover:bg-gray-800 text-gray-200'
            }`}
            onClick={() => setChosenId(ROOT_PRIVATE_ID)}
          >
            <Home size={14} className="text-gray-400 mr-2 shrink-0" />
            <span className="truncate">My Documents (root)</span>
          </div>
          {privateChildren.map(node => (
            <PickerRow
              key={node.id}
              node={node}
              depth={0}
              selectedId={chosenId}
              excludeId={excludeFolderId ?? null}
              expandedIds={expandedIds}
              onPick={setChosenId}
              onToggle={toggleExpand}
            />
          ))}
        </div>
        <div className="flex gap-3 mt-4 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="bg-gray-700 hover:bg-gray-600 text-white text-sm px-4 py-2 rounded"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={confirm}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-2 rounded"
          >
            Move Here
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
