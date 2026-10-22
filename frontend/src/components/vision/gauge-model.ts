import { formatNumber, formatPercent } from '@/lib/number'
import { text } from '@/texts'

/**
 * What a tolerance gauge computes from its numbers (docs/frontend.md §19.3): the scale, whether a sample is on the
 * right side of the limit, the margin in words and in the unit of the measure, and the count of samples on each side.
 */
export type Unit = 'fraction' | 'count' | 'score' | 'px' | 'px2' | 'mm' | 'mm2'
export type Side = 'min' | 'max'

export interface Dot {
  id: string
  kind: 'reference' | 'good' | 'bad'
  /** the sample's name, shown on hover and read by a screen reader */
  name: string
  /** its measured value; null: the tool did not measure it */
  value: number | null
}

export interface Limits {
  min: number | null
  max: number | null
}

/** The scale of a gauge: the range the tool says, or for a count (no natural top) what the data and the limits need. */
export function domainOf(
  unit: Unit,
  range: readonly (number | null)[],
  values: readonly (number | null)[],
): [number, number] {
  const low = range[0] ?? 0
  const top = range[1]
  if (top !== null && top !== undefined) return [low, top]
  const largest = Math.max(0, ...values.filter((v): v is number => v !== null))
  const nice = unit === 'count' ? 5 : unit === 'px2' ? 100 : 1
  return [low, Math.max(nice, Math.ceil((largest * 1.25) / nice) * nice)]
}

/** True when the value stays inside the allowed band. */
export function allowed(value: number, limits: Limits): boolean {
  return (
    (limits.min === null || value >= limits.min) && (limits.max === null || value <= limits.max)
  )
}

/** A good sample outside the band, or a bad one inside it: the dot is ringed. */
export function wrongSide(dot: Dot, limits: Limits): boolean {
  if (dot.value === null || dot.kind === 'reference') return false
  return dot.kind === 'good' ? !allowed(dot.value, limits) : allowed(dot.value, limits)
}

/** Decimals of a measure: whole for what is counted (a count, an area of pixels), one for a physical size, two otherwise. */
export const decimalsOf = (unit: Unit | undefined) =>
  unit === 'count' || unit === 'px2' ? 0 : unit === 'px' || unit === 'mm' || unit === 'mm2' ? 1 : 2

/** The suffix a number is written with: the physical units; a fraction is a percentage and the others have none. */
export const suffixOf = (unit: string | undefined) =>
  ({ px: 'px', px2: 'px²', mm: 'mm', mm2: 'mm²', ΔE: 'ΔE' })[unit ?? ''] ?? undefined

export function formatValue(value: number, unit: Unit): string {
  const text = unit === 'fraction' ? formatPercent(value, 1) : formatNumber(value, decimalsOf(unit))
  const suffix = suffixOf(unit)
  return suffix ? `${text} ${suffix}` : text
}

/** A distance between two values in the unit of the measure: percentage points, never "0,15". */
export function formatDistance(distance: number, unit: Unit): string {
  const d = Math.abs(distance)
  if (unit === 'fraction') return text.editor.gauge.points(formatNumber(d * 100, 1))
  const suffix = suffixOf(unit)
  return `${formatNumber(d, decimalsOf(unit))}${suffix ? ` ${suffix}` : ''}`
}

const known = (dots: Dot[], kind: Dot['kind']) =>
  dots.filter((d) => d.kind === kind && d.value !== null).map((d) => d.value as number)

/** How many good samples are inside the band, and how many bad ones are outside it. */
export function tally(dots: Dot[], limits: Limits) {
  const good = known(dots, 'good')
  const bad = known(dots, 'bad')
  return {
    goodN: good.length,
    goodIn: good.filter((v) => allowed(v, limits)).length,
    badN: bad.length,
    badOut: bad.filter((v) => !allowed(v, limits)).length,
  }
}

/**
 * The margin of each limit in words: how far the worst good sample is from it, and the nearest bad one on the other
 * side. `null` when there is no sample to talk about.
 */
export function marginText(dots: Dot[], limits: Limits, unit: Unit): string | null {
  const g = text.editor.gauge
  const good = known(dots, 'good')
  const bad = known(dots, 'bad')
  const parts: string[] = []
  for (const side of ['min', 'max'] as const) {
    const limit = limits[side]
    if (limit === null) continue
    if (good.length) {
      const worst = side === 'min' ? Math.min(...good) : Math.max(...good)
      const room = side === 'min' ? worst - limit : limit - worst // positive: on the right side
      parts.push(g.worstGood(side, formatValue(worst, unit), formatDistance(room, unit), room >= 0))
    }
    const beyond = side === 'min' ? bad.filter((v) => v < limit) : bad.filter((v) => v > limit)
    if (beyond.length) {
      const nearest = side === 'min' ? Math.max(...beyond) : Math.min(...beyond)
      parts.push(g.nearestBad(side, formatDistance(limit - nearest, unit)))
    }
  }
  return parts.length ? g.margin(parts.join('; ')) : null
}
