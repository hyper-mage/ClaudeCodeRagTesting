import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { renderWithProviders, makeAuthMock, makeApiMock, resetMockAuth } from '../test/utils'
import { apiFetch } from '../lib/api'
import { INTERRUPTED_CONTENT, type Message } from '../hooks/useChat'
import ChatContainer from './ChatContainer'

// ChatContainer calls useAuth() for isAnon — mock the module so renderWithProviders'
// `isAnon` option drives the empty-state hint without a live Supabase session.
vi.mock('../contexts/AuthContext', () => makeAuthMock())

// The per-thread ModelSelector may fetch GET /api/models — mock the api boundary so no live call
// fires. The MODEL-06 cases below pass a pre-fetched `models` prop so names resolve synchronously.
vi.mock('../lib/api', () => makeApiMock())
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

// ChatContainer reads connected + demo_enabled from the shared useKeyStatus store (D-10/D-11) —
// mock the module with a mutable state object so each test controls the status shape directly.
const keyStatusMock = vi.hoisted(() => ({
  state: { status: null as null | { connected: boolean; demo_enabled?: boolean } },
}))
vi.mock('../hooks/useKeyStatus', () => ({
  useKeyStatus: () => ({
    status: keyStatusMock.state.status,
    loading: keyStatusMock.state.status === null,
    refresh: async () => {},
    balance: null,
    isLow: false,
    balanceLoading: false,
    balanceError: false,
    refreshBalance: async () => {},
  }),
}))

// Default every test to the loading (null) status so pre-existing cases are unaffected.
beforeEach(() => {
  keyStatusMock.state.status = null
})

// Two catalog rows for the per-thread selector cases (Phase-12 ModelResponse shape).
const MODELS = [
  {
    id: 'meta/llama-free',
    name: 'Llama Free',
    context_length: 128000,
    is_free: true,
    price_per_mtok_prompt: null,
    price_per_mtok_completion: null,
    popularity_rank: 1,
    pricing: {},
  },
  {
    id: 'anthropic/claude',
    name: 'Claude Paid',
    context_length: 200000,
    is_free: false,
    price_per_mtok_prompt: 3,
    price_per_mtok_completion: 15,
    popularity_rank: 2,
    pricing: {},
  },
]

// The three locked example-prompt chips (UI-SPEC § Copywriting Contract — exact strings).
const CHIP_TEXTS = ['Compare Catan vs Wingspan', 'How do you win Azul?', 'Recommend a 2-player game']

// The anon-only onboarding hint mentions the attached D&D sample.
const ANON_HINT = /D&D 5e quick-reference is already attached/i

