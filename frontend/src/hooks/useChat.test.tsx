import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { ProvidersWrapper, mockSSEResponse } from '../test/utils'
import { useChat } from './useChat'
import { apiStream, apiFetch } from '../lib/api'

// Mock the I/O boundary — no real backend, no network.
vi.mock('../lib/api', () => ({
  apiFetch: vi.fn(),
  apiStream: vi.fn(),
}))

const mockedApiStream = vi.mocked(apiStream)
const mockedApiFetch = vi.mocked(apiFetch)

// A short, well-formed SSE stream: one content delta + a done event.
function streamReply() {
  return mockSSEResponse(['data: {"text":"hello"}', 'data: {"message_id":"m1"}'])
}

describe('useChat.sendMessage — closure-proof explicit threadId (D-01)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApiStream.mockResolvedValue(streamReply())
  })

  it('Test 1: sends with an explicit threadId even when the hook threadId is null', async () => {
    const { result } = renderHook(() => useChat(null), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi', { threadId: 't-new' })
    })

    // The optimistic user bubble was appended with content 'hi'.
    expect(result.current.messages.some(m => m.role === 'user' && m.content === 'hi')).toBe(true)

    // apiStream was called against the explicit thread id.
    expect(mockedApiStream).toHaveBeenCalledTimes(1)
    const url = mockedApiStream.mock.calls[0][0]
    expect(url).toContain('/api/threads/t-new/messages')
  })

  it('Test 2: falls back to the closured threadId when no opts.threadId (regression)', async () => {
    const { result } = renderHook(() => useChat('t-existing'), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(mockedApiStream).toHaveBeenCalledTimes(1)
    const url = mockedApiStream.mock.calls[0][0]
    expect(url).toContain('/api/threads/t-existing/messages')
  })

  it('Test 3: still no-ops when threadId is null and no opts.threadId (guard preserved)', async () => {
    const { result } = renderHook(() => useChat(null), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(mockedApiStream).not.toHaveBeenCalled()
    expect(result.current.messages).toHaveLength(0)
  })
})

describe('useChat.loadMessages — no-clobber while streaming (D-02 / Pitfall 2)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Test 4: does not replace messages while a send is in flight', async () => {
    // A never-resolving stream so isStreaming stays true across the loadMessages call.
    let releaseReader: (() => void) | null = null
    const pendingReader: ReadableStreamDefaultReader<Uint8Array> = {
      read: () =>
        new Promise(resolve => {
          releaseReader = () => resolve({ done: true, value: undefined })
        }),
      releaseLock: () => {},
      cancel: async () => {},
      closed: Promise.resolve(undefined),
    }
    mockedApiStream.mockResolvedValue({
      ok: true,
      status: 200,
      body: { getReader: () => pendingReader },
    } as unknown as Response)

    // loadMessages would (without the guard) replace messages with this payload.
    mockedApiFetch.mockResolvedValue({ messages: [{ id: 'srv-1', role: 'user', content: 'from-server' }] })

    const { result } = renderHook(() => useChat('t-existing'), { wrapper: ProvidersWrapper })

    // Start a send (do not await — it hangs on the pending reader, keeping isStreaming true).
    let sendPromise!: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('hi')
      // Let the optimistic state + isStreaming flush.
      await Promise.resolve()
    })

    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    const before = result.current.messages
    expect(before.some(m => m.content === 'hi')).toBe(true)

    // Call loadMessages mid-stream — it must NOT clobber the optimistic messages.
    await act(async () => {
      await result.current.loadMessages()
    })

    // Messages unchanged: still the optimistic bubble, never the server payload.
    expect(result.current.messages.some(m => m.content === 'hi')).toBe(true)
    expect(result.current.messages.some(m => m.content === 'from-server')).toBe(false)

    // Cleanly finish the in-flight send.
    await act(async () => {
      releaseReader?.()
      await sendPromise
    })
  })
})
