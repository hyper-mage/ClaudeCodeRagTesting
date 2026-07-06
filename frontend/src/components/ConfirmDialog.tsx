import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, KeyRound } from 'lucide-react'

interface Props {
  heading: string
  body: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onCancel: () => void
  /** Visual intent (UI-SPEC § ConfirmDialog primary variant). 'danger' (default — zero call-site
   *  changes for disconnect/docs) keeps the red destructive treatment; 'primary' is the
   *  NON-destructive blue confirm used by the key-gate modal — never red-600/AlertTriangle. */
  variant?: 'danger' | 'primary'
}

export default function ConfirmDialog({
  heading,
  body,
  confirmLabel,
  cancelLabel,
  onConfirm,
  onCancel,
  variant = 'danger',
}: Props) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onCancel])

  return createPortal(
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onCancel}
    >
      <div
        className="bg-white border border-gray-300 dark:bg-gray-900 dark:border-gray-700 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl"
        onClick={e => e.stopPropagation()}
      >
        {variant === 'primary' ? (
          <KeyRound size={24} className="text-blue-600" />
        ) : (
          <AlertTriangle size={24} className="text-red-400" />
        )}
        <h2 className="text-lg font-bold text-gray-900 dark:text-white mt-3">{heading}</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">{body}</p>
        <div className="flex gap-3 mt-6 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="bg-gray-200 hover:bg-gray-300 text-gray-900 dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-white text-sm px-4 py-2 rounded"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`${
              variant === 'primary'
                ? 'bg-blue-600 hover:bg-blue-700'
                : 'bg-red-600 hover:bg-red-700'
            } text-white text-sm px-4 py-2 rounded`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
