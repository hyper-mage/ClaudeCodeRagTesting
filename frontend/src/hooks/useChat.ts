import { useState, useCallback, useRef } from 'react'
import { apiFetch, apiStream } from '../lib/api'
import * as Sentry from '@sentry/react'
import { useToast } from '../contexts/ToastContext'

export interface SubEvent {
  type: 'sub_iteration' | 'sub_tool_start' | 'sub_tool_result'
  iteration?: number
  call_id?: string
  tool?: string
  args_preview?: string
  output?: string
}

export interface ToolEvent {
  tool: string
  args_preview: string
  output?: string
  call_id?: string
  subagent?: boolean
  status: 'running' | 'complete'
  subEvents?: SubEvent[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  toolsUsed?: ToolEvent[]
}

export function useChat(threadId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  // Mirror of isStreaming for the loadMessages guard. Kept in a ref (not a dep) so that
  // toggling isStreaming does NOT re-create loadMessages and thus does NOT re-fire the
  // thread-load effect when a stream STARTS or STOPS. Listing isStreaming in the deps
  // caused loadMessages to re-run on stream-end and refetch `/api/threads/{id}`, clobbering
  // the freshly-streamed assistant reply (and any error bubble) the instant the send
  // finished — the "no response / retry popup flashed then vanished" regression. The load
  // effect must fire ONLY on threadId change.
  const isStreamingRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const { showToast } = useToast()

  const loadMessages = useCallback(async () => {
    if (!threadId) {
      setMessages([])
      return
    }
    // Pitfall 2: do not clobber the optimistic/streaming bubble. When the thread-switch
    // effect re-runs mid-send (e.g. Plan 03 calls setActiveThreadId on a freshly-created
    // thread), an unconditional replace would fetch `[]` and wipe the just-appended bubble.
    // Read the ref, not the state, so this guard does not add isStreaming to the deps.
    if (isStreamingRef.current) return
    try {
      const data = await apiFetch(`/api/threads/${threadId}`)
      setMessages(data.messages.map((m: Record<string, unknown>) => ({
        ...m,
        toolsUsed: m.tools_used as ToolEvent[] | undefined,
      })))
    } catch {
      // Preserve previous silent-on-error behavior (old code had `if (res.ok)`)
    }
  }, [threadId])

  const sendMessage = useCallback(async (content: string, opts?: { retry?: boolean; threadId?: string }) => {
    // Pitfall 1 (stale closure): an explicit threadId from the caller must win over the
    // closured one so a message sent against a null-thread state (a freshly-created thread
    // id passed in by Plan 03) actually fires instead of silently no-opping.
    const effectiveThreadId = opts?.threadId ?? threadId
    if (!effectiveThreadId || isStreaming) return
    const isRetry = opts?.retry === true

    // Add user message optimistically (skip on retry — the prior user row is preserved on the backend
    // via POST /api/threads/{id}/messages?retry=true; the prior optimistic user message also remains
    // in client state since retry callers strip only role==='error' messages).
    if (!isRetry) {
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
      }
      setMessages(prev => [...prev, userMsg])
    }

    // Add placeholder assistant message
    const assistantId = crypto.randomUUID()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])
    isStreamingRef.current = true
    setIsStreaming(true)

    // Abort any in-flight request
    abortRef.current?.abort()

