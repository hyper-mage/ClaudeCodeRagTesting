import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { ProvidersWrapper, mockSSEResponse } from '../test/utils'
import { useChat, INTERRUPTED_CONTENT } from './useChat'
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

describe('useChat demo signal + demo retry (15-07 D-10/D-11)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApiFetch.mockResolvedValue({ messages: [] })
    mockedApiStream.mockResolvedValue(streamReply())
  })

  // A demo turn: the done event carries the Phase-11 mode:"demo" signal.
  function demoStreamReply() {
    return mockSSEResponse(['data: {"text":"hi"}', 'data: {"message_id":"m1","mode":"demo"}'])
  }

  it('Demo 1: a done event with mode:"demo" sets lastTurnWasDemo to true', async () => {
    mockedApiStream.mockResolvedValue(demoStreamReply())
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    expect(result.current.lastTurnWasDemo).toBe(false)

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(result.current.lastTurnWasDemo).toBe(true)
  })

  it('Demo 2: a done event WITHOUT mode leaves lastTurnWasDemo false', async () => {
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(mockedApiStream).toHaveBeenCalledTimes(1)
    expect(result.current.lastTurnWasDemo).toBe(false)
  })

  it('Demo 3: lastTurnWasDemo resets to false on thread switch (Open Q2 resolution)', async () => {
    mockedApiStream.mockResolvedValue(demoStreamReply())
    const { result, rerender } = renderHook(({ id }) => useChat(id), {
      wrapper: ProvidersWrapper,
      initialProps: { id: 't-a' as string | null },
    })

    await act(async () => {
      await result.current.sendMessage('hi')
    })
    expect(result.current.lastTurnWasDemo).toBe(true)

    // Genuine thread switch — per-hook demo state follows the thread-scoped reset semantics.
    rerender({ id: 't-b' })

    await waitFor(() => expect(result.current.lastTurnWasDemo).toBe(false))
  })

  it('Demo 4: a normal send body is {"content": ...} with NO use_demo key', async () => {
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi')
    })

    expect(mockedApiStream).toHaveBeenCalledTimes(1)
    const init = mockedApiStream.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body).toEqual({ content: 'hi' })
    expect(body).not.toHaveProperty('use_demo')
  })

  it('Demo 5: sendMessage(content, {useDemo: true}) body contains "use_demo": true', async () => {
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    await act(async () => {
      await result.current.sendMessage('hi', { useDemo: true })
    })

    expect(mockedApiStream).toHaveBeenCalledTimes(1)
    const init = mockedApiStream.mock.calls[0][1] as RequestInit
    const body = JSON.parse(init.body as string)
    expect(body).toEqual({ content: 'hi', use_demo: true })
  })

  it('Demo 6: retryWithDemo strips error bubbles and re-sends the last user turn with retry + use_demo', async () => {
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    // Seed a failed 403 turn: the user message + its typed error bubble.
    act(() => {
      result.current.setMessages([
        { id: 'u1', role: 'user', content: 'question' },
        { id: 'e1', role: 'error', content: '', errorType: 'forbidden' },
      ])
    })

    await act(async () => {
      result.current.retryWithDemo()
      await Promise.resolve()
    })

    // The retry re-sent the LAST user message against the retry endpoint with the demo override.
    await waitFor(() => expect(mockedApiStream).toHaveBeenCalledTimes(1))
    const [url, init] = mockedApiStream.mock.calls[0]
    expect(url).toContain('/api/threads/t-1/messages?retry=true')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body).toMatchObject({ content: 'question', use_demo: true })

    // The error bubble was stripped the moment the retry started.
    await waitFor(() =>
      expect(result.current.messages.some(m => m.role === 'error')).toBe(false)
    )
  })

  it('Demo 7: retryWithDemo is a no-op when no prior user message exists', async () => {
    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    await act(async () => {
      result.current.retryWithDemo()
      await Promise.resolve()
    })

    expect(mockedApiStream).not.toHaveBeenCalled()
  })

  // Gap 2 / 17-13: a PERSISTED '[Response interrupted]' assistant row (backend stamp) must be
  // recoverable via retryLastUserMessage — the SAME send path, no second implementation.
  it('Interrupted: retryLastUserMessage strips the interrupted assistant row and re-sends the last user turn', async () => {
    const { result } = renderHook(() => useChat('t1'), { wrapper: ProvidersWrapper })

    // Seed a persisted interrupted turn: the user message + the backend interrupted sentinel row.
    act(() => {
      result.current.setMessages([
        { id: 'u1', role: 'user', content: 'Q' },
        { id: 'a1', role: 'assistant', content: INTERRUPTED_CONTENT },
      ])
    })

    await act(async () => {
      result.current.retryLastUserMessage()
      await Promise.resolve()
    })

    // (a) The retry re-sent the LAST user message via the existing retry:true endpoint.
    await waitFor(() => expect(mockedApiStream).toHaveBeenCalledTimes(1))
    const [url, init] = mockedApiStream.mock.calls[0]
    expect(url).toContain('/api/threads/t1/messages?retry=true')
    const body = JSON.parse((init as RequestInit).body as string)
    expect(body).toMatchObject({ content: 'Q' })

    // (b) The interrupted assistant row was stripped the moment the new attempt started.
    await waitFor(() =>
      expect(result.current.messages.some(m => m.content === INTERRUPTED_CONTENT)).toBe(false)
    )
  })

  it('Demo 8: retryWithDemo is a no-op while a stream is in flight', async () => {
    // A never-resolving stream keeps isStreaming true across the retry attempt.
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

    const { result } = renderHook(() => useChat('t-1'), { wrapper: ProvidersWrapper })

    let sendPromise!: Promise<void>
    await act(async () => {
      sendPromise = result.current.sendMessage('hi')
      await Promise.resolve()
    })
    await waitFor(() => expect(result.current.isStreaming).toBe(true))

    await act(async () => {
      result.current.retryWithDemo()
      await Promise.resolve()
    })

    // Only the original send hit the wire — the mid-stream retry was refused.
    expect(mockedApiStream).toHaveBeenCalledTimes(1)

    await act(async () => {
      releaseReader?.()
      await sendPromise
    })
  })
})
