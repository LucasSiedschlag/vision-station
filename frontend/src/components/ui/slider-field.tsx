import { Slider as RadixSlider } from 'radix-ui'
import { NumberInput } from './input'

/** A slider with a number box beside it: the slider to explore, the box to type an exact value. */
export function SliderField({
  value,
  onValueChange,
  min,
  max,
  step = 1,
  unit,
  label,
  decimals,
}: {
  value: number
  onValueChange: (value: number) => void
  min: number
  max: number
  step?: number
  unit?: string
  label: string
  decimals?: number
}) {
  return (
    <div className="flex items-center gap-4">
      <RadixSlider.Root
        value={[value]}
        onValueChange={([v]) => v !== undefined && onValueChange(v)}
        min={min}
        max={max}
        step={step}
        className="relative flex h-6 flex-1 touch-none select-none items-center"
      >
        <RadixSlider.Track className="relative h-1.5 grow rounded-pill bg-surface-3">
          <RadixSlider.Range className="absolute h-full rounded-pill bg-accent" />
        </RadixSlider.Track>
        <RadixSlider.Thumb
          aria-label={label}
          className="block size-5 rounded-pill border-2 border-accent bg-surface-1"
        />
      </RadixSlider.Root>
      <div className="w-32 shrink-0">
        <NumberInput
          aria-label={`${label} (valor exato)`}
          value={value}
          onChange={(v) => v !== null && onValueChange(Math.min(max, Math.max(min, v)))}
          min={min}
          max={max}
          step={step}
          unit={unit}
          decimals={decimals}
        />
      </div>
    </div>
  )
}
