import { useCallback, useEffect, useState } from 'react'
import ThreadSidebar from '../components/ThreadSidebar'
import ChatContainer from '../components/ChatContainer'
import { apiFetch } from '../lib/api'
import { useChat } from '../hooks/useChat'

interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export default function ChatPage() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const { messages, isStreaming, sendMessage, loadMessages } = useChat(activeThreadId)

  const loadThreads = useCallback(async () => {
    const data = await apiFetch('/api/threads')
    setThreads(data)
  }, [])

  useEffect(() => {
    loadThreads()
  }, [loadThreads])

  useEffect(() => {
    loadMessages()
  }, [loadMessages])

  const handleNewThread = async () => {
    const thread = await apiFetch('/api/threads', {
      method: 'POST',
      body: JSON.stringify({}),
    })
    setThreads(prev => [thread, ...prev])
    setActiveThreadId(thread.id)
  }

  const handleDeleteThread = async (id: string) => {
    await apiFetch(`/api/threads/${id}`, { method: 'DELETE' })
    setThreads(prev => prev.filter(t => t.id !== id))
    if (activeThreadId === id) {
      setActiveThreadId(null)
    }
  }

  const handleSend = async (content: string) => {
    await sendMessage(content)
    // Reload threads to pick up title changes
    loadThreads()
  }

  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      <ThreadSidebar
        threads={threads}
        activeThreadId={activeThreadId}
        onSelectThread={setActiveThreadId}
        onNewThread={handleNewThread}
        onDeleteThread={handleDeleteThread}
      />
      <ChatContainer
        messages={messages}
        onSend={handleSend}
        isStreaming={isStreaming}
      />
    </div>
  )
}
