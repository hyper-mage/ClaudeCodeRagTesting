import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'

/**
 * PersonaOption — a persona catalog row as served by GET /api/personas. Only the render-safe
 * fields cross the wire (id/label/is_default); the secret voice_block is withheld server-side
 * (A5/T-17-06), so it is deliberately absent from this shape.
 */
export interface PersonaOption {
  id: string
  label: string
  is_default: boolean
}

interface Props {
  /** The currently-selected persona id, or null (no selection). */
  value: string | null
  /** Called with the chosen persona id on click. The parent (ChatPage) owns any PATCH persistence. */
  onSelect: (personaId: string) => void
  /** Server-fetched catalog (GET /api/personas). NEVER hardcoded (D-07) — the parent supplies it. */
  personas?: PersonaOption[]
  /** Trigger label shown when nothing matches `value`. */
  placeholder?: string
}

/**
 * PersonaSelector — a lightweight persona dropdown over the (server-fetched) persona catalog.
 *
 * Deliberately NOT ModelSelector: persona carries NO key/cost/demo surface, so there is no key
 * gate here (PERS-01 — a keyless user can pick a persona), and the 560-line ModelResponse /
 * search / favorites machinery does not fit. The component is presentation-only: it reports the
 * chosen id via onSelect and lets the parent own persistence. Picker-only attribution (D-12) —
 * it renders no per-message persona badge.
 *
 * The options are rendered from the `personas` prop verbatim (fetched by the parent from
 * GET /api/personas) — the list is never hardcoded in the component.
 */
export default function PersonaSelector({ value, onSelect, personas, placeholder }: Props) {
  const options = personas ?? []
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listboxId = useId()

  const closeMenu = useCallback((returnFocus = true) => {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }, [])

  // Outside-click closes (mousedown so it fires before a focus shift).
  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [open])

  function selectOption(personaId: string) {
    // No gate, no modal — a click always reports the pick straight up (PERS-01).
    onSelect(personaId)
    closeMenu()
  }

  // Trigger label: the selected persona's label, else the placeholder.
  const selected = options.find(p => p.id === value) ?? null
  const triggerLabel = selected ? selected.label : (placeholder ?? 'Select a persona')

  return (
    <div ref={rootRef} className="relative w-full">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        onClick={() => (open ? closeMenu(false) : setOpen(true))}
        className="flex min-h-11 w-full items-center justify-between gap-2 rounded border border-gray-300 bg-gray-100 px-3 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDown size={16} className="shrink-0 text-gray-500 dark:text-gray-400" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-full overflow-hidden rounded border border-gray-300 bg-gray-50 shadow-lg dark:border-gray-700 dark:bg-gray-900">
          {options.length === 0 ? (
            <p className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">No personas available.</p>
          ) : (
            <ul id={listboxId} role="listbox" aria-label="Personas" className="max-h-72 overflow-y-auto">
              {options.map(p => {
                const isSelected = p.id === value
                return (
                  <li
                    key={p.id}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => selectOption(p.id)}
                    className={`relative flex min-h-11 cursor-pointer items-center py-2 pl-6 pr-3 text-sm ${
                      isSelected
                        ? 'bg-gray-100 dark:bg-gray-800'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                    } text-gray-900 dark:text-white`}
                  >
                    {isSelected && (
                      <Check
                        size={16}
                        className="absolute left-1.5 top-1/2 -translate-y-1/2 text-blue-600"
                        aria-hidden="true"
                      />
                    )}
                    <span className="font-normal">{p.label}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
