import { useCallback, useEffect, useRef, useState } from 'react'
import ThreadSidebar, { ThreadListContent } from '../components/ThreadSidebar'
import ChatContainer from '../components/ChatContainer'
import MobileTopBar from '../components/MobileTopBar'
import MobileDrawer from '../components/MobileDrawer'
import { IconNavRow } from '../components/IconSidebar'
import { apiFetch } from '../lib/api'
import { useChat } from '../hooks/useChat'
import * as Sentry from '@sentry/react'
import { useToast } from '../contexts/ToastContext'

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
  // Pitfall 2 (optimistic-bubble clobber): when handleSend auto-creates a thread and
  // calls setActiveThreadId, the loadMessages effect re-runs for the brand-new thread
  // and would fetch `[]`, wiping the just-appended optimistic user bubble. The new
  // thread has no server-side messages yet, so that load is pure clobber — skip it
  // once. (useChat.loadMessages also guards on isStreaming; this closes the closure-
  // timing window deterministically.)
  const skipNextLoadRef = useRef(false)
  const closeDrawer = () => setIsDrawerOpen(false)
  const openDrawer = () => setIsDrawerOpen(true)
  const { messages, isStreaming, sendMessage, loadMessages, cancel, retryLastUserMessage } =
    useChat(activeThreadId)
  const { showToast } = useToast()

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
    if (skipNextLoadRef.current) {
      // Skip the clobbering load for a freshly auto-created thread (see ref comment).
      skipNextLoadRef.current = false
      return
    }
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
    // Auto-create-on-send (D-01/D-04): a message sent while no thread is active —
    // cold start OR the post-delete null state — silently creates an untitled thread
    // first, then sends into it. One code path covers both null states.
    let targetId = activeThreadId
    if (targetId === null) {
      try {
        // Untitled create (body {}) — the backend titles the thread from the first
        // message (D-03); no placeholder "New Chat" is ever persisted.
        const thread = await apiFetch('/api/threads', {
          method: 'POST',
          body: JSON.stringify({}),
        })
        targetId = thread.id
        setThreads(prev => [thread, ...prev])
        // Suppress the one loadMessages the next setActiveThreadId triggers — the new
        // thread has no server messages and the load would clobber the optimistic bubble.
        skipNextLoadRef.current = true
        setActiveThreadId(thread.id) // updates the sidebar; NOT relied on for the send (stale closure)
      } catch (err) {
        // Create-failure feedback (Pitfall 5): never a silent dead-end. Reuse the
        // existing generic send-failure toast copy — do NOT interpolate the caught
        // error / HTTP status / response body (T-999.1-08).
        Sentry.captureException(err)
        showToast("The assistant didn't respond. Tap the message to retry.", 'error')
        return
      }
    }
    // targetId is guaranteed non-null here: it was either already set, or the create
    // succeeded (a failed create returns above before reaching this point).
    // Explicit threadId defeats the React stale closure (Pitfall 1) so the optimistic
    // user bubble renders on the very first send instead of silently no-opping.
    await sendMessage(content, { threadId: targetId as string })
    // Reload threads to pick up the backend auto-generated title (D-03).
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
        onRetry={retryLastUserMessage}
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
