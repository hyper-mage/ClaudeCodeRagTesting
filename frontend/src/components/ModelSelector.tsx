import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { apiFetch } from '../lib/api'

/**
 * ModelResponse — mirrors the Phase-12 GET /api/models row (render-ready). The frontend NEVER
 * recomputes is_free; it renders the precomputed fields verbatim.
 */
export interface ModelResponse {
  id: string
  name: string | null
  context_length: number | null
  is_free: boolean
  price_per_mtok_prompt: number | null
  price_per_mtok_completion: number | null
  popularity_rank?: number | null
  pricing?: Record<string, unknown>
}

interface ExtraOption {
  label: string
  value: null
}

interface Props {
  /** The currently-selected model id, or null (no selection / following default). */
  value: string | null
  /** Called with the chosen model id, or null for the extraOption clear row. */
  onSelect: (modelId: string | null) => void
  /** Trigger label shown when nothing matches `value` (e.g. "Default model" / "Select a model"). */
  placeholder?: string
  /** Optional leading row (e.g. "Use my default model" → clears the pin). Plan 06 supplies it. */
  extraOption?: ExtraOption
  /** Optional pre-fetched catalog; when omitted the component fetches GET /api/models on first open. */
  models?: ModelResponse[]
}

type LoadState = 'idle' | 'loading' | 'loaded' | 'error'

// LOCKED copy (UI-SPEC § Copywriting). Do not paraphrase.
const COPY = {
  loading: 'Loading models…',
  error: "Couldn't load models. Tap to retry.",
  free: 'Free',
} as const

/** Format the paid price hint: "In ${p} · Out ${c}/M tokens" when both present, else the single figure. */
function priceHint(prompt: number | null, completion: number | null): string | null {
  if (prompt != null && completion != null) {
    return `In $${prompt} · Out $${completion}/M tokens`
  }
  const single = prompt ?? completion
  if (single != null) return `$${single}/M tokens`
  return null
}

/** "{context_length/1000}K context", or null when context_length is null (line omitted). */
function contextHint(contextLength: number | null): string | null {
  if (contextLength == null) return null
  return `${Math.round(contextLength / 1000)}K context`
}

/**
 * ModelSelector — hand-rolled accessible listbox dropdown over the GET /api/models catalog
 * (no shadcn — shadcn is gated to Phase 15 per STATE.md). Presentation + a11y only: the caller
 * supplies onSelect (Plan 06 wires the PATCH/PUT). Theme-aware via the core-surface tokens so it
 * reads correctly in both light and dark. The trigger is NEUTRAL surface, not the blue-600 accent.
 *
 * LOCKED a11y contract (UI-SPEC § Components): aria-haspopup="listbox" + aria-expanded on the
 * trigger; role="listbox"/"option" on the list; Enter/Space opens; arrow-nav; Enter selects; Esc
 * closes and returns focus to the trigger; outside-click closes; focus trap while open; ≥44px rows;
 * selected row carries a blue-600 check/left-border.
 */
