import { useAuth } from '../contexts/AuthContext'

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
}

export default function ThreadSidebar({ threads, activeThreadId, onSelectThread, onNewThread, onDeleteThread }: Props) {
  const { signOut } = useAuth()

  return (
    <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
      <div className="p-3">
        <button
          onClick={onNewThread}
          className="w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium"
        >
          + New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads.map(thread => (
          <div
            key={thread.id}
            className={`group flex items-center px-3 py-2 cursor-pointer text-sm hover:bg-gray-800 ${
              thread.id === activeThreadId ? 'bg-gray-800' : ''
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
        ))}
      </div>
      <div className="p-3 border-t border-gray-800">
        <button
          onClick={signOut}
          className="w-full py-2 px-3 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded"
        >
          Sign Out
        </button>
      </div>
    </div>
  )
}
