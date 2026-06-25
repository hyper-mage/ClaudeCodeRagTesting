import { Info } from 'lucide-react'

interface Props {
  /** The server-composed notice copy (SC#4). Rendered VERBATIM as escaped React text. */
  content: string
}

/**
 * DeprecationNotice — a quiet, persisted system line shown inline in the message stream when a
 * pinned model has left the catalog and the at-send fallback swapped in the default (Plan 04
 * wrote the role='notice' row; D-06). It is NOT a message bubble, NOT a toast, NOT red — the
 * model simply changed, nothing failed (UI-SPEC § Deprecation-notice colors).
 *
 * Layout: a full-width centered row, a muted lucide Info icon (14px) + Caption (text-xs) text.
 * Theme-aware quiet colors (LOCKED): light gray-100 bg / gray-700 text / gray-200 border;
 * dark gray-800 bg / gray-300 text / gray-700 border. Reuses the visual language of a divider.
 *
 * Security (T-13-XSS-NOTICE): the content is rendered as escaped React text — no
 * dangerouslySetInnerHTML, no interpolation — so a server string can never inject markup.
 */
export default function DeprecationNotice({ content }: Props) {
  return (
    <div className="flex justify-center my-4">
      <div className="flex max-w-[90%] items-center gap-2 rounded border border-gray-200 bg-gray-100 px-3 py-1.5 dark:border-gray-700 dark:bg-gray-800">
        <Info
          size={14}
          className="shrink-0 text-gray-500 dark:text-gray-400"
          aria-hidden="true"
        />
        <span className="text-xs text-gray-700 dark:text-gray-300">{content}</span>
      </div>
    </div>
  )
}
