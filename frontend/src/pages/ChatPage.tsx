import { useCallback, useEffect, useRef, useState } from 'react'
import ThreadSidebar, { ThreadListContent } from '../components/ThreadSidebar'
import ChatContainer from '../components/ChatContainer'
import MobileTopBar from '../components/MobileTopBar'
import MobileDrawer from '../components/MobileDrawer'
import { IconNavRow } from '../components/IconSidebar'
import type { ModelResponse } from '../components/ModelSelector'
import { apiFetch } from '../lib/api'
import { applyStoredTheme } from '../lib/themeBootstrap'
import { useChat } from '../hooks/useChat'
import * as Sentry from '@sentry/react'
import { useToast } from '../contexts/ToastContext'

interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
  // The thread's pinned model id, or null when the thread follows the user's default (D-05).
  model: string | null
}

export default function ChatPage() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  // The shared model catalog (so the per-thread selector resolves names without firing its own
  // /api/models fetch). Hydrates from the one-time mount fetch below.
  const [models, setModels] = useState<ModelResponse[] | undefined>(undefined)
  const hamburgerRef = useRef<HTMLButtonElement>(null)
  const closeDrawer = () => setIsDrawerOpen(false)
  const openDrawer = () => setIsDrawerOpen(true)
  // useChat owns thread loading + abort-on-switch (CR-01). skipNextLoad requests a one-shot
  // skip of the next [threadId] load for a freshly auto-created thread (see handleSend).
  const { messages, isStreaming, sendMessage, skipNextLoad, cancel, retryLastUserMessage } =
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

  // One-time catalog fetch so both selectors render model names synchronously (no per-selector
  // fetch). Silent on failure — each ModelSelector falls back to its own lazy fetch + error UI.
  // Only set when the payload is actually an array: a malformed/unexpected response must never
  // poison `models` (a non-array would crash ModelSelector's rows.map — T-13-CRASH defensive).
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/models')
      .then((data: unknown) => {
        if (!cancelled && Array.isArray(data)) setModels(data as ModelResponse[])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Post-login theme reconcile (Pitfall 6 / D-04). GET /api/preferences once on mount: if the
  // server theme differs from the current (localStorage-derived) class, the server wins — write
  // localStorage + re-apply (a one-frame snap is acceptable per D-02). The default-model hydrate
  // now lives in SettingsPage (D-06 relocation). Best-effort: a failed GET leaves the
  // localStorage-painted theme untouched.
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/preferences')
      .then((prefs: { theme?: string | null } | null) => {
        if (cancelled || !prefs) return
        const serverTheme = prefs.theme === 'dark' || prefs.theme === 'light' ? prefs.theme : null
        if (serverTheme) {
          const current = document.documentElement.classList.contains('dark') ? 'dark' : 'light'
          if (serverTheme !== current) {
            try { localStorage.setItem('theme', serverTheme) } catch { /* storage disabled */ }
            applyStoredTheme() // server wins; re-paint the root class from the just-written value
          }
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Per-thread model change (D-05). PATCH /api/threads/{id} {model} — a concrete id pins the
  // thread; null clears it back to the user default. Mirror the new value into local state so the
  // header trigger updates immediately (optimistic; the PATCH echo is authoritative on reload).
  const handleThreadModelChange = useCallback(
    async (modelId: string | null) => {
      if (!activeThreadId) return
      setThreads(prev =>
        prev.map(t => (t.id === activeThreadId ? { ...t, model: modelId } : t))
      )
      try {
        await apiFetch(`/api/threads/${activeThreadId}`, {
          method: 'PATCH',
          body: JSON.stringify({ model: modelId }),
        })
      } catch (err) {
        Sentry.captureException(err)
        showToast("Couldn't update the model for this chat. Try again.", 'error')
      }
    },
    [activeThreadId, showToast]
  )

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
        // Suppress the one [threadId] load the next setActiveThreadId triggers — the new
        // thread has no server messages and the load would clobber the optimistic bubble.
        // Must be requested BEFORE setActiveThreadId so the flag is set when the effect fires.
        skipNextLoad()
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
    // Core-surface light token (D-01): white in light, gray-950 in dark.
    <div className="flex-1 bg-white text-gray-900 dark:bg-gray-950 dark:text-white flex flex-col md:flex-row overflow-hidden">
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
        activeThreadId={activeThreadId}
        threadModel={activeThread?.model ?? null}
        onThreadModelChange={handleThreadModelChange}
        models={models}
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
