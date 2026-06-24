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

describe('useChat.loadMessages — unconditional fetch contract (CR-01)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApiStream.mockResolvedValue(streamReply())
  })

  it('Test 4: loadMessages unconditionally fetches the thread and replaces messages', async () => {
    // The old in-stream guard inside loadMessages is GONE (CR-01): the clobber protection now
    // lives in the [threadId] effect + skipNextLoad, not in loadMessages itself. So a direct
    // call to loadMessages with a threadId always fetches and replaces.
    mockedApiFetch.mockResolvedValue({
      messages: [{ id: 'srv-1', role: 'user', content: 'from-server' }],
    })

    const { result } = renderHook(() => useChat('t-existing'), { wrapper: ProvidersWrapper })

    // The mount [threadId] effect already loaded the thread once.
    await waitFor(() =>
      expect(result.current.messages.some(m => m.content === 'from-server')).toBe(true)
    )

    // Append an optimistic bubble, then call loadMessages directly: it replaces with the
    // server payload (no guard), proving loadMessages is now unconditional.
    act(() => {
      result.current.setMessages(prev => [
        ...prev,
        { id: 'opt', role: 'user', content: 'optimistic' },
      ])
    })
    expect(result.current.messages.some(m => m.content === 'optimistic')).toBe(true)

    await act(async () => {
      await result.current.loadMessages()
    })

    // The fetch landed and replaced everything — the optimistic bubble is gone.
    expect(result.current.messages.some(m => m.content === 'from-server')).toBe(true)
    expect(result.current.messages.some(m => m.content === 'optimistic')).toBe(false)
  })

  it('Test 5: loadMessages with a null threadId clears messages and does not fetch', async () => {
    const { result } = renderHook(() => useChat(null), { wrapper: ProvidersWrapper })

    // Seed some state, then load with a null thread — the !threadId branch clears it.
    act(() => {
      result.current.setMessages([{ id: 'x', role: 'user', content: 'stale' }])
    })
    expect(result.current.messages).toHaveLength(1)

    await act(async () => {
      await result.current.loadMessages()
    })

    expect(result.current.messages).toHaveLength(0)
    expect(mockedApiFetch).not.toHaveBeenCalled()
  })

  it('Test 6: skipNextLoad suppresses exactly one [threadId] load (auto-created thread)', async () => {
    // Simulate ChatPage's auto-create handoff: request the one-shot skip, THEN point the hook at
    // a fresh thread. The [threadId] effect must consume the flag and NOT fetch (which would
    // clobber the optimistic bubble). The very next switch must load normally again.
    mockedApiFetch.mockResolvedValue({ messages: [] })

    const { result, rerender } = renderHook(({ id }) => useChat(id), {
      wrapper: ProvidersWrapper,
      initialProps: { id: 't-a' as string | null },
    })

    // Mount load for t-a fired.
    await waitFor(() => expect(mockedApiFetch).toHaveBeenCalledTimes(1))
    expect(mockedApiFetch.mock.calls[0][0]).toBe('/api/threads/t-a')

    // Request the skip, then switch to the freshly auto-created thread.
    act(() => {
      result.current.skipNextLoad()
    })
    rerender({ id: 't-new' })

    // No fetch for t-new — the one-shot skip consumed it.
    await waitFor(() => expect(result.current).toBeTruthy())
    const fetchedNew = mockedApiFetch.mock.calls.some(([p]) => p === '/api/threads/t-new')
    expect(fetchedNew).toBe(false)
    expect(mockedApiFetch).toHaveBeenCalledTimes(1)

    // A subsequent genuine switch loads normally (flag was one-shot).
    rerender({ id: 't-b' })
    await waitFor(() =>
      expect(mockedApiFetch.mock.calls.some(([p]) => p === '/api/threads/t-b')).toBe(true)
    )
  })

  it('Test 7: switching threads mid-stream aborts the in-flight stream and loads the new thread (CR-01)', async () => {
    // A never-resolving stream so the first thread's send stays in flight across the switch.
    let releaseReader: (() => void) | null = null
    let capturedSignal: AbortSignal | null = null
    const pendingReader: ReadableStreamDefaultReader<Uint8Array> = {
      read: () =>
        new Promise(resolve => {
          releaseReader = () => resolve({ done: true, value: undefined })
        }),
      releaseLock: () => {},
      cancel: async () => {},
      closed: Promise.resolve(undefined),
    }
    mockedApiStream.mockImplementation(async (_url: string, init?: RequestInit) => {
      capturedSignal = (init?.signal as AbortSignal) ?? null
      return {
        ok: true,
        status: 200,
        body: { getReader: () => pendingReader },
      } as unknown as Response
    })
    mockedApiFetch.mockResolvedValue({
      messages: [{ id: 'srv-b', role: 'assistant', content: 'thread-b-content' }],
    })

    const { result, rerender } = renderHook(({ id }) => useChat(id), {
      wrapper: ProvidersWrapper,
      initialProps: { id: 't-a' as string | null },
    })

    // Start a send into t-a (do not await — it hangs on the pending reader).
    let sendPromise!: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('hi', { threadId: 't-a' })
      await Promise.resolve()
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(true))
    expect(capturedSignal).not.toBeNull()
    expect(capturedSignal!.aborted).toBe(false)

    // Switch to a DIFFERENT existing thread mid-stream.
    rerender({ id: 't-b' })

    // (a) the in-flight stream's AbortController was aborted on switch.
    await waitFor(() => expect(capturedSignal!.aborted).toBe(true))
    // isStreaming was reset by the abort-on-switch effect.
    await waitFor(() => expect(result.current.isStreaming).toBe(false))

    // (b) the new thread's messages were fetched and rendered (not t-a's streamed content).
    await waitFor(() =>
      expect(mockedApiFetch.mock.calls.some(([p]) => p === '/api/threads/t-b')).toBe(true)
    )
    await waitFor(() =>
      expect(result.current.messages.some(m => m.content === 'thread-b-content')).toBe(true)
    )

    // Release the (now-aborted) reader to settle the hung send promise cleanly.
    await act(async () => {
      releaseReader?.()
      await sendPromise
    })
  })
})
