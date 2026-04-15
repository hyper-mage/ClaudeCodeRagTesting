import { useEffect } from 'react'
import { FolderInput, Trash2 } from 'lucide-react'

interface Props {
  selectedCount: number
  onDelete: () => void
  onMove: () => void
  onClear: () => void
}

export default function BulkActionBar({
  selectedCount,
  onDelete,
  onMove,
  onClear,
}: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClear()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClear])

  return (
    <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 flex items-center justify-between">
      <span className="text-sm text-gray-300">{selectedCount} selected</span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onDelete}
          className="bg-red-600 hover:bg-red-700 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1"
        >
          <Trash2 size={14} />
          Delete {selectedCount} Items
        </button>
        <button
          type="button"
          onClick={onMove}
          className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1"
        >
          <FolderInput size={14} />
          Move to...
        </button>
      </div>
    </div>
  )
}
