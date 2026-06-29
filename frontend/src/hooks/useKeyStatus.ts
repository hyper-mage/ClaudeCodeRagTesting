import { useState, useCallback, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface KeyStatus {
  connected: boolean
  masked_label?: string
  connected_at?: string
}

// GET /api/keys/balance shape (Plan 01 BalanceResponse). Secret-free by construction — the backend
// returns ONLY these derived display fields, never the key or the raw provider body (T-14-09).
// `limit_remaining` is null for pay-as-you-go (uncapped) accounts; `is_low` is computed SERVER-side
// against LOW_BALANCE_THRESHOLD_USD (D-03 — the threshold never crosses to the client, tamper-proof).
export interface Balance {
  connected: boolean
  limit_remaining: number | null
  is_low: boolean
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
  // Balance is a separate on-demand fetch (GET /api/keys/balance) with its own loading/error state
  // so the dots (isLow) and SettingsPage (4-state balance line) read it independently of status.
  const [balance, setBalance] = useState<Balance | null>(null)
  const [balanceLoading, setBalanceLoading] = useState(false)
  const [balanceError, setBalanceError] = useState(false)
  const { session } = useAuth()

  const connected = status?.connected ?? false

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

  // Same fetch-into-state shape as refresh, gated additionally on `connected`: a no-key fetch would
  // be a pointless OpenRouter round-trip, so skip it (and clear any stale balance) when not connected.
  // On failure we DO NOT throw and DO NOT clear the last-known balance — a transient failure must
  // never flip the dot off green (isLow stays false). We only raise balanceError so SettingsPage can
  // render "Balance unavailable right now." On-demand only — no poll, no Realtime (D-50 / T-14-10).
  const refreshBalance = useCallback(async () => {
    if (!session || !connected) {
      setBalance(null)
      setBalanceError(false)
      return
    }
    setBalanceLoading(true)
    setBalanceError(false)
    try {
      setBalance(await apiFetch('/api/keys/balance'))
    } catch {
      // Keep last-known balance; flag the failure for the settings line (never clobber the dot).
      setBalanceError(true)
    } finally {
      setBalanceLoading(false)
    }
  }, [session, connected])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Fetch balance on demand: on mount and whenever connection state resolves to connected (e.g.
  // after refresh() lands). Gated on connected inside refreshBalance; re-runs only when
  // session/connected change — no poll.
  useEffect(() => {
    refreshBalance()
  }, [refreshBalance])

  // Re-fetch when any instance broadcasts a mutation (e.g. disconnect on the settings page updates
  // the persistent sidebar/top-bar dots). Re-fetch BOTH status and balance so a post-turn broadcast
  // refreshes the balance even when connection state is unchanged.
  useEffect(() => {
    const handler = () => {
      refresh()
      refreshBalance()
    }
    window.addEventListener(KEY_STATUS_EVENT, handler)
    return () => window.removeEventListener(KEY_STATUS_EVENT, handler)
  }, [refresh, refreshBalance])

  // Derived low-balance flag — read the SERVER's is_low directly (D-03: threshold is backend-only,
  // never recomputed here). Defaults to false when balance is unknown so a transient balance failure
  // never clobbers the green dot.
  const isLow = balance?.is_low ?? false

  return { status, loading, refresh, balance, isLow, balanceLoading, balanceError, refreshBalance }
}
