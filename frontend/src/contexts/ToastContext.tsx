import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

export type ToastVariant = 'info' | 'success' | 'warning' | 'error'

export interface Toast {
  id: number
  variant: ToastVariant
  message: string
}

interface ToastContextValue {
  showToast: (message: string, variant?: ToastVariant) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const VARIANT_STYLES: Record<ToastVariant, string> = {
  info: 'bg-gray-800 border-gray-600 text-gray-100',
  success: 'bg-green-700 border-green-500 text-white',
  warning: 'bg-amber-600 border-amber-400 text-white',
  error: 'bg-red-700 border-red-500 text-white',
}

const AUTO_DISMISS_MS = 4000

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'info') => {
      idRef.current += 1
      const id = idRef.current
      setToasts(prev => [...prev, { id, message, variant }])
    },
    []
  )

  // Auto-dismiss any toast after the timeout.
  useEffect(() => {
    if (toasts.length === 0) return
    const timers = toasts.map(t =>
      setTimeout(() => dismiss(t.id), AUTO_DISMISS_MS)
    )
    return () => {
      timers.forEach(clearTimeout)
    }
  }, [toasts, dismiss])

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
      >
        {toasts.map(t => (
          <div
            key={t.id}
            role="status"
            className={`pointer-events-auto px-4 py-2 rounded border text-sm shadow-lg max-w-sm ${VARIANT_STYLES[t.variant]}`}
          >
            <div className="flex items-start gap-3">
              <span className="flex-1 break-words">{t.message}</span>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                className="text-xs opacity-70 hover:opacity-100"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return ctx
}
