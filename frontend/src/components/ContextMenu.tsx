import { useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  x: number
  y: number
  children: React.ReactNode
}

export default function ContextMenu({ x, y, children }: Props) {
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: y, left: x })

  useLayoutEffect(() => {
    if (!menuRef.current) return
    const rect = menuRef.current.getBoundingClientRect()
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
    setPos({ top, left })
  }, [x, y])

  return createPortal(
    <div
      ref={menuRef}
      className="fixed bg-gray-900 border border-gray-700 shadow-lg rounded-md py-1 z-50 min-w-[160px] max-w-[200px]"
      style={{ top: pos.top, left: pos.left }}
      onClick={e => e.stopPropagation()}
      onContextMenu={e => e.preventDefault()}
    >
      {children}
    </div>,
    document.body
  )
}
