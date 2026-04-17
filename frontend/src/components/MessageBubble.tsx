import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import ToolCallCard from './ToolCallCard'
import type { ToolEvent } from '../hooks/useChat'

interface Props {
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
}

export default function MessageBubble({ role, content, toolsUsed }: Props) {
  const [showTools, setShowTools] = useState(true)
  const hasTools = role === 'assistant' && toolsUsed && toolsUsed.length > 0

  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] px-4 py-2 rounded-lg ${
          role === 'user'
            ? 'bg-blue-600 text-white whitespace-pre-wrap'
            : 'bg-gray-800 text-gray-100'
        }`}
      >
        {hasTools && (
          <>
            <button
              onClick={() => setShowTools(!showTools)}
              className="text-xs text-gray-500 hover:text-gray-300 mb-1"
            >
              {showTools ? 'Hide tools' : `Show tools (${toolsUsed.length})`}
            </button>
            {showTools && (
              <div className="flex flex-col gap-2 mb-2">
                {toolsUsed.map((t, i) => (
                  <ToolCallCard
                    key={t.call_id || i}
                    tool={t.tool}
                    args_preview={t.args_preview}
                    output={t.output}
                    call_id={t.call_id}
                    subagent={t.subagent}
                    status={t.status}
                    subEvents={t.subEvents}
                  />
                ))}
              </div>
            )}
          </>
        )}
        {role === 'assistant' ? (
          <div className="prose prose-invert prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 underline">
                  {children}
                </a>
              ),
              table: ({ children }) => (
                <table className="border-collapse border border-gray-600 text-sm my-2">
                  {children}
                </table>
              ),
              th: ({ children }) => (
                <th className="border border-gray-600 px-2 py-1 bg-gray-700">{children}</th>
              ),
              td: ({ children }) => (
                <td className="border border-gray-600 px-2 py-1">{children}</td>
              ),
            }}
          >
            {content || ''}
          </ReactMarkdown>
          </div>
        ) : (
          content
        )}
      </div>
    </div>
  )
}
