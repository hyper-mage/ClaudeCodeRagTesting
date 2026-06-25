import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
import ModelSelector from './ModelSelector'

// ModelSelector fetches GET /api/models via apiFetch on first open — mock the api boundary.
vi.mock('../lib/api', () => makeApiMock())

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

// Two rows mirroring the Phase-12 ModelResponse shape: one free, one paid with context.
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

describe('ModelSelector (a11y contract — UI-SPEC LOCKED)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('trigger carries aria-haspopup="listbox" and aria-expanded reflects open state', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    const trigger = screen.getByRole('button', { name: /pick a model/i })
    expect(trigger).toHaveAttribute('aria-haspopup', 'listbox')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('opening fetches /api/models and renders a listbox with option rows (≥44px / min-h-11)', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))

    expect(mockApiFetch).toHaveBeenCalledWith('/api/models')
    const listbox = await screen.findByRole('listbox')
    const options = within(listbox).getAllByRole('option')
    expect(options).toHaveLength(2)
    // Each row must carry the 44px-min touch class.
    for (const opt of options) {
      expect(opt.className).toContain('min-h-11')
    }
  })

  it('shows the LOCKED loading string while pending and the LOCKED error string on failure (retry refetches)', async () => {
    const user = userEvent.setup()
    let reject!: (e: Error) => void
    mockApiFetch.mockReturnValueOnce(new Promise((_res, rej) => { reject = rej }))
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    expect(screen.getByText('Loading models…')).toBeInTheDocument()

    reject(new Error('boom'))
    const retry = await screen.findByText("Couldn't load models. Tap to retry.")
    expect(retry).toBeInTheDocument()

    // Retry re-fetches.
    mockApiFetch.mockResolvedValueOnce(MODELS)
    await user.click(retry)
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    expect(mockApiFetch).toHaveBeenCalledTimes(2)
  })

  it('renders the Free tag for free models and a price hint for paid models', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')

    expect(screen.getByText('Free')).toBeInTheDocument()
    // Paid model shows the price hint with both In/Out figures present.
    expect(screen.getByText(/\$3.*Out.*\$15\/M tokens/i)).toBeInTheDocument()
    // Context lines render for both (128K / 200K).
    expect(screen.getByText('128K context')).toBeInTheDocument()
    expect(screen.getByText('200K context')).toBeInTheDocument()
  })

  it('marks the selected row with a blue-600 indicator', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(
      <ModelSelector value="anthropic/claude" onSelect={vi.fn()} placeholder="Pick a model" />
    )

    // Trigger label resolves the model name after the on-mount catalog fetch settles.
    await user.click(await screen.findByRole('button', { name: /claude paid/i }))
    const listbox = await screen.findByRole('listbox')
    const selected = within(listbox)
      .getAllByRole('option')
      .find(o => o.getAttribute('aria-selected') === 'true')
    expect(selected).toBeTruthy()
    // The selected indicator uses the accent blue-600 (check or left-border).
    expect(selected!.querySelector('[class*="blue-600"]')).toBeTruthy()
  })

  it('selecting a row calls onSelect with the model id and closes the listbox', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(<ModelSelector value={null} onSelect={onSelect} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')
    await user.click(screen.getByRole('option', { name: /claude paid/i }))

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('anthropic/claude')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })

  it('Esc closes the listbox and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    const trigger = screen.getByRole('button', { name: /pick a model/i })
    await user.click(trigger)
    await screen.findByRole('listbox')

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('renders an extraOption row that selects null (clear to default)', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockApiFetch.mockResolvedValue(MODELS)
    renderWithProviders(
      <ModelSelector
        value="anthropic/claude"
        onSelect={onSelect}
        placeholder="Pick a model"
        extraOption={{ label: 'Use my default model', value: null }}
      />
    )

    // Trigger label resolves the model name after the on-mount catalog fetch settles.
    await user.click(await screen.findByRole('button', { name: /claude paid/i }))
    await screen.findByRole('listbox')
    await user.click(screen.getByRole('option', { name: 'Use my default model' }))

    expect(onSelect).toHaveBeenCalledWith(null)
  })
})
