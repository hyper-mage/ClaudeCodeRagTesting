import { useEffect, useRef } from 'react'

interface Props {
  currentName?: string
  placeholder?: string
  onConfirm: (newName: string) => void
  onCancel: () => void
}

export default function InlineRename({
  currentName,
  placeholder,
  onConfirm,
  onCancel,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!inputRef.current) return
    inputRef.current.focus()
    if (currentName) {
      inputRef.current.select()
    }
  }, [currentName])

  const commit = () => {
    const value = inputRef.current?.value.trim() ?? ''
    if (!value) {
      onCancel()
      return
    }
    if (value === currentName) {
      onCancel()
      return
    }
    onConfirm(value)
  }

  return (
    <input
      ref={inputRef}
      type="text"
      defaultValue={currentName ?? ''}
      placeholder={placeholder ?? ''}
      onClick={e => e.stopPropagation()}
      onKeyDown={e => {
        if (e.key === 'Enter') {
          e.preventDefault()
          commit()
        } else if (e.key === 'Escape') {
          e.preventDefault()
          onCancel()
        }
      }}
      onBlur={commit}
      className="bg-gray-800 border border-blue-500 text-sm text-white px-1 py-0.5 rounded outline-none w-full"
    />
  )
}
