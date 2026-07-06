import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import ConfirmDialog from '../components/ConfirmDialog'
import DefaultModelSelector from '../components/DefaultModelSelector'
import ThemeToggle from '../components/ThemeToggle'
import type { ModelResponse } from '../components/ModelSelector'
import { useKeyStatus, notifyKeyStatusChanged } from '../hooks/useKeyStatus'
import { apiFetch } from '../lib/api'
import { startOpenRouterConnect } from '../lib/pkce'

// Format the stored connected_at ISO timestamp as a locale-friendly short date
// (e.g. "Jun 19, 2026"), no time-of-day — per UI-SPEC Copywriting Contract.
function formatConnectedSince(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default function SettingsPage() {
  // Key status + on-demand balance (Plan 02 contract: balance/balanceLoading/balanceError; the
  // four-state balance line composes these per 14-02-SUMMARY's documented field names).
  const { status, loading, balance, balanceLoading, balanceError } = useKeyStatus()
  const [confirmOpen, setConfirmOpen] = useState(false)
  // This page now owns the default-model control (D-06 relocation), so it seeds the current
  // default + the shared catalog itself — mirroring ChatPage's silent-on-failure, array-guarded
  // mount fetches. The Theme toggle self-PUTs and needs no local state here.
  const [defaultModel, setDefaultModel] = useState<string | null>(null)
  const [models, setModels] = useState<ModelResponse[] | undefined>(undefined)

  // One-time catalog fetch (silent on failure). Only set when the payload is actually an array so a
  // malformed response can never poison `models` (ModelSelector's rows.map would crash otherwise).
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/models')
      .then((data: unknown) => {
        if (!cancelled && Array.isArray(data)) setModels(data as ModelResponse[])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Seed the current default model from preferences (best-effort; a failed GET leaves it null and
  // DefaultModelSelector shows its placeholder). Theme reconcile stays in ChatPage (global concern).
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/preferences')
      .then((prefs: { default_model?: string | null } | null) => {
        if (cancelled || !prefs) return
        if (prefs.default_model !== undefined) setDefaultModel(prefs.default_model ?? null)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  const handleConnect = () => {
    // Stale-stash hygiene (Pitfall 6 / T-15-18): useKeyGate is the stash's ONLY writer. A plain
    // Settings connect must never auto-apply a leftover pick from an earlier abandoned gate flow.
    sessionStorage.removeItem('or_pending_selection')
    startOpenRouterConnect()
  }

  const handleDisconnect = async () => {
    setConfirmOpen(false)
    await apiFetch('/api/keys', { method: 'DELETE' })
    // Broadcast so this card AND the persistent sidebar/top-bar dots flip to
    // not-connected without a page reload (refresh() alone only updates this
    // instance). See notifyKeyStatusChanged() in useKeyStatus.
    notifyKeyStatusChanged()
  }

  return (
    // Theme-aware page surface (D-06): white in light, gray-950 in dark — the page hosts the Theme
    // toggle now, so it must read coherently in both themes (no orphan dark panel in light mode).
    <div className="flex-1 bg-white text-gray-900 dark:bg-gray-950 dark:text-white overflow-y-auto p-4">
      <div className="bg-gray-50 border border-gray-200 dark:bg-gray-900 dark:border-gray-800 rounded-lg p-6 max-w-md">
        <h1 className="text-2xl font-bold">Settings</h1>

        <h2 className="text-base font-semibold mt-6">OpenRouter</h2>

        {loading ? (
          <div className="mt-4">
            <span className="inline-block w-6 h-6 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : status?.connected ? (
          <div className="mt-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              <span className="text-sm font-semibold text-green-600 dark:text-green-400">
                Your key: connected
              </span>
            </div>
            {status.masked_label && (
              <p className="text-sm font-mono mt-2">{status.masked_label}</p>
            )}
            {status.connected_at && (
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                Connected since {formatConnectedSince(status.connected_at)}
              </p>
            )}

            {/* Balance line — four locked states (COST-02). limit_remaining is rendered as reported
                by OpenRouter, never recomputed client-side (ROADMAP SC#1 / Phase 11 D-04). The
                loading/failed states compose `&& balance === null` so an in-flight refetch never
                masks an already-resolved value (14-02-SUMMARY guidance). */}
            {balanceLoading && balance === null ? (
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">Checking balance…</p>
            ) : balanceError && balance === null ? (
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                Balance unavailable right now.
              </p>
            ) : balance === null ? null : !balance.connected ? (
              // IN-01: a key deleted between the status fetch and the balance fetch returns
              // {connected:false, limit_remaining:null}. Treat that as unavailable — NOT as
              // "Pay-as-you-go — no limit set", which would mislabel a disconnected key.
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                Balance unavailable right now.
              </p>
            ) : balance.limit_remaining === null ? (
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                Pay-as-you-go — no limit set
              </p>
            ) : (
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
                Balance: ${balance.limit_remaining.toFixed(2)}
              </p>
            )}

            {/* Low-balance warning line (COST-03 / D-05 surface #2). Gated on the SERVER-computed
                is_low — the FE never re-derives low-ness from a client threshold (T-14-18). Inline
                caption with the lucide AlertTriangle as the warning mark — not a pill/toast/banner. */}
            {balance?.is_low && (
              <p className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300 mt-2">
                <AlertTriangle size={14} className="text-amber-500 shrink-0" aria-hidden="true" />
                <span>Balance low: ${balance.limit_remaining?.toFixed(2)} — add credits</span>
              </p>
            )}

            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              className="bg-red-600 hover:bg-red-700 text-white text-base font-semibold w-full py-3 rounded mt-4"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <div className="mt-4">
            <p className="text-sm font-semibold">No key — connect to chat</p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
              Connect your OpenRouter account to chat with your own key. No key to
              copy or paste.
            </p>
            <button
              type="button"
              onClick={handleConnect}
              className="bg-blue-600 hover:bg-blue-700 text-white text-base font-semibold w-full py-3 rounded mt-4"
            >
              Connect OpenRouter
            </button>
          </div>
        )}

        {/* Default model section (D-06). DefaultModelSelector supplies its own "Default model"
            heading + helper, so the page must NOT add a duplicate heading. */}
        <div className="mt-6">
          <DefaultModelSelector value={defaultModel} onChange={setDefaultModel} models={models} />
        </div>

        {/* Theme section (D-06): heading row + the self-contained ThemeToggle. */}
        <h2 className="text-base font-semibold mt-6">Theme</h2>
        <div className="mt-2">
          <ThemeToggle />
        </div>
      </div>

      {confirmOpen && (
        <ConfirmDialog
          heading="Disconnect OpenRouter?"
          body="You'll need to reconnect to chat with your own key."
          confirmLabel="Disconnect"
          cancelLabel="Cancel"
          onConfirm={handleDisconnect}
          onCancel={() => setConfirmOpen(false)}
        />
      )}
    </div>
  )
}
