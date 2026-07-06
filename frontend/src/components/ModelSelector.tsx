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
  favorites: 'Favorites',
  popular: 'Popular',
  allModels: 'All models',
} as const

/** A selectable row — the flat NAVIGABLE array indexes these (headers are never navigable). */
interface NavOption {
  /** React key, section-scoped: a model may appear in up to 3 sections (Pitfall 1). */
  key: string
  /** Stable DOM id, section-scoped: `${listboxId}-opt-${section}-${index}`. */
  id: string
  value: string | null
  label: string
  model: ModelResponse | null
}

/** The RENDER list interleaves non-interactive section headers with option rows. */
type RenderRow =
  | { kind: 'header'; key: string; label: string }
  | { kind: 'option'; navIndex: number; opt: NavOption }

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
 * (no shadcn — `Tool: none` per the approved Phase-15 UI-SPEC). Presentation + a11y only: the
 * caller supplies onSelect. Theme-aware via the core-surface tokens so it reads correctly in
 * both light and dark. The trigger is NEUTRAL surface, not the blue-600 accent.
 *
 * Sections (D-06): Favorites → Popular → All models, with non-interactive role="presentation"
 * headers. Favorites is hidden entirely when empty (LOCKED — no empty-state hint). Popular
 * preserves popularity_rank order; All models is the complete catalog alphabetical by label.
 * Duplication across sections is deliberate — keys and option DOM ids are section-scoped.
 *
 * LOCKED a11y contract (UI-SPEC § Components): aria-haspopup="listbox" + aria-expanded on the
 * trigger; role="listbox"/"option" on the list; Enter/Space opens; arrow-nav skips headers;
 * Enter selects; Esc closes and returns focus to the trigger; outside-click closes; focus trap
 * while open; ≥44px rows; selected row carries a blue-600 check in EVERY duplicate instance.
 */
