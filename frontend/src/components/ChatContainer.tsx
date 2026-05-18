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

export default function ChatContainer({ messages, onSend, isStreaming, onRetry }: Props) {
  const { isAnon } = useAuth()
  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-500">
            <p>
              {isAnon
                ? "Ask me about the board games in the library, or about the sample D&D 5e quick-reference that's already attached."
                : 'Send a message to start the conversation.'}
            </p>
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
