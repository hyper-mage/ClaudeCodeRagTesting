import { File, FileText, Image, Trash2 } from 'lucide-react'
import type { Document } from '../hooks/useDocuments'

interface Props {
  doc: Document
  onDelete: (id: string) => void
  onContextMenu?: (e: React.MouseEvent, doc: Document) => void
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

export default function FileListRow({ doc, onDelete, onContextMenu }: Props) {
  return (
    <div
      className="flex items-center px-4 py-2 hover:bg-gray-800 text-sm border-b border-gray-800 group"
      onContextMenu={e => onContextMenu?.(e, doc)}
    >
      {/* Checkbox placeholder for Plan 04 */}
      <div className="w-4 shrink-0" />
      {renderIcon(doc.mime_type || '')}
      <div className="flex-1 truncate text-gray-200 text-sm">{doc.filename}</div>
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
        onClick={() => onDelete(doc.id)}
        className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 ml-2 shrink-0"
        aria-label="Delete"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}
