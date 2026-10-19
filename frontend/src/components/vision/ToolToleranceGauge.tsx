import { useId } from 'react'
import { Slider as AriaSlider, SliderThumb, SliderTrack } from 'react-aria-components'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { NumberField } from '@/components/ui/number-field'
import { thumbClasses } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import {
  domainOf,
  formatDistance,
  formatValue,
  marginText,
  tally,
  wrongSide,
  type Dot,
  type Limits,
  type Side,
  type Unit,
} from './gauge-model'

/** A proposal from `POST /api/editor/suggest/limits`, as far as the gauge needs it. */
export interface GaugeProposal {
  side: Side
  proposed: number | null
  reason: '' | 'few_good' | 'overlap' | 'bounds'
  margin_good: number | null
  margin_bad: number | null
}

export interface GaugeLimit {
  /** The limit the person may switch off (a parameter that can be empty). */
  optional: boolean
  /** What the parameter accepts. */
  bounds: readonly [number | null, number | null]
}

/**
 * One gauge per criterion of a tool (docs/frontend.md §19.3): the allowed band, the limits as draggable thumbs with a
 * number box each, the current value as a needle, the samples as dots (*Boas* above the band, *Ruins* below it), the
 * margin in words and the proposal of *Ajustar pelas amostras* with *Aplicar* and *Descartar*. The needle jumps to
 * each measurement; nothing here animates.
 */
