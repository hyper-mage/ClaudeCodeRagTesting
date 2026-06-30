import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import ToolCallCard from './ToolCallCard'
import type { ToolEvent, Usage } from '../hooks/useChat'

interface Props {
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
  /** Per-message cost/tokens as reported by OpenRouter (D-01). Drives the muted cost caption
   *  on assistant bubbles only. Shown exactly as reported — never recomputed client-side. */
  usage?: Usage
}

// Format a token count per the locked copy: `1.2k` for >= 1000 (one decimal, drop a trailing
// `.0`), otherwise the integer (`840`). Pure display helper.
function formatTokens(n: number): string {
  if (n >= 1000) {
    const k = (n / 1000).toFixed(1)
    return `${k.endsWith('.0') ? k.slice(0, -2) : k}k`
  }
  return String(n)
}

// Muted per-message cost caption (UI-SPEC § Copywriting — `${cost} · ${tokens} tok`).
// The cost segment AND the `·` separator are omitted when usage.cost is null/absent (e.g. a
// free model); renders nothing when there is no displayable figure at all.
// IN-04: this caption sits inside the assistant bubble, which is `bg-gray-800` with NO light-mode
// variant. `text-gray-600 dark:text-gray-400` left a low-contrast gray-600-on-gray-800 caption in
// light mode. Since the bubble surface is dark in BOTH themes, use a single light token
// (`text-gray-300`) that reads on gray-800 either way.
function CostLine({ usage }: { usage: Usage }) {
  const costPart = usage.cost != null ? `$${usage.cost.toFixed(4)}` : null
  const tokensPart = usage.total_tokens != null ? `${formatTokens(usage.total_tokens)} tok` : null
  const text = [costPart, tokensPart].filter(Boolean).join(' · ')
  if (!text) return null
  return <div className="text-xs text-gray-300 mt-1">{text}</div>
}

export default function MessageBubble({ role, content, toolsUsed, usage }: Props) {
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
        {role === 'assistant' && usage && <CostLine usage={usage} />}
      </div>
    </div>
  )
}
