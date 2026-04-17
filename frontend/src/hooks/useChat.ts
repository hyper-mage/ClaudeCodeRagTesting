import { useState, useCallback, useRef } from 'react'
import { supabase } from '../lib/supabase'

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
  role: 'user' | 'assistant'
  content: string
  toolsUsed?: ToolEvent[]
}

export function useChat(threadId: string | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const loadMessages = useCallback(async () => {
    if (!threadId) {
      setMessages([])
      return
    }
    const { data: { session } } = await supabase.auth.getSession()
    const res = await fetch(`/api/threads/${threadId}`, {
      headers: { Authorization: `Bearer ${session?.access_token}` },
    })
    if (res.ok) {
      const data = await res.json()
      setMessages(data.messages.map((m: Record<string, unknown>) => ({
        ...m,
        toolsUsed: m.tools_used as ToolEvent[] | undefined,
      })))
    }
  }, [threadId])

  const sendMessage = useCallback(async (content: string) => {
    if (!threadId || isStreaming) return

    // Add user message optimistically
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    }
    setMessages(prev => [...prev, userMsg])

    // Add placeholder assistant message
    const assistantId = crypto.randomUUID()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])
    setIsStreaming(true)

    // Abort any in-flight request
    abortRef.current?.abort()

    try {
      const controller = new AbortController()
      abortRef.current = controller

      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch(`/api/threads/${threadId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      })

      if (!res.ok) throw new Error(`API error: ${res.status}`)

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
              }
            } catch {
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
      // Remove the empty assistant message on error
      setMessages(prev => prev.filter(m => m.id !== assistantId || m.content))
    } finally {
      abortRef.current = null
      setIsStreaming(false)
    }
  }, [threadId, isStreaming])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
  }, [])

  return { messages, setMessages, isStreaming, sendMessage, loadMessages, cancel }
}
