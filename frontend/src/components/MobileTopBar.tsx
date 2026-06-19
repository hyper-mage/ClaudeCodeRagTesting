import type { RefObject } from 'react'
import { Menu } from 'lucide-react'
import { useKeyStatus } from '../hooks/useKeyStatus'
import DemoPill from './DemoPill'

interface Props {
  title: string
  onOpenDrawer: () => void
  hamburgerRef: RefObject<HTMLButtonElement | null>
  isDrawerOpen: boolean
}

/**
 * MobileTopBar — visible only below md: (md:hidden). Hamburger left + page
 * title center; right spacer keeps the title visually centered. The drawer
 * surface carries the "+ New Chat" CTA, so the top bar is title-only.
 */
export default function MobileTopBar({ title, onOpenDrawer, hamburgerRef, isDrawerOpen }: Props) {
  const { status } = useKeyStatus()
  return (
    <div className="md:hidden h-12 bg-gray-900 border-b border-gray-800 flex items-center px-2 shrink-0">
      <button
        ref={hamburgerRef}
        aria-label="Open menu"
        aria-expanded={isDrawerOpen}
        aria-controls="mobile-drawer"
        onClick={onOpenDrawer}
        className="h-11 w-11 p-3 flex items-center justify-center text-white"
      >
        <Menu size={24} />
      </button>
      <h1 className="flex-1 text-center text-base font-semibold text-white truncate px-2">
        {title}
      </h1>
      <span
        role="status"
        aria-label={status?.connected ? 'OpenRouter connected' : 'OpenRouter not connected'}
        className={`h-2 w-2 rounded-full ${status?.connected ? 'bg-green-500' : 'bg-gray-500'}`}
      />
      <div className="h-11 w-11 flex items-center justify-center">
        <DemoPill />
      </div>
    </div>
  )
}
