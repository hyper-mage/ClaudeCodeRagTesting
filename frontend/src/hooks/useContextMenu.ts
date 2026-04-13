import { useState, useCallback, useEffect } from 'react'
import type { FolderNode } from './useFolderTree'
import type { Document } from './useDocuments'

export type ContextTarget =
  | { type: 'folder'; node: FolderNode }
  | { type: 'file'; doc: Document }

export interface ContextMenuState {
  x: number
  y: number
  target: ContextTarget
}

export function useContextMenu() {
  const [menu, setMenu] = useState<ContextMenuState | null>(null)

  const openMenu = useCallback((e: React.MouseEvent, target: ContextTarget) => {
    e.preventDefault()
    e.stopPropagation()
    setMenu({ x: e.clientX, y: e.clientY, target })
  }, [])

  const closeMenu = useCallback(() => {
    setMenu(null)
  }, [])

  useEffect(() => {
    if (!menu) return
    const handleClick = () => setMenu(null)
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenu(null)
    }
    document.addEventListener('click', handleClick)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('click', handleClick)
      document.removeEventListener('keydown', handleKey)
    }
  }, [menu])

  return { menu, openMenu, closeMenu }
}
