import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { startOpenRouterConnect } from '../lib/pkce'
import { useToast } from '../contexts/ToastContext'
import type { ModelResponse } from '../components/ModelSelector'

type CallbackState = 'in-flight' | 'failure'

// Locked D-02 stash contract — written by useKeyGate immediately before the OAuth
// redirect; consumed here ONE-SHOT after a successful exchange.
interface PendingSelection {
  kind: 'thread' | 'default'
  modelId: string
  threadId?: string
  returnTo: string
}

// T-15-10: stash contents are client-writable — post-apply navigation may only
// target these SPA paths, and only via navigate() (never window.location).
const RETURN_TO_ALLOWLIST = ['/', '/settings']

function parsePendingSelection(raw: string): PendingSelection | null {
  try {
    const parsed = JSON.parse(raw) as PendingSelection
    return parsed !== null && typeof parsed === 'object' ? parsed : null
  } catch {
    // Unparseable stash → treated exactly like no stash (legacy path).
    return null
  }
}

// One-shot OAuth callback state machine (KEY-01).
//
// On mount (guarded against React StrictMode double-run), read code+state from
// the URL and verifier+state from sessionStorage (NOT React state — Pitfall 3,
// so a hard refresh re-runs successfully, D-07). CSRF check: reject when the
// returned state does not match the stored one. On success: clear the
// sessionStorage keys, then consume any `or_pending_selection` stash ONE-SHOT
// (D-02 resume: apply the pre-OAuth model pick via thread PATCH / prefs PUT,
// combined toast, navigate to the allowlisted returnTo); with no stash the
// legacy path is unchanged (plain toast → /settings). On ANY exchange error
// render the locked generic failure sentence — the caught error / HTTP status /
// any sk-or-… fragment is NEVER interpolated into the UI (Pitfall 1 / D-06).
// An APPLY error never renders the failure screen (the connection succeeded).
export default function OAuthCallbackPage() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [state, setState] = useState<CallbackState>('in-flight')
  const ranRef = useRef(false)

  useEffect(() => {
    if (ranRef.current) return
    ranRef.current = true

    const run = async () => {
      const params = new URLSearchParams(window.location.search)
      const code = params.get('code')
      const returnedState = params.get('state')
      const verifier = sessionStorage.getItem('or_pkce_verifier')
      const storedState = sessionStorage.getItem('or_pkce_state')

      try {
        if (!code || !verifier || returnedState !== storedState) {
          throw new Error('csrf')
        }
        await apiFetch('/api/keys/openrouter/exchange', {
          method: 'POST',
          body: JSON.stringify({ code, code_verifier: verifier }),
        })
        sessionStorage.removeItem('or_pkce_verifier')
        sessionStorage.removeItem('or_pkce_state')

        // D-02 resume: consume the pending-selection stash one-shot.
        const raw = sessionStorage.getItem('or_pending_selection')
        if (raw !== null) {
          // Remove FIRST — one-shot even if the apply throws (Pitfall 6).
          sessionStorage.removeItem('or_pending_selection')
          const pending = parsePendingSelection(raw)
          if (pending) {
            // Best-effort display name; ANY catalog failure silently falls back
            // to the raw id — ${label} is the ONLY interpolation (SEC-01).
            let label = pending.modelId
            try {
              const models = (await apiFetch('/api/models')) as ModelResponse[]
              const row = models.find(m => m.id === pending.modelId)
              if (row) label = row.name ?? row.id
            } catch {
              // silent — the raw model id is an acceptable label
            }
            try {
              if (pending.kind === 'thread' && pending.threadId) {
                await apiFetch(`/api/threads/${pending.threadId}`, {
                  method: 'PATCH',
                  body: JSON.stringify({ model: pending.modelId }),
                })
                showToast(`Connected — ${label} is set for this chat.`, 'success')
              } else {
                await apiFetch('/api/preferences', {
                  method: 'PUT',
                  body: JSON.stringify({ default_model: pending.modelId }),
                })
                showToast(`Connected — ${label} is now your default model.`, 'success')
              }
            } catch {
              // The connection itself succeeded — an apply error NEVER renders
              // the failure screen; degrade to the locked warning toast.
              showToast("Connected, but your model pick didn't apply — pick it again.", 'warning')
            }
            const target = RETURN_TO_ALLOWLIST.includes(pending.returnTo)
              ? pending.returnTo
              : '/settings'
            navigate(target, { replace: true })
            return
          }
        }

        // No stash (or unparseable stash) → legacy behavior unchanged.
        showToast('OpenRouter connected.', 'success')
        navigate('/settings', { replace: true })
      } catch {
        // Never surface the caught reason — locked generic copy only (D-06).
        setState('failure')
      }
    }

    run()
  }, [navigate, showToast])

  return (
    <div className="flex-1 bg-gray-950 text-white flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-lg p-6 max-w-sm w-full mx-4 text-center">
        {state === 'in-flight' ? (
          <div role="status" aria-live="polite" className="flex flex-col items-center gap-4">
            <span className="w-6 h-6 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-400">
              Connecting your OpenRouter account…
            </p>
          </div>
        ) : (
          <div role="alert" className="flex flex-col items-center gap-4">
            <AlertCircle size={24} className="text-red-400" />
            <p className="text-sm text-red-400 leading-relaxed">
              Couldn't connect your OpenRouter account — please try again.
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => startOpenRouterConnect()}
                className="bg-blue-600 hover:bg-blue-700 text-white text-base font-semibold px-4 py-3 rounded"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => {
                  // Abandoning the connect flow — clear the pending stash so a
                  // later manual connect can't replay a stale pick (D-02).
                  sessionStorage.removeItem('or_pending_selection')
                  navigate('/settings')
                }}
                className="bg-gray-700 hover:bg-gray-600 text-white text-base font-semibold px-4 py-3 rounded"
              >
                Back to settings
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
