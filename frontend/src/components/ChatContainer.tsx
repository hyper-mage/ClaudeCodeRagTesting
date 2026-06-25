import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import ErrorMessageBubble from './ErrorMessageBubble'
import DeprecationNotice from './DeprecationNotice'
import ModelSelector, { type ModelResponse } from './ModelSelector'
import { useAuth } from '../contexts/AuthContext'

interface ToolEvent {
  tool: string
  args_preview: string
  output?: string
  call_id?: string
  subagent?: boolean
  status: 'running' | 'complete'
}

interface Message {
  id: string
  role: 'user' | 'assistant' | 'error' | 'notice'
  content: string
  toolsUsed?: ToolEvent[]
}

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
}

// LOCKED copy (UI-SPEC § Copywriting Contract) for the per-thread selector.
const THREAD_SELECTOR_COPY = {
  heading: 'Model for this chat',
  useDefault: 'Use my default model',
  defaultSubState: 'Default model',
} as const

// Board-game example prompts surfaced as tappable empty-state chips. Each one
// exercises a different agent capability: comparison, rules lookup, recommendation.
// Locked strings per the approved UI-SPEC § Copywriting Contract.
const EXAMPLE_PROMPTS = [
  'Compare Catan vs Wingspan',
  'How do you win Azul?',
  'Recommend a 2-player game',
]

export default function ChatContainer({
  messages,
  onSend,
  isStreaming,
  onRetry,
  activeThreadId,
  threadModel,
  onThreadModelChange,
  models,
}: Props) {
  const { isAnon } = useAuth()
  return (
    // Core-surface light token (D-01): white in light, gray-950 in dark — no orphan dark panel.
    <div className="flex-1 flex flex-col h-full bg-white text-gray-900 dark:bg-gray-950 dark:text-white">
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
            <ErrorMessageBubble key={msg.id} onRetry={onRetry} isStreaming={isStreaming} />
          ) : msg.role === 'notice' ? (
            <DeprecationNotice key={msg.id} content={msg.content} />
          ) : (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              toolsUsed={msg.toolsUsed}
            />
          )
        )}
      </div>
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  )
}
