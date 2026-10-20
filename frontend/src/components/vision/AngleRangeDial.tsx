import { useRef, type KeyboardEvent, type PointerEvent } from 'react'
import { cn } from '@/lib/cn'

const CX = 110
const CY = 108
const R = 88
const TICKS = [-90, -75, -60, -45, -30, -15, 0, 15, 30, 45, 60, 75, 90]

/** A point of the dial: 0° at the top; a positive angle (counter-clockwise on the picture) goes to the left. */
const at = (angle: number, radius: number): [number, number] => {
  const a = (angle * Math.PI) / 180
  return [CX - radius * Math.sin(a), CY - radius * Math.cos(a)]
}

const arc = (from: number, to: number) => {
  // from the larger angle (left) to the smaller (right), clockwise on the screen
  const [x0, y0] = at(to, R)
  const [x1, y1] = at(from, R)
  return `M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x1} ${y1}`
}

/**
 * The allowed turn of an object (docs/frontend.md §19.5): a half circle with two handles for the least and the most the
 * object may be turned from the way it was taught, and a needle for the turn found now. A turn is counter-clockwise on
 * the picture, so a positive angle is on the left of the dial. Each handle is a slider of its own, for the pointer and
 * for the keys (arrows by 1°, with Shift by 5°).
 */
export function AngleRangeDial({
  value,
  found,
  onChange,
  labels,
  className,
}: {
  value: [number, number]
  /** The turn found on the picture on show; null: none. */
  found?: number | null
  onChange: (next: [number, number]) => void
  /** The names of the two handles: the least and the most turn. */
  labels: [string, string]
  className?: string
}) {
  const svg = useRef<SVGSVGElement>(null)
  const [min, max] = value
  const clamp = (a: number) => Math.max(-90, Math.min(90, Math.round(a)))
  const set = (which: 0 | 1, angle: number) =>
    onChange(which === 0 ? [Math.min(clamp(angle), max), max] : [min, Math.max(clamp(angle), min)])
  const angleAt = (e: PointerEvent) => {
    const r = svg.current!.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * 220 - CX
    const y = ((e.clientY - r.top) / r.height) * 120 - CY
    return (Math.atan2(-x, -y) * 180) / Math.PI
  }
  const onKey = (e: KeyboardEvent, which: 0 | 1) => {
    const step = e.shiftKey ? 5 : 1
    const delta: Record<string, number> = {
      ArrowLeft: step,
      ArrowUp: step,
      ArrowRight: -step,
      ArrowDown: -step,
    }
    if (e.key in delta) {
      e.preventDefault()
      set(which, value[which] + delta[e.key]!)
    }
  }
  return (
    <svg
      ref={svg}
      viewBox="0 0 220 120"
      role="group"
      className={cn('w-full max-w-72 touch-none select-none', className)}
      aria-label={labels.join(' – ')}
    >
      <path
        d={arc(-90, 90)}
        className="fill-none stroke-surface-3"
        strokeWidth={14}
        strokeLinecap="round"
      />
      <path
        d={arc(min, max)}
        className="fill-none stroke-accent"
        strokeWidth={14}
        strokeLinecap="round"
      />
      {TICKS.map((t) => {
        const [x0, y0] = at(t, R + 12)
        const [x1, y1] = at(t, R + (t % 45 === 0 ? 20 : 16))
        return (
          <line
            key={t}
            x1={x0}
            y1={y0}
            x2={x1}
            y2={y1}
            className="stroke-fg-muted"
            strokeWidth={1}
          />
        )
      })}
      {[-90, 0, 90].map((t) => {
        const [x, y] = at(t, R + 30)
        return (
          <text key={t} x={x} y={y + 4} textAnchor="middle" className="fill-fg-muted text-xs">
            {t}°
          </text>
        )
      })}
      {found === null || found === undefined || Math.abs(found) > 90 ? null : (
        <g>
          <line
            x1={CX}
            y1={CY}
            x2={at(found, R - 8)[0]}
            y2={at(found, R - 8)[1]}
            className={cn(found >= min && found <= max ? 'stroke-ok-text' : 'stroke-fail-text')}
            strokeWidth={3}
            strokeLinecap="round"
          />
          <circle cx={CX} cy={CY} r={4} className="fill-fg" />
        </g>
      )}
      {([0, 1] as const).map((which) => {
        const [x, y] = at(value[which], R)
        return (
          <circle
            key={which}
            role="slider"
            tabIndex={0}
            aria-label={labels[which]}
            aria-valuemin={-90}
            aria-valuemax={90}
            aria-valuenow={value[which]}
            aria-valuetext={`${value[which]}°`}
            cx={x}
            cy={y}
            r={11}
            className="cursor-grab fill-surface-1 stroke-accent outline-none focus-visible:stroke-accent-text"
            strokeWidth={3}
            onKeyDown={(e) => onKey(e, which)}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId)
              set(which, angleAt(e))
            }}
            onPointerMove={(e) => e.buttons === 1 && set(which, angleAt(e))}
          />
        )
      })}
    </svg>
  )
}
