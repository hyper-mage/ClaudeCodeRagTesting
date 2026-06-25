import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
import DefaultModelSelector from './DefaultModelSelector'

// DefaultModelSelector self-PUTs /api/preferences and (via ModelSelector) fetches /api/models —
// mock the api boundary.
vi.mock('../lib/api', () => makeApiMock())

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

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

describe('DefaultModelSelector (D-04 — PUT /api/preferences {default_model})', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(MODELS)
  })

  it('renders the LOCKED heading and helper copy', () => {
    renderWithProviders(<DefaultModelSelector value={null} models={MODELS} />)
    expect(screen.getByText('Default model')).toBeInTheDocument()
    expect(
      screen.getByText(
        'New chats use this model unless you pick a different one for a chat.'
      )
    ).toBeInTheDocument()
  })

  it('selecting a model PUTs /api/preferences with {default_model: id}', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DefaultModelSelector value={null} models={MODELS} />)

    // Open the selector (heading is separate; the trigger is the model-selector button).
    await user.click(screen.getByRole('button', { name: /select a model|default model/i }))
    await screen.findByRole('listbox')
    await user.click(screen.getByRole('option', { name: /claude paid/i }))

    const putCall = mockApiFetch.mock.calls.find(
      ([path, opts]) => path === '/api/preferences' && opts?.method === 'PUT'
    )
    expect(putCall).toBeTruthy()
    expect(JSON.parse(putCall![1].body)).toEqual({ default_model: 'anthropic/claude' })
  })

  it('invokes onChange with the selected id so the parent can hydrate its state', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(
      <DefaultModelSelector value={null} models={MODELS} onChange={onChange} />
    )

    await user.click(screen.getByRole('button', { name: /select a model|default model/i }))
    await screen.findByRole('listbox')
    await user.click(screen.getByRole('option', { name: /llama free/i }))

    expect(onChange).toHaveBeenCalledWith('meta/llama-free')
  })
})
