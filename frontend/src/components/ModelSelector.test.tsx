import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
import ModelSelector from './ModelSelector'

// ModelSelector fetches GET /api/models (first open) and GET /api/preferences (favorites read
// at mount) via apiFetch — mock the api boundary and dispatch per-URL.
vi.mock('../lib/api', () => makeApiMock())

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

// Three rows mirroring the Phase-12 ModelResponse shape: one free+popular (with '3.3' in the
// id/name so the locked 'lama33' typo-tolerance case has a real target), one paid+popular,
// one paid unranked (popularity_rank null → no Popular section membership, no chip).
const MODELS = [
  {
    id: 'meta/llama-3.3-free',
    name: 'Llama 3.3 Free',
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
  {
    id: 'mistral/mistral-7b',
    name: 'Mistral 7B',
    context_length: 32000,
    is_free: false,
    price_per_mtok_prompt: 0.25,
    price_per_mtok_completion: 0.25,
    popularity_rank: null,
    pricing: {},
  },
]

// Section math with no favorites: Popular (2 ranked) + All models (3) = 5 option instances.
const SECTIONED_COUNT = 5

/** Per-URL apiFetch dispatch: catalog + favorites (default none). */
function mockCatalog({ models = MODELS, favorites = [] as string[] } = {}) {
  mockApiFetch.mockImplementation((url: string) => {
    if (url === '/api/models') return Promise.resolve(models)
    if (url === '/api/preferences') {
      return Promise.resolve({ default_model: null, theme: 'dark', favorite_models: favorites })
    }
    return Promise.resolve({})
  })
}

/** True when the element contains a Popular chip span (Free-tag-mirroring classes). */
function hasPopularChip(el: Element): boolean {
  return Array.from(el.querySelectorAll('span')).some(
    s => s.textContent === 'Popular' && s.className.includes('bg-gray-200')
  )
}

/** All PUT /api/preferences call bodies, JSON-parsed (MODEL-08 whole-array replace assertions). */
function preferencesPutBodies(): unknown[] {
  return mockApiFetch.mock.calls
    .filter(c => c[0] === '/api/preferences' && c[1]?.method === 'PUT')
    .map(c => JSON.parse(c[1].body as string))
}

describe('ModelSelector (a11y contract — UI-SPEC LOCKED)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('trigger carries aria-haspopup="listbox" and aria-expanded reflects open state', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    const trigger = screen.getByRole('button', { name: /pick a model/i })
    expect(trigger).toHaveAttribute('aria-haspopup', 'listbox')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await user.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
  })

  it('opening fetches /api/models and renders a listbox with option rows (≥44px / min-h-11)', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))

    expect(mockApiFetch).toHaveBeenCalledWith('/api/models')
    const listbox = await screen.findByRole('listbox')
    const options = within(listbox).getAllByRole('option')
    expect(options).toHaveLength(SECTIONED_COUNT)
    // Each row must carry the 44px-min touch class.
    for (const opt of options) {
      expect(opt.className).toContain('min-h-11')
    }
  })

  it('shows the LOCKED loading string while pending and the LOCKED error string on failure (retry refetches)', async () => {
    const user = userEvent.setup()
    let reject!: (e: Error) => void
    let modelCalls = 0
    mockApiFetch.mockImplementation((url: string) => {
      if (url === '/api/preferences') return Promise.resolve({ favorite_models: [] })
      modelCalls += 1
      if (modelCalls === 1) return new Promise((_res, rej) => { reject = rej })
      return Promise.resolve(MODELS)
    })
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    expect(screen.getByText('Loading models…')).toBeInTheDocument()

    reject(new Error('boom'))
    const retry = await screen.findByText("Couldn't load models. Tap to retry.")
    expect(retry).toBeInTheDocument()

    // Retry re-fetches the catalog.
    await user.click(retry)
    expect(await screen.findByRole('listbox')).toBeInTheDocument()
    expect(mockApiFetch.mock.calls.filter(c => c[0] === '/api/models')).toHaveLength(2)
  })

  it('renders the Free tag for free models and a price hint for paid models', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')

    // Free llama appears in Popular + All models → one Free tag per instance.
    expect(screen.getAllByText('Free')).toHaveLength(2)
    // Paid claude shows the price hint with both In/Out figures, in both instances.
    expect(screen.getAllByText(/\$3.*Out.*\$15\/M tokens/i)).toHaveLength(2)
    // Context lines render per instance (128K/200K twice; 32K once — mistral is unranked).
    expect(screen.getAllByText('128K context')).toHaveLength(2)
    expect(screen.getAllByText('200K context')).toHaveLength(2)
    expect(screen.getAllByText('32K context')).toHaveLength(1)
  })

  it('marks the selected row with a blue-600 indicator in EVERY duplicate instance', async () => {
    const user = userEvent.setup()
    // Favorited + popular + catalog → claude appears in all 3 sections.
    mockCatalog({ favorites: ['anthropic/claude'] })
    renderWithProviders(
      <ModelSelector value="anthropic/claude" onSelect={vi.fn()} placeholder="Pick a model" />
    )

    // Trigger label resolves the model name after the on-mount catalog fetch settles.
    await user.click(await screen.findByRole('button', { name: /claude paid/i }))
    const listbox = await screen.findByRole('listbox')
    const selected = within(listbox)
      .getAllByRole('option')
      .filter(o => o.getAttribute('aria-selected') === 'true')
    expect(selected).toHaveLength(3)
    for (const instance of selected) {
      // The selected indicator uses the accent blue-600 (check at left-1.5).
      expect(instance.querySelector('[class*="blue-600"]')).toBeTruthy()
    }
  })

  it('selecting a row calls onSelect with the model id and closes the listbox', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={onSelect} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')
    // Duplicate instances are deliberate — clicking any instance selects the same id.
    await user.click(screen.getAllByRole('option', { name: /claude paid/i })[0])

    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('anthropic/claude')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })

  it('Esc closes the listbox and returns focus to the trigger', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    const trigger = screen.getByRole('button', { name: /pick a model/i })
    await user.click(trigger)
    await screen.findByRole('listbox')

    // The combobox focus model puts focus on the search input — Esc lands there.
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('renders an extraOption row that selects null (clear to default)', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockCatalog()
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

  it('treats an empty models=[] prop as "no catalog" and lazy-fetches on open (regression)', async () => {
    const user = userEvent.setup()
    mockCatalog()
    // An empty array is truthy — it must NOT pin a silent empty "loaded" panel.
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" models={[]} />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')
    expect(screen.getAllByRole('option')).toHaveLength(SECTIONED_COUNT)
    expect(mockApiFetch).toHaveBeenCalledWith('/api/models')
  })

  it('shows an empty-state when the catalog genuinely loads zero models', async () => {
    const user = userEvent.setup()
    mockCatalog({ models: [] })
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    expect(await screen.findByText('No models available.')).toBeInTheDocument()
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })
})

