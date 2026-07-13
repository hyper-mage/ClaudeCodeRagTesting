import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, makeApiMock } from '../test/utils'
// RED: PersonaSelector is authored in 17-09 — this import is unresolvable until then, so the whole
// suite fails at collection (cannot-resolve './PersonaSelector'). That is the intended RED signal.
import PersonaSelector from './PersonaSelector'

// PersonaSelector is a lightweight dropdown over the (server-fetched) persona catalog — it has NO
// key/cost/demo surface and the parent (ChatPage) owns the PATCH, so the component never writes to
// the api itself. We still mock the api boundary so the suite stays network-free even if a future
// variant lazy-fetches the catalog.
//
// DELIBERATELY NO useKeyStatus / useKeyGate mock (contrast DefaultModelSelector.test.tsx L16-21):
// a keyless user MUST be able to pick a persona — there is no gate to drive.
vi.mock('../lib/api', () => makeApiMock())

const PERSONAS = [
  { id: 'board_game_expert', label: 'Board-Game Expert', is_default: true },
  { id: 'general_assistant', label: 'General Assistant', is_default: false },
]

describe('PersonaSelector (PERS-01 — onSelect(personaId), no key gate)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the persona options', async () => {
    const user = userEvent.setup()
    renderWithProviders(<PersonaSelector value={null} personas={PERSONAS} onSelect={vi.fn()} />)

    // Open the dropdown from its (placeholder) trigger, then both labels appear as options.
    await user.click(screen.getByRole('button', { name: /select a persona/i }))

    expect(screen.getByRole('option', { name: /board-game expert/i })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /general assistant/i })).toBeInTheDocument()
  })

  it('calls onSelect with the persona id on click', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    renderWithProviders(<PersonaSelector value={null} personas={PERSONAS} onSelect={onSelect} />)

    await user.click(screen.getByRole('button', { name: /select a persona/i }))
    await user.click(screen.getByRole('option', { name: /general assistant/i }))

    // PERS-01: the chat picker reports the chosen id up; the parent owns the PATCH.
    expect(onSelect).toHaveBeenCalledWith('general_assistant')
  })

  it('reflects the current value on the trigger', () => {
    renderWithProviders(
      <PersonaSelector value="general_assistant" personas={PERSONAS} onSelect={vi.fn()} />
    )
    // The (closed) trigger shows the selected persona's label, not the placeholder.
    expect(screen.getByRole('button', { name: /general assistant/i })).toBeInTheDocument()
  })

  it('does NOT gate a keyless pick (no modal, no gate)', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    // No useKeyStatus mock present — a keyless user picking a persona must flow straight through.
    renderWithProviders(<PersonaSelector value={null} personas={PERSONAS} onSelect={onSelect} />)

    await user.click(screen.getByRole('button', { name: /select a persona/i }))
    await user.click(screen.getByRole('option', { name: /general assistant/i }))

    // The pick lands with no interception...
    expect(onSelect).toHaveBeenCalledWith('general_assistant')
    // ...and the key-gate modal never appears (persona has no key/cost surface).
    expect(screen.queryByText('Connect OpenRouter?')).not.toBeInTheDocument()
  })
})
