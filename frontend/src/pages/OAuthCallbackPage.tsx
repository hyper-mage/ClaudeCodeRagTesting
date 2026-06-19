import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { startOpenRouterConnect } from '../lib/pkce'
import { useToast } from '../contexts/ToastContext'

type CallbackState = 'in-flight' | 'failure'

// One-shot OAuth callback state machine (KEY-01).
//
// On mount (guarded against React StrictMode double-run), read code+state from
// the URL and verifier+state from sessionStorage (NOT React state — Pitfall 3,
// so a hard refresh re-runs successfully, D-07). CSRF check: reject when the
// returned state does not match the stored one. On success: clear the
// sessionStorage keys, toast, and redirect to /settings. On ANY error render the
// locked generic failure sentence — the caught error / HTTP status / any
// sk-or-… fragment is NEVER interpolated into the UI (Pitfall 1 / D-06).
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
                onClick={() => navigate('/settings')}
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
