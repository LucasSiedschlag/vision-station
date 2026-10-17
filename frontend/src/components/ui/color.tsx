import {
  ColorArea as AriaColorArea,
  ColorField as AriaColorField,
  ColorSlider as AriaColorSlider,
  ColorThumb,
  Input,
  Label,
  SliderOutput,
  SliderTrack,
  type Color,
  type ColorChannel,
} from 'react-aria-components'
import { cn } from '@/lib/cn'
import { controlClasses } from './input'

// Colour controls in HSB channels (React Aria, TD-29): the building blocks of HsvRangePicker and the
// reference-colour control (document 05 §19.4). The gradients come from React Aria at run time.

const colorThumbClasses =
  'size-5 rounded-pill border-2 border-surface-1 shadow-md ring-1 ring-line-strong data-[dragging]:size-6 data-[focus-visible]:outline-2 data-[focus-visible]:outline-offset-2 data-[focus-visible]:outline-accent-text'

/** Two channels on a square: saturation across and brightness up by default. */
export function ColorArea({
  value,
  onChange,
  onChangeEnd,
  xChannel = 'saturation',
  yChannel = 'brightness',
  isDisabled,
  className,
  'aria-label': ariaLabel,
}: {
  value: Color
  onChange: (value: Color) => void
  onChangeEnd?: (value: Color) => void
  xChannel?: ColorChannel
  yChannel?: ColorChannel
  isDisabled?: boolean
  className?: string
  'aria-label': string
}) {
  return (
    <AriaColorArea
      value={value}
      onChange={onChange}
      onChangeEnd={onChangeEnd}
      xChannel={xChannel}
      yChannel={yChannel}
      isDisabled={isDisabled}
      aria-label={ariaLabel}
      className={cn(
        'aspect-square w-full max-w-64 shrink-0 rounded-control data-[disabled]:opacity-50',
        className,
      )}
    >
      <ColorThumb className={colorThumbClasses} />
    </AriaColorArea>
  )
}

/** One channel of a colour along a track (hue, saturation, brightness), with its label and value. */
export function ColorSlider({
  label,
  channel,
  value,
  onChange,
  onChangeEnd,
  isDisabled,
  className,
}: {
  label: string
  channel: ColorChannel
  value: Color
  onChange: (value: Color) => void
  onChangeEnd?: (value: Color) => void
  isDisabled?: boolean
  className?: string
}) {
  return (
    <AriaColorSlider
      channel={channel}
      colorSpace="hsb"
      value={value}
      onChange={onChange}
      onChangeEnd={onChangeEnd}
      isDisabled={isDisabled}
      className={cn('flex w-full flex-col gap-1', className)}
    >
      <div className="flex items-baseline justify-between gap-4">
        <Label className="text-sm font-medium">{label}</Label>
        <SliderOutput className="font-mono text-sm tabular-nums text-fg-muted" />
      </div>
      {/* only the track fades when disabled: the label and the value stay readable (contrast) */}
      <SliderTrack className="h-6 w-full rounded-control data-[disabled]:opacity-50">
        <ColorThumb className={cn(colorThumbClasses, 'top-1/2')} />
      </SliderTrack>
    </AriaColorSlider>
  )
}

/** A colour typed as hex (#RRGGBB); `channel` turns it into one channel's number. */
export function ColorField({
  label,
  value,
  onChange,
  channel,
  isDisabled,
  className,
}: {
  label: string
  value: Color | null
  onChange: (value: Color | null) => void
  channel?: ColorChannel
  isDisabled?: boolean
  className?: string
}) {
  return (
    <AriaColorField
      value={value}
      onChange={onChange}
      channel={channel}
      colorSpace={channel ? 'hsb' : undefined}
      isDisabled={isDisabled}
      className={cn('flex flex-col gap-1', className)}
    >
      <Label className="text-sm font-medium">{label}</Label>
      <Input className={cn(controlClasses, 'h-control font-mono tabular-nums')} />
    </AriaColorField>
  )
}
