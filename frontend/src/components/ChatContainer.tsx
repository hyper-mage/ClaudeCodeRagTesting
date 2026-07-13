import { Info } from 'lucide-react'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import ErrorMessageBubble from './ErrorMessageBubble'
import DeprecationNotice from './DeprecationNotice'
import ModelSelector, { type ModelResponse } from './ModelSelector'
import PersonaSelector, { type PersonaOption } from './PersonaSelector'
import { useAuth } from '../contexts/AuthContext'
import { useKeyStatus } from '../hooks/useKeyStatus'
// Single source of truth for the message shape (incl. usage + errorType) — Plan 02 hook contract.
import type { Message } from '../hooks/useChat'

interface Props {
  messages: Message[]
  onSend: (content: string) => void
  isStreaming: boolean
  onRetry: () => void
  /** The active thread id; the per-thread header row only renders when this is non-null (D-05). */
  activeThreadId: string | null
  /** The active thread's pinned model id, or null when it follows the user default ('Default model'). */
  threadModel: string | null
  /** Called with the chosen model id, or null when the user clears back to their default (PATCH path). */
  onThreadModelChange: (modelId: string | null) => void
  /** Optional pre-fetched catalog forwarded to the per-thread ModelSelector (avoids a duplicate fetch). */
  models?: ModelResponse[]
  /** The active thread's pinned persona id, or null when it follows the user's default (PERS-05). */
  threadPersona: string | null
  /** Called with the chosen persona id (PATCH path). No key gate — persona carries no cost (PERS-01). */
  onThreadPersonaChange: (personaId: string) => void
  /** Optional pre-fetched persona catalog (GET /api/personas) forwarded to PersonaSelector (D-07). */
  personas?: PersonaOption[]
  /** True after a mode:"demo" done event was observed on this thread (useChat latch, D-10). */
  lastTurnWasDemo?: boolean
  /** [Use demo] recovery on the 403 bubble (D-11): retries the last user turn with use_demo:true. */
  onUseDemo?: () => void
}

// LOCKED copy (UI-SPEC § Copywriting Contract) for the per-thread selector.
const THREAD_SELECTOR_COPY = {
  heading: 'Model for this chat',
  useDefault: 'Use my default model',
  defaultSubState: 'Default model',
  personaHeading: 'Persona',
} as const

// Board-game example prompts surfaced as tappable empty-state chips. Each one
// exercises a different agent capability: comparison, rules lookup, recommendation.
// Locked strings per the approved UI-SPEC § Copywriting Contract.
const EXAMPLE_PROMPTS = [
  'Compare Catan vs Wingspan',
  'How do you win Azul?',
  'Recommend a 2-player game',
]

// LOCKED copy (UI-SPEC § Copywriting Contract, verbatim from Phase 11 D-08). Do not paraphrase.
const DEMO_BANNER_COPY =
  'Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left).'

