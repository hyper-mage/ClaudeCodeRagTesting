import { useAuth } from '../contexts/AuthContext'

/**
 * DemoPill — amber identity badge rendered when the current session is an
 * anonymous (demo) user. Returns null otherwise. Non-interactive; tooltip
 * via native `title` attribute. Color tokens locked by UI-SPEC § Color.
 */
export default function DemoPill() {
  const { isAnon } = useAuth()
  if (!isAnon) return null
  return (
    <span
      role="status"
      aria-label="Demo account"
      title="You're using a temporary demo account. Data is cleared after 7 days."
      className="inline-flex items-center justify-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"
    >
      Demo
    </span>
  )
}
