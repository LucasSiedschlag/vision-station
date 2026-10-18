import { useContext, useLayoutEffect, useMemo, useRef } from 'react'
import {
  Group,
  Input,
  NumberField as AriaNumberField,
  NumberFieldStateContext,
  useLocale,
} from 'react-aria-components'
import { cn } from '@/lib/cn'
import { controlClasses } from './input'

export interface NumberFieldProps {
  value: number | null
  /** Called when the value is committed: on leaving the field, on Enter and on each arrow step. */
  onChange: (value: number | null) => void
  /** Shown after the number (µs, ms, mm): units are always visible. */
  unit?: string
  /** The value is a fraction (0 to 1) written as a percentage: `30%` stands for 0.3. The step is then a fraction too. */
  percent?: boolean
  min?: number
  max?: number
  step?: number
  decimals?: number
  isDisabled?: boolean
  placeholder?: string
  className?: string
  id?: string
  'aria-label'?: string
  'aria-labelledby'?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean | 'true' | 'false'
}

/**
 * A number in the interface language (React Aria, TD-29): `1500,5` in Portuguese. Out-of-range
 * values are flagged (aria-invalid) but never silently changed, and the step only drives the
 * arrows: an exact value typed off the step is kept.
 */
export function NumberField({
  value,
  onChange,
  unit,
  percent,
  min,
  max,
  step = 1,
  decimals = 3,
  isDisabled,
  placeholder,
  className,
  'aria-invalid': ariaInvalid,
  ...props
}: NumberFieldProps) {
  const outOfRange =
    value !== null && ((min !== undefined && value < min) || (max !== undefined && value > max))
  return (
    <AriaNumberField
      {...props}
      value={value ?? NaN}
      onChange={(v) => onChange(Number.isNaN(v) ? null : v)}
      minValue={min}
      maxValue={max}
      step={step}
      formatOptions={
        percent
          ? {
              style: 'percent',
              maximumFractionDigits: Math.max(decimals - 2, 0),
              useGrouping: false,
            }
          : { maximumFractionDigits: decimals, useGrouping: false }
      }
      commitBehavior="validate"
      // decided here, so the browser's own range and step messages never show
      isInvalid={outOfRange || ariaInvalid === true || ariaInvalid === 'true'}
      isDisabled={isDisabled}
      className={cn('relative', className)}
    >
      <Group className="relative">
        <NumberInput placeholder={placeholder} unit={unit} />
        {unit ? (
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center text-xs text-fg-muted"
          >
            {unit}
          </span>
        ) : null}
      </Group>
    </AriaNumberField>
  )
}

/**
 * The text box. React Aria refuses a dot in Portuguese (and a comma in English) without a word, so
 * "0.8" would become "08", that is 8: both keys write the decimal mark of the language instead.
 */
function NumberInput({ placeholder, unit }: { placeholder?: string; unit?: string }) {
  const state = useContext(NumberFieldStateContext)
  const { locale } = useLocale()
  const mark = useMemo(
    () => new Intl.NumberFormat(locale).formatToParts(1.5).find((p) => p.type === 'decimal')?.value,
    [locale],
  )
  const ref = useRef<HTMLInputElement>(null)
  const caret = useRef<number | null>(null)
  useLayoutEffect(() => {
    if (caret.current === null || !ref.current) return
    ref.current.setSelectionRange(caret.current, caret.current)
    caret.current = null
  })
  return (
    <Input
      ref={ref}
      autoComplete="off"
      placeholder={placeholder}
      onKeyDown={(event) => {
        if (!state || !mark || (event.key !== '.' && event.key !== ',') || event.key === mark)
          return
        event.preventDefault()
        const input = event.currentTarget
        const start = input.selectionStart ?? input.value.length
        const end = input.selectionEnd ?? start
        const next = input.value.slice(0, start) + mark + input.value.slice(end)
        if (!state.validate(next)) return // a second decimal mark, or none allowed
        caret.current = start + 1
        state.setInputValue(next)
      }}
      className={cn(controlClasses, 'h-control text-right font-mono tabular-nums', unit && 'pr-12')}
    />
  )
}
