import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeAuthMock, makeApiMock, resetMockAuth } from '../test/utils'
import { apiFetch } from '../lib/api'
import ChatContainer from './ChatContainer'

// ChatContainer calls useAuth() for isAnon — mock the module so renderWithProviders'
// `isAnon` option drives the empty-state hint without a live Supabase session.
vi.mock('../contexts/AuthContext', () => makeAuthMock())

// The per-thread ModelSelector may fetch GET /api/models — mock the api boundary so no live call
// fires. The MODEL-06 cases below pass a pre-fetched `models` prop so names resolve synchronously.
vi.mock('../lib/api', () => makeApiMock())
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

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
        models={MODELS}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Default model' }))
    const listbox = await screen.findByRole('listbox')
    await user.click(within(listbox).getByRole('option', { name: /claude paid/i }))

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
