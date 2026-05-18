import { AlertCircle, RotateCw } from 'lucide-react'

interface Props {
  onRetry: () => void
  isStreaming: boolean
}

/**
 * ErrorMessageBubble — in-thread red-wash error bubble shown when the SSE
 * chat stream fails. Replaces the empty assistant placeholder. Carries a
 * Retry button that is disabled while a fresh attempt is mid-stream.
 *
 * Locked classes + copy per UI-SPEC § Surface 2 + § Copywriting Contract.
 */
export default function ErrorMessageBubble({ onRetry, isStreaming }: Props) {
  return (
    <div className="flex justify-start mb-4">
      <div
        role="alert"
        className="max-w-[85%] md:max-w-[70%] px-4 py-3 rounded-lg bg-red-950/40 border border-red-700 text-gray-100"
      >
        <div className="flex items-start gap-2">
          <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm leading-[1.5]">
            The assistant ran into a problem. Try again, or rephrase your question.
          </p>
        </div>
        <div className="mt-2">
          <button
            type="button"
            onClick={onRetry}
            disabled={isStreaming}
            className="inline-flex items-center gap-1 px-3 py-2.5 md:py-1.5 rounded text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCw size={14} />
            Retry
          </button>
        </div>
      </div>
    </div>
  )
}
