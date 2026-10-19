import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from 'react'
import { cn } from '@/lib/cn'
import { hueSpans, outsideSpans as outside } from './hsv-model'
import { paintHue } from './hsv-paint'

type Hue = [number, number]

const pct = (tick: number) => `${(tick / 180) * 100}%`

/**
 * The hue bar of the colour picker (docs/frontend.md §19.4): every hue in its real colour, the band the range takes
 * in marked with two handles, and the band continues past the right end for a red (170 to 10). Each handle is a
 * slider of its own on the circle of 180 hues (2° each); the one that is not moved keeps its exact value.
 * `histogram` is how many of the region's pixels have each hue; `ghost` is a proposal not applied yet.
 */
export function HueBar({
  value,
  ghost,
  histogram,
  saturation,
  brightness,
  onChange,
  labels,
  className,
}: {
  value: Hue
  ghost?: Hue | null
  histogram?: number[]
  /** the saturation and value the bar is painted at, so its colours are the ones in the range */
  saturation: number
  brightness: number
  onChange: (next: Hue) => void
  labels: [string, string]
  className?: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const track = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (canvas.current) paintHue(canvas.current, saturation, brightness)
  }, [saturation, brightness])

  const tickAt = (e: PointerEvent) => {
    const r = track.current!.getBoundingClientRect()
    return Math.min(179, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * 180)))
  }
  const set = (which: 0 | 1, tick: number) =>
    onChange(which === 0 ? [(tick + 180) % 180, value[1]] : [value[0], (tick + 180) % 180])

  const onKey = (e: KeyboardEvent, which: 0 | 1) => {
    const step = e.shiftKey ? 5 : 1
    const delta: Record<string, number> = {
      ArrowLeft: -step,
      ArrowDown: -step,
      ArrowRight: step,
      ArrowUp: step,
    }
    if (e.key in delta) {
      e.preventDefault()
      set(which, value[which] + delta[e.key]!)
    }
  }
  const max = Math.max(1, ...(histogram ?? [0]))
  const band = (h: Hue, className: string) =>
    hueSpans(h).map(([a, b], i) => (
      <div
        key={i}
        aria-hidden
        className={cn('absolute inset-y-0', className)}
        style={{ left: pct(a), width: pct(b - a + 1) }}
      />
    ))

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div ref={track} className="relative my-3 h-7 w-full touch-none select-none">
        <canvas
          ref={canvas}
          aria-hidden
          className="absolute inset-0 size-full rounded-control border border-line"
        />
        {/* the hues the range leaves out are dimmed, the ones it takes in stay in colour */}
        {outside(value).map(([a, b], i) => (
          <div
            key={i}
            aria-hidden
            className="absolute inset-y-0 bg-surface-1/60"
            style={{ left: pct(a), width: pct(b - a + 1) }}
          />
        ))}
        {ghost ? band(ghost, 'border-y-2 border-dashed border-accent-text') : null}
        {band(value, 'border-y-2 border-accent-text')}
        {([0, 1] as const).map((which) => (
          <div
            key={which}
            role="slider"
            tabIndex={0}
            aria-label={labels[which]}
            aria-valuemin={0}
            aria-valuemax={358}
            aria-valuenow={value[which] * 2}
            aria-valuetext={`${value[which] * 2}°`}
            onKeyDown={(e) => onKey(e, which)}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId)
              set(which, tickAt(e))
            }}
            onPointerMove={(e) => e.buttons === 1 && set(which, tickAt(e))}
            className={cn(
              // the first handle sits on the top edge and the second on the bottom one: a narrow band keeps both
              // reachable, 24 px targets that never cover each other (WCAG 2.5.8)
              'absolute size-6 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize rounded-pill border-2 border-accent bg-surface-1 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-text',
              which === 0 ? 'top-0' : 'top-full',
            )}
            style={{ left: pct(value[which] + (which === 0 ? 0 : 1)) }}
          />
        ))}
      </div>
      {histogram ? (
        <svg
          aria-hidden
          viewBox="0 0 180 12"
          preserveAspectRatio="none"
          className="h-3 w-full text-fg-muted"
        >
          {histogram.map((n, h) =>
            n > 0 ? (
              <rect
                key={h}
                x={h}
                y={12 - (n / max) * 12}
                width={1}
                height={(n / max) * 12}
                fill="currentColor"
              />
            ) : null,
          )}
        </svg>
      ) : null}
    </div>
  )
}
