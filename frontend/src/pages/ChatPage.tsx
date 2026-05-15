import { useCallback, useEffect, useRef, useState } from 'react'
import ThreadSidebar, { ThreadListContent } from '../components/ThreadSidebar'
import ChatContainer from '../components/ChatContainer'
import MobileTopBar from '../components/MobileTopBar'
import MobileDrawer from '../components/MobileDrawer'
import { IconNavRow } from '../components/IconSidebar'
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
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const hamburgerRef = useRef<HTMLButtonElement>(null)
  const closeDrawer = () => setIsDrawerOpen(false)
  const openDrawer = () => setIsDrawerOpen(true)
  const { messages, isStreaming, sendMessage, loadMessages, cancel } = useChat(activeThreadId)

  useEffect(() => {
    return () => { cancel() }
  }, [cancel])

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

  const activeThread = threads.find(t => t.id === activeThreadId)
  const topBarTitle = activeThread?.title || (activeThreadId ? 'New Chat' : 'Chat')

  return (
    <div className="flex-1 bg-gray-950 text-white flex flex-col md:flex-row overflow-hidden">
      <MobileTopBar
        title={topBarTitle}
        onOpenDrawer={openDrawer}
        hamburgerRef={hamburgerRef}
        isDrawerOpen={isDrawerOpen}
      />
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
      <MobileDrawer isOpen={isDrawerOpen} onClose={closeDrawer} triggerRef={hamburgerRef}>
        <IconNavRow onNavigate={closeDrawer} />
        <ThreadListContent
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={(id) => { setActiveThreadId(id); closeDrawer() }}
          onNewThread={async () => { await handleNewThread(); closeDrawer() }}
          onDeleteThread={handleDeleteThread}
        />
      </MobileDrawer>
    </div>
  )
}
