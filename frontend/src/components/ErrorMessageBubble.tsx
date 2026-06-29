import { AlertCircle, RotateCw, ExternalLink } from 'lucide-react'
import { startOpenRouterConnect } from '../lib/pkce'

interface Props {
  onRetry: () => void
  isStreaming: boolean
  /** Structured key-failure code (D-09). When set, the typed recovery variant renders the locked
   *  UI-SPEC sentence + code-mapped action buttons instead of the generic Retry path. */
  type?: 'no_api_key' | 'payment_required' | 'forbidden'
  /** Whether demo fallback is eligible. Phase-14 prod default is false → `[Use demo]` is hidden on
   *  the 403 path; Phase 15 owns enabling demo. */
  demoEligible?: boolean
  /** Optional handler for the (Phase-15) `[Use demo]` action; only wired when demoEligible. */
  onUseDemo?: () => void
}

// Locked recovery sentences keyed on the structured error CODE (UI-SPEC § Copywriting Contract).
// NEVER interpolate parsed.detail, a caught error, an HTTP body, or an sk-or fragment — only these
// fixed strings (the parenthetical 401/402/403 is the structured taxonomy code, which is allowed).
const RECOVERY_SENTENCE: Record<NonNullable<Props['type']>, string> = {
  no_api_key: 'Connect your OpenRouter account to keep chatting.',
  payment_required: 'Your key is out of credit (402).',
  forbidden: 'Your key was rejected (403).',
}

// Recovery buttons reuse the existing Retry sizing (>=44px on touch, compact on desktop).
const BTN_BASE = 'inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold'
const BTN_PRIMARY = 'bg-blue-600 hover:bg-blue-700 text-white'
// Neutral secondary surface, mirroring ConfirmDialog's cancel button in both themes.
const BTN_SECONDARY =
  'bg-gray-200 hover:bg-gray-300 text-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-white'

/**
 * ErrorMessageBubble — in-thread red-wash error bubble shown when the SSE chat stream fails.
 * Two variants:
 *  • Generic (no `type`): the existing single Retry button for non-key stream errors.
 *  • Typed (`type` set, D-09): code-mapped recovery copy + action buttons for 401/402/403, the
 *    single in-thread surface (no toast). `[Reconnect]` runs the existing PKCE OAuth flow;
 *    `[Add credits ⇗]` is a static external link.
 *
 * Locked classes + copy per UI-SPEC § Copywriting Contract + § Color (light + dark error tokens).
 */
export default function ErrorMessageBubble({
  onRetry,
  isStreaming,
  type,
  demoEligible = false,
  onUseDemo,
}: Props) {
  if (!type) {
    // Generic untyped path (unchanged) — non-key stream errors keep the single Retry button.
    return (
      <div className="flex justify-start mb-4">
        <div
          role="alert"
          className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100"
        >
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
            <p className="text-sm leading-[1.5]">
              The assistant ran into a problem. Try again, or rephrase your question.
            </p>
          </div>
          <div className="mt-2">
            <button
              type="button"
              onClick={onRetry}
              disabled={isStreaming}
              className={`${BTN_BASE} ${BTN_PRIMARY} disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <RotateCw size={14} />
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  // `[Reconnect]` runs the same PKCE flow as the Settings Connect CTA. Primary on 401/403,
  // secondary on 402 (where `[Add credits ⇗]` is the primary action).
  const reconnect = (
    <button
      type="button"
      onClick={() => {
        void startOpenRouterConnect()
      }}
      className={`${BTN_BASE} ${type === 'payment_required' ? BTN_SECONDARY : BTN_PRIMARY}`}
    >
      <RotateCw size={14} />
      Reconnect
    </button>
  )

  return (
    <div className="flex justify-start mb-4">
      <div
        role="alert"
        className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg border bg-red-50 border-red-300 text-gray-900 dark:bg-red-950/40 dark:border-red-700 dark:text-gray-100"
      >
        <div className="flex items-start gap-2">
          <AlertCircle size={16} className="text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm leading-[1.5]">{RECOVERY_SENTENCE[type]}</p>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {type === 'payment_required' && (
            <a
              href="https://openrouter.ai/settings/credits"
              target="_blank"
              rel="noopener noreferrer"
              className={`${BTN_BASE} ${BTN_PRIMARY}`}
            >
              <ExternalLink size={14} />
              Add credits
            </a>
          )}
          {reconnect}
          {type === 'forbidden' && demoEligible && (
            <button type="button" onClick={onUseDemo} className={`${BTN_BASE} ${BTN_SECONDARY}`}>
              Use demo
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