describe('ModelSelector sections + Popular chip (D-06 / D-07)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('reads favorites from GET /api/preferences exactly once at mount', async () => {
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await waitFor(() => expect(mockApiFetch).toHaveBeenCalledWith('/api/preferences'))
    expect(mockApiFetch.mock.calls.filter(c => c[0] === '/api/preferences')).toHaveLength(1)
  })

  it('renders section headers in order Favorites → Popular → All models (with a favorite)', async () => {
    const user = userEvent.setup()
    mockCatalog({ favorites: ['anthropic/claude'] })
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    const headers = Array.from(listbox.querySelectorAll('li[role="presentation"]'))
    expect(headers.map(h => h.textContent)).toEqual(['Favorites', 'Popular', 'All models'])
    // Headers are non-interactive — never options, never navigable.
    for (const h of headers) {
      expect(h.getAttribute('role')).toBe('presentation')
    }
  })

  it('hides the Favorites section entirely when favorite_models is empty (LOCKED — no hint)', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    const headers = Array.from(listbox.querySelectorAll('li[role="presentation"]'))
    expect(headers.map(h => h.textContent)).toEqual(['Popular', 'All models'])
    expect(within(listbox).queryByText('Favorites')).not.toBeInTheDocument()
  })

  it('orders the Popular section by popularity_rank (curated order, not alphabetical)', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    const popInstances = Array.from(listbox.querySelectorAll('[id*="-opt-pop-"]'))
    expect(popInstances).toHaveLength(2)
    expect(popInstances[0].textContent).toContain('Llama 3.3 Free') // rank 1
    expect(popInstances[1].textContent).toContain('Claude Paid') // rank 2
    // Unranked mistral never joins Popular.
    expect(popInstances.some(el => el.textContent!.includes('Mistral'))).toBe(false)
  })

  it('renders the complete catalog alphabetically in All models', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    const allInstances = Array.from(listbox.querySelectorAll('[id*="-opt-all-"]'))
    expect(allInstances).toHaveLength(MODELS.length)
    expect(allInstances[0].textContent).toContain('Claude Paid')
    expect(allInstances[1].textContent).toContain('Llama 3.3 Free')
    expect(allInstances[2].textContent).toContain('Mistral 7B')
  })

  it('shows the Popular chip on ranked rows in EVERY section instance, never on unranked rows', async () => {
    const user = userEvent.setup()
    mockCatalog({ favorites: ['meta/llama-3.3-free'] })
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    // Ranked llama: Favorites + Popular + All instances all carry the chip.
    const favInstances = Array.from(listbox.querySelectorAll('[id*="-opt-fav-"]'))
    expect(favInstances).toHaveLength(1)
    expect(hasPopularChip(favInstances[0])).toBe(true)

    const popInstances = Array.from(listbox.querySelectorAll('[id*="-opt-pop-"]'))
    expect(popInstances.every(hasPopularChip)).toBe(true)

    const allInstances = Array.from(listbox.querySelectorAll('[id*="-opt-all-"]'))
    const llamaAll = allInstances.find(el => el.textContent!.includes('Llama 3.3 Free'))!
    const claudeAll = allInstances.find(el => el.textContent!.includes('Claude Paid'))!
    const mistralAll = allInstances.find(el => el.textContent!.includes('Mistral 7B'))!
    expect(hasPopularChip(llamaAll)).toBe(true)
    expect(hasPopularChip(claudeAll)).toBe(true)
    expect(hasPopularChip(mistralAll)).toBe(false)
  })

  it('renders duplicate section instances with section-scoped keys (no duplicate-key warnings)', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      const user = userEvent.setup()
      // llama favorited + ranked → appears in all 3 sections; keys must be section-scoped.
      mockCatalog({ favorites: ['meta/llama-3.3-free'] })
      renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

      await user.click(screen.getByRole('button', { name: /pick a model/i }))
      await screen.findByRole('listbox')

      const keyWarnings = errorSpy.mock.calls.filter(args => String(args[0]).includes('same key'))
      expect(keyWarnings).toHaveLength(0)
    } finally {
      errorSpy.mockRestore()
    }
  })
})

