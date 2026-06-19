import { useState } from 'react'
import ConfirmDialog from '../components/ConfirmDialog'
import { useKeyStatus } from '../hooks/useKeyStatus'
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
  const { status, loading, refresh } = useKeyStatus()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const handleConnect = () => {
    startOpenRouterConnect()
  }

  const handleDisconnect = async () => {
    setConfirmOpen(false)
    await apiFetch('/api/keys', { method: 'DELETE' })
    refresh()
  }

  return (
    <div className="flex-1 bg-gray-950 text-white overflow-y-auto p-4">
      <div className="bg-gray-900 rounded-lg p-6 max-w-md">
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
              <span className="text-sm text-green-400">Connected</span>
            </div>
            {status.masked_label && (
              <p className="text-sm font-mono mt-2">{status.masked_label}</p>
            )}
            {status.connected_at && (
              <p className="text-xs text-gray-400 mt-2">
                Connected since {formatConnectedSince(status.connected_at)}
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
            <p className="text-sm text-gray-400">
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
