import { useRef } from 'react'
import { cn } from '@/lib/cn'

const clamp = (n: number) => Math.min(255, Math.max(0, Math.round(n)))

/**
 * The gray histogram of a region with the threshold as a line to drag (docs/frontend.md §19.5). The levels the
 * threshold takes as object (<= the line for `dark`, > the line for `light`) are in the accent colour. The
 * bars are on a square-root scale, as in `Histogram`. While the level is automatic the line is dashed; any move
 * makes it a chosen level through `onChange`.
 */
export function GrayThreshold({
  counts,
  mode,
  level,
  auto,
  label,
  autoLabel,
  onChange,
  className,
}: {
  counts: number[]
  mode: 'dark' | 'light'
  level: number
  auto: boolean
  label: string
  autoLabel?: string
  onChange: (level: number) => void
  className?: string
}) {
  const peak = Math.sqrt(Math.max(1, ...counts))
  const track = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const at = (clientX: number) => {
    const box = track.current!.getBoundingClientRect()
    return clamp(((clientX - box.left) / box.width) * 255)
  }
  const inObject = (i: number) => (mode === 'dark' ? i <= level : i > level)
  const pct = (level / 255) * 100

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div
        ref={track}
        data-testid="gray-track"
        className="relative h-16 w-full touch-none select-none rounded-control border border-line bg-surface-2"
        onPointerDown={(e) => {
          dragging.current = true
          e.currentTarget.setPointerCapture?.(e.pointerId)
          onChange(at(e.clientX))
        }}
        onPointerMove={(e) => {
          if (dragging.current) onChange(at(e.clientX))
        }}
        onPointerUp={() => (dragging.current = false)}
        onPointerCancel={() => (dragging.current = false)}
      >
        <svg aria-hidden viewBox="0 0 256 40" preserveAspectRatio="none" className="absolute inset-0 size-full">
          {counts.map((n, i) =>
            n > 0 ? (
              <rect
                key={i}
                x={i}
                y={40 - (Math.sqrt(n) / peak) * 40}
                width={1}
                height={(Math.sqrt(n) / peak) * 40}
                className={inObject(i) ? 'text-accent' : 'text-fg-muted'}
                fill="currentColor"
              />
            ) : null,
          )}
        </svg>
        <div
          role="slider"
          tabIndex={0}
          aria-label={label}
          aria-orientation="horizontal"
          aria-valuemin={0}
          aria-valuemax={255}
          aria-valuenow={level}
          className="absolute inset-y-0 -ml-3 flex w-6 cursor-ew-resize justify-center outline-none focus-visible:ring-2 focus-visible:ring-accent"
          style={{ left: `${pct}%` }}
          onKeyDown={(e) => {
            const step = e.shiftKey ? 10 : 1
            const next =
              e.key === 'ArrowRight' || e.key === 'ArrowUp'
                ? level + step
                : e.key === 'ArrowLeft' || e.key === 'ArrowDown'
                  ? level - step
                  : e.key === 'Home'
                    ? 0
                    : e.key === 'End'
                      ? 255
                      : null
            if (next === null) return
            e.preventDefault()
            onChange(clamp(next))
          }}
        >
          <span className={cn('h-full w-0.5 bg-fg', auto && 'opacity-60 [background:repeating-linear-gradient(to_bottom,currentColor_0_4px,transparent_4px_8px)]')} />
        </div>
      </div>
      <div className="flex justify-between text-xs tabular-nums text-fg-muted">
        <span>0</span>
        {autoLabel ? <span>{autoLabel}</span> : null}
        <span>255</span>
      </div>
    </div>
  )
}
