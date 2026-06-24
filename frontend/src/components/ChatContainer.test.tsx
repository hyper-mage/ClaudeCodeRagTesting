import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeAuthMock, resetMockAuth } from '../test/utils'
import ChatContainer from './ChatContainer'

// ChatContainer calls useAuth() for isAnon — mock the module so renderWithProviders'
// `isAnon` option drives the empty-state hint without a live Supabase session.
vi.mock('../contexts/AuthContext', () => makeAuthMock())

// The three locked example-prompt chips (UI-SPEC § Copywriting Contract — exact strings).
const CHIP_TEXTS = ['Compare Catan vs Wingspan', 'How do you win Azul?', 'Recommend a 2-player game']

// The anon-only onboarding hint mentions the attached D&D sample.
const ANON_HINT = /D&D 5e quick-reference is already attached/i

describe('ChatContainer empty-state (D-02)', () => {
  beforeEach(() => {
    resetMockAuth()
  })

  it('Test 1: renders the headline and exactly the example-prompt chips when messages is empty', () => {
    renderWithProviders(
      <ChatContainer messages={[]} onSend={vi.fn()} isStreaming={false} onRetry={vi.fn()} />
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
      <ChatContainer messages={[]} onSend={onSend} isStreaming={false} onRetry={vi.fn()} />
    )

    await user.click(screen.getByRole('button', { name: 'How do you win Azul?' }))

    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith('How do you win Azul?')
  })

  it('Test 3a: anon users see the D&D hint AND all three chips (shared layout)', () => {
    renderWithProviders(
      <ChatContainer messages={[]} onSend={vi.fn()} isStreaming={false} onRetry={vi.fn()} />,
      { isAnon: true }
    )

    expect(screen.getByText(ANON_HINT)).toBeInTheDocument()
    for (const text of CHIP_TEXTS) {
      expect(screen.getByRole('button', { name: text })).toBeInTheDocument()
    }
  })

  it('Test 3b: authed users do NOT see the D&D hint but DO see the same three chips', () => {
    renderWithProviders(
      <ChatContainer messages={[]} onSend={vi.fn()} isStreaming={false} onRetry={vi.fn()} />,
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
      />
    )

    // The empty-state lives strictly behind messages.length === 0.
    expect(screen.queryByRole('heading', { name: /board game/i })).not.toBeInTheDocument()
    for (const text of CHIP_TEXTS) {
      expect(screen.queryByRole('button', { name: text })).not.toBeInTheDocument()
    }
  })
})
