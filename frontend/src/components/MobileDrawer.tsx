import { useEffect, useRef } from 'react'
import type { ReactNode, RefObject } from 'react'
import { X } from 'lucide-react'
import { useBodyScrollLock } from '../hooks/useBodyScrollLock'
import { useSwipeToClose } from '../hooks/useSwipeToClose'

interface Props {
  isOpen: boolean
  onClose: () => void
  children: ReactNode
  triggerRef: RefObject<HTMLButtonElement | null>
}

/**
 * MobileDrawer — left-edge slide-in panel with backdrop, dialog semantics,
 * focus trap, Escape-to-close, body-scroll-lock, and swipe-left-to-close.
 *
 * Locked structure per 06.1-UI-SPEC.md:
 *   - Backdrop: fixed inset-0 z-40 bg-black/60, fade 200ms.
 *   - Panel: fixed left-0 top-0 z-50 h-dvh w-72 bg-gray-900, slide 250ms.
 *
 * Renders both backdrop and panel unconditionally so CSS transitions fire on
 * every open/close cycle; visibility/interaction gated via classes.
 */
export default function MobileDrawer({ isOpen, onClose, children, triggerRef }: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const swipe = useSwipeToClose(onClose)

  useBodyScrollLock(isOpen)

  // Escape-to-close — only listen while open.
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, onClose])

  // Focus management — close X on open, hamburger on close.
  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus()
    } else {
      triggerRef.current?.focus()
    }
  }, [isOpen, triggerRef])

  // Focus trap — cycle Tab / Shift+Tab within panel.
  useEffect(() => {
    if (!isOpen) return
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const panel = panelRef.current
      if (!panel) return
      const focusable = panel.querySelectorAll<HTMLElement>(
        'button, [href], [tabindex]:not([tabindex="-1"])',
      )
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (e.shiftKey) {
        if (active === first || !panel.contains(active)) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (active === last || !panel.contains(active)) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    window.addEventListener('keydown', handleTab)
    return () => {
      window.removeEventListener('keydown', handleTab)
    }
  }, [isOpen])

  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/60 transition-opacity duration-200 ease-out ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      />
      <div
        id="mobile-drawer"
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation and threads"
        onPointerDown={swipe.onPointerDown}
        onPointerMove={swipe.onPointerMove}
        onPointerUp={swipe.onPointerUp}
        onPointerCancel={swipe.onPointerCancel}
        className={`fixed left-0 top-0 z-50 h-dvh w-72 bg-gray-900 border-r border-gray-800 flex flex-col transition-transform duration-250 ease-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between p-3 border-b border-gray-800">
          <h2 className="text-base font-semibold text-white">Menu</h2>
          <button
            ref={closeButtonRef}
            aria-label="Close menu"
            onClick={onClose}
            className="h-11 w-11 p-3 flex items-center justify-center text-gray-500 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </>
  )
}
