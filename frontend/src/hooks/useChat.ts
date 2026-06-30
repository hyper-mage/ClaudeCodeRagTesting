import { useState, useCallback, useRef, useEffect } from 'react'
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

// Per-message cost + token usage, summed across the tool loop on the backend (Phase 11) and
// persisted to messages.usage. Arrives live on the `done` SSE event and on history load.
// All fields optional — a turn may report tokens without a cost (or neither).
export interface Usage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cost?: number
}

export interface Message {
  // 'notice' is the persisted deprecation-fallback line (Plan 04, role='notice'); it arrives from
  // GET /api/threads/{id} like any other row and renders via DeprecationNotice (not a bubble).
  id: string
  role: 'user' | 'assistant' | 'error' | 'notice'
  content: string
  toolsUsed?: ToolEvent[]
  // Per-message cost/tokens (live done.usage + reloaded). Drives the cost caption (Wave 3 Plan 04).
  usage?: Usage
  // Structured typed-error code. When set, the typed ErrorMessageBubble supplies the locked copy
  // from the code — `content` stays empty and NO toast fires (single in-thread surface). Covers the
  // key-failure family (D-09: no_api_key/payment_required/forbidden) AND the model-unavailable
  // family (FU-C: a 404/400 "No endpoints found" — pinned model has no live endpoint for this turn).
  errorType?: 'no_api_key' | 'payment_required' | 'forbidden' | 'model_unavailable'
}

