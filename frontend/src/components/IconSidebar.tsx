import { MessageSquare, FileText, LogOut } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function IconSidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { signOut } = useAuth()

  const isChat = location.pathname === '/'
  const isDocs = location.pathname === '/documents'

  return (
    <div className="w-14 bg-gray-900 border-r border-gray-800 flex flex-col items-center py-3 h-screen shrink-0">
      <button
        onClick={() => navigate('/')}
        className={`p-2 rounded mb-2 ${isChat ? 'bg-gray-800 text-white' : 'text-gray-500 hover:text-white'}`}
        title="Chat"
      >
        <MessageSquare size={20} />
      </button>
      <button
        onClick={() => navigate('/documents')}
        className={`p-2 rounded mb-2 ${isDocs ? 'bg-gray-800 text-white' : 'text-gray-500 hover:text-white'}`}
        title="Documents"
      >
        <FileText size={20} />
      </button>
      <div className="flex-1" />
      <button
        onClick={signOut}
        className="p-2 rounded text-gray-500 hover:text-white"
        title="Sign Out"
      >
        <LogOut size={20} />
      </button>
    </div>
  )
}
