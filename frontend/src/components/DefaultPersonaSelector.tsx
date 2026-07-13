import PersonaSelector, { type PersonaOption } from './PersonaSelector'
import { apiFetch } from '../lib/api'

// LOCKED copy — the persona equivalent of DefaultModelSelector's heading + helper. Do not paraphrase.
const COPY = {
  heading: 'Default persona',
  helper: 'New chats use this persona unless you pick a different one for a chat.',
} as const

interface Props {
  /** The user's current default persona id, or null when none is set. */
  value: string | null
  /** Optional notify-up so the parent can mirror the new default in its own state without a refetch. */
  onChange?: (personaId: string) => void
  /** Server-fetched catalog forwarded to PersonaSelector. NEVER hardcoded (D-07). */
  personas?: PersonaOption[]
}

/**
 * DefaultPersonaSelector — the settings default-persona control (PERS-04). A LOCKED heading +
 * helper line above a PersonaSelector. On select it self-PUTs /api/preferences {default_persona}
 * (fire-and-forget, mirroring DefaultModelSelector's self-contained PUT) and notifies the parent
 * via onChange so the value stays in sync without a refetch.
 *
 * Unlike the model default, there is NO key gate here — persona carries no key/cost surface, so a
 * keyless user MUST be able to set a default persona (the 17-03 test asserts it). Persistence is
 * best-effort: the UI is never blocked and never reverts on failure (house style).
 */
export default function DefaultPersonaSelector({ value, onChange, personas }: Props) {
  function onSelect(personaId: string) {
    // Optimistic notify-up first...
    onChange?.(personaId)
    // ...then a best-effort server persist. Exactly one PUT per selection, body = {default_persona}.
    void apiFetch('/api/preferences', {
      method: 'PUT',
      body: JSON.stringify({ default_persona: personaId }),
    }).catch(() => {})
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">{COPY.heading}</h3>
        <p className="text-xs text-gray-600 dark:text-gray-400">{COPY.helper}</p>
      </div>
      <PersonaSelector
        value={value}
        onSelect={onSelect}
        personas={personas}
        placeholder="Select a persona"
      />
    </div>
  )
}
