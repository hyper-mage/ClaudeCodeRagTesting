import { useState, useCallback, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface DocumentMetadata {
  document_type: string
  topic: string
  keywords: string[]
  summary: string
  language: string
}

export interface Document {
  id: string
  filename: string
  file_size: number
  mime_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message: string | null
  chunk_count: number | null
  metadata: DocumentMetadata | null
  created_at: string
  updated_at: string
}

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const { user, session } = useAuth()

  const loadDocuments = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      const data = await apiFetch('/api/documents')
      setDocuments(data)
    } catch {
      // Preserve silent-on-error behavior
    } finally {
      setLoading(false)
    }
  }, [session])

  const uploadDocument = useCallback(async (file: File, folderId?: string) => {
    if (!session) return
    const formData = new FormData()
    formData.append('file', file)
    if (folderId) formData.append('folder_id', folderId)

    let doc
    try {
      doc = await apiFetch('/api/documents/upload', {
        method: 'POST',
        body: formData,
      })
    } catch (e) {
      throw new Error(`Upload failed: ${(e as Error).message}`)
    }

    if (doc.duplicate) {
      return doc  // Don't add to list — it already exists
    }
    setDocuments(prev => [doc, ...prev])
    return doc
  }, [session])

  const deleteDocument = useCallback(async (id: string) => {
    if (!session) return
    await apiFetch(`/api/documents/${id}`, { method: 'DELETE' })
    setDocuments(prev => prev.filter(d => d.id !== id))
  }, [session])

  const bulkDeleteDocuments = useCallback(
    async (ids: string[]) => {
      if (!session || ids.length === 0) return
      try {
        await apiFetch('/api/documents/bulk-delete', {
          method: 'POST',
          body: JSON.stringify({ ids }),
        })
      } catch (e) {
        throw new Error(`Bulk delete failed: ${(e as Error).message}`)
      }
      setDocuments(prev => prev.filter(d => !ids.includes(d.id)))
    },
    [session]
  )

  const bulkMoveDocuments = useCallback(
    async (ids: string[], folderId: string | null) => {
      if (!session || ids.length === 0) return
      try {
        await apiFetch('/api/documents/bulk-move', {
          method: 'POST',
          body: JSON.stringify({ ids, folder_id: folderId }),
        })
      } catch (e) {
        throw new Error(`Bulk move failed: ${(e as Error).message}`)
      }
    },
    [session]
  )

  // Realtime subscription for document status updates
  useEffect(() => {
    if (!user) return

    const channel = supabase
      .channel('documents-status')
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'documents',
        filter: `user_id=eq.${user.id}`,
      }, (payload) => {
        if (payload.eventType === 'UPDATE') {
          setDocuments(prev =>
            prev.map(d => d.id === (payload.new as Document).id ? payload.new as Document : d)
          )
        } else if (payload.eventType === 'INSERT') {
          setDocuments(prev => {
            if (prev.some(d => d.id === (payload.new as Document).id)) return prev
            return [payload.new as Document, ...prev]
          })
        } else if (payload.eventType === 'DELETE') {
          setDocuments(prev =>
            prev.filter(d => d.id !== (payload.old as { id: string }).id)
          )
        }
      })
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [user])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  return {
    documents,
    loading,
    uploadDocument,
    deleteDocument,
    bulkDeleteDocuments,
    bulkMoveDocuments,
    loadDocuments,
  }
}
