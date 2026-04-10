import { useState } from 'react'
import { FolderOpen, GitBranch, FileText, Search, Globe, Database, Brain, Check, ChevronDown, ChevronUp } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface Props {
  tool: string
  args_preview: string
  output?: string
  call_id?: string
  subagent?: boolean
  status: 'running' | 'complete'
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
}

export { TOOL_LABELS }

export default function ToolCallCard({ tool, args_preview, output, subagent, status }: Props) {
  const [expanded, setExpanded] = useState(false)

  const Icon = TOOL_ICONS[tool] || Search
  const label = TOOL_LABELS[tool] || tool
  const iconColor = subagent
    ? 'text-indigo-300'
    : tool.startsWith('kb_')
      ? 'text-emerald-400'
      : 'text-gray-400'
  const borderColor = subagent ? 'border-indigo-700' : 'border-gray-700'

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
            <span className="text-xs font-mono text-gray-400 truncate max-w-[200px] ml-1">
              {args_preview}
            </span>
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
      {expanded && output && (
        <div className="border-t border-gray-700 px-4 py-2 bg-gray-800">
          <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap max-h-[300px] overflow-y-auto">
            {output}
          </pre>
        </div>
      )}
    </div>
  )
}
