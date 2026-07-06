import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { useKeyGate } from './useKeyGate'
import { startOpenRouterConnect } from '../lib/pkce'
import type { ModelResponse } from '../components/ModelSelector'

// Mock the PKCE seam — the gate must CALL it, never re-implement it (Don't Hand-Roll).
vi.mock('../lib/pkce', () => ({
  startOpenRouterConnect: vi.fn(),
}))

// Configurable useKeyStatus per test (the gate reads ONLY status.connected + status.demo_enabled
// from the shared no-poll store — RESEARCH Pattern 1).
const keyStatusState = vi.hoisted(() => ({
  status: null as { connected: boolean; demo_enabled?: boolean } | null,
  loading: false,
}))
vi.mock('./useKeyStatus', () => ({
  useKeyStatus: () => ({ status: keyStatusState.status, loading: keyStatusState.loading }),
}))

const mockedStart = vi.mocked(startOpenRouterConnect)

const FREE_MODEL: ModelResponse = {
  id: 'meta-llama/llama-3.3-70b-instruct:free',
  name: 'Llama 3.3 70B (free)',
  context_length: 128000,
  is_free: true,
  price_per_mtok_prompt: null,
  price_per_mtok_completion: null,
  popularity_rank: 1,
  pricing: {},
}

const PAID_MODEL: ModelResponse = {
  id: 'anthropic/claude-sonnet',
  name: 'Claude Sonnet',
  context_length: 200000,
  is_free: false,
  price_per_mtok_prompt: 3,
  price_per_mtok_completion: 15,
  popularity_rank: 2,
  pricing: {},
}

const MODELS: ModelResponse[] = [FREE_MODEL, PAID_MODEL]

type GateOptions = Parameters<typeof useKeyGate>[0]
type GateApi = ReturnType<typeof useKeyGate>

// Host component: renders gateModal and exposes the hook surface for imperative driving.
// The ref assignment lives in an effect (not render) per react-hooks/refs; act() in select()
// flushes effects, so the ref is always populated before tests drive guardedSelect.
function Host({ opts, apiRef }: { opts: GateOptions; apiRef: { current: GateApi | null } }) {
  const gate = useKeyGate(opts)
  useEffect(() => {
    apiRef.current = gate
  })
  return <>{gate.gateModal}</>
}

function renderGate(over: Partial<GateOptions> = {}) {
  const onApply = vi.fn()
  const apiRef = { current: null as GateApi | null }
  const opts: GateOptions = {
    kind: 'thread',
    threadId: 't-1',
    models: MODELS,
    onApply,
    ...over,
  }
  render(<Host opts={opts} apiRef={apiRef} />)
  return { onApply, apiRef }
}

function select(apiRef: { current: GateApi | null }, modelId: string | null) {
  act(() => {
    apiRef.current!.guardedSelect(modelId)
  })
}

const modalHeading = () => screen.queryByText('Connect OpenRouter?')

