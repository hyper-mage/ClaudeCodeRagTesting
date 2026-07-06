import ModelSelector, { type ModelResponse } from './ModelSelector'
import { apiFetch } from '../lib/api'
import { useKeyGate } from '../hooks/useKeyGate'

// LOCKED copy (UI-SPEC § Copywriting Contract). Do not paraphrase.
const COPY = {
  heading: 'Default model',
  helper: 'New chats use this model unless you pick a different one for a chat.',
} as const

interface Props {
  /** The user's current default model id, or null when none is set. */
  value: string | null
  /** Optional notify-up so the parent (ChatPage) can mirror the new default in its own state. */
  onChange?: (modelId: string) => void
  /** Optional pre-fetched catalog forwarded to ModelSelector (avoids a duplicate /api/models fetch). */
  models?: ModelResponse[]
}

/**
 * DefaultModelSelector — the user's default-model control (D-04). A LOCKED heading + helper line
 * above a ModelSelector. On select it self-PUTs /api/preferences {default_model} (fire-and-forget,
 * mirroring ThemeToggle's self-contained PUT) and notifies the parent via onChange so the inline
 * value stays in sync without a refetch.
 *
 * Temporary inline placement (sidebar footer + mobile drawer) — Phase 14 moves it to the settings
 * page, so it is kept visually quiet and self-contained. Clearing the default is NOT a Phase-13
 * action (the default is always a concrete model id once set), so no extraOption is wired here.
 */
export default function DefaultModelSelector({ value, onChange, models }: Props) {
  // Shared key gate (KEY-05, D-04): the gate decision runs BEFORE onChange/PUT (Pitfall 7) — a
  // keyless gated pick leaves the trigger on the prior model and fires NO PUT. The former
  // handleSelect body is now the gate's onApply, reachable ONLY when the gate applies.
  const { guardedSelect, gateModal } = useKeyGate({
    kind: 'default',
    models: models ?? [],
    onApply: (modelId: string | null) => {
      // The default-model control never offers a clear row, so modelId is always a concrete id
      // here; guard defensively so a null can never PUT {default_model: null}.
      if (modelId == null) return
      onChange?.(modelId)
      // Best-effort server persist; never block the UI and never revert on failure (house style).
      void apiFetch('/api/preferences', {
        method: 'PUT',
        body: JSON.stringify({ default_model: modelId }),
      }).catch(() => {})
    },
  })

  return (
    <div className="flex flex-col gap-1.5">
      <div>
        <h3 className="text-base font-semibold text-gray-900 dark:text-white">{COPY.heading}</h3>
        <p className="text-xs text-gray-600 dark:text-gray-400">{COPY.helper}</p>
      </div>
      <ModelSelector value={value} onSelect={guardedSelect} placeholder="Select a model" models={models} />
      {gateModal}
    </div>
  )
}