export default function ChatContainer({
  messages,
  onSend,
  isStreaming,
  onRetry,
  activeThreadId,
  threadModel,
  onThreadModelChange,
  models,
  threadPersona,
  onThreadPersonaChange,
  personas,
  lastTurnWasDemo = false,
  onUseDemo,
}: Props) {
  const { isAnon } = useAuth()
  // Shared no-poll key-status store (zero extra fetches — the same instance serves the sidebar
  // dots and the gate hook). Carries connected + demo_enabled for the banner and [Use demo].
  const { status } = useKeyStatus()
  // Locked render condition (D-10): proactive for keyless users under the flag, and guaranteed
  // after any observed mode:"demo" turn. While status is still null (loading), demo_enabled is
  // undefined → both terms false → no banner flash.
  const showDemoBanner = (!status?.connected && Boolean(status?.demo_enabled)) || lastTurnWasDemo
  // Per-thread running total (D-02, COST-04): sum the persisted per-message usage.cost. The
  // persisted sum is the source of truth, so the total is correct on reload. Free/empty threads
  // sum to 0 and the Σ caption below is omitted entirely (no `Σ $0.0000` clutter).
  const threadCost = messages.reduce((s, m) => s + (m.usage?.cost ?? 0), 0)
  return (
    // Core-surface light token (D-01): white in light, gray-950 in dark — no orphan dark panel.
    <div className="flex-1 flex flex-col h-full bg-white text-gray-900 dark:bg-gray-950 dark:text-white">
      {/* Demo banner (DEMO-02, D-10) — FIRST shrink-0 child, above the thread-header row,
          full-bleed, present with or without an active thread. Non-dismissible: no close button,
          no interactive children, not a pill. Locked classes + copy (UI-SPEC § Components).
          NOT the same concept as DemoPill (anon-session badge) — both may legitimately show. */}
      {showDemoBanner && (
        <div
          role="status"
          className="shrink-0 flex items-center gap-2 px-4 py-2 text-xs border-b bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300"
        >
          <Info size={14} className="text-amber-500 shrink-0" aria-hidden="true" />
          <span>{DEMO_BANNER_COPY}</span>
        </div>
      )}
      {/* Per-thread model selector row (D-05). shrink-0 sibling above the scroll area so the
          existing flex-1 flex flex-col h-full layout is preserved (UI-SPEC Consistency req).
          Only renders when a thread is active — hidden on the cold-start empty state. */}
      {activeThreadId !== null && (
        <div className="shrink-0 h-12 flex items-center gap-2 px-3 border-b bg-gray-50 border-gray-200 dark:bg-gray-900 dark:border-gray-800">
          <span className="shrink-0 text-xs font-semibold text-gray-600 dark:text-gray-400">
            {THREAD_SELECTOR_COPY.heading}
          </span>
          <div className="max-w-xs flex-1">
            <ModelSelector
              value={threadModel}
              onSelect={onThreadModelChange}
              placeholder={THREAD_SELECTOR_COPY.defaultSubState}
              extraOption={{ label: THREAD_SELECTOR_COPY.useDefault, value: null }}
              models={models}
            />
          </div>
          {/* Per-thread persona pin (PERS-01/PERS-05). Sibling of the ModelSelector in the SAME
              shrink-0 header row. No key gate — persona carries no cost, so the parent's handler is
              passed straight through (a keyless user can pick). Catalog comes from GET /api/personas
              via the `personas` prop (never hardcoded, D-07). */}
          <span className="shrink-0 text-xs font-semibold text-gray-600 dark:text-gray-400">
            {THREAD_SELECTOR_COPY.personaHeading}
          </span>
          <div className="max-w-xs flex-1">
            <PersonaSelector
              value={threadPersona}
              onSelect={onThreadPersonaChange}
              personas={personas}
            />
          </div>
          {/* Per-thread running total (COST-04). Right-aligned in the SAME h-12 row via ml-auto
              (no second header row). Muted caption token; rendered only when > 0. */}
          {threadCost > 0 && (
            <span className="ml-auto shrink-0 text-xs text-gray-600 dark:text-gray-400">
              Σ ${threadCost.toFixed(4)}
            </span>
          )}
        </div>
      )}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center">
            <div className="max-w-md w-full flex flex-col items-center gap-4 text-center">
              <h2 className="text-2xl font-bold text-gray-200">Ask about any board game</h2>
              <p className="text-sm text-gray-400">
                Search rules, compare mechanics, or get a recommendation.
              </p>
              <div className="flex flex-col gap-2 w-full">
                {EXAMPLE_PROMPTS.map(q => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => onSend(q)}
                    className="min-h-11 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 rounded text-left text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {q}
                  </button>
                ))}
              </div>
              {isAnon && (
                <p className="text-xs text-gray-500">
                  A D&amp;D 5e quick-reference is already attached — try asking about it.
                </p>
              )}
            </div>
          </div>
        )}
        {messages.map(msg =>
          msg.role === 'error' ? (
            // errorType set → typed recovery variant (D-09); undefined → generic Retry path.
            // demoEligible rides the live flag (D-11): [Use demo] renders on the forbidden (403)
            // bubble when demo fallback is ON; clicking retries the turn with use_demo:true.
            <ErrorMessageBubble
              key={msg.id}
              onRetry={onRetry}
              isStreaming={isStreaming}
              type={msg.errorType}
              demoEligible={Boolean(status?.demo_enabled)}
              onUseDemo={onUseDemo}
            />
          ) : msg.role === 'notice' ? (
            <DeprecationNotice key={msg.id} content={msg.content} />
          ) : (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              toolsUsed={msg.toolsUsed}
              usage={msg.usage}
            />
          )
        )}
      </div>
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  )
}