    try {
      const controller = new AbortController()
      abortRef.current = controller

      const url = isRetry
        ? `/api/threads/${effectiveThreadId}/messages?retry=true`
        : `/api/threads/${effectiveThreadId}/messages`
      const res = await apiStream(url, {
        method: 'POST',
        body: JSON.stringify({ content }),
        signal: controller.signal,
      })

      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const eventData = line.slice(6)
            // Find the event type from the previous line
            try {
              const parsed = JSON.parse(eventData)
              if (parsed.tool_event === true) {
                if (parsed.type === 'tool_start') {
                  // Add new card in running state
                  setMessages(prev =>
                    prev.map(m => {
                      if (m.id !== assistantId) return m
                      return {
                        ...m,
                        toolsUsed: [...(m.toolsUsed || []), {
                          tool: parsed.tool,
                          args_preview: parsed.args_preview || '',
                          call_id: parsed.call_id,
                          subagent: parsed.subagent || false,
                          status: 'running' as const,
                        }],
                      }
                    })
                  )
                } else if (parsed.type === 'tool_result') {
                  // Update existing card by call_id with output and complete status
                  setMessages(prev =>
                    prev.map(m => {
                      if (m.id !== assistantId) return m
                      return {
                        ...m,
                        toolsUsed: (m.toolsUsed || []).map(t =>
                          t.call_id === parsed.call_id
                            ? { ...t, status: 'complete' as const, output: parsed.output }
                            : t
                        ),
                      }
                    })
                  )
                } else if (parsed.type === 'sub_event') {
                  // Explorer sub-agent progress event — append to parent ToolEvent's subEvents
                  setMessages(prev =>
                    prev.map(m => {
                      if (m.id !== assistantId) return m
                      return {
                        ...m,
                        toolsUsed: (m.toolsUsed || []).map(t =>
                          t.call_id === parsed.parent_call_id
                            ? { ...t, subEvents: [...(t.subEvents || []), parsed.sub_event as SubEvent] }
                            : t
                        ),
                      }
                    })
                  )
                } else {
                  // Legacy format (no type field) — backward compat
                  setMessages(prev =>
                    prev.map(m => {
                      if (m.id !== assistantId) return m
                      return {
                        ...m,
                        toolsUsed: [...(m.toolsUsed || []), {
                          tool: parsed.tool,
                          args_preview: parsed.args_preview || '',
                          subagent: parsed.subagent || false,
                          status: 'complete' as const,
                        }],
                      }
                    })
                  )
                }
              } else if (parsed.text !== undefined) {
                // content_delta
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, content: m.content + parsed.text }
                      : m
                  )
                )
              } else if (parsed.message_id) {
                // done event - update with final message ID
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId ? { ...m, id: parsed.message_id } : m
                  )
                )
              } else if (parsed.error !== undefined) {
                // Backend yielded `event: error / data: {error}` — in-band SSE error path
                // (e.g. upstream LLM 401). Throw so the outer catch handles
                // bubble + toast + Sentry uniformly (UI-SPEC Surface 2).
                throw new Error(typeof parsed.error === 'string' ? parsed.error : 'Chat stream error')
              }
            } catch (parseErr) {
              // Re-throw structured chat errors; swallow JSON.parse failures on truncated lines.
              if (parseErr instanceof Error && parseErr.message && !(parseErr instanceof SyntaxError)) {
                throw parseErr
              }
              // skip unparseable lines
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // Navigation interrupted — tool events already persisted by backend
        return
      }
      console.error('Chat error:', err)
      // Sentry global handlers only capture UNCAUGHT errors — explicit capture for caught ones
      // (RESEARCH § Pitfall 4 / Standard Stack).
      Sentry.captureException(err)

      // Replace the empty assistant placeholder with an in-thread error bubble.
      // Locked copy per UI-SPEC § Surface 2 + § Copywriting Contract.
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? {
                ...m,
                role: 'error' as const,
                content:
                  'The assistant ran into a problem. Try again, or rephrase your question.',
              }
            : m
        )
      )

      // Simultaneous 4s red toast (UI-SPEC § Surface 2 dual-surface).
      showToast(
        "The assistant didn't respond. Tap the message to retry.",
        'error'
      )
    } finally {
      abortRef.current = null
      isStreamingRef.current = false
      setIsStreaming(false)
    }
  }, [threadId, isStreaming, showToast])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  // Re-send the most recent user message after a failure. Disabled while a fresh
  // attempt is mid-stream (UI-SPEC § Surface 2 Retry behavior, locked by D-07).
  // Strips any role==='error' bubbles before retrying so the failed turn
  // disappears from the thread the moment the new attempt starts.
  const retryLastUserMessage = useCallback(() => {
    if (isStreaming) return
    const lastUser = [...messages].reverse().find(m => m.role === 'user')
    if (!lastUser) return
    setMessages(prev => prev.filter(m => m.role !== 'error'))
    void sendMessage(lastUser.content, { retry: true })
  }, [messages, isStreaming, sendMessage])

  return {
    messages,
    setMessages,
    isStreaming,
    sendMessage,
    loadMessages,
    cancel,
    retryLastUserMessage,
  }
}