export function useChat(threadId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  // Ref mirror of isStreaming, used by the re-entrancy guard in sendMessage (WR-01) and the
  // abort-on-switch effect below. Kept in a ref (not a dep) so toggling isStreaming does NOT
  // re-create loadMessages; the thread-load effect must fire ONLY on threadId change, never on
  // stream start/stop (the latter caused the post-stream refetch clobber — "no response / retry
  // popup flashed then vanished").
  const isStreamingRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  // One-shot suppression of the [threadId] load effect. ChatPage sets this (via skipNextLoad)
  // right before pointing the hook at a freshly auto-created thread: that thread has no server
  // messages yet and the send into it is intentional, so we must neither abort the in-flight
  // send nor fetch `[]` (which would clobber the optimistic user bubble). See CR-01.
  const skipNextLoadRef = useRef(false)
  const { showToast } = useToast()

  const loadMessages = useCallback(async () => {
    if (!threadId) {
      setMessages([])
      return
    }
    try {
      const data = await apiFetch(`/api/threads/${threadId}`)
      setMessages(data.messages.map((m: Record<string, unknown>) => ({
        ...m,
        toolsUsed: m.tools_used as ToolEvent[] | undefined,
        // D-02 source-of-truth: persisted per-message usage must survive a reload so the cost
        // caption + per-thread Σ total reconstruct identically after refresh (read-path fix).
        usage: m.usage as Usage | undefined,
      })))
    } catch {
      // Preserve previous silent-on-error behavior (old code had `if (res.ok)`)
    }
  }, [threadId])

  // Thread-load + abort-on-switch (CR-01). Owns loading for the hook — ChatPage no longer runs
  // its own load effect. Fires only on threadId change (loadMessages is stable per threadId).
  useEffect(() => {
    if (skipNextLoadRef.current) {
      // Freshly auto-created thread: the send into it is intentional — do NOT abort it and do
      // NOT load (no server messages yet; a load would clobber the optimistic user bubble).
      // Consume the one-shot flag.
      skipNextLoadRef.current = false
      return
    }
    // Genuine thread switch (or initial mount): abort any in-flight stream from the previous
    // thread so its deltas don't bleed into the new thread, then load the newly selected thread.
    abortRef.current?.abort()
    abortRef.current = null
    isStreamingRef.current = false
    setIsStreaming(false)
    void loadMessages()
  }, [threadId, loadMessages])

  // Request a one-shot skip of the next [threadId] load effect (ChatPage uses this right before
  // pointing the hook at a freshly auto-created thread). See skipNextLoadRef / CR-01.
  const skipNextLoad = useCallback(() => {
    skipNextLoadRef.current = true
  }, [])

  const sendMessage = useCallback(async (content: string, opts?: { retry?: boolean; threadId?: string }) => {
    // Pitfall 1 (stale closure): an explicit threadId from the caller must win over the
    // closured one so a message sent against a null-thread state (a freshly-created thread
    // id passed in by Plan 03) actually fires instead of silently no-opping.
    const effectiveThreadId = opts?.threadId ?? threadId
    // WR-01: re-entrancy guard reads the ref (synchronously up-to-date), not the isStreaming
    // STATE (stale within the same tick), so a rapid double-send / double-chip-tap can't slip a
    // second stream through before React re-renders. The isStreaming STATE still drives rendering.
    if (!effectiveThreadId || isStreamingRef.current) return
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
                // done event - update with final message ID and capture the live turn's summed
                // usage (cost + tokens). Falls back to any usage already on the message so we never
                // clobber an existing value with an absent one.
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, id: parsed.message_id, usage: parsed.usage ?? m.usage }
                      : m
                  )
                )
              } else if (parsed.error !== undefined) {
                // Backend yielded `event: error / data: {error}` — in-band SSE error path
                // (e.g. upstream LLM 401). Throw so the outer catch handles
                // bubble + toast + Sentry uniformly (UI-SPEC Surface 2).
                // IN-02: default an empty/non-string code to 'upstream_error'. The outer
                // `catch (parseErr)` only re-throws when `parseErr.message` is truthy, so a
                // bare `new Error('')` (e.g. the generic Exception path yields {"error": ""})
                // would be silently swallowed as an unparseable line — leaving an empty
                // assistant bubble with no error surface. A non-empty code keeps it on the
                // generic error path (toast + bubble).
                throw new Error(
                  typeof parsed.error === 'string' && parsed.error ? parsed.error : 'upstream_error'
                )
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

      // The error SSE branch throws the structured CODE as err.message. A typed code drives the
      // typed ErrorMessageBubble and suppresses the toast (single in-thread surface): the key-failure
      // family (D-09: no_api_key/payment_required/forbidden) AND model_unavailable (FU-C). Every
      // other code (rate_limit, upstream_error) and any network error keeps the generic copy + toast.
      const TYPED_ERROR_CODES: ReadonlyArray<NonNullable<Message['errorType']>> = [
        'no_api_key',
        'payment_required',
        'forbidden',
        'model_unavailable',
      ]
      const code = err instanceof Error ? err.message : ''
      const errorType = TYPED_ERROR_CODES.find(c => c === code)

      // Replace the empty assistant placeholder with an in-thread error bubble.
      // Typed path (key-failure D-09 OR model_unavailable FU-C): stamp errorType + empty content
      // (the bubble renders locked copy from the code, never parsed.detail — Pitfall 3 / T-14-08).
      // Generic path: locked copy per UI-SPEC § Surface 2 + § Copywriting Contract.
      setMessages(prev =>
        prev.map(m => {
          if (m.id !== assistantId) return m
          if (errorType) {
            return { ...m, role: 'error' as const, errorType, content: '' }
          }
          return {
            ...m,
            role: 'error' as const,
            content:
              'The assistant ran into a problem. Try again, or rephrase your question.',
          }
        })
      )

      // Generic stream failures keep the 4s red toast (UI-SPEC § Surface 2 dual-surface). The typed
      // 401/402/403 recovery path suppresses it — the in-thread bubble is the single surface (D-09).
      if (!errorType) {
        showToast(
          "The assistant didn't respond. Tap the message to retry.",
          'error'
        )
      }
    } finally {
      abortRef.current = null
      isStreamingRef.current = false
      setIsStreaming(false)
    }
    // isStreaming dropped from deps (WR-01): the guard now reads isStreamingRef.current, so the
    // STATE is no longer referenced in this callback.
  }, [threadId, showToast])

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
    // WR-05: pass the current thread explicitly so retry targets it deterministically (matching
    // the explicit-threadId send path) rather than relying solely on the closured threadId.
    void sendMessage(lastUser.content, { retry: true, threadId: threadId ?? undefined })
  }, [messages, isStreaming, sendMessage, threadId])

  return {
    messages,
    setMessages,
    isStreaming,
    sendMessage,
    loadMessages,
    skipNextLoad,
    cancel,
    retryLastUserMessage,
  }
}
