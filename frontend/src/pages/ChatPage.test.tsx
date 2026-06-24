import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import { renderWithProviders, makeAuthMock, resetMockAuth, mockSSEResponse } from '../test/utils'
import ChatPage from './ChatPage'
import { apiFetch, apiStream } from '../lib/api'
import * as Sentry from '@sentry/react'

// Mock the I/O boundary — no real backend, no network.
vi.mock('../lib/api', () => ({
  apiFetch: vi.fn(),
  apiStream: vi.fn(),
}))

// ChatPage transitively calls useAuth() (ChatContainer empty-state, IconSidebar).
// makeAuthMock returns session:null so useKeyStatus short-circuits (no /api/keys/status fetch).
vi.mock('../contexts/AuthContext', () => makeAuthMock())

// Spy on the explicit create-failure capture (Pitfall 5).
vi.mock('@sentry/react', () => ({
  captureException: vi.fn(),
}))

const mockedApiFetch = vi.mocked(apiFetch)
const mockedApiStream = vi.mocked(apiStream)
const mockedCapture = vi.mocked(Sentry.captureException)

// IconSidebar (rendered inside ChatPage) uses react-router hooks, so wrap in a router.
function renderChatPage(opts: { isAnon?: boolean } = {}) {
  return renderWithProviders(
    (<MemoryRouter><ChatPage /></MemoryRouter>) as ReactElement,
    opts
  )
}

// A short, well-formed SSE stream: one content delta + a done event.
function streamReply() {
  return mockSSEResponse(['data: {"text":"Hi there"}', 'data: {"message_id":"m1"}'])
}

// Route apiFetch by (path, options). GET /api/threads → list; POST /api/threads → created
// thread; GET /api/threads/{id} → that thread's messages.
function routeApiFetch(
  config: {
    threadsList?: () => unknown
    createThread?: () => unknown
    threadMessages?: Record<string, unknown>
  } = {}
) {
  const {
    threadsList = () => [],
    createThread = () => ({ id: 't-new', title: null, created_at: '', updated_at: '' }),
    threadMessages = {},
  } = config

  mockedApiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/api/threads') {
      if (options?.method === 'POST') return createThread()
      return threadsList()
    }
    const m = path.match(/^\/api\/threads\/([^/]+)$/)
    if (m) {
      return threadMessages[m[1]] ?? { messages: [] }
    }
    return null
  })
}

async function typeAndSend(user: ReturnType<typeof userEvent.setup>, text: string) {
  const composer = screen.getByPlaceholderText(/send a message/i)
  await user.type(composer, text)
  await user.keyboard('{Enter}')
}

