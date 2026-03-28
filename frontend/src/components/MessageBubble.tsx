import ReactMarkdown from 'react-markdown'

interface ToolEvent {
  tool: string
  args_preview: string
}

interface Props {
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
}

const TOOL_LABELS: Record<string, string> = {
  search_documents: 'Document Search',
  query_database: 'Database Query',
  web_search: 'Web Search',
}

export default function MessageBubble({ role, content, toolsUsed }: Props) {
  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] px-4 py-2 rounded-lg whitespace-pre-wrap ${
          role === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-100'
        }`}
      >
        {role === 'assistant' && toolsUsed && toolsUsed.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {toolsUsed.map((t, i) => (
              <span
                key={i}
                className="text-xs px-2 py-0.5 rounded-full bg-gray-700 text-gray-300"
              >
                {TOOL_LABELS[t.tool] || t.tool}
              </span>
            ))}
          </div>
        )}
        {role === 'assistant' ? (
          <ReactMarkdown
            className="prose prose-invert prose-sm max-w-none"
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
            {content}
          </ReactMarkdown>
        ) : (
          content
        )}
      </div>
    </div>
  )
}