describe('useKeyGate — locked decision table (KEY-05 / D-01 / D-03 / D-04)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    keyStatusState.status = null
    keyStatusState.loading = false
  })

  it('row 1: connected → onApply immediately, no modal', () => {
    keyStatusState.status = { connected: true }
    const { onApply, apiRef } = renderGate()
    select(apiRef, PAID_MODEL.id)
    expect(onApply).toHaveBeenCalledWith(PAID_MODEL.id)
    expect(modalHeading()).not.toBeInTheDocument()
  })

  it('row 2: status null (unresolved) → onApply immediately (A3 — no flash-gate; server stays fail-closed)', () => {
    keyStatusState.status = null
    const { onApply, apiRef } = renderGate()
    select(apiRef, PAID_MODEL.id)
    expect(onApply).toHaveBeenCalledWith(PAID_MODEL.id)
    expect(modalHeading()).not.toBeInTheDocument()
  })

  it('row 3: keyless + demo ON + is_free === true → onApply immediately (D-03 free fast-path)', () => {
    keyStatusState.status = { connected: false, demo_enabled: true }
    const { onApply, apiRef } = renderGate()
    select(apiRef, FREE_MODEL.id)
    expect(onApply).toHaveBeenCalledWith(FREE_MODEL.id)
    expect(modalHeading()).not.toBeInTheDocument()
  })

  it('row 4: keyless + demo ON + paid model → modal with the paid body; onApply NOT called', () => {
    keyStatusState.status = { connected: false, demo_enabled: true }
    const { onApply, apiRef } = renderGate()
    select(apiRef, PAID_MODEL.id)
    expect(onApply).not.toHaveBeenCalled()
    expect(modalHeading()).toBeInTheDocument()
    expect(
      screen.getByText(
        "Paid models need your OpenRouter key. Connect to continue — Claude Sonnet will be applied when you're back."
      )
    ).toBeInTheDocument()
  })

  it('row 5: keyless + demo ON + modelId not found in catalog → treated as paid (modal), display name = id', () => {
    keyStatusState.status = { connected: false, demo_enabled: true }
    const { onApply, apiRef } = renderGate()
    select(apiRef, 'ghost/unknown-model')
    expect(onApply).not.toHaveBeenCalled()
    expect(modalHeading()).toBeInTheDocument()
    expect(
      screen.getByText(
        "Paid models need your OpenRouter key. Connect to continue — ghost/unknown-model will be applied when you're back."
      )
    ).toBeInTheDocument()
  })

  it('row 6: keyless + demo OFF + ANY model (even free) → modal with the demo-OFF body', () => {
    keyStatusState.status = { connected: false, demo_enabled: false }
    const { onApply, apiRef } = renderGate()
    select(apiRef, FREE_MODEL.id)
    expect(onApply).not.toHaveBeenCalled()
    expect(modalHeading()).toBeInTheDocument()
    expect(
      screen.getByText(
        "Chatting needs your OpenRouter key. Connect to continue — Llama 3.3 70B (free) will be applied when you're back."
      )
    ).toBeInTheDocument()
  })

  it('row 7: modelId null (extraOption clear row) → onApply immediately, NEVER gated (Open Q1)', () => {
    keyStatusState.status = { connected: false, demo_enabled: false }
    const { onApply, apiRef } = renderGate()
    select(apiRef, null)
    expect(onApply).toHaveBeenCalledWith(null)
    expect(modalHeading()).not.toBeInTheDocument()
  })

  it('row 8a: [Connect] on a thread pick → stash written with the exact locked JSON THEN startOpenRouterConnect()', async () => {
    const user = userEvent.setup()
    keyStatusState.status = { connected: false, demo_enabled: true }
    // Capture the stash AS SEEN at launch time — proves write-before-launch ordering.
    let stashAtLaunch: string | null = null
    mockedStart.mockImplementation(async () => {
      stashAtLaunch = sessionStorage.getItem('or_pending_selection')
    })
    const { onApply, apiRef } = renderGate({ kind: 'thread', threadId: 't-42' })
    select(apiRef, PAID_MODEL.id)

    await user.click(screen.getByRole('button', { name: 'Connect' }))

    expect(mockedStart).toHaveBeenCalledTimes(1)
    expect(stashAtLaunch).not.toBeNull()
    expect(JSON.parse(stashAtLaunch!)).toEqual({
      kind: 'thread',
      modelId: PAID_MODEL.id,
      threadId: 't-42',
      returnTo: '/',
    })
    // The selection is stashed, not applied — apply happens on the OAuth resume (plan 15-03).
    expect(onApply).not.toHaveBeenCalled()
  })

  it('row 8b: [Connect] on a default pick → stash omits threadId, returnTo /settings', async () => {
    const user = userEvent.setup()
    keyStatusState.status = { connected: false, demo_enabled: false }
    const { apiRef } = renderGate({ kind: 'default', threadId: undefined })
    select(apiRef, PAID_MODEL.id)

    await user.click(screen.getByRole('button', { name: 'Connect' }))

    expect(mockedStart).toHaveBeenCalledTimes(1)
    const stash = sessionStorage.getItem('or_pending_selection')
    expect(stash).not.toBeNull()
    expect(JSON.parse(stash!)).toEqual({
      kind: 'default',
      modelId: PAID_MODEL.id,
      returnTo: '/settings',
    })
  })

  it('row 9: [Cancel] → modal closes, onApply never called, no stash written, no PKCE launch', async () => {
    const user = userEvent.setup()
    keyStatusState.status = { connected: false, demo_enabled: true }
    const { onApply, apiRef } = renderGate()
    select(apiRef, PAID_MODEL.id)
    expect(modalHeading()).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(modalHeading()).not.toBeInTheDocument()
    expect(onApply).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('or_pending_selection')).toBeNull()
    expect(mockedStart).not.toHaveBeenCalled()
  })
})
