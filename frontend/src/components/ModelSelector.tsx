import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown, Search } from 'lucide-react'
import { apiFetch } from '../lib/api'
import { matchModel } from '../lib/fuzzy'

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
  searchPlaceholder: 'Search models…',
  noMatch: 'No models match your search.',
} as const

/** The applied search query trails the input value by this much (LOCKED). */
const SEARCH_DEBOUNCE_MS = 150

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
 * ModelSelector — hand-rolled accessible searchable combobox over the GET /api/models catalog
 * (no shadcn — `Tool: none` per the approved Phase-15 UI-SPEC). Presentation + a11y only: the
 * caller supplies onSelect. Theme-aware via the core-surface tokens so it reads correctly in
 * both light and dark. The trigger is NEUTRAL surface, not the blue-600 accent.
 *
 * Sections (D-06): Favorites → Popular → All models, with non-interactive role="presentation"
 * headers. Favorites is hidden entirely when empty (LOCKED — no empty-state hint). Popular
 * preserves popularity_rank order; All models is the complete catalog alphabetical by label.
 * Duplication across sections is deliberate — keys and option DOM ids are section-scoped.
 *
 * Search (D-08, MODEL-01): a pinned input atop the open panel filters the catalog fuzzily
 * (lib/fuzzy matchModel over id AND name, 150ms debounce). While the applied query is non-empty
 * the sections collapse into ONE flat score-ranked list — no headers, extraOption hidden,
 * non-matches removed.
 *
 * LOCKED a11y contract (UI-SPEC § Interaction Contract — combobox-with-list-popup, supersedes
 * the listbox-focus model): trigger keeps aria-haspopup="listbox"/aria-expanded/aria-controls
 * and Enter/Space/ArrowDown opens; on open, focus moves to the SEARCH INPUT which carries
 * aria-autocomplete="list", aria-controls={listboxId} and aria-activedescendant of the active
 * navigable row; ArrowUp/Down skip headers structurally; Enter selects; Esc closes back to the
 * trigger; Tab stays trapped; Home/End keep native caret behavior; outside-click closes;
 * ≥44px rows; selected row carries a blue-600 check in EVERY duplicate instance.
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
  // Search: the input value is live; the APPLIED query trails it by 150ms (LOCKED debounce).
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  // Favorites are read-only this plan (render the section): the star toggle + PUT land in
  // plan 15-06. Seeded once at mount from GET /api/preferences (favorite_models ?? []).
  const [favorites, setFavorites] = useState<string[]>([])
  // Open upward when the trigger sits too low for the panel to fit below (e.g. the
  // default-model control in the sidebar footer) — otherwise the list spills off-screen.
  const [dropUp, setDropUp] = useState(false)

  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listboxId = useId()

  const rows: ModelResponse[] = suppliedModels ?? fetched ?? []
  const searching = debouncedQuery !== ''

  // Build the two derived structures: a flat NAVIGABLE array of selectable options only
  // (activeIndex indexes this — headers are never navigable) and a RENDER row list interleaving
  // header rows and option rows. Sections mode (D-06): extraOption first (outside sections),
  // then Favorites → Popular → All models. Search mode (D-08): ONE flat score-ranked list —
  // no headers, extraOption hidden, non-matches removed.
  const sortByLabel = (a: ModelResponse, b: ModelResponse) =>
    (a.name ?? a.id).localeCompare(b.name ?? b.id)

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

  if (searching) {
    const scored = rows
      .map(m => ({ m, score: matchModel(debouncedQuery, m.id, m.name) }))
      .filter((x): x is { m: ModelResponse; score: number } => x.score !== null)
      // Score desc; ties alphabetical by label (the scorer bakes in no tie-breaking).
      .sort((a, b) => b.score - a.score || sortByLabel(a.m, b.m))
    scored.forEach((x, i) => pushOption('search', i, x.m.id, x.m.name ?? x.m.id, x.m))
  } else {
    const favoriteRows = rows.filter(m => favorites.includes(m.id)).sort(sortByLabel)
    const popularRows = rows
      .filter(m => m.popularity_rank != null)
      .sort((a, b) => (a.popularity_rank ?? 0) - (b.popularity_rank ?? 0))
    const allRows = [...rows].sort(sortByLabel)

    if (extraOption) pushOption('extra', 0, extraOption.value, extraOption.label, null)
    pushSection('fav', COPY.favorites, favoriteRows)
    pushSection('pop', COPY.popular, popularRows)
    pushSection('all', COPY.allModels, allRows)
  }

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
    // Each open starts with a fresh query (cmdk convention) — both the live value and the
    // applied query, so a stale filter can never flash while the debounce catches up.
    setQuery('')
    setDebouncedQuery('')
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
    const PANEL_MAX = 370 // ~ max-h-72 list + h-11 search row + chrome
    const spaceBelow = window.innerHeight - rect.bottom
    const spaceAbove = rect.top
    setDropUp(spaceBelow < PANEL_MAX && spaceAbove > spaceBelow)
  }, [open])

  // Apply the query 150ms behind the input (LOCKED debounce). The same tick resets the
  // active row to the first navigable option — and implicitly clamps when the filtered
  // list shrinks (Pitfall 2).
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedQuery(query)
      setActiveIndex(0)
    }, SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(t)
  }, [query])

  // Seed the active row to the selected option's NAVIGABLE index (else 0) on OPEN only —
  // plus once more when the lazy fetch lands (state flips to 'loaded' while open).
  // Deliberately NOT keyed on option count: live filtering must never re-seed per
  // keystroke (Pitfall 2).
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

  // LOCKED focus model (combobox-with-list-popup): on open, focus moves to the search
  // input — not the list. Arrow-nav/Enter/Esc are handled on the input's keydown.
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

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

  // Keyboard machinery lives on the search input (LOCKED contract): ArrowUp/Down move over
  // the NAVIGABLE array (headers skipped structurally, wrapping not required); Enter selects;
  // Esc closes back to the trigger; Tab stays trapped; printable keys fall through to the
  // input natively; Home/End keep the native caret behavior (no list jump).
  // Shift+Enter is deliberately NOT implemented here — it needs the favorite toggle (plan 15-06).
  function onInputKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
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
      case 'Enter':
        e.preventDefault()
        if (!e.shiftKey) selectOption(activeIndex)
        break
      case 'Tab':
        // Focus trap: keep focus inside the open panel.
        e.preventDefault()
        break
      default:
        break
    }
  }

  // Trigger label: the selected model's display name, else the placeholder.
  const selectedModel = rows.find(m => m.id === value) ?? null
  const triggerLabel = selectedModel ? (selectedModel.name ?? selectedModel.id) : (placeholder ?? 'Select a model')

  // The section-scoped DOM id of the active navigable row (aria-activedescendant wiring).
  const activeOptionId = navigable[activeIndex]?.id

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
          {/* Pinned search row — first element inside the open panel, above everything.
              No focus ring inside the panel (cmdk convention): the panel border frames it. */}
          <div className="flex h-11 w-full items-center border-b border-gray-300 bg-gray-50 dark:border-gray-700 dark:bg-gray-900">
            <Search size={14} className="ml-3 shrink-0 text-gray-500 dark:text-gray-400" aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={onInputKeyDown}
              placeholder={COPY.searchPlaceholder}
              aria-autocomplete="list"
              aria-controls={listboxId}
              aria-activedescendant={activeOptionId}
              className="h-full w-full bg-transparent px-3 text-sm text-gray-900 placeholder-gray-500 focus:outline-none dark:text-white dark:placeholder-gray-400"
            />
          </div>

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
            searching ? (
              <p className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{COPY.noMatch}</p>
            ) : (
              <p className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400">No models available.</p>
            )
          )}

          {state === 'loaded' && navigable.length > 0 && (
            <ul
              id={listboxId}
              role="listbox"
              aria-label="Models"
              className="max-h-72 overflow-y-auto"
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
