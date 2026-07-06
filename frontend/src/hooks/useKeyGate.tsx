import { useState, type ReactNode } from 'react'
import ConfirmDialog from '../components/ConfirmDialog'
import type { ModelResponse } from '../components/ModelSelector'
import { useKeyStatus } from './useKeyStatus'
import { startOpenRouterConnect } from '../lib/pkce'

/**
 * useKeyGate — the shared key gate (KEY-05, D-01/D-03/D-04). One hook wraps the apply path of
 * BOTH selection surfaces (thread-header ModelSelector via ChatPage, settings
 * DefaultModelSelector) so keyless UX never diverges between chat and settings.
 *
 * Locked decision table (UI-SPEC / RESEARCH Pattern 1) on select of model m:
 *   - connected → onApply immediately (existing PATCH/PUT path, no gate)
 *   - status null (unresolved) → onApply immediately (A3: no flash-gate; the server stays
 *     fail-closed, so an ungated pick still cannot spend)
 *   - keyless + demo ON + m.is_free === true → onApply immediately (D-03 free fast-path — demo
 *     turns run the picked free model)
 *   - keyless + demo ON + paid (or modelId absent from the catalog — unknown ≠ free) → gate
 *     modal with the paid body
 *   - keyless + demo OFF → gate modal with the demo-OFF body, regardless of free/paid
 *   - modelId null (extraOption clear row) → onApply immediately, NEVER gated (Open Q1:
 *     clearing a pin needs no key; send stays fail-closed server-side)
 *
 * [Connect] writes the or_pending_selection stash (consumed by the OAuthCallbackPage resume,
 * plan 15-03) immediately BEFORE launching the existing PKCE flow. [Cancel] closes with the
 * selection unchanged — the trigger keeps the prior model, no side effects.
 *
 * The gate is UX only — enforcement stays the server's fail-closed resolution (a bypassed gate
 * still cannot spend). is_free is read from the catalog row verbatim, never recomputed
 * client-side (Phase 12 contract).
 */

// LOCKED copy (UI-SPEC § Copywriting Contract). ${model} = display name (name ?? id), the ONLY
// interpolation — never a caught error, HTTP body, or sk-or- fragment (SEC-01, T-15-19).
const HEADING = 'Connect OpenRouter?'
const CONFIRM_LABEL = 'Connect'
const CANCEL_LABEL = 'Cancel'
const paidBody = (model: string) =>
  `Paid models need your OpenRouter key. Connect to continue — ${model} will be applied when you're back.`
const demoOffBody = (model: string) =>
  `Chatting needs your OpenRouter key. Connect to continue — ${model} will be applied when you're back.`

interface UseKeyGateOptions {
  /** Which surface the gate wraps: 'thread' (chat header) or 'default' (settings). */
  kind: 'thread' | 'default'
  /** The active thread id — carried in the stash for thread picks only. */
  threadId?: string | null
  /** The already-fetched catalog (RESEARCH Pattern 1 option (b) — the onSelect signature stays
   *  string | null; both callers hold the catalog). */
  models: ModelResponse[]
  /** The surface's real apply path (PATCH/PUT), invoked ONLY when the gate decides to apply. */
  onApply: (modelId: string | null) => void
}

interface PendingGate {
  modelId: string
  /** Display name (name ?? id) frozen at decision time — the only interpolation. */
  displayName: string
  body: 'paid' | 'demo_off'
}

export function useKeyGate({ kind, threadId, models, onApply }: UseKeyGateOptions): {
  guardedSelect: (modelId: string | null) => void
  gateModal: ReactNode
} {
  const { status } = useKeyStatus()
  const [pending, setPending] = useState<PendingGate | null>(null)

  const guardedSelect = (modelId: string | null) => {
    // extraOption clear row — never gated (Open Q1 resolution).
    if (modelId === null) {
      onApply(null)
      return
    }
    // Connected, or status not yet resolved (A3 — no flash-gate; server stays fail-closed).
    if (status === null || status.connected) {
      onApply(modelId)
      return
    }
    const demoOn = status.demo_enabled === true
    const row = models.find(m => m.id === modelId)
    // D-03 free fast-path: catalog-verified free row applies immediately under demo ON.
    // A modelId absent from the catalog is treated as paid (unknown ≠ free).
    if (demoOn && row?.is_free === true) {
      onApply(modelId)
      return
    }
    setPending({
      modelId,
      displayName: row?.name ?? modelId,
      body: demoOn ? 'paid' : 'demo_off',
    })
  }

  const handleConfirm = () => {
    if (!pending) return
    // Stash the pending selection FIRST (locked contract consumed by plan 15-03's resume),
    // then launch the existing PKCE flow as-is. sessionStorage only — tab-scoped, zero secret
    // material (T-15-20); useKeyGate is the stash's ONLY writer (T-15-18).
    sessionStorage.setItem(
      'or_pending_selection',
      JSON.stringify({
        kind,
        modelId: pending.modelId,
        ...(kind === 'thread' && threadId ? { threadId } : {}),
        returnTo: kind === 'thread' ? '/' : '/settings',
      })
    )
    void startOpenRouterConnect()
    setPending(null)
  }

  const gateModal: ReactNode = pending ? (
    <ConfirmDialog
      variant="primary"
      heading={HEADING}
      body={pending.body === 'paid' ? paidBody(pending.displayName) : demoOffBody(pending.displayName)}
      confirmLabel={CONFIRM_LABEL}
      cancelLabel={CANCEL_LABEL}
      onConfirm={handleConfirm}
      onCancel={() => setPending(null)}
    />
  ) : null

  return { guardedSelect, gateModal }
}
