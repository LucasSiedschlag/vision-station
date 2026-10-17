import {
  Label,
  Slider as AriaSlider,
  SliderOutput,
  SliderThumb,
  SliderTrack,
} from 'react-aria-components'
import { useState } from 'react'
import { cn } from '@/lib/cn'
import { NumberField } from './number-field'

export const thumbClasses =
  'top-1/2 size-5 rounded-pill border-2 border-accent bg-surface-1 data-[dragging]:bg-accent data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-accent-text data-[disabled]:border-line-control'

/**
 * A slider with one or more thumbs (React Aria, TD-29): one thumb for a limit, two for a range.
 * The thumbs never cross. With `fields`, a number box beside each thumb takes an exact value; a
 * value out of range typed there is flagged and does not move the thumb.
 */
export function Slider({
  label,
  thumbLabels,
  value,
  onChange,
  onChangeEnd,
  min,
  max,
  step = 1,
  decimals = 3,
  unit,
  fields,
  isDisabled,
  className,
}: {
  /** Shown above the slider; with one thumb it is also the thumb's name. */
  label: string
  /** One name per thumb when there is more than one ("Início", "Fim"). */
  thumbLabels?: string[]
  value: number[]
  onChange: (value: number[]) => void
  onChangeEnd?: (value: number[]) => void
  min: number
  max: number
  step?: number
  decimals?: number
  unit?: string
  fields?: boolean
  isDisabled?: boolean
  className?: string
}) {
  const formatOptions = { maximumFractionDigits: decimals, useGrouping: false }
  const thumbName = (i: number) => (value.length > 1 ? thumbLabels?.[i] : undefined)
  const setOne = (i: number, v: number) => {
    const next = value.map((old, j) => (j === i ? v : old))
    onChange(next)
    onChangeEnd?.(next)
  }
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <AriaSlider
        value={value}
        onChange={(v) => onChange(Array.isArray(v) ? v : [v])}
        onChangeEnd={onChangeEnd && ((v) => onChangeEnd(Array.isArray(v) ? v : [v]))}
        minValue={min}
        maxValue={max}
        step={step}
        formatOptions={formatOptions}
        isDisabled={isDisabled}
        className="flex flex-col gap-1"
      >
        <div className="flex items-baseline justify-between gap-4">
          <Label className="text-sm font-medium">{label}</Label>
          <SliderOutput className="font-mono text-sm tabular-nums text-fg-muted">
            {({ state }) =>
              state.values
                .map((_, i) => state.getThumbValueLabel(i) + (unit ? ` ${unit}` : ''))
                .join(' – ')
            }
          </SliderOutput>
        </div>
        {/* only the track fades when disabled: the label and the value stay readable (contrast) */}
        <SliderTrack className="relative h-6 w-full touch-none data-[disabled]:opacity-50">
          {({ state }) => {
            const ends =
              state.values.length > 1
                ? [state.getThumbPercent(0), state.getThumbPercent(state.values.length - 1)]
                : [0, state.getThumbPercent(0)]
            return (
              <>
                <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-pill bg-surface-3" />
                <div
                  className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-pill bg-accent"
                  style={{ left: `${ends[0]! * 100}%`, width: `${(ends[1]! - ends[0]!) * 100}%` }}
                />
                {state.values.map((_, i) => (
                  <SliderThumb
                    key={i}
                    index={i}
                    aria-label={thumbName(i)}
                    className={thumbClasses}
                  />
                ))}
              </>
            )
          }}
        </SliderTrack>
      </AriaSlider>
      {fields ? (
        <div className="flex flex-wrap gap-3">
          {value.map((v, i) => {
            const name = thumbName(i) ?? label
            return (
              <div key={i} className="flex w-40 flex-col gap-1">
                {value.length > 1 ? (
                  <span aria-hidden className="text-xs text-fg-muted">
                    {name}
                  </span>
                ) : null}
                <ThumbField
                  name={name}
                  value={v}
                  // a box may not push one thumb past its neighbours
                  low={value[i - 1] ?? min}
                  high={value[i + 1] ?? max}
                  onCommit={(next) => setOne(i, next)}
                  step={step}
                  decimals={decimals}
                  unit={unit}
                  isDisabled={isDisabled}
                />
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

/** The number box of one thumb: keeps what was typed, flags it when out of reach, moves the thumb only when it fits. */
function ThumbField({
  name,
  value,
  low,
  high,
  onCommit,
  step,
  decimals,
  unit,
  isDisabled,
}: {
  name: string
  value: number
  low: number
  high: number
  onCommit: (value: number) => void
  step: number
  decimals: number
  unit?: string
  isDisabled?: boolean
}) {
  // what was typed and does not fit; none: the box shows the thumb's value
  const [refused, setRefused] = useState<number | null | undefined>(undefined)
  return (
    <NumberField
      aria-label={`${name} (valor exato)`}
      value={refused === undefined ? value : refused}
      onChange={(next) => {
        const fits = next !== null && next >= low && next <= high
        setRefused(fits ? undefined : next)
        if (fits) onCommit(next)
      }}
      min={low}
      max={high}
      step={step}
      decimals={decimals}
      unit={unit}
      isDisabled={isDisabled}
    />
  )
}
