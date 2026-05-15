import { useRef } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

interface UseSwipeToCloseOptions {
  thresholdPx?: number
  widthPercent?: number
}

interface SwipeHandlers {
  onPointerDown: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerMove: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerUp: (e: ReactPointerEvent<HTMLElement>) => void
  onPointerCancel: (e: ReactPointerEvent<HTMLElement>) => void
}

/**
 * Hand-rolled swipe-left-to-close gesture for the mobile drawer surface.
 *
 * Returns four pointer handlers to spread onto the drawer panel element.
 * Detection only — no DOM mutation during drag; the CSS `transition-transform`
 * on the panel handles the actual close animation when `onClose` fires.
 *
 * Threshold defaults to `min(80px, 30% of element width)`, per UI-SPEC.md.
 * Gesture scoped to the element it is spread onto — does NOT install
 * document-level listeners.
 */
export function useSwipeToClose(
  onClose: () => void,
  options?: UseSwipeToCloseOptions,
): SwipeHandlers {
  const startXRef = useRef<number | null>(null)
  const currentDeltaXRef = useRef<number | null>(null)

  const reset = () => {
    startXRef.current = null
    currentDeltaXRef.current = null
  }

  const onPointerDown = (e: ReactPointerEvent<HTMLElement>) => {
    startXRef.current = e.clientX
    currentDeltaXRef.current = 0
    try {
      e.currentTarget.setPointerCapture(e.pointerId)
    } catch {
      // Some browsers throw if pointer is already captured; safe to ignore.
    }
  }

  const onPointerMove = (e: ReactPointerEvent<HTMLElement>) => {
    if (startXRef.current == null) return
    const delta = e.clientX - startXRef.current
    // Ignore right-drag; only track leftward motion.
    if (delta >= 0) {
      currentDeltaXRef.current = 0
      return
    }
    currentDeltaXRef.current = delta
  }

  const finishGesture = (e: ReactPointerEvent<HTMLElement>) => {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      // No-op if capture was never set.
    }

    const delta = currentDeltaXRef.current
    if (delta != null) {
      const width = (e.currentTarget as HTMLElement).offsetWidth
      const threshold = Math.min(
        options?.thresholdPx ?? 80,
        width * (options?.widthPercent ?? 0.3),
      )
      if (Math.abs(delta) >= threshold) {
        onClose()
      }
    }
    reset()
  }

  const onPointerUp = (e: ReactPointerEvent<HTMLElement>) => {
    finishGesture(e)
  }

  const onPointerCancel = (e: ReactPointerEvent<HTMLElement>) => {
    finishGesture(e)
  }

  return { onPointerDown, onPointerMove, onPointerUp, onPointerCancel }
}
