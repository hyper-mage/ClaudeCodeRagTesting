import { File, FileText, Image, Trash2 } from 'lucide-react'
import { useDraggable } from '@dnd-kit/react'
import type { Document } from '../hooks/useDocuments'
import InlineRename from './InlineRename'

interface Props {
  doc: Document
  onDelete: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, doc: Document) => void
  isRenaming?: boolean
  onStartRename?: (id: string) => void
  onConfirmRename?: (id: string, newName: string) => void
  onCancelRename?: () => void
  isSelected?: boolean
  onToggleSelect?: (id: string, shiftKey: boolean) => void
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-gray-600 text-gray-200',
  processing: 'bg-blue-600 text-blue-100',
  completed: 'bg-green-600 text-green-100',
  failed: 'bg-red-600 text-red-100',
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function renderIcon(mime: string) {
  const cls = 'text-gray-400 mr-2 shrink-0'
  if (mime === 'text/plain' || mime === 'text/markdown' || mime.startsWith('text/')) {
    return <FileText size={14} className={cls} />
  }
  if (mime === 'image/jpeg' || mime === 'image/png' || mime.startsWith('image/')) {
    return <Image size={14} className={cls} />
  }
  return <File size={14} className={cls} />
}

function extensionOf(filename: string): string {
  const parts = filename.split('.')
  if (parts.length <= 1) return ''
  return parts[parts.length - 1].toUpperCase()
}

export default function FileListRow({
  doc,
  onDelete,
  onContextMenu,
  isRenaming,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  isSelected,
  onToggleSelect,
}: Props) {
  const { ref: dragRef, isDragging } = useDraggable({
    id: `file-${doc.id}`,
  })

  const rowClasses = [
    'flex items-center px-4 py-2 text-sm border-b border-gray-800 group',
    isSelected ? 'bg-gray-800/50' : 'hover:bg-gray-800',
    isDragging ? 'opacity-50' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      ref={dragRef}
      className={rowClasses}
      onContextMenu={e => onContextMenu?.(e, doc)}
      onClick={e => {
        // Clicking the row (not the checkbox) with shift performs range select.
        if (e.shiftKey && onToggleSelect) {
          e.preventDefault()
          onToggleSelect(doc.id, true)
        }
      }}
    >
      {/* Checkbox */}
      <div className="w-4 shrink-0 flex items-center">
        <input
          type="checkbox"
          checked={!!isSelected}
          onChange={() => onToggleSelect?.(doc.id, false)}
          onClick={e => {
            e.stopPropagation()
          }}
          className="accent-blue-600"
          aria-label={`Select ${doc.filename}`}
        />
      </div>
      <span className="ml-2 flex items-center">{renderIcon(doc.mime_type || '')}</span>
      {isRenaming ? (
        <div className="flex-1" onClick={e => e.stopPropagation()}>
          <InlineRename
            currentName={doc.filename}
            onConfirm={name => onConfirmRename?.(doc.id, name)}
            onCancel={() => onCancelRename?.()}
          />
        </div>
      ) : (
        <div
          className="flex-1 truncate text-gray-200 text-sm"
          onDoubleClick={() => onStartRename?.(doc.id)}
        >
          {doc.filename}
        </div>
      )}
      <span
        className={`px-1.5 py-0.5 rounded text-xs ${STATUS_STYLES[doc.status] ?? 'bg-gray-600 text-gray-200'} mr-4`}
      >
        {doc.status}
      </span>
      <span className="w-20 text-xs text-gray-500 text-right">
        {extensionOf(doc.filename)}
      </span>
      <span className="w-20 text-xs text-gray-500 text-right">
        {formatFileSize(doc.file_size)}
      </span>
      <button
        type="button"
        onClick={e => {
          e.stopPropagation()
          onDelete(doc.id)
        }}
        className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 ml-2 shrink-0"
        aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
