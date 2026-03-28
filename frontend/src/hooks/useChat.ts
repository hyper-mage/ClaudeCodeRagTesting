import { useState, useCallback } from 'react'
import { supabase } from '../lib/supabase'

export interface ToolEvent {
  tool: string
  args_preview: string
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
      setMessages(data.messages)
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

    try {
      const { data: { session } } = await supabase.auth.getSession()
      const res = await fetch(`/api/threads/${threadId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({ content }),
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
                // tool usage event — add to assistant message's toolsUsed
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, toolsUsed: [...(m.toolsUsed || []), { tool: parsed.tool, args_preview: parsed.args_preview }] }
                      : m
                  )
                )
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
      console.error('Chat error:', err)
      // Remove the empty assistant message on error
      setMessages(prev => prev.filter(m => m.id !== assistantId || m.content))
    } finally {
      setIsStreaming(false)
    }
  }, [threadId, isStreaming])

  return { messages, setMessages, isStreaming, sendMessage, loadMessages }
}
