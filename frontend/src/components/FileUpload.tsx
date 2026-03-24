import { useState, useRef, type DragEvent } from 'react'
import { Upload } from 'lucide-react'

interface Props {
  onUpload: (file: File) => Promise<any>
}

export default function FileUpload({ onUpload }: Props) {
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const ACCEPTED_TYPES = ['.txt', '.md']

  const handleFile = async (file: File) => {
    setError(null)
    setInfo(null)
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_TYPES.includes(ext)) {
      setError(`Unsupported file type: ${ext}. Supported: .txt, .md`)
      return
    }
    setIsUploading(true)
    try {
      const result = await onUpload(file)
      if (result?.duplicate) {
        setInfo(result.message || 'This file has already been uploaded')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setIsUploading(false)
    }
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  const handleClick = () => fileInputRef.current?.click()

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="p-6">
      <div
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-blue-500 bg-blue-500/10'
            : 'border-gray-700 hover:border-gray-600'
        }`}
      >
        <Upload className="mx-auto mb-4 text-gray-500" size={40} />
        {isUploading ? (
          <p className="text-gray-400">Uploading...</p>
        ) : (
          <>
            <p className="text-gray-300 mb-1">Drag and drop a file here</p>
            <p className="text-gray-500 text-sm">or click to browse</p>
            <p className="text-gray-600 text-xs mt-2">Supports: .txt, .md</p>
          </>
        )}
      </div>
      {error && (
        <p className="mt-3 text-red-400 text-sm">{error}</p>
      )}
      {info && (
        <p className="mt-3 text-amber-400 text-sm">{info}</p>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.md"
        onChange={handleChange}
        className="hidden"
      />
    </div>
  )
}
