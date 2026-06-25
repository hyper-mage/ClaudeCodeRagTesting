import { MessageSquare, FileText, Settings, LogOut } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useKeyStatus } from '../hooks/useKeyStatus'
import DemoPill from './DemoPill'

export default function IconSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { signOut } = useAuth()
  const { status } = useKeyStatus()

  const isChat = location.pathname === '/'
  const isDocs = location.pathname === '/documents'
  const isSettings = location.pathname === '/settings'

  return (
    <div className="hidden md:flex w-14 bg-gray-100 border-r border-gray-200 flex-col items-center py-3 h-screen shrink-0 dark:bg-gray-900 dark:border-gray-800">
      <button
        onClick={() => navigate('/')}
        className={`p-2 rounded mb-2 ${isChat ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Chat"
      >
        <MessageSquare size={20} />
      </button>
      <button
        onClick={() => navigate('/documents')}
        className={`p-2 rounded mb-2 ${isDocs ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Documents"
      >
        <FileText size={20} />
      </button>
      <button
        onClick={() => navigate('/settings')}
        className={`p-2 rounded mb-2 ${isSettings ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Settings"
      >
        <Settings size={20} />
      </button>
      <div className="flex-1" />
      <span
        role="status"
        aria-label={status?.connected ? 'OpenRouter connected' : 'OpenRouter not connected'}
        className={`h-2 w-2 rounded-full mb-2 ${status?.connected ? 'bg-green-500' : 'bg-gray-500'}`}
      />
      <DemoPill />
      <button
        onClick={signOut}
        className="p-2 rounded text-gray-500 hover:text-gray-900 dark:hover:text-white"
        title="Sign Out"
      >
        <LogOut size={20} />
      </button>
    </div>
  )
}

interface IconNavRowProps {
  onNavigate?: () => void
}

/**
 * IconNavRow — horizontal nav cluster (Chat / Documents / Sign Out) for
 * reuse inside MobileDrawer. Same active/inactive style logic as the
 * desktop rail. When `onNavigate` is provided, it fires AFTER the
 * navigation / signOut call so the drawer can auto-close on tap.
 */
export function IconNavRow({ onNavigate }: IconNavRowProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { signOut } = useAuth()

  const isChat = location.pathname === '/'
  const isDocs = location.pathname === '/documents'
  const isSettings = location.pathname === '/settings'

  const handleNavigate = (path: string) => {
    navigate(path)
    onNavigate?.()
  }

  const handleSignOut = () => {
    signOut()
    onNavigate?.()
  }

  return (
    <div className="flex items-center gap-2 px-3 py-3 border-b border-gray-200 dark:border-gray-800">
      <button
        onClick={() => handleNavigate('/')}
        className={`p-2 rounded ${isChat ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Chat"
      >
        <MessageSquare size={20} />
      </button>
      <button
        onClick={() => handleNavigate('/documents')}
        className={`p-2 rounded ${isDocs ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Documents"
      >
        <FileText size={20} />
      </button>
      <button
        onClick={() => handleNavigate('/settings')}
        className={`p-2 rounded ${isSettings ? 'bg-gray-200 text-gray-900 dark:bg-gray-800 dark:text-white' : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'}`}
        title="Settings"
      >
        <Settings size={20} />
      </button>
      <div className="flex-1" />
      <DemoPill />
      <button
        onClick={handleSignOut}
        className="p-2 rounded text-gray-500 hover:text-gray-900 dark:hover:text-white"
        title="Sign Out"
      >
        <LogOut size={20} />
      </button>
    </div>
  )
}