export function ToolToleranceGauge({
  label,
  unit,
  range,
  limits,
  limitInfo,
  current,
  currentPassed,
  dots,
  selected,
  proposals,
  canPropose,
  proposing,
  stale,
  onSelect,
  onLimit,
  onPropose,
  onApply,
  onDiscard,
}: {
  label: string
  unit: Unit
  /** `[low, high]` from the tool's criterion; `null` high: no natural top (a count) */
  range: readonly (number | null)[]
  limits: Limits
  /** which limits the criterion has, and what each accepts */
  limitInfo: Partial<Record<Side, GaugeLimit>>
  /** the live or frozen value; null: not measured (loading, anchor not found, camera lost) */
  current: number | null
  currentPassed?: boolean
  dots: Dot[]
  /** the id of the sample shown in the image */
  selected?: string | null
  proposals: GaugeProposal[]
  /** false: *Ajustar pelas amostras* is off, and `reason` says why */
  canPropose: { ok: boolean; reason: string }
  proposing?: boolean
  /** the dots were measured with another draft: they are being measured again */
  stale?: boolean
  onSelect: (id: string) => void
  onLimit: (side: Side, value: number | null) => void
  onPropose: () => void
  onApply: (proposal: GaugeProposal) => void
  onDiscard: () => void
}) {
  const g = text.editor.gauge
  const id = useId()
  const sides = (['min', 'max'] as const).filter((side) => limitInfo[side])
  const values = [
    ...dots.map((d) => d.value),
    current,
    limits.min,
    limits.max,
    ...proposals.map((p) => p.proposed),
  ]
  const [low, high] = domainOf(unit, range, values)
  const percent = (v: number) =>
    `${Math.min(100, Math.max(0, ((v - low) / (high - low || 1)) * 100))}%`
  const step = unit === 'count' ? 1 : 0.01
  const counts = tally(dots, limits)
  const margin = marginText(dots, limits, unit)
  const hasSamples = counts.goodN + counts.badN > 0
  const active = sides.filter((side) => limits[side] !== null)
  const thumbs = active.map((side) => limits[side] as number)
  const limitName = (side: Side) => (side === 'min' ? g.limitMin : g.limitMax)
  const spoken = g.valueText(
    active
      .map((side) => `${limitName(side)} ${formatValue(limits[side] as number, unit)}`)
      .join(', ') || g.notMeasured,
    current === null ? g.notMeasured : formatValue(current, unit),
    counts.goodIn,
    counts.goodN,
  )
  const row = (kind: 'good' | 'bad') => (
    <div className="relative h-5" aria-label={kind === 'good' ? g.good : g.bad} role="group">
      {dots
        .filter((d) => d.kind === kind && d.value !== null)
        .map((d) => (
          <button
            key={d.id}
            type="button"
            title={`${d.name}: ${formatValue(d.value as number, unit)}`}
            aria-label={`${d.name}: ${formatValue(d.value as number, unit)}`}
            aria-pressed={selected === d.id}
            onClick={() => onSelect(d.id)}
            className={cn(
              'absolute top-1/2 grid size-4 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-pill text-xs leading-none',
              kind === 'good' ? 'bg-fg text-surface-0' : 'text-fg',
              wrongSide(d, limits) && 'ring-2 ring-fail',
              selected === d.id && 'outline-2 outline-offset-2 outline-accent-text',
            )}
            style={{ left: percent(d.value as number) }}
          >
            {kind === 'bad' ? '✕' : null}
          </button>
        ))}
    </div>
  )
  const reference = dots.find((d) => d.kind === 'reference' && d.value !== null)

  return (
    <section
      aria-label={label}
      className="flex flex-col gap-2 rounded-control border border-line p-3"
    >
      <header className="flex items-baseline justify-between gap-3">
        <h4 className="text-sm font-medium">{label}</h4>
        <span className="flex items-center gap-2 font-mono text-sm tabular-nums">
          {current === null ? (
            <span className="text-fg-muted">{g.notMeasured}</span>
          ) : (
            <>
              {formatValue(current, unit)}
              {currentPassed === undefined ? null : currentPassed ? (
                <CheckCircle2 aria-label="✓" className="size-4 text-ok-text" />
              ) : (
                <XCircle aria-label="✕" className="size-4 text-fail-text" />
              )}
            </>
          )}
        </span>
      </header>

      <div className="flex gap-2">
        <span className="w-14 shrink-0 self-center text-xs text-fg-muted">{g.good}</span>
        <div className="flex-1">{row('good')}</div>
      </div>
      <div className="flex gap-2">
        <span className="w-14 shrink-0" aria-hidden />
        <AriaSlider
          aria-label={label}
          aria-describedby={`${id}-spoken`}
          value={thumbs}
          minValue={low}
          maxValue={high}
          step={step}
          isDisabled={active.length === 0}
          onChange={(v) => {
            const next = Array.isArray(v) ? v : [v]
            active.forEach((side, i) => onLimit(side, next[i] as number))
          }}
          className="relative flex-1"
        >
          <SliderTrack className="relative h-8 w-full touch-none">
            {({ state }) => (
              <>
                <div className="absolute top-1/2 h-2 w-full -translate-y-1/2 rounded-pill border border-line" />
                <div
                  className="absolute top-1/2 h-2 -translate-y-1/2 rounded-pill bg-surface-3"
                  style={{
                    left: limits.min === null ? '0%' : percent(limits.min),
                    right: limits.max === null ? '0%' : `calc(100% - ${percent(limits.max)})`,
                  }}
                />
                {reference ? (
                  <span
                    title={`${g.reference}: ${formatValue(reference.value as number, unit)}`}
                    className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-pill bg-accent"
                    style={{ left: percent(reference.value as number) }}
                  />
                ) : null}
                {current !== null ? (
                  <span
                    aria-hidden
                    className={cn(
                      'absolute -top-1 -translate-x-1/2 text-xs leading-none',
                      currentPassed === false ? 'text-fail-text' : 'text-ok-text',
                    )}
                    style={{ left: percent(current) }}
                  >
                    ▼
                  </span>
                ) : null}
                {proposals
                  .filter((p) => p.proposed !== null)
                  .map((p) => (
                    <span
                      key={p.side}
                      aria-hidden
                      className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-pill border-2 border-dashed border-accent-text"
                      style={{ left: percent(p.proposed as number) }}
                    />
                  ))}
                {state.values.map((_, i) => (
                  <SliderThumb
                    key={i}
                    index={i}
                    aria-label={limitName(active[i] as Side)}
                    className={thumbClasses}
                  />
                ))}
              </>
            )}
          </SliderTrack>
        </AriaSlider>
      </div>
      <div className="flex gap-2">
        <span className="w-14 shrink-0 self-center text-xs text-fg-muted">{g.bad}</span>
        <div className="flex-1">{row('bad')}</div>
      </div>

      <span id={`${id}-spoken`} className="sr-only">
        {spoken}
      </span>

      <div className="flex flex-wrap gap-4">
        {sides.map((side) => {
          const info = limitInfo[side] as GaugeLimit
          const value = limits[side]
          return (
            <div key={side} className="flex items-end gap-2">
              {info.optional ? (
                <Switch
                  checked={value !== null}
                  onCheckedChange={(on) =>
                    onLimit(
                      side,
                      on
                        ? (proposals.find((p) => p.side === side)?.proposed ??
                            (side === 'min' ? low : high))
                        : null,
                    )
                  }
                  label={side === 'min' ? g.useMin : g.useMax}
                />
              ) : null}
              {value !== null ? (
                <NumberField
                  aria-label={limitName(side)}
                  className="w-28"
                  value={value}
                  onChange={(v) => v !== null && onLimit(side, v)}
                  min={info.bounds[0] ?? undefined}
                  max={info.bounds[1] ?? undefined}
                  step={step}
                  decimals={unit === 'count' ? 0 : 4}
                  percent={unit === 'fraction'}
                />
              ) : null}
            </div>
          )
        })}
      </div>

      {hasSamples ? (
        <>
          {margin ? <p className="text-sm">{margin}</p> : null}
          <p className="text-sm text-fg-muted">
            {g.tally(counts.goodIn, counts.goodN, counts.badOut, counts.badN)}
          </p>
        </>
      ) : (
        <p className="text-sm text-fg-muted">{g.onlyReference}</p>
      )}
      {stale ? <p className="text-xs text-fg-muted">{g.stale}</p> : null}

      {proposals.map((p) => (
        <p key={p.side} role="status" className="text-sm">
          {p.proposed === null
            ? p.reason === 'overlap'
              ? g.overlap
              : p.reason === 'few_good'
                ? g.fewGood(3)
                : g.bounds
            : g.proposal(
                p.side,
                formatValue(p.proposed, unit),
                formatDistance(p.margin_good ?? 0, unit),
                p.margin_bad === null ? null : formatDistance(p.margin_bad, unit),
              )}
        </p>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        {proposals.length ? (
          <>
            {proposals.some((p) => p.proposed !== null) ? (
              <Button
                variant="primary"
                onClick={() =>
                  proposals.filter((p) => p.proposed !== null).forEach((p) => onApply(p))
                }
              >
                {g.apply}
              </Button>
            ) : null}
            <Button variant="ghost" onClick={onDiscard}>
              {g.discard}
            </Button>
          </>
        ) : (
          <Button
            variant="secondary"
            loading={proposing}
            aria-disabled={!canPropose.ok || undefined}
            title={canPropose.ok ? undefined : canPropose.reason}
            onClick={canPropose.ok ? onPropose : undefined}
          >
            {g.adjust}
          </Button>
        )}
        {!canPropose.ok && !proposals.length ? (
          <span className="text-xs text-fg-muted">{canPropose.reason}</span>
        ) : null}
      </div>
    </section>
  )
}
