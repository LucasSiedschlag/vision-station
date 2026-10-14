import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface FieldControlProps {
  id: string
  'aria-describedby'?: string
  'aria-invalid'?: true
}

/**
 * Label, hint and error around one control, with the ids wired for assistive technology.
 * `children` receives the props the control must spread.
 */
export function Field({
  label,
  hint,
  error,
  required,
  className,
  children,
}: {
  label: string
  hint?: string
  error?: string
  required?: boolean
  className?: string
  children: (props: FieldControlProps) => ReactNode
}) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ')
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {required ? (
          <span aria-hidden className="text-fail-text">
            {' '}
            *
          </span>
        ) : null}
      </label>
      {children({
        id,
        'aria-describedby': describedBy || undefined,
        'aria-invalid': error ? true : undefined,
      })}
      {hint ? (
        <p id={hintId} className="text-xs text-fg-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-fail-text">
          {error}
        </p>
      ) : null}
    </div>
  )
}
