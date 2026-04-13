import { useMemo } from 'react'
import { useDocuments } from '../hooks/useDocuments'
import {
  useFolderTree,
  ROOT_PUBLIC_ID,
  ROOT_PRIVATE_ID,
} from '../hooks/useFolderTree'
import FolderTree from '../components/FolderTree'
import FileListView from '../components/FileListView'
import Breadcrumb from '../components/Breadcrumb'
import FileUpload from '../components/FileUpload'

export default function DocumentsPage() {
  const { uploadDocument, deleteDocument } = useDocuments()
  const {
    folders,
    rawFolders,
    selectedFolderId,
    expandedIds,
    folderContents,
    loadingContents,
    selectFolder,
    toggleExpand,
    breadcrumbs,
  } = useFolderTree()

  const selectedFolder = useMemo(() => {
    if (!selectedFolderId) return null
    if (selectedFolderId === ROOT_PUBLIC_ID || selectedFolderId === ROOT_PRIVATE_ID) {
      return {
        id: selectedFolderId,
        name: selectedFolderId === ROOT_PUBLIC_ID ? 'Board Games' : 'My Documents',
        visibility: selectedFolderId === ROOT_PUBLIC_ID ? 'public' : 'private',
      }
    }
    const found = rawFolders.find(f => f.id === selectedFolderId)
    return found ?? null
  }, [selectedFolderId, rawFolders])

  const isReadOnly = selectedFolder?.visibility === 'public'

  const handleUpload = async (file: File, overrideFolderId?: string) => {
    // Determine folder_id: only real (non-virtual) private folder ids are valid
    let targetFolderId: string | undefined = overrideFolderId
    if (targetFolderId === undefined && selectedFolderId) {
      if (
        selectedFolderId !== ROOT_PUBLIC_ID &&
        selectedFolderId !== ROOT_PRIVATE_ID &&
        !isReadOnly
      ) {
        targetFolderId = selectedFolderId
      }
    }
    return await uploadDocument(file, targetFolderId)
  }

  return (
    <div className="flex-1 bg-gray-950 text-white flex overflow-hidden">
      {/* Tree Sidebar */}
      <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full overflow-y-auto">
        <FolderTree
          folders={folders}
          selectedFolderId={selectedFolderId}
          expandedIds={expandedIds}
          onSelect={selectFolder}
          onToggleExpand={toggleExpand}
        />
      </div>

      {/* Content Panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedFolderId ? (
          <>
            <Breadcrumb segments={breadcrumbs} onNavigate={selectFolder} />
            <FileListView
              folder={folderContents?.folder ?? null}
              subfolders={folderContents?.subfolders ?? []}
              documents={folderContents?.documents ?? []}
              loading={loadingContents}
              onDeleteDoc={deleteDocument}
              onSelectFolder={selectFolder}
              onUpload={handleUpload}
              isReadOnly={!!isReadOnly}
            />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="w-full max-w-lg">
              <FileUpload onUpload={handleUpload} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
