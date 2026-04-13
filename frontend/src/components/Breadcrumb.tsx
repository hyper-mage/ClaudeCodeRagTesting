import type { BreadcrumbSegment } from '../hooks/useFolderTree'

interface Props {
  segments: BreadcrumbSegment[]
  onNavigate: (id: string | null) => void
}

export default function Breadcrumb({ segments, onNavigate }: Props) {
  if (segments.length === 0) return null

  return (
    <div className="h-10 px-4 border-b border-gray-800 flex items-center gap-1">
      {segments.map((seg, idx) => {
        const isLast = idx === segments.length - 1
        return (
          <span key={`${seg.id ?? 'root'}-${idx}`} className="flex items-center gap-1">
            {idx > 0 && <span className="text-xs text-gray-600">/</span>}
            {isLast ? (
              <span className="text-xs text-gray-200">{seg.name}</span>
            ) : (
              <button
                type="button"
                onClick={() => onNavigate(seg.id)}
                className="text-xs text-gray-400 hover:text-gray-200 cursor-pointer"
              >
                {seg.name}
              </button>
            )}
          </span>
        )
      })}
    </div>
  )
}
