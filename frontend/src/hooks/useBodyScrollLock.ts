import { useEffect } from 'react'

/**
 * Lock `<body>` scroll while `locked` is true. Captures the previous
 * `document.body.style.overflow` value on mount/activation and restores it
 * on cleanup so we never leave the page non-scrollable after unmount.
 *
 * Used by MobileDrawer to prevent background content scroll while the drawer
 * is open (UI-SPEC.md: "Drawer open → <body> gets overflow-hidden until close").
 */
export function useBodyScrollLock(locked: boolean): void {
  useEffect(() => {
    if (!locked) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.body.style.overflow = previousOverflow
    }
  }, [locked])
}