describe('ModelSelector search (MODEL-01 — LOCKED combobox contract)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('moves focus to the search input on open (combobox focus model, supersedes UL focus)', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const input = screen.getByPlaceholderText('Search models…')
    await waitFor(() => expect(input).toHaveFocus())
    expect(input).toHaveAttribute('aria-autocomplete', 'list')
    const listbox = await screen.findByRole('listbox')
    expect(input.getAttribute('aria-controls')).toBe(listbox.id)
  })

  // NOTE on the debounce tests: RTL 16's async event wrapper drains via setTimeout(0) and only
  // auto-advances when it detects JEST fake timers (`typeof jest !== 'undefined'`), so every
  // `await user.*` call hangs forever under VITEST fake timers. The plan-sanctioned
  // vi.useFakeTimers + advanceTimersByTime(150) flow therefore drives the input with the SYNC
  // fireEvent API (controlled-input change) instead of userEvent.

  it("typing 'lama33' filters into ONE flat score-ranked list after the 150ms debounce (typo-tolerant)", async () => {
    vi.useFakeTimers()
    try {
      mockCatalog()
      renderWithProviders(
        <ModelSelector
          value={null}
          onSelect={vi.fn()}
          placeholder="Pick a model"
          models={MODELS}
          extraOption={{ label: 'Use my default model', value: null }}
        />
      )
      // Drain the mount-time preferences microtask inside act (no timers involved).
      await act(async () => {})

      fireEvent.click(screen.getByRole('button', { name: /pick a model/i }))
      const listbox = screen.getByRole('listbox')
      expect(listbox.querySelectorAll('li[role="presentation"]').length).toBeGreaterThan(0)

      fireEvent.change(screen.getByPlaceholderText('Search models…'), {
        target: { value: 'lama33' },
      })
      // Debounce respected: the sections survive until 150ms elapse.
      expect(listbox.querySelectorAll('li[role="presentation"]').length).toBeGreaterThan(0)
      act(() => {
        vi.advanceTimersByTime(150)
      })

      const options = within(screen.getByRole('listbox')).getAllByRole('option')
      expect(options).toHaveLength(1)
      expect(options[0].textContent).toContain('Llama 3.3 Free')
      // Flat search mode: no headers, extraOption hidden, non-matches removed.
      expect(screen.getByRole('listbox').querySelectorAll('li[role="presentation"]')).toHaveLength(0)
      expect(screen.queryByRole('option', { name: 'Use my default model' })).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('renders the LOCKED no-match caption when nothing matches', async () => {
    vi.useFakeTimers()
    try {
      mockCatalog()
      renderWithProviders(
        <ModelSelector value={null} onSelect={vi.fn()} placeholder="Pick a model" models={MODELS} />
      )
      await act(async () => {})

      fireEvent.click(screen.getByRole('button', { name: /pick a model/i }))
      fireEvent.change(screen.getByPlaceholderText('Search models…'), {
        target: { value: 'zzzqqq' },
      })
      act(() => {
        vi.advanceTimersByTime(150)
      })

      expect(screen.getByText('No models match your search.')).toBeInTheDocument()
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('clearing the query restores the sections and the extraOption row', async () => {
    vi.useFakeTimers()
    try {
      mockCatalog()
      renderWithProviders(
        <ModelSelector
          value={null}
          onSelect={vi.fn()}
          placeholder="Pick a model"
          models={MODELS}
          extraOption={{ label: 'Use my default model', value: null }}
        />
      )
      await act(async () => {})

      fireEvent.click(screen.getByRole('button', { name: /pick a model/i }))
      const input = screen.getByPlaceholderText('Search models…')
      fireEvent.change(input, { target: { value: 'lama33' } })
      act(() => {
        vi.advanceTimersByTime(150)
      })
      expect(screen.getByRole('listbox').querySelectorAll('li[role="presentation"]')).toHaveLength(0)

      fireEvent.change(input, { target: { value: '' } })
      act(() => {
        vi.advanceTimersByTime(150)
      })

      const headers = Array.from(
        screen.getByRole('listbox').querySelectorAll('li[role="presentation"]')
      )
      expect(headers.map(h => h.textContent)).toEqual(['Popular', 'All models'])
      expect(screen.getByRole('option', { name: 'Use my default model' })).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('ArrowDown moves the active row over options only (headers skipped) and Enter selects it', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockCatalog({ favorites: ['anthropic/claude'] })
    renderWithProviders(<ModelSelector value={null} onSelect={onSelect} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')
    const input = screen.getByPlaceholderText('Search models…')
    const optionIds = within(listbox).getAllByRole('option').map(o => o.id)

    // Active starts on the first navigable option; headers are never activedescendant targets.
    await waitFor(() => expect(input).toHaveAttribute('aria-activedescendant', optionIds[0]))
    await user.keyboard('{ArrowDown}')
    expect(input).toHaveAttribute('aria-activedescendant', optionIds[1])
    const active = document.getElementById(input.getAttribute('aria-activedescendant')!)
    expect(active).toHaveAttribute('role', 'option')

    // Enter selects the active row (Favorites: claude → Popular: llama rank 1).
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledWith('meta/llama-3.3-free')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })
})

describe('ModelSelector favorite star (MODEL-08 / D-05)', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
  })

  it('star click toggles: whole-array PUT, dropdown stays OPEN, onSelect NOT called', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={onSelect} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')

    // Sectioned picker: a model renders in multiple sections — take the FIRST star instance.
    const star = screen.getAllByRole('button', { name: 'Add Claude Paid to favorites' })[0]
    await user.click(star)

    // Whole-array replace, favorite_models the ONLY key in the body (D-05 partial upsert).
    expect(preferencesPutBodies()).toEqual([{ favorite_models: ['anthropic/claude'] }])
    // stopPropagation: no selection, no close — users can star several in one open.
    expect(onSelect).not.toHaveBeenCalled()
    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })

  it('Shift+Enter toggles favorite on the active row while plain Enter still selects', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    mockCatalog()
    renderWithProviders(<ModelSelector value={null} onSelect={onSelect} placeholder="Pick a model" />)

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    await screen.findByRole('listbox')

    // Active row starts on the first navigable option (Popular: llama, rank 1).
    await user.keyboard('{Shift>}{Enter}{/Shift}')
    expect(preferencesPutBodies()).toEqual([{ favorite_models: ['meta/llama-3.3-free'] }])
    expect(onSelect).not.toHaveBeenCalled()
    expect(screen.getByRole('listbox')).toBeInTheDocument()

    // Plain Enter still selects the active row (now Favorites: llama) and closes.
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('meta/llama-3.3-free')
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument())
  })

  it('renders a star on every catalog row but never on the extraOption row', async () => {
    const user = userEvent.setup()
    mockCatalog()
    renderWithProviders(
      <ModelSelector
        value={null}
        onSelect={vi.fn()}
        placeholder="Pick a model"
        extraOption={{ label: 'Use my default model', value: null }}
      />
    )

    await user.click(screen.getByRole('button', { name: /pick a model/i }))
    const listbox = await screen.findByRole('listbox')

    const extra = within(listbox).getByRole('option', { name: 'Use my default model' })
    expect(within(extra).queryByRole('button')).not.toBeInTheDocument()

    // Every catalog instance (Popular 2 + All 3) carries exactly one always-visible star.
    const stars = within(listbox).getAllByRole('button', { name: /favorites$/ })
    expect(stars).toHaveLength(SECTIONED_COUNT)
  })
})
