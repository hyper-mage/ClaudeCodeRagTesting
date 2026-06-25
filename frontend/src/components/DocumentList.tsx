import { Trash2 } from 'lucide-react'
import type { Document } from '../hooks/useDocuments'

interface Props {
  documents: Document[]
  onDelete: (id: string) => void
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-gray-600 text-gray-200',
  processing: 'bg-blue-600 text-blue-100',
  completed: 'bg-green-600 text-green-100',
  failed: 'bg-red-600 text-red-100',
}

export default function DocumentList({ documents, onDelete }: Props) {
  if (documents.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 text-sm">
        No documents uploaded yet
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {documents.map(doc => (
        <div
          key={doc.id}
          className="group flex items-center px-3 py-2 hover:bg-gray-100 text-sm border-b border-gray-200 dark:hover:bg-gray-800 dark:border-gray-800"
        >
          <div className="flex-1 min-w-0">
            <p className="truncate text-gray-200">{doc.filename}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`px-1.5 py-0.5 rounded text-xs ${STATUS_STYLES[doc.status]}`}>
                {doc.status}
              </span>
              {doc.chunk_count != null && doc.status === 'completed' && (
                <span className="text-gray-500 text-xs">{doc.chunk_count} chunks</span>
              )}
              {doc.status === 'completed' && doc.metadata?.document_type && (
                <span className="bg-purple-600 text-purple-100 px-1.5 py-0.5 rounded text-xs">
                  {doc.metadata.document_type.replace(/_/g, ' ')}
                </span>
              )}
            </div>
            {doc.status === 'completed' && doc.metadata?.topic && (
              <p className="text-gray-500 text-xs mt-0.5 truncate">{doc.metadata.topic}</p>
            )}
            {doc.error_message && (
              <p className="text-red-400 text-xs mt-1 truncate">{doc.error_message}</p>
            )}
          </div>
          <button
            onClick={() => onDelete(doc.id)}
            className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 ml-2 shrink-0"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
