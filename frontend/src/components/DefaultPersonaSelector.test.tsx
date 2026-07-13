import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
import { apiFetch } from '../lib/api'
// RED: DefaultPersonaSelector is authored in 17-09 — this import is unresolvable until then, so the
// whole suite fails at collection (cannot-resolve './DefaultPersonaSelector'). Intended RED signal.
import DefaultPersonaSelector from './DefaultPersonaSelector'

// DefaultPersonaSelector self-PUTs /api/preferences {default_persona} (fire-and-forget, mirroring
// DefaultModelSelector's self-contained PUT) — mock the api boundary and assert on it.
//
// DELIBERATELY NO useKeyStatus / useKeyGate mock (contrast DefaultModelSelector.test.tsx L16-21 and
// its keyless-gate test): unlike the model default, a keyless user MUST be able to set a default
// persona — persona has no key/cost surface, so there is no gate to drive.
vi.mock('../lib/api', () => makeApiMock())

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

const PERSONAS = [
  { id: 'board_game_expert', label: 'Board-Game Expert', is_default: true },
  { id: 'general_assistant', label: 'General Assistant', is_default: false },
]

describe('DefaultPersonaSelector (PERS-04 — PUT /api/preferences {default_persona})', () => {
  beforeEach(() => {
    mockApiFetch.mockReset()
    mockApiFetch.mockResolvedValue(PERSONAS)
  })

  it('selecting a persona PUTs /api/preferences with {default_persona: id}', async () => {
    const user = userEvent.setup()
    renderWithProviders(<DefaultPersonaSelector value={null} personas={PERSONAS} />)

    await user.click(screen.getByRole('button', { name: /select a persona|default persona/i }))
    await user.click(screen.getByRole('option', { name: /general assistant/i }))

    const putCall = mockApiFetch.mock.calls.find(
      ([path, opts]) => path === '/api/preferences' && opts?.method === 'PUT'
    )
    expect(putCall).toBeTruthy()
    // PERS-04: the exact request body — {default_persona: <id>}, nothing else.
    expect(JSON.parse(putCall![1].body)).toEqual({ default_persona: 'general_assistant' })
  })

  it('invokes onChange with the selected id so the parent can hydrate its state', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(
      <DefaultPersonaSelector value={null} personas={PERSONAS} onChange={onChange} />
    )

    await user.click(screen.getByRole('button', { name: /select a persona|default persona/i }))
    await user.click(screen.getByRole('option', { name: /board-game expert/i }))

    expect(onChange).toHaveBeenCalledWith('board_game_expert')
  })

  it('a keyless user can set a default persona (no gate)', async () => {
    const user = userEvent.setup()
    // No useKeyStatus mock: demo OFF / no key must NOT block a persona default (no key/cost surface).
    renderWithProviders(<DefaultPersonaSelector value={null} personas={PERSONAS} />)

    await user.click(screen.getByRole('button', { name: /select a persona|default persona/i }))
    await user.click(screen.getByRole('option', { name: /general assistant/i }))

    // The persist still fires...
    const putCall = mockApiFetch.mock.calls.find(
      ([path, opts]) => path === '/api/preferences' && opts?.method === 'PUT'
    )
    expect(putCall).toBeTruthy()
    // ...and the key-gate modal never appears for a persona default.
    expect(screen.queryByText('Connect OpenRouter?')).not.toBeInTheDocument()
  })
})
