import { useState, useCallback, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'

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
      const res = await fetch('/api/documents', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setDocuments(data)
      }
    } finally {
      setLoading(false)
    }
  }, [session])

  const uploadDocument = useCallback(async (file: File, folderId?: string) => {
    if (!session) return
    const formData = new FormData()
    formData.append('file', file)
    if (folderId) formData.append('folder_id', folderId)

    const res = await fetch('/api/documents/upload', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
      body: formData,
    })

    if (!res.ok) {
      const body = await res.text()
      throw new Error(`Upload failed: ${body}`)
    }

    const doc = await res.json()
    if (doc.duplicate) {
      return doc  // Don't add to list — it already exists
    }
    setDocuments(prev => [doc, ...prev])
    return doc
  }, [session])

  const deleteDocument = useCallback(async (id: string) => {
    if (!session) return
    await fetch(`/api/documents/${id}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
    setDocuments(prev => prev.filter(d => d.id !== id))
  }, [session])

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

  return { documents, loading, uploadDocument, deleteDocument, loadDocuments }
}