export default function ModelSelector({ value, onSelect, placeholder, extraOption, models }: Props) {
  const [open, setOpen] = useState(false)
  const [fetched, setFetched] = useState<ModelResponse[] | null>(models ?? null)
  const [state, setState] = useState<LoadState>(models ? 'loaded' : 'idle')
  const [activeIndex, setActiveIndex] = useState(0)

  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listboxId = useId()

  const rows: ModelResponse[] = models ?? fetched ?? []

  // Build the flat option list: optional extraOption first (value null), then the catalog rows.
  const options: { key: string; value: string | null; label: string; model: ModelResponse | null }[] =
    [
      ...(extraOption ? [{ key: '__extra__', value: extraOption.value, label: extraOption.label, model: null }] : []),
      ...rows.map(m => ({ key: m.id, value: m.id, label: m.name ?? m.id, model: m })),
    ]

  const loadModels = useCallback(async () => {
    if (models) return // caller-supplied list — never fetch
    setState('loading')
    try {
      const data = (await apiFetch('/api/models')) as ModelResponse[]
      setFetched(data ?? [])
      setState('loaded')
    } catch {
      // House style: never surface the caught error / HTTP code in copy.
      setState('error')
    }
  }, [models])

  const openMenu = useCallback(() => {
    setOpen(true)
    if (state === 'idle') void loadModels()
  }, [state, loadModels])

  const closeMenu = useCallback((returnFocus = true) => {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }, [])

  // A preselected value needs its display name resolved for the (closed) trigger,
  // so fetch the catalog on mount when a value is set and no list was supplied.
  // When value is null we stay lazy (fetch on open) so the trigger just shows the placeholder.
  useEffect(() => {
    if (value != null && !models && state === 'idle') void loadModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, models])

  // Seed the active row to the selected one (or 0) each time the menu opens with rows present.
  useEffect(() => {
    if (!open) return
    const idx = options.findIndex(o => o.value === value)
    setActiveIndex(idx >= 0 ? idx : 0)
    // Only re-seed on open / option count changes, not on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, options.length])

  // Outside-click closes (mousedown so it fires before a focus shift).
  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        closeMenu(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [open, closeMenu])

  // Move focus into the list when it opens with options, so arrow-nav + focus-trap work.
  useEffect(() => {
    if (open && options.length > 0) {
      listRef.current?.focus()
    }
     
  }, [open, options.length])

  function selectOption(idx: number) {
    const opt = options[idx]
    if (!opt) return
    onSelect(opt.value)
    closeMenu()
  }

  function onTriggerKeyDown(e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
      e.preventDefault()
      openMenu()
    }
  }

  function onListKeyDown(e: React.KeyboardEvent<HTMLUListElement>) {
    switch (e.key) {
      case 'Escape':
        e.preventDefault()
        closeMenu()
        break
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex(i => Math.min(i + 1, options.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex(i => Math.max(i - 1, 0))
        break
      case 'Home':
        e.preventDefault()
        setActiveIndex(0)
        break
      case 'End':
        e.preventDefault()
        setActiveIndex(options.length - 1)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        selectOption(activeIndex)
        break
      case 'Tab':
        // Focus trap: keep focus in the list while open.
        e.preventDefault()
        break
      default:
        break
    }
  }

  // Trigger label: the selected model's display name, else the placeholder.
  const selectedModel = rows.find(m => m.id === value) ?? null
  const triggerLabel = selectedModel ? (selectedModel.name ?? selectedModel.id) : (placeholder ?? 'Select a model')

  return (
    <div ref={rootRef} className="relative w-full">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        onClick={() => (open ? closeMenu(false) : openMenu())}
        onKeyDown={onTriggerKeyDown}
        className="flex min-h-11 w-full items-center justify-between gap-2 rounded border border-gray-300 bg-gray-100 px-3 py-2 text-sm font-semibold text-gray-900 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-700 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700"
      >
        <span className="truncate">{triggerLabel}</span>
        <ChevronDown size={16} className="shrink-0 text-gray-500 dark:text-gray-400" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded border border-gray-300 bg-gray-50 shadow-lg dark:border-gray-700 dark:bg-gray-900">
          {state === 'loading' && (
            <p className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">{COPY.loading}</p>
          )}

          {state === 'error' && (
            <button
              type="button"
              onClick={() => void loadModels()}
              className="block w-full px-3 py-2 text-left text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
            >
              {COPY.error}
            </button>
          )}

          {state === 'loaded' && (
            <ul
              ref={listRef}
              id={listboxId}
              role="listbox"
              tabIndex={-1}
              aria-label="Models"
              onKeyDown={onListKeyDown}
              className="max-h-72 overflow-y-auto focus:outline-none"
            >
              {options.map((opt, idx) => {
                const isSelected = opt.value === value
                const isActive = idx === activeIndex
                const hint = opt.model ? null : undefined // placeholder for extraOption (no hint)
                return (
                  <li
                    key={opt.key}
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => selectOption(idx)}
                    className={`relative flex min-h-11 cursor-pointer flex-col justify-center gap-0.5 py-2 pl-6 pr-3 text-sm ${
                      isActive
                        ? 'bg-gray-100 dark:bg-gray-800'
                        : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                  >
                    {isSelected && (
                      <Check
                        size={16}
                        className="absolute left-1.5 top-1/2 -translate-y-1/2 text-blue-600"
                        aria-hidden="true"
                      />
                    )}
                    <span className="font-normal text-gray-900 dark:text-white">{opt.label}</span>
                    {opt.model && (
                      <ModelHint model={opt.model} />
                    )}
                    {hint === null && null}
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

/** Caption sub-line: the Free tag OR the price hint, plus the context line when present. */
function ModelHint({ model }: { model: ModelResponse }) {
  const price = priceHint(model.price_per_mtok_prompt, model.price_per_mtok_completion)
  const context = contextHint(model.context_length)
  return (
    <span className="flex flex-wrap items-center gap-x-2 text-xs text-gray-600 dark:text-gray-400">
      {model.is_free ? (
        <span className="rounded bg-gray-200 px-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200">
          {COPY.free}
        </span>
      ) : (
        price && <span>{price}</span>
      )}
      {context && <span>{context}</span>}
    </span>
  )
}