describe('ChatContainer empty-state (D-02)', () => {
  beforeEach(() => {
    resetMockAuth()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  it('Test 1: renders the headline and exactly the example-prompt chips when messages is empty', () => {
    renderWithProviders(
      <ChatContainer
        messages={[]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId={null}
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
      />
    )

    // Headline is a real heading element.
    expect(screen.getByRole('heading', { name: /board game/i })).toBeInTheDocument()

    // Each chip is reachable by role + accessible name (its visible question text).
    for (const text of CHIP_TEXTS) {
      expect(screen.getByRole('button', { name: text })).toBeInTheDocument()
    }
  })

  it('Test 2: clicking a chip calls onSend once with that chip exact text', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    renderWithProviders(
      <ChatContainer
        messages={[]}
        onSend={onSend}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId={null}
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
      />
    )

    await user.click(screen.getByRole('button', { name: 'How do you win Azul?' }))

    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith('How do you win Azul?')
  })

  it('Test 3a: anon users see the D&D hint AND all three chips (shared layout)', () => {
    renderWithProviders(
      <ChatContainer
        messages={[]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId={null}
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
      />,
      { isAnon: true }
    )

    expect(screen.getByText(ANON_HINT)).toBeInTheDocument()
    for (const text of CHIP_TEXTS) {
      expect(screen.getByRole('button', { name: text })).toBeInTheDocument()
    }
  })

  it('Test 3b: authed users do NOT see the D&D hint but DO see the same three chips', () => {
    renderWithProviders(
      <ChatContainer
        messages={[]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId={null}
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
      />,
      { isAnon: false }
    )

    expect(screen.queryByText(ANON_HINT)).not.toBeInTheDocument()
    for (const text of CHIP_TEXTS) {
      expect(screen.getByRole('button', { name: text })).toBeInTheDocument()
    }
  })

  it('Test 4: a non-empty messages array hides the headline and chips', () => {
    renderWithProviders(
      <ChatContainer
        messages={[{ id: 'u1', role: 'user', content: 'Hello there' }]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId="t1"
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
      />
    )

    // The empty-state lives strictly behind messages.length === 0.
    expect(screen.queryByRole('heading', { name: /board game/i })).not.toBeInTheDocument()
    for (const text of CHIP_TEXTS) {
      expect(screen.queryByRole('button', { name: text })).not.toBeInTheDocument()
    }
  })
})

describe('ChatContainer per-thread model header (MODEL-06 / D-05)', () => {
  beforeEach(() => {
    resetMockAuth()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  it('shows the "Default model" sub-state on the trigger when threadModel is null and a thread is active', () => {
    renderWithProviders(
      <ChatContainer
        messages={[{ id: 'a1', role: 'assistant', content: 'hi' }]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId="t1"
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
        models={MODELS}
      />
    )

    // The locked row label is present, and the selector trigger shows the 'Default model' sub-state.
    expect(screen.getByText('Model for this chat')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Default model' })).toBeInTheDocument()
  })

  it('does NOT render the header row on the cold-start empty state (activeThreadId null)', () => {
    renderWithProviders(
      <ChatContainer
        messages={[]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId={null}
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
        models={MODELS}
      />
    )

    // The whole per-thread row (label + selector) is gated behind activeThreadId !== null.
    expect(screen.queryByText('Model for this chat')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Default model' })).not.toBeInTheDocument()
  })

  it('selecting a model invokes onThreadModelChange with the model id', async () => {
    const user = userEvent.setup()
    const onThreadModelChange = vi.fn()
    renderWithProviders(
      <ChatContainer
        messages={[{ id: 'a1', role: 'assistant', content: 'hi' }]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId="t1"
        threadModel={null}
        onThreadModelChange={onThreadModelChange}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
        models={MODELS}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Default model' }))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getAllByRole('option', { name: /claude paid/i })[0])

    expect(onThreadModelChange).toHaveBeenCalledWith('anthropic/claude')
  })

  it('the "Use my default model" clear option invokes onThreadModelChange with null', async () => {
    const user = userEvent.setup()
    const onThreadModelChange = vi.fn()
    renderWithProviders(
      <ChatContainer
        messages={[{ id: 'a1', role: 'assistant', content: 'hi' }]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId="t1"
        threadModel="anthropic/claude"
        onThreadModelChange={onThreadModelChange}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
        models={MODELS}
      />
    )

    // With a model pinned the trigger shows its name; open and pick the clear row.
    await user.click(screen.getByRole('button', { name: /claude paid/i }))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByRole('option', { name: 'Use my default model' }))

    expect(onThreadModelChange).toHaveBeenCalledWith(null)
  })

  it('renders a role "notice" message as a quiet system line (DeprecationNotice), not a bubble', () => {
    const NOTICE = 'Model "x" is no longer available — using y instead.'
    renderWithProviders(
      <ChatContainer
        messages={[{ id: 'n1', role: 'notice', content: NOTICE }]}
        onSend={vi.fn()}
        isStreaming={false}
        onRetry={vi.fn()}
        activeThreadId="t1"
        threadModel={null}
        onThreadModelChange={vi.fn()}
        threadPersona={null}
        onThreadPersonaChange={vi.fn()}
        models={MODELS}
      />
    )

    // The notice copy renders. Scope the bubble checks to the notice line itself (the ChatContainer
    // legitimately contains a blue-600 Send CTA in the composer — that must NOT fail this case).
    const noticeText = screen.getByText(NOTICE)
    const noticeLine = noticeText.closest('div')!.parentElement!
    expect(noticeLine.querySelector('[class*="rounded-lg"]')).toBeNull()
    expect(noticeLine.querySelector('[class*="bg-blue-600"]')).toBeNull()
    // It is not a MessageBubble user/assistant bubble — no whitespace-pre-wrap user bubble markup.
    expect(noticeLine.querySelector('[class*="max-w-[70%]"]')).toBeNull()
  })
})

// LOCKED banner sentence (UI-SPEC § Copywriting, verbatim from Phase 11 D-08) — asserted exactly.
const DEMO_BANNER_SENTENCE =
  'Demo mode — a free model is in use; it may be slower, less accurate, or temporarily rate-limited (no usage left).'

// Shared render helper for the demo cases: sensible defaults, overridable per test.
function renderContainer(props: Partial<ComponentProps<typeof ChatContainer>> = {}) {
  return renderWithProviders(
    <ChatContainer
      messages={[]}
      onSend={vi.fn()}
      isStreaming={false}
      onRetry={vi.fn()}
      activeThreadId={null}
      threadModel={null}
      onThreadModelChange={vi.fn()}
      threadPersona={null}
      onThreadPersonaChange={vi.fn()}
      {...props}
    />
  )
}

describe('ChatContainer demo banner (DEMO-02 / D-10)', () => {
  beforeEach(() => {
    resetMockAuth()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  it('matrix (a): keyless + demo_enabled → banner present with the locked copy verbatim', () => {
    keyStatusMock.state.status = { connected: false, demo_enabled: true }
    renderContainer()

    expect(screen.getByText(DEMO_BANNER_SENTENCE)).toBeInTheDocument()
  })

  it('matrix (b): connected + no demo turn → banner absent', () => {
    keyStatusMock.state.status = { connected: true, demo_enabled: true }
    renderContainer()

    expect(screen.queryByText(DEMO_BANNER_SENTENCE)).not.toBeInTheDocument()
  })

  it('matrix (c): connected + lastTurnWasDemo → banner present (mode:"demo" latch)', () => {
    keyStatusMock.state.status = { connected: true, demo_enabled: true }
    renderContainer({ lastTurnWasDemo: true })

    expect(screen.getByText(DEMO_BANNER_SENTENCE)).toBeInTheDocument()
  })

  it('matrix (d): status null (still loading) → banner absent — no flash', () => {
    keyStatusMock.state.status = null
    renderContainer()

    expect(screen.queryByText(DEMO_BANNER_SENTENCE)).not.toBeInTheDocument()
  })

  it('banner is role="status", non-dismissible (no interactive children), and sits ABOVE the thread header', () => {
    keyStatusMock.state.status = { connected: false, demo_enabled: true }
    renderContainer({
      messages: [{ id: 'a1', role: 'assistant', content: 'hi' }],
      activeThreadId: 't1',
      models: MODELS,
    })

    const banner = screen
      .getByText(DEMO_BANNER_SENTENCE)
      .closest('[role="status"]') as HTMLElement
    expect(banner).not.toBeNull()
    // shrink-0 sibling — preserves the flex-1 scroll layout (Pitfall 11 / T-15-27).
    expect(banner.className).toContain('shrink-0')
    // DEMO-02 non-dismissible: no close button, no interactive children of any kind.
    expect(banner.querySelector('button')).toBeNull()
    expect(banner.querySelector('a')).toBeNull()
    expect(banner.querySelector('input')).toBeNull()
    // First shrink-0 child: the banner precedes the per-thread header row in DOM order.
    const headerLabel = screen.getByText('Model for this chat')
    expect(
      banner.compareDocumentPosition(headerLabel) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })
})

describe('ChatContainer [Use demo] wiring (D-11)', () => {
  beforeEach(() => {
    resetMockAuth()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  // A failed 403 turn: the typed forbidden error bubble.
  const forbiddenError: Message[] = [
    { id: 'e1', role: 'error', content: '', errorType: 'forbidden' },
  ]

  it('forbidden bubble + demo_enabled → [Use demo] visible; clicking calls onUseDemo', async () => {
    const user = userEvent.setup()
    keyStatusMock.state.status = { connected: true, demo_enabled: true }
    const onUseDemo = vi.fn()
    renderContainer({ messages: forbiddenError, activeThreadId: 't1', models: MODELS, onUseDemo })

    const btn = screen.getByRole('button', { name: 'Use demo' })
    await user.click(btn)

    expect(onUseDemo).toHaveBeenCalledTimes(1)
  })

  it('forbidden bubble + demo_enabled false → [Use demo] absent', () => {
    keyStatusMock.state.status = { connected: true, demo_enabled: false }
    renderContainer({
      messages: forbiddenError,
      activeThreadId: 't1',
      models: MODELS,
      onUseDemo: vi.fn(),
    })

    expect(screen.queryByRole('button', { name: 'Use demo' })).not.toBeInTheDocument()
  })
})

describe('ChatContainer interrupted-turn Retry (Gap 2)', () => {
  beforeEach(() => {
    resetMockAuth()
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  // A PERSISTED interrupted turn: the last user message + the backend-stamped assistant sentinel row
  // (role='assistant', content='[Response interrupted]'), sourced from the shared INTERRUPTED_CONTENT.
  const interruptedThread: Message[] = [
    { id: 'u1', role: 'user', content: 'How do you win Azul?' },
    { id: 'a1', role: 'assistant', content: INTERRUPTED_CONTENT },
  ]

  it('it A: renders an alert Retry card for the interrupted turn, not a plain sentinel bubble', () => {
    renderContainer({ messages: interruptedThread, activeThreadId: 't1', models: MODELS })

    // The recovery card is a role="alert" container carrying a Retry control.
    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
    expect(within(alert).getByRole('button', { name: /retry/i })).toBeInTheDocument()
    // The raw sentinel is NOT surfaced as a plain MessageBubble body.
    expect(screen.queryByText(INTERRUPTED_CONTENT)).not.toBeInTheDocument()
  })

  it('it B: clicking Retry calls onRetry exactly once', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    renderContainer({ messages: interruptedThread, activeThreadId: 't1', models: MODELS, onRetry })

    await user.click(screen.getByRole('button', { name: /retry/i }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('it C: the Retry button is disabled while a fresh attempt is streaming (no double-submit)', () => {
    renderContainer({
      messages: interruptedThread,
      activeThreadId: 't1',
      models: MODELS,
      isStreaming: true,
    })

    expect(screen.getByRole('button', { name: /retry/i })).toBeDisabled()
  })
})
