import { Upload } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { cn } from '@/lib/cn'
import { text } from '@/texts'

/**
 * Drop a file or press Enter/Space to choose one. `accept` lists extensions (".vjob,.vbak"); a file with
 * another extension is refused with a message instead of being passed on.
 */
export function FileDrop({
  accept,
  onFiles,
  label,
  hint,
  multiple = false,
}: {
  accept: string
  onFiles: (files: File[]) => void
  label: string
  hint?: string
  multiple?: boolean
}) {
  const id = useId()
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [error, setError] = useState('')
  const allowed = accept.split(',').map((e) => e.trim().toLowerCase())

  const take = (list: FileList | null) => {
    const files = Array.from(list ?? [])
    if (files.length === 0) return
    const bad = files.filter((f) => !allowed.some((ext) => f.name.toLowerCase().endsWith(ext)))
    if (bad.length > 0) {
      setError(text.ui.badFileType(bad.map((f) => f.name).join(', '), accept))
      return
    }
    setError('')
    onFiles(multiple ? files : files.slice(0, 1))
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          take(e.dataTransfer.files)
        }}
        className={cn(
          'flex flex-col items-center gap-2 rounded-card border-2 border-dashed border-line-control px-6 py-8 text-center',
          over && 'border-accent bg-surface-2',
        )}
      >
        <Upload aria-hidden className="size-6 text-fg-muted" />
        <label
          htmlFor={id}
          className="cursor-pointer text-sm font-medium text-accent-text underline"
        >
          {label}
        </label>
        <p className="text-xs text-fg-muted">{hint ?? `ou solte o arquivo aqui (${accept})`}</p>
        <input
          ref={input}
          id={id}
          type="file"
          accept={accept}
          multiple={multiple}
          className="sr-only"
          onChange={(e) => take(e.target.files)}
        />
      </div>
      {error ? (
        <p role="alert" className="text-xs text-fail-text">
          {error}
        </p>
      ) : null}
    </div>
  )
}
