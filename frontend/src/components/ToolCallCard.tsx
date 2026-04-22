import { useState } from 'react'
import { FolderOpen, GitBranch, FileText, Search, Globe, Database, Brain, Check, ChevronDown, ChevronUp, Compass } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { SubEvent } from '../hooks/useChat'

interface Props {
  tool: string
  args_preview: string
  output?: string
  call_id?: string
  subagent?: boolean
  status: 'running' | 'complete'
  subEvents?: SubEvent[]
}

const TOOL_LABELS: Record<string, string> = {
  kb_ls: 'List Files',
  kb_tree: 'KB Tree',
  kb_read: 'Read Document',
  kb_grep: 'Search Content',
  kb_glob: 'Find Files',
  search_documents: 'Document Search',
  query_database: 'Database Query',
  web_search: 'Web Search',
  analyze_document: 'Document Analysis',
  explore_kb: 'Explore KB',
}

const TOOL_ICONS: Record<string, LucideIcon> = {
  kb_ls: FolderOpen,
  kb_tree: GitBranch,
  kb_read: FileText,
  kb_grep: Search,
  kb_glob: Globe,
  search_documents: Search,
  query_database: Database,
  web_search: Globe,
  analyze_document: Brain,
  explore_kb: Compass,
}

// Must match backend/config.py -> Settings.explorer_max_tool_calls default.
// Denominator for the Explore KB progress indicator; both numerator (sub_tool_start
// count) and denominator (tool-call budget) share the same axis, so the ratio is
// meaningful. If you change this, update the backend default at the same time.
const EXPLORER_MAX_TOOL_CALLS = 10

export { TOOL_LABELS }

// Parse a leading "scope:<scope>" prefix from args_preview and render a
// colored badge before the rest of the preview (Phase 6, D-03).
function renderArgsPreview(preview: string) {
  const scopeMatch = preview.match(/^scope:(\S+)\s*/)
  if (!scopeMatch) {
    return <span className="text-xs font-mono text-gray-400 truncate">{preview}</span>
  }
  const scope = scopeMatch[1]
  const rest = preview.slice(scopeMatch[0].length)
  const scopeColors: Record<string, string> = {
    default_kb: 'text-blue-400',
    private: 'text-green-400',
    both: 'text-yellow-400',
  }
  const colorClass = scopeColors[scope] || 'text-zinc-400'
  return (
    <>
      <span className={`text-xs font-medium ${colorClass} mr-1`}>
        [{scope.replace('_', ' ')}]
      </span>
      <span className="text-xs font-mono text-gray-400 truncate">{rest}</span>
    </>
  )
}

export default function ToolCallCard({ tool, args_preview, output, subagent, status, subEvents }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [subExpanded, setSubExpanded] = useState(false)

  const Icon = TOOL_ICONS[tool] || Search
  const label = TOOL_LABELS[tool] || tool
  const iconColor = subagent
    ? 'text-indigo-300'
    : tool.startsWith('kb_')
      ? 'text-emerald-400'
      : 'text-gray-400'
  const borderColor = subagent ? 'border-indigo-700' : 'border-gray-700'

  // Pair up sub_tool_start + sub_tool_result by call_id; collect iteration markers.
  const subToolStarts = (subEvents || []).filter(s => s.type === 'sub_tool_start')
  const subToolResults = new Map<string, SubEvent>()
  for (const s of (subEvents || [])) {
    if (s.type === 'sub_tool_result' && s.call_id) subToolResults.set(s.call_id, s)
  }
  const subIterations = (subEvents || []).filter(s => s.type === 'sub_iteration')
  // Progress ratio: tool-calls-started / tool-call-budget. Both share the same axis
  // (explorer_max_tool_calls on the backend), so the number is meaningful.
  const explorerProgress = tool === 'explore_kb' && status === 'running'
    ? `Exploring... (${subToolStarts.length}/${EXPLORER_MAX_TOOL_CALLS})`
    : null

  return (
    <div className={`border ${borderColor} rounded-md overflow-hidden`}>
      <div
        className="flex items-center justify-between px-2 py-2 cursor-pointer bg-gray-800/50"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-1 min-w-0">
          <Icon className={`w-4 h-4 flex-shrink-0 ${iconColor}`} />
          <span className="text-xs font-semibold text-gray-200">{label}</span>
          {args_preview && (
            <span className="ml-1 truncate max-w-[240px] flex items-center">
              {renderArgsPreview(args_preview)}
            </span>
          )}
          {explorerProgress && (
            <span className="text-xs text-indigo-300 ml-2">{explorerProgress}</span>
          )}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0 ml-2">
          {status === 'running' ? (
            <span className="w-3.5 h-3.5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
          ) : (
            <Check className="w-3.5 h-3.5 text-gray-500" />
          )}
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
          )}
        </div>
      </div>
      {expanded && (
        <div className="border-t border-gray-700 px-4 py-2 bg-gray-800">
          {/* Nested sub-events for explore_kb */}
          {tool === 'explore_kb' && subEvents && subEvents.length > 0 && (
            <div className="mb-2">
              <button
                onClick={(e) => { e.stopPropagation(); setSubExpanded(!subExpanded) }}
                className="text-xs text-indigo-300 hover:text-indigo-200 mb-1"
              >
                {subExpanded
                  ? `Hide sub-steps (${subToolStarts.length})`
                  : `Show sub-steps (${subToolStarts.length})`}
              </button>
              {subExpanded && (
                <ul className="border-l-2 border-indigo-700 pl-3 space-y-1">
                  {subIterations.length > 0 && (
                    <li className="text-xs text-gray-500 italic">
                      {subIterations.length} iteration{subIterations.length !== 1 ? 's' : ''}
                    </li>
                  )}
                  {subToolStarts.map((s, i) => {
                    const result = s.call_id ? subToolResults.get(s.call_id) : undefined
                    const SubIcon = s.tool ? (TOOL_ICONS[s.tool] || Search) : Search
                    const subLabel = s.tool ? (TOOL_LABELS[s.tool] || s.tool) : 'tool'
                    return (
                      <li key={s.call_id || i} className="flex items-start gap-1 text-xs">
                        <SubIcon className="w-3 h-3 mt-0.5 text-emerald-400 flex-shrink-0" />
                        <span className="font-semibold text-gray-300">{subLabel}</span>
                        {s.args_preview && (
                          <span className="font-mono text-gray-500 truncate max-w-[180px]">
                            {s.args_preview}
                          </span>
                        )}
                        {result ? (
                          <Check className="w-3 h-3 text-gray-500 flex-shrink-0" />
                        ) : (
                          <span className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}
          {/* Original output payload */}
          {output && (
            <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
              {output}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
