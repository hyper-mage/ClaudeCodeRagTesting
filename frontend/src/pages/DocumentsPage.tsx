import { useDocuments } from '../hooks/useDocuments'
import DocumentList from '../components/DocumentList'
import FileUpload from '../components/FileUpload'

export default function DocumentsPage() {
  const { documents, uploadDocument, deleteDocument } = useDocuments()

  const handleUpload = async (file: File) => {
    return await uploadDocument(file)
  }

  return (
    <div className="flex-1 bg-gray-950 text-white flex overflow-hidden">
      <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
        <div className="p-3 border-b border-gray-800">
          <h2 className="text-sm font-medium text-gray-300">Documents</h2>
        </div>
        <DocumentList documents={documents} onDelete={deleteDocument} />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="w-full max-w-lg">
          <FileUpload onUpload={handleUpload} />
        </div>
      </div>
    </div>
  )
}
