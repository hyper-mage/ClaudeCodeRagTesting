import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'

interface ToolEvent {
  tool: string
  args_preview: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
}

interface Props {
  messages: Message[]
  onSend: (content: string) => void
  isStreaming: boolean
}

export default function ChatContainer({ messages, onSend, isStreaming }: Props) {
  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="h-full flex items-center justify-center text-gray-500">
            <p>Send a message to start the conversation.</p>
          </div>
        )}
        {messages.map(msg => (
          <MessageBubble key={msg.id} role={msg.role} content={msg.content} toolsUsed={msg.toolsUsed} />
        ))}
      </div>
      <ChatInput onSend={onSend} disabled={isStreaming} />
    </div>
  )
}
