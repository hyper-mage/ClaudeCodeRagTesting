interface Props {
  icon: React.ReactNode
  label: string
  onClick: () => void
  variant?: 'default' | 'destructive'
}

export default function ContextMenuItem({
  icon,
  label,
  onClick,
  variant = 'default',
}: Props) {
  const variantClasses =
    variant === 'destructive'
      ? 'text-red-400 hover:bg-red-600/20 hover:text-red-300'
      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer w-full text-left min-h-[32px] ${variantClasses}`}
    >
      <span className="shrink-0 flex items-center justify-center">{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  )
}