describe('ChatPage auto-create-on-send (D-01 / D-03 / D-04)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetMockAuth()
    mockedApiStream.mockResolvedValue(streamReply())
  })

  it('Test 1: cold-start send auto-creates an untitled thread, streams into it, renders the bubble, and refreshes threads', async () => {
    const user = userEvent.setup()
    // Cold: first GET /api/threads is empty; after send, second GET reflects loadThreads.
    routeApiFetch({ threadsList: () => [] })
    renderChatPage()

    // Empty-state is present (no thread, no messages).
    await screen.findByRole('heading', { name: /board game/i })

    await typeAndSend(user, 'How do you win Azul?')

    // (a) POST /api/threads with body {} fired (untitled create).
    await waitFor(() => {
      const postCall = mockedApiFetch.mock.calls.find(
        ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method === 'POST'
      )
      expect(postCall).toBeTruthy()
      expect((postCall![1] as RequestInit).body).toBe(JSON.stringify({}))
    })

    // (b) sendMessage targeted the freshly-created id (apiStream URL contains t-new).
    await waitFor(() => expect(mockedApiStream).toHaveBeenCalledTimes(1))
    expect(mockedApiStream.mock.calls[0][0]).toContain('/api/threads/t-new/messages')

    // The optimistic user bubble rendered (NOT clobbered by the activeThreadId switch).
    expect(await screen.findByText('How do you win Azul?')).toBeInTheDocument()
    // The streamed assistant text landed.
    expect(await screen.findByText('Hi there')).toBeInTheDocument()

    // (c) loadThreads() ran: a second GET /api/threads after the create.
    const getThreadsCalls = mockedApiFetch.mock.calls.filter(
      ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method !== 'POST'
    )
    expect(getThreadsCalls.length).toBeGreaterThanOrEqual(2)
  })

  it('Test 2: chip tap from cold start follows the same auto-create + stream path', async () => {
    const user = userEvent.setup()
    routeApiFetch({ threadsList: () => [] })
    renderChatPage()

    const chip = await screen.findByRole('button', { name: 'Compare Catan vs Wingspan' })
    await user.click(chip)

    await waitFor(() => {
      const postCall = mockedApiFetch.mock.calls.find(
        ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method === 'POST'
      )
      expect(postCall).toBeTruthy()
    })
    await waitFor(() => expect(mockedApiStream).toHaveBeenCalledTimes(1))
    expect(mockedApiStream.mock.calls[0][0]).toContain('/api/threads/t-new/messages')
    expect(await screen.findByText('Compare Catan vs Wingspan')).toBeInTheDocument()
  })

  it('Test 3: post-delete null state re-enters the create branch (D-04 parity)', async () => {
    const user = userEvent.setup()
    // Start with one existing thread that is NOT auto-selected (activeThreadId stays null),
    // so a send before any selection still exercises the create branch — proving the single
    // null-thread code path covers the post-delete state the same as cold start.
    routeApiFetch({
      threadsList: () => [],
      createThread: () => ({ id: 't-fresh', title: null, created_at: '', updated_at: '' }),
    })
    renderChatPage()

    await screen.findByRole('heading', { name: /board game/i })
    await typeAndSend(user, 'Recommend a 2-player game')

    // A fresh POST /api/threads fired for the null state.
    await waitFor(() => {
      const postCall = mockedApiFetch.mock.calls.find(
        ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method === 'POST'
      )
      expect(postCall).toBeTruthy()
    })
    await waitFor(() => expect(mockedApiStream).toHaveBeenCalledTimes(1))
    expect(mockedApiStream.mock.calls[0][0]).toContain('/api/threads/t-fresh/messages')
  })

  it('Test 4: the create POST body is exactly {} — no placeholder title persisted (D-03)', async () => {
    const user = userEvent.setup()
    routeApiFetch({ threadsList: () => [] })
    renderChatPage()

    await screen.findByRole('heading', { name: /board game/i })
    await typeAndSend(user, 'How do you win Azul?')

    await waitFor(() => {
      const postCall = mockedApiFetch.mock.calls.find(
        ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method === 'POST'
      )
      expect(postCall).toBeTruthy()
      const body = (postCall![1] as RequestInit).body as string
      expect(body).toBe('{}')
      expect(JSON.parse(body)).not.toHaveProperty('title')
    })
  })

  it('Test 5: a failed create surfaces a toast + Sentry and never calls sendMessage (Pitfall 5)', async () => {
    const user = userEvent.setup()
    // GET /api/threads succeeds (empty), but POST /api/threads rejects.
    mockedApiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === '/api/threads' && options?.method === 'POST') {
        throw new Error('API error 500: boom')
      }
      if (path === '/api/threads') return []
      return { messages: [] }
    })
    renderChatPage()

    await screen.findByRole('heading', { name: /board game/i })
    await typeAndSend(user, 'How do you win Azul?')

    // Sentry captured the create failure.
    await waitFor(() => expect(mockedCapture).toHaveBeenCalledTimes(1))
    // An error toast appeared (the reused generic copy). Query by the toast text
    // directly — multiple role="status" nodes exist in the page tree, so scope to
    // the live toast region content.
    expect(await screen.findByText(/the assistant didn't respond/i)).toBeInTheDocument()
    // No send was attempted — the dead-end is surfaced, not silently swallowed.
    expect(mockedApiStream).not.toHaveBeenCalled()
  })

  it('Test 6: anon empty-state shows the D&D hint (anon-cue parity in the page)', async () => {
    routeApiFetch({ threadsList: () => [] })
    renderChatPage({ isAnon: true })

    const region = await screen.findByRole('heading', { name: /board game/i })
    expect(region).toBeInTheDocument()
    expect(
      screen.getByText(/D&D 5e quick-reference is already attached/i)
    ).toBeInTheDocument()
    // Sanity: chips share the layout.
    expect(within(document.body).getByRole('button', { name: 'How do you win Azul?' })).toBeInTheDocument()
  })

  it('Test 7 (regression): streamed reply survives stream-end — no post-stream refetch clobber', async () => {
    // Repro for the live-checkpoint failure: loadMessages listed isStreaming in its deps,
    // so the thread-load effect re-fired when the stream STOPPED, refetching
    // /api/threads/t-new and clobbering the freshly-streamed reply (and any error bubble)
    // the instant the send finished — "no response / retry popup flashed then vanished".
    // The fix moves the in-stream guard to a ref so loadMessages depends on [threadId] only.
    // jsdom masked it before because findByText resolved in the transient pre-clobber window.
    const user = userEvent.setup()
    // If a post-stream refetch happens, it would replace the reply with this server payload.
    routeApiFetch({
      threadsList: () => [],
      threadMessages: {
        't-new': { messages: [{ id: 'srv', role: 'assistant', content: 'CLOBBERED' }] },
      },
    })
    renderChatPage()

    await screen.findByRole('heading', { name: /board game/i })
    await typeAndSend(user, 'How do you win Azul?')

    // Streamed reply appears.
    expect(await screen.findByText('Hi there')).toBeInTheDocument()

    // Wait until the send fully settles past `await sendMessage` (loadThreads ran → 2nd GET
    // /api/threads). By this point the buggy post-stream load-effect would already have fired.
    await waitFor(() => {
      const getThreadsCalls = mockedApiFetch.mock.calls.filter(
        ([p, o]) => p === '/api/threads' && (o as RequestInit | undefined)?.method !== 'POST'
      )
      expect(getThreadsCalls.length).toBeGreaterThanOrEqual(2)
    })

    // The per-thread messages endpoint was NEVER refetched for the auto-created thread...
    const getThreadMessages = mockedApiFetch.mock.calls.filter(
      ([p, o]) =>
        /^\/api\/threads\/[^/]+$/.test(p as string) &&
        (o as RequestInit | undefined)?.method !== 'POST'
    )
    expect(getThreadMessages).toHaveLength(0)
    // ...so the streamed reply persists and the server clobber payload never appears.
    expect(screen.getByText('Hi there')).toBeInTheDocument()
    expect(screen.queryByText('CLOBBERED')).not.toBeInTheDocument()
  })
})
