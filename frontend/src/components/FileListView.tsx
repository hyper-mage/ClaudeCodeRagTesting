import { useRef } from 'react'
import { Folder, FolderPlus, Upload } from 'lucide-react'
import type { Document } from '../hooks/useDocuments'
import type { FolderNode, FolderRow } from '../hooks/useFolderTree'
import FileListRow from './FileListRow'
import InlineRename from './InlineRename'

interface Props {
  folder: FolderRow | null
  subfolders: FolderNode[]
  documents: Document[]
  loading: boolean
  onDeleteDoc: (id: string) => void
  onSelectFolder: (id: string) => void
  onUpload: (file: File) => Promise<unknown>
  isReadOnly: boolean
  onContextMenu?: (e: React.MouseEvent, target: FolderNode | Document) => void
  renamingId?: string | null
  onStartRename?: (id: string) => void
  onConfirmRename?: (id: string, newName: string) => void
  onCancelRename?: () => void
  creatingInCurrentFolder?: boolean
  onStartCreate?: () => void
  onConfirmCreate?: (name: string) => void
  onCancelCreate?: () => void
}

export default function FileListView({
  folder,
  subfolders,
  documents,
  loading,
  onDeleteDoc,
  onSelectFolder,
  onUpload,
  isReadOnly,
  onContextMenu,
  renamingId,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  creatingInCurrentFolder,
  onStartCreate,
  onConfirmCreate,
  onCancelCreate,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const triggerUpload = () => fileInputRef.current?.click()

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      try {
        await onUpload(file)
      } catch {
        // Errors bubble up to FileUpload pattern; here silently swallow for now
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const folderName = folder?.name ?? ''

  const isEmpty =
    subfolders.length === 0 && documents.length === 0 && !creatingInCurrentFolder

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="h-10 px-4 border-b border-gray-800 flex items-center justify-between shrink-0">
        <span className="text-sm text-gray-200 truncate">{folderName}</span>
        {!isReadOnly && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={triggerUpload}
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1"
            >
              <Upload size={14} />
              Upload File
            </button>
            <button
              type="button"
              onClick={() => onStartCreate?.()}
              className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-3 py-1.5 rounded flex items-center gap-1"
            >
              <FolderPlus size={14} />
              New Folder
            </button>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          onChange={handleFileChange}
          className="hidden"
          accept=".txt,.md,.pdf,.docx,.html,.htm,.jpg,.jpeg,.png,.xlsx"
        />
      </div>

      {/* Content list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-sm text-gray-500">Loading...</div>
        ) : isEmpty ? (
          <div className="p-8 text-center">
            {isReadOnly ? (
              <p className="text-sm text-gray-500">
                No documents in this folder yet.
              </p>
            ) : (
              <>
                <h3 className="text-sm text-gray-300 mb-1">
                  This folder is empty
                </h3>
                <p className="text-xs text-gray-500">
                  Upload files or create subfolders to organize your documents.
                </p>
              </>
            )}
          </div>
        ) : (
          <>
            {creatingInCurrentFolder && (
              <div className="flex items-center px-4 py-2 text-sm border-b border-gray-800">
                <div className="w-4 shrink-0" />
                <Folder size={14} className="text-gray-400 mr-2 shrink-0" />
                <div className="flex-1">
                  <InlineRename
                    placeholder="New folder name"
                    onConfirm={name => onConfirmCreate?.(name)}
                    onCancel={() => onCancelCreate?.()}
                  />
                </div>
                <span className="w-20 text-xs text-gray-500 text-right">
                  FOLDER
                </span>
                <span className="w-20 text-xs text-gray-500 text-right" />
                <div className="w-4 ml-2 shrink-0" />
              </div>
            )}
            {subfolders.map(sf => (
              <div
                key={sf.id}
                className="flex items-center px-4 py-2 hover:bg-gray-800 text-sm border-b border-gray-800 cursor-pointer group"
                onClick={() => onSelectFolder(sf.id)}
                onContextMenu={e => onContextMenu?.(e, sf)}
              >
                <div className="w-4 shrink-0" />
                <Folder size={14} className="text-gray-400 mr-2 shrink-0" />
                <div
                  className={`flex-1 truncate text-sm ${
                    sf.visibility === 'public' ? 'text-gray-500' : 'text-gray-200'
                  }`}
                >
                  {sf.name}
                </div>
                <span className="w-20 text-xs text-gray-500 text-right">FOLDER</span>
                <span className="w-20 text-xs text-gray-500 text-right" />
                <div className="w-4 ml-2 shrink-0" />
              </div>
            ))}
            {documents.map(doc => (
              <FileListRow
                key={doc.id}
                doc={doc}
                onDelete={onDeleteDoc}
                onContextMenu={onContextMenu}
                isRenaming={renamingId === doc.id}
                onStartRename={onStartRename}
                onConfirmRename={onConfirmRename}
                onCancelRename={onCancelRename}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
