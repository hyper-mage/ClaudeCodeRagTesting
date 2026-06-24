import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import ErrorMessageBubble from './ErrorMessageBubble'
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
  role: 'user' | 'assistant' | 'error'
  content: string
  toolsUsed?: ToolEvent[]
}

interface Props {
  messages: Message[]
  onSend: (content: string) => void
  isStreaming: boolean
  onRetry: () => void
}

// Board-game example prompts surfaced as tappable empty-state chips. Each one
// exercises a different agent capability: comparison, rules lookup, recommendation.
// Locked strings per the approved UI-SPEC § Copywriting Contract.
const EXAMPLE_PROMPTS = [
  'Compare Catan vs Wingspan',
  'How do you win Azul?',
  'Recommend a 2-player game',
]

export default function ChatContainer({ messages, onSend, isStreaming, onRetry }: Props) {
  const { isAnon } = useAuth()
  return (
    <div className="flex-1 flex flex-col h-full">
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