export default function ModelSelector({ value, onSelect, placeholder, extraOption, models }: Props) {
  // An empty array prop ([]) means "no catalog yet" — NOT an authoritative empty list — so the
  // selector still lazy-fetches on open. (An empty [] is truthy, which otherwise pinned 'loaded'
  // and silently showed an empty panel when the parent's one-time fetch hadn't populated.)
  const suppliedModels = models && models.length > 0 ? models : undefined

  const [open, setOpen] = useState(false)
  const [fetched, setFetched] = useState<ModelResponse[] | null>(suppliedModels ?? null)
  const [state, setState] = useState<LoadState>(suppliedModels ? 'loaded' : 'idle')
  const [activeIndex, setActiveIndex] = useState(0)
  // Favorites are read-only this plan (render the section): the star toggle + PUT land in
  // plan 15-06. Seeded once at mount from GET /api/preferences (favorite_models ?? []).
  const [favorites, setFavorites] = useState<string[]>([])
  // Open upward when the trigger sits too low for the panel to fit below (e.g. the
  // default-model control in the sidebar footer) — otherwise the list spills off-screen.
  const [dropUp, setDropUp] = useState(false)

  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listboxId = useId()

  const rows: ModelResponse[] = suppliedModels ?? fetched ?? []

  // Build the two derived structures (D-06): a flat NAVIGABLE array of selectable options only
  // (activeIndex indexes this — headers are never navigable) and a RENDER row list interleaving
  // header rows and option rows. The extraOption row renders first, outside all sections.
  const sortByLabel = (a: ModelResponse, b: ModelResponse) =>
    (a.name ?? a.id).localeCompare(b.name ?? b.id)
  const favoriteRows = rows.filter(m => favorites.includes(m.id)).sort(sortByLabel)
  const popularRows = rows
    .filter(m => m.popularity_rank != null)
    .sort((a, b) => (a.popularity_rank ?? 0) - (b.popularity_rank ?? 0))
  const allRows = [...rows].sort(sortByLabel)

  const navigable: NavOption[] = []
  const renderRows: RenderRow[] = []
  const pushOption = (
    section: string,
    index: number,
    value_: string | null,
    label: string,
    model: ModelResponse | null
  ) => {
    const opt: NavOption = {
      key: `${section}:${model ? model.id : '__extra__'}`,
      id: `${listboxId}-opt-${section}-${index}`,
      value: value_,
      label,
      model,
    }
    renderRows.push({ kind: 'option', navIndex: navigable.length, opt })
    navigable.push(opt)
  }
  const pushSection = (section: string, label: string, sectionRows: ModelResponse[]) => {
    // A section with no rows renders nothing — Favorites hidden-when-empty is LOCKED
    // (no empty-state hint), and a rowless header would be meaningless for the others.
    if (sectionRows.length === 0) return
    renderRows.push({ kind: 'header', key: `header:${section}`, label })
    sectionRows.forEach((m, i) => pushOption(section, i, m.id, m.name ?? m.id, m))
  }
  if (extraOption) pushOption('extra', 0, extraOption.value, extraOption.label, null)
  pushSection('fav', COPY.favorites, favoriteRows)
  pushSection('pop', COPY.popular, popularRows)
  pushSection('all', COPY.allModels, allRows)

  const loadModels = useCallback(async () => {
    if (suppliedModels) return // caller-supplied non-empty list — never fetch
    setState('loading')
    try {
      const data = (await apiFetch('/api/models')) as ModelResponse[]
      setFetched(data ?? [])
      setState('loaded')
    } catch {
      // House style: never surface the caught error / HTTP code in copy.
      setState('error')
    }
  }, [suppliedModels])

  const openMenu = useCallback(() => {
    setOpen(true)
    if (state === 'idle') void loadModels()
  }, [state, loadModels])

  const closeMenu = useCallback((returnFocus = true) => {
    setOpen(false)
    if (returnFocus) triggerRef.current?.focus()
  }, [])

  // Favorites read once at mount (MODEL-08 read side). Silent array-guarded fetch — a
  // malformed/unexpected payload must never poison the section build (house pattern,
  // ChatPage catalog fetch).
  useEffect(() => {
    let cancelled = false
    apiFetch('/api/preferences')
      .then((data: unknown) => {
        const fav = (data as { favorite_models?: unknown } | null)?.favorite_models
        if (!cancelled && Array.isArray(fav)) setFavorites(fav as string[])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  // A preselected value needs its display name resolved for the (closed) trigger,
  // so fetch the catalog on mount when a value is set and no list was supplied.
  // When value is null we stay lazy (fetch on open) so the trigger just shows the placeholder.
  useEffect(() => {
    if (value != null && !suppliedModels && state === 'idle') void loadModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, suppliedModels])

  // Decide drop direction when the menu opens: flip up if there isn't ~enough room below
  // the trigger and there's more room above. Re-measured each open (layout may have changed).
  useEffect(() => {
    if (!open) return
    const rect = triggerRef.current?.getBoundingClientRect()
    if (!rect) return
    const PANEL_MAX = 320 // ~ max-h-72 list + chrome
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    setDropUp(spaceBelow < PANEL_MAX && spaceAbove > spaceBelow)
  }, [open])

  // Seed the active row to the selected option's NAVIGABLE index (else 0) on OPEN only —
  // plus once more when the lazy fetch lands (state flips to 'loaded' while open).
  // Deliberately NOT keyed on option count: live filtering must never re-seed per
  // keystroke (Pitfall 2 groundwork — search lands next task).
  useEffect(() => {
    if (!open) return
    const idx = navigable.findIndex(o => o.value === value)
    setActiveIndex(idx >= 0 ? idx : 0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, state])

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
    if (open && navigable.length > 0) {
      listRef.current?.focus()
    }
  }, [open, navigable.length])

  function selectOption(idx: number) {
    const opt = navigable[idx]
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
        setActiveIndex(i => Math.min(i + 1, navigable.length - 1))
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
        setActiveIndex(navigable.length - 1)
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
        <div className={`absolute left-0 z-50 w-full overflow-hidden rounded border border-gray-300 bg-gray-50 shadow-lg dark:border-gray-700 dark:bg-gray-900 ${dropUp ? 'bottom-full mb-1' : 'top-full mt-1'}`}>
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

          {state === 'loaded' && navigable.length === 0 && (
            <p className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">No models available.</p>
          )}

          {state === 'loaded' && navigable.length > 0 && (
            <ul
              ref={listRef}
              id={listboxId}
              role="listbox"
              tabIndex={-1}
              aria-label="Models"
              onKeyDown={onListKeyDown}
              className="max-h-72 overflow-y-auto focus:outline-none"
            >
              {renderRows.map(row => {
                if (row.kind === 'header') {
                  return (
                    <li
                      key={row.key}
                      role="presentation"
                      className="px-3 pt-2 pb-1 text-xs font-semibold text-gray-600 dark:text-gray-400"
                    >
                      {row.label}
                    </li>
                  )
                }
                const { opt, navIndex } = row
                const isSelected = opt.value === value
                const isActive = navIndex === activeIndex
                return (
                  <li
                    key={opt.key}
                    id={opt.id}
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setActiveIndex(navIndex)}
                    onClick={() => selectOption(navIndex)}
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
                    {opt.model && <ModelHint model={opt.model} />}
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

/**
 * Caption sub-line: the Free tag OR the price hint, then the Popular chip (D-07 — renders in
 * EVERY section instance whenever popularity_rank is non-null, closing audit B-1 / MODEL-03),
 * then the context line when present. Order: [Free|price] [Popular] [context].
 */
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
      {model.popularity_rank != null && (
        <span className="rounded bg-gray-200 px-1 text-gray-700 dark:bg-gray-700 dark:text-gray-200">
          {COPY.popular}
        </span>
      )}
      {context && <span>{context}</span>}
    </span>
  )
}
