import { useCallback, useMemo, useState } from 'react'

/**
 * Selection hook with shift-click range support.
 *
 * - `toggle(id, shiftKey)`: single-toggle when no shift, otherwise range-select from
 *   the last-clicked id to the current id (inclusive).
 * - `selectAll()`: select every item in the provided list.
 * - `clearSelection()`: reset selection and last-clicked.
 *
 * The returned `selected` is a derived Set filtered against `items`, so ids
 * that no longer exist in the current items list are pruned from consumer view
 * without scheduling state updates.
 */
export function useSelection(items: { id: string }[]) {
  const [selectedRaw, setSelected] = useState<Set<string>>(new Set())
  const [lastClicked, setLastClicked] = useState<string | null>(null)

  // Filter out ids that no longer exist in the items list (derived, not stored).
  const selected = useMemo(() => {
    if (selectedRaw.size === 0) return selectedRaw
    const ids = new Set(items.map(i => i.id))
    const next = new Set<string>()
    for (const id of selectedRaw) {
      if (ids.has(id)) next.add(id)
    }
    return next
  }, [selectedRaw, items])

  const toggle = useCallback(
    (id: string, shiftKey: boolean) => {
      setSelected(prev => {
        const next = new Set(prev)
        if (shiftKey && lastClicked) {
          const ids = items.map(i => i.id)
          const start = ids.indexOf(lastClicked)
          const end = ids.indexOf(id)
          if (start !== -1 && end !== -1) {
            const [lo, hi] = start < end ? [start, end] : [end, start]
            for (let i = lo; i <= hi; i++) {
              next.add(ids[i])
            }
          } else {
            if (next.has(id)) next.delete(id)
            else next.add(id)
          }
        } else {
          if (next.has(id)) next.delete(id)
          else next.add(id)
        }
        return next
      })
      setLastClicked(id)
    },
    [items, lastClicked]
  )

  const selectAll = useCallback(() => {
    setSelected(new Set(items.map(i => i.id)))
  }, [items])

  const clearSelection = useCallback(() => {
    setSelected(new Set())
    setLastClicked(null)
  }, [])

  return { selected, toggle, selectAll, clearSelection }
}
