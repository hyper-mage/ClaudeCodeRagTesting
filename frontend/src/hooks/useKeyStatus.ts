import { useCallback, useEffect, useReducer } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { apiFetch } from '../lib/api'

export interface KeyStatus {
  connected: boolean
  masked_label?: string
  connected_at?: string
  // Demo-fallback flag (Phase 15 D-03/D-11), carried on GET /api/keys/status — the smallest seam
  // (UI-SPEC resolved). Optional: while status is null/loading it is undefined, which downstream
  // render conditions treat as false (no flash-gate, no flash-banner).
  demo_enabled?: boolean
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

// Cross-instance refresh signal. useKeyStatus is consumed by THREE always-mounted-ish surfaces —
// IconSidebar (desktop rail, md:flex), MobileTopBar (md:hidden), and SettingsPage — so a connect
// goes through a full OAuth page reload (every instance remounts), but a disconnect is in-SPA. After
// a disconnect the dots would stay stale without this broadcast. notifyKeyStatusChanged() pokes the
// shared store to re-fetch, keeping the "always-visible accurate" dot contract (D-02/D-04) without
// polling.
const KEY_STATUS_EVENT = 'openrouter-key-status-changed'

export function notifyKeyStatusChanged() {
  window.dispatchEvent(new Event(KEY_STATUS_EVENT))
}

// --- Shared module-level store (WR-02) -------------------------------------------------------
// Previously each useKeyStatus() instance held its OWN state and independently fired GET
// /api/keys/status AND GET /api/keys/balance on mount + on every broadcast. Because both
// IconSidebar and MobileTopBar are mounted on every page regardless of viewport (plus SettingsPage),
// navigating to Settings fired ~3 simultaneous authenticated OpenRouter round-trips for the same
// data — multiplying the user's OpenRouter usage and amplifying WR-01's event-loop blocking.
//
// Now all instances read ONE shared store and share a single in-flight request, so one /status and
// one /balance call serve every consumer. Still on-demand only — no polling, no Realtime (D-50 /
// T-14-10): the store fetches on first mount and on each notifyKeyStatusChanged() broadcast.
interface KeyStatusState {
  status: KeyStatus | null
  loading: boolean
  balance: Balance | null
  balanceLoading: boolean
  balanceError: boolean
}

let store: KeyStatusState = {
  status: null,
  loading: true,
  balance: null,
  balanceLoading: false,
  balanceError: false,
}

const subscribers = new Set<() => void>()

function emit() {
  subscribers.forEach((cb) => cb())
}

function setStore(patch: Partial<KeyStatusState>) {
  store = { ...store, ...patch }
  emit()
}

// In-flight promise dedup: when several instances mount together (or a broadcast hits every
// instance at once) the concurrent callers share ONE network round-trip instead of N.
let statusInFlight: Promise<void> | null = null
let balanceInFlight: Promise<void> | null = null

// Shared balance fetch. Gated on connected (a no-key fetch would be a pointless OpenRouter
// round-trip), clears any stale balance when not connected. On failure we DO NOT clear the
// last-known balance — a transient failure must never flip the dot off green (isLow stays false);
// we only raise balanceError so SettingsPage can render "Balance unavailable right now."
async function loadBalance(): Promise<void> {
  const connected = store.status?.connected ?? false
  if (!connected) {
    setStore({ balance: null, balanceError: false })
    return
  }
  if (balanceInFlight) return balanceInFlight
  setStore({ balanceLoading: true, balanceError: false })
  balanceInFlight = (async () => {
    try {
      setStore({ balance: await apiFetch('/api/keys/balance') })
    } catch {
      // Keep last-known balance; flag the failure for the settings line (never clobber the dot).
      setStore({ balanceError: true })
    } finally {
      setStore({ balanceLoading: false })
      balanceInFlight = null
    }
  })()
  return balanceInFlight
}

// Shared status fetch (silent on error — keep last-known status). After status resolves we chain
// loadBalance() so connection-state changes (e.g. a connect resolving to connected) refresh the
// balance. The chain runs ONCE per real fetch: concurrent callers return the in-flight promise and
// never trigger their own balance fetch.
async function loadStatus(): Promise<void> {
  if (statusInFlight) return statusInFlight
  setStore({ loading: true })
  statusInFlight = (async () => {
    try {
      setStore({ status: await apiFetch('/api/keys/status') })
    } catch {
      // Preserve silent-on-error behavior (keep last-known status)
    } finally {
      setStore({ loading: false })
      statusInFlight = null
    }
  })()
  await statusInFlight
  await loadBalance()
}

// Per-component hook: subscribes to the shared store and re-renders on any update, but all fetching
// flows through the shared, deduped loaders above. Public surface (status/loading/balance/isLow/
// balanceLoading/balanceError/refresh/refreshBalance) is unchanged for IconSidebar, MobileTopBar,
// and SettingsPage.
export function useKeyStatus() {
  const [, forceRender] = useReducer((n: number) => n + 1, 0)
  const { session } = useAuth()

  // Subscribe to shared-store updates for this instance's lifetime.
  useEffect(() => {
    subscribers.add(forceRender)
    return () => {
      subscribers.delete(forceRender)
    }
  }, [])

  const refresh = useCallback(async () => {
    if (!session) return
    await loadStatus()
  }, [session])

  const refreshBalance = useCallback(async () => {
    if (!session) return
    await loadBalance()
  }, [session])

  // Fetch once on mount (deduped across all mounted instances). loadStatus chains loadBalance.
  useEffect(() => {
    refresh()
  }, [refresh])

  // Re-fetch when any instance broadcasts a mutation (e.g. disconnect on the settings page updates
  // the persistent sidebar/top-bar dots). refresh() re-fetches status AND chains balance, so a
  // post-turn broadcast refreshes the balance even when connection state is unchanged.
  useEffect(() => {
    const handler = () => {
      refresh()
    }
    window.addEventListener(KEY_STATUS_EVENT, handler)
    return () => window.removeEventListener(KEY_STATUS_EVENT, handler)
  }, [refresh])

  // Derived low-balance flag — read the SERVER's is_low directly (D-03: threshold is backend-only,
  // never recomputed here). Defaults to false when balance is unknown so a transient balance failure
  // never clobbers the green dot.
  const isLow = store.balance?.is_low ?? false

  return {
    status: store.status,
    loading: store.loading,
    refresh,
    balance: store.balance,
    isLow,
    balanceLoading: store.balanceLoading,
    balanceError: store.balanceError,
    refreshBalance,
  }
}
