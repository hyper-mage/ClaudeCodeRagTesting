import { useState, useCallback, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface KeyStatus {
  connected: boolean
  masked_label?: string
  connected_at?: string
}

// Cross-instance refresh signal. useKeyStatus is a per-component hook, so the
// persistent IconSidebar / MobileTopBar connection dots hold independent state
// from the SettingsPage instance. A connect goes through a full OAuth page reload
// (every instance remounts), but a disconnect is in-SPA — so after disconnect the
// dots would stay stale without this broadcast. notifyKeyStatusChanged() pokes
// every live instance to re-fetch, keeping the "always-visible accurate" dot
// contract (D-02/D-04) without polling.
const KEY_STATUS_EVENT = 'openrouter-key-status-changed'

export function notifyKeyStatusChanged() {
  window.dispatchEvent(new Event(KEY_STATUS_EVENT))
}

// Shared GET /api/keys/status fetch-into-state. Mirrors useDocuments.loadDocuments:
// gates on the Supabase session, sets a loading flag, silent-on-error catch (keeps
// last-known status), clears loading in finally. Fetches once on mount and on every
// notifyKeyStatusChanged() broadcast. Does NOT poll and does NOT add a Realtime
// subscription — key state only changes via the user's own actions.
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

  // Re-fetch when any instance broadcasts a mutation (e.g. disconnect on the
  // settings page updates the persistent sidebar/top-bar dots).
  useEffect(() => {
    const handler = () => refresh()
    window.addEventListener(KEY_STATUS_EVENT, handler)
    return () => window.removeEventListener(KEY_STATUS_EVENT, handler)
  }, [refresh])

  return { status, loading, refresh }
}
