import { useState, useCallback, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface KeyStatus {
  connected: boolean
  masked_label?: string
  connected_at?: string
}

// Shared GET /api/keys/status fetch-into-state. Mirrors useDocuments.loadDocuments:
// gates on the Supabase session, sets a loading flag, silent-on-error catch (keeps
// last-known status), clears loading in finally. Fetches once on mount; callers
// invoke refresh() after their own connect/disconnect. Does NOT poll and does NOT
// add a Realtime subscription — key state only changes via the user's own actions.
export function useKeyStatus() {
  const [status, setStatus] = useState<KeyStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const { session } = useAuth()

  const refresh = useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      setStatus(await apiFetch('/api/keys/status'))
    } catch {
      // Preserve silent-on-error behavior (keep last-known status)
    } finally {
      setLoading(false)
    }
  }, [session])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { status, loading, refresh }
}
