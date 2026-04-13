import { useCallback } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  x: number
  y: number
  children: React.ReactNode
}

export default function ContextMenu({ x, y, children }: Props) {
  // Ref callback measures menu after mount and adjusts position in-place,
  // avoiding setState-in-effect (react-hooks/set-state-in-effect).
  const measureRef = useCallback(
    (el: HTMLDivElement | null) => {
      if (!el) return
      const rect = el.getBoundingClientRect()
      const vw = window.innerWidth
      const vh = window.innerHeight
      let top = y
      let left = x
      if (left + rect.width > vw) {
        left = Math.max(0, x - rect.width)
      }
      if (top + rect.height > vh) {
        top = Math.max(0, y - rect.height)
      }
      if (top !== y) el.style.top = `${top}px`
      if (left !== x) el.style.left = `${left}px`
    },
    [x, y]
  )

  return createPortal(
    <div
      ref={measureRef}
      className="fixed bg-gray-900 border border-gray-700 shadow-lg rounded-md py-1 z-50 min-w-[160px] max-w-[200px]"
      style={{ top: y, left: x }}
      onClick={e => e.stopPropagation()}
      onContextMenu={e => e.preventDefault()}
    >
      {children}
    </div>,
    document.body
  )
}
