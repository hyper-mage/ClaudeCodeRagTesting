import type { ReactNode } from 'react'

interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

interface Props {
  threads: Thread[]
  activeThreadId: string | null
  onSelectThread: (id: string) => void
  onNewThread: () => void
  onDeleteThread: (id: string) => void
  /**
   * Optional footer slot rendered BELOW the thread list (Plan 06): hosts the default-model
   * control + theme toggle. Temporary spot until the Phase-14 settings page absorbs it.
   */
  footer?: ReactNode
}

/**
 * ThreadListContent — inner content (`+ New Chat` CTA + thread list)
 * without the outer `w-64` chrome. Reused by the desktop ThreadSidebar
 * and by MobileDrawer (Plan 02) so the surface lives in one place.
 *
 * Empty state copy locked by 06.1-UI-SPEC.md Copywriting Contract:
 *   "No conversations yet" / Tap "+ New Chat" to start.
 */
export function ThreadListContent({
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onDeleteThread,
  footer,
}: Props) {
  return (
    <>
      <div className="p-3">
        <button
          onClick={onNewThread}
          className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium text-white"
        >
          + New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads.length === 0 ? (
          <div className="px-3 py-6 text-center">
            <p className="text-sm text-gray-500">No conversations yet</p>
            <p className="text-sm text-gray-500 mt-1">Tap "+ New Chat" to start.</p>
          </div>
        ) : (
          threads.map(thread => (
            <div
              key={thread.id}
              className={`group flex items-center px-3 py-2 cursor-pointer text-sm text-gray-900 hover:bg-gray-100 dark:text-gray-100 dark:hover:bg-gray-800 ${
                thread.id === activeThreadId ? 'bg-gray-100 dark:bg-gray-800' : ''
              }`}
              onClick={() => onSelectThread(thread.id)}
            >
              <span className="flex-1 truncate">{thread.title || 'New Chat'}</span>
              <button
                onClick={e => { e.stopPropagation(); onDeleteThread(thread.id) }}
                className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 ml-2"
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
      {footer && (
        <div className="shrink-0 border-t border-gray-200 p-3 dark:border-gray-800">{footer}</div>
      )}
    </>
  )
}

export default function ThreadSidebar(props: Props) {
  return (
    // Core-surface light token (D-01): gray-50 in light, gray-900 in dark.
    <div className="hidden md:flex w-64 bg-gray-50 border-r border-gray-200 text-gray-900 dark:bg-gray-900 dark:border-gray-800 dark:text-white flex-col h-full">
      <ThreadListContent {...props} />
    </div>
  )
}
