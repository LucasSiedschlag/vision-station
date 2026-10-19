import { CheckCircle2, XCircle } from 'lucide-react'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import { domainOf, formatDistance, formatValue, type Limits, type Unit } from './gauge-model'

/**
 * A tolerance gauge of a result that was recorded (docs/frontend.md §7.4): the allowed band, the value the tool
 * measured as a needle and the limits it had then, in words. It is a picture of that moment: nothing in it can be moved.
 */
export function FrozenGauge({
  label,
  unit,
  range,
  limits,
  value,
  passed,
}: {
  label: string
  unit: Unit
  range: readonly (number | null)[]
  limits: Limits
  value: number
  passed: boolean
}) {
  const g = text.results.gauge
  const [low, high] = domainOf(unit, range, [value, limits.min, limits.max])
  const at = (v: number) =>
    `${((Math.min(high, Math.max(low, v)) - low) / (high - low || 1)) * 100}%`
  const from =
    limits.min === null ? 0 : ((Math.max(low, limits.min) - low) / (high - low || 1)) * 100
  const to =
    limits.max === null ? 100 : ((Math.min(high, limits.max) - low) / (high - low || 1)) * 100
  // how far the value is from the nearest edge it respects or breaks, in the unit of the measure
  const edges = [limits.min, limits.max].filter((v): v is number => v !== null)
  const room = edges.length
    ? Math.min(...edges.map((e) => (e === limits.min ? value - e : e - value)))
    : null
  const words = [
    limits.min === null ? null : g.min(formatValue(limits.min, unit)),
    limits.max === null ? null : g.max(formatValue(limits.max, unit)),
    room === null
      ? null
      : room >= 0
        ? g.inside(formatDistance(room, unit))
        : g.outside(formatDistance(room, unit)),
  ].filter(Boolean)
  return (
    <section
      aria-label={label}
      className="flex flex-col gap-1 rounded-control border border-line p-2"
    >
      <header className="flex items-baseline justify-between gap-3">
        <h4 className="text-sm font-medium">{label}</h4>
        <span className="flex items-center gap-1 font-mono text-sm tabular-nums">
          {formatValue(value, unit)}
          {passed ? (
            <CheckCircle2 aria-label="✓" className="size-4 text-ok-text" />
          ) : (
            <XCircle aria-label="✕" className="size-4 text-fail-text" />
          )}
        </span>
      </header>
      <div role="img" aria-label={words.join(', ')} className="relative h-4">
        <div className="absolute top-1/2 h-1.5 w-full -translate-y-1/2 rounded-pill bg-surface-3" />
        <div
          className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-pill bg-accent"
          style={{ left: `${from}%`, width: `${Math.max(0, to - from)}%` }}
        />
        <div
          className={cn(
            'absolute top-0 h-4 w-1 -translate-x-1/2 rounded-pill',
            passed ? 'bg-ok-text' : 'bg-fail-text',
          )}
          style={{ left: at(value) }}
        />
      </div>
      <p className="text-xs text-fg-muted">{words.join(' · ')}</p>
    </section>
  )
}
