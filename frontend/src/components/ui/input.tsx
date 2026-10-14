import {
  forwardRef,
  useEffect,
  useState,
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { cn } from '@/lib/cn'
import { formatNumber, parseNumber } from '@/lib/number'

export const controlClasses =
  'w-full rounded-control border border-line-control bg-surface-2 px-3 fs-control text-fg placeholder:text-fg-muted disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-fail-text'

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cn(controlClasses, 'h-control', className)} {...props} />
  },
)

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea ref={ref} className={cn(controlClasses, 'min-h-24 py-2', className)} {...props} />
  )
})

export interface NumberInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'value' | 'onChange' | 'type' | 'min' | 'max' | 'step'
> {
  value: number | null
  onChange: (value: number | null) => void
  /** Shown after the number (µs, ms, mm, %): units are always visible. */
  unit?: string
  min?: number
  max?: number
  step?: number
  decimals?: number
}

/**
 * A number the way it is written in Portuguese (comma as the decimal mark). Out-of-range values are
 * flagged (aria-invalid) but never silently changed; ArrowUp/ArrowDown step within the range.
 */
export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(function NumberInput(
  {
    value,
    onChange,
    unit,
    min,
    max,
    step = 1,
    decimals = 3,
    className,
    onBlur,
    onKeyDown,
    ...props
  },
  ref,
) {
  const [text, setText] = useState(value === null ? '' : formatNumber(value, decimals))
  const [focused, setFocused] = useState(false)

  useEffect(() => {
    // follow the value from outside, but never rewrite what the person is typing
    if (!focused) setText(value === null ? '' : formatNumber(value, decimals))
  }, [value, focused, decimals])

  const parsed = parseNumber(text)
  const outOfRange =
    parsed !== null && ((min !== undefined && parsed < min) || (max !== undefined && parsed > max))
  const invalid = (text.trim() !== '' && parsed === null) || outOfRange

  const commit = (next: number | null) => {
    setText(next === null ? '' : formatNumber(next, decimals))
    onChange(next)
  }

  return (
    <div className="relative">
      <input
        ref={ref}
        inputMode="decimal"
        autoComplete="off"
        className={cn(
          controlClasses,
          'h-control text-right font-mono tabular-nums',
          unit && 'pr-12',
          className,
        )}
        value={text}
        aria-invalid={invalid || props['aria-invalid'] || undefined}
        onFocus={() => setFocused(true)}
        onChange={(event) => {
          setText(event.target.value)
          onChange(parseNumber(event.target.value))
        }}
        onBlur={(event) => {
          setFocused(false)
          setText(parsed === null ? text : formatNumber(parsed, decimals))
          onBlur?.(event)
        }}
        onKeyDown={(event) => {
          onKeyDown?.(event)
          if (event.defaultPrevented || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown'))
            return
          event.preventDefault()
          const base = parsed ?? min ?? 0
          const next = base + (event.key === 'ArrowUp' ? step : -step)
          const bounded = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, next))
          commit(Number(bounded.toFixed(decimals)))
        }}
        {...props}
      />
      {unit ? (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center text-xs text-fg-muted"
        >
          {unit}
        </span>
      ) : null}
    </div>
  )
})
