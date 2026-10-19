import { Eraser, Minus, Pipette, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { editorApi } from '@/api/queries/editor'
import { HueBar } from '@/components/vision/HueBar'
import {
  degrees,
  fromPercent,
  hueHistogram,
  rangeOf,
  ticks,
  toPercent,
  widen,
  type HsvRange,
} from '@/components/vision/hsv-model'
import { paintSaturation, paintValue } from '@/components/vision/hsv-paint'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NumberField } from '@/components/ui/number-field'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { sample } from './image'
import { useImageAids } from './image-aids'
import type { WidgetProps } from './widgets'

const t = text.editor.colour
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
/** *Folga* goes from narrowing the range by 10 hues to widening it by 20 (2° each). */
const MARGIN = { min: -10, max: 20 }

interface Proposal {
  range: HsvRange
  kept: number
  leak: number | null
}

/**
 * Colour as a task done on the image (docs/frontend.md §19.4): drag over the image to sample the colour (*incluir*)
 * or what must stay out (*excluir*), look at the proposed range, apply it, then widen or narrow it all together
 * with *Folga*. The hue bar, the saturation and value bars and the hatched mask on the image show what the range
 * takes in. It owns `hue`, `s_min`, `s_max`, `v_min` and `v_max`; the job keeps OpenCV's numbers and a value is only
 * written when its handle moves, whatever the unit it is shown in (§17).
 */
export function HsvRangePicker({ values, patch, level, error }: WidgetProps) {
  const aids = useImageAids()
  const range = useMemo(() => rangeOf(values), [values])
  // Folga is taken from the range as it was last set by hand; a range that changed from outside (undo, a proposal) is the new base
  const [fold, setFold] = useState({ base: range, margin: 0 })
  const current = same(widen(fold.base, fold.margin), range) ? fold : { base: range, margin: 0 }
  const [maskOn, setMaskOn] = useState(true)
  const [samples, setSamples] = useState<{ include: string[]; exclude: string[] }>({
    include: [],
    exclude: [],
  })
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [asking, setAsking] = useState(false)

  const rangeKey = JSON.stringify(range)
  const showMask = aids?.showMask
  useEffect(() => {
    showMask?.(maskOn ? (JSON.parse(rangeKey) as HsvRange) : null)
    return () => showMask?.(null)
  }, [showMask, maskOn, rangeKey])

  /** Writes only what differs from the job, so a value nobody moved is never rewritten from its rounded display. */
  const write = (next: HsvRange, margin = 0) => {
    const changes: Record<string, unknown> = {}
    if (!same(next.hue, range.hue)) changes.hue = next.hue ?? undefined
    for (const key of ['s_min', 's_max', 'v_min', 'v_max'] as const)
      if (next[key] !== range[key]) changes[key] = next[key]
    if (Object.keys(changes).length > 0) patch(changes)
    setFold({ base: margin === 0 ? next : current.base, margin })
  }

  const framePixels = aids?.pixels
  const region = aids?.region
  const hasHue = range.hue !== null
  const histogram = useMemo(
    () =>
      framePixels && hasHue ? hueHistogram(sample(framePixels, region ?? [0, 0, 1, 1])) : undefined,
    [framePixels, region, hasHue],
  )

  const take = async (mode: 'include' | 'exclude') => {
    if (!aids) return
    if (aids.sampling === mode) return aids.cancelSample()
    const png = await aids.sample(mode)
    if (!png) return
    const next = { ...samples, [mode]: [...samples[mode], png] }
    setSamples(next)
    if (next.include.length === 0) return toast.info(t.markColourFirst)
    setAsking(true)
    try {
      const found = await editorApi.suggestColour(next.include, next.exclude)
      if (!found.ok) return void toast.error(found.message ?? t.noProposal)
      setProposal({
        range: {
          hue: found.hue ? ([found.hue[0], found.hue[1]] as [number, number]) : null,
          s_min: found.s_min,
          s_max: found.s_max,
          v_min: found.v_min,
          v_max: found.v_max,
        },
        kept: found.kept,
        leak: found.leak ?? null,
      })
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setAsking(false)
    }
  }

  const exact = level >= 3
  const unitMax = exact ? 255 : 100
  const toUnit = (v: number) => (exact ? v : toPercent(v))
  const fromUnit = (v: number) => (exact ? v : fromPercent(v))
  /** A two-thumb slider's new pair: only the thumb that moved is written. */
  const pair = (key: 's' | 'v') => (next: number[]) => {
    const lo = `${key}_min` as const
    const hi = `${key}_max` as const
    const moved: HsvRange = { ...range }
    if (next[0] !== toUnit(range[lo])) moved[lo] = fromUnit(next[0]!)
    if (next[1] !== toUnit(range[hi])) moved[hi] = fromUnit(next[1]!)
    write(moved)
  }
  const middleHue = range.hue ? range.hue[0] : 0
  const paintS = useCallback(
    (c: HTMLCanvasElement) =>
      paintSaturation(c, middleHue, Math.round((range.v_min + range.v_max) / 2)),
    [middleHue, range.v_min, range.v_max],
  )
  const paintV = useCallback(
    (c: HTMLCanvasElement) => paintValue(c, middleHue, Math.round((range.s_min + range.s_max) / 2)),
    [middleHue, range.s_min, range.s_max],
  )
  const hue = range.hue

  return (
    <fieldset className="flex flex-col gap-3 rounded-control border border-line p-3">
      <legend className="px-1 text-sm font-medium">{t.title}</legend>
      {aids ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant={aids.sampling === 'include' ? 'primary' : 'secondary'}
            aria-pressed={aids.sampling === 'include'}
            onClick={() => void take('include')}
            disabled={asking}
          >
            <Pipette aria-hidden className="size-4" />
            <Plus aria-hidden className="size-3" />
            {t.include}
          </Button>
          <Button
            variant={aids.sampling === 'exclude' ? 'primary' : 'secondary'}
            aria-pressed={aids.sampling === 'exclude'}
            onClick={() => void take('exclude')}
            disabled={asking || samples.include.length === 0}
          >
            <Pipette aria-hidden className="size-4" />
            <Minus aria-hidden className="size-3" />
            {t.exclude}
          </Button>
          {samples.include.length + samples.exclude.length > 0 ? (
            <Button
              variant="ghost"
              onClick={() => {
                setSamples({ include: [], exclude: [] })
                setProposal(null)
              }}
            >
              <Eraser aria-hidden className="size-4" />
              {t.clear(samples.include.length, samples.exclude.length)}
            </Button>
          ) : null}
          {aids.sampling ? (
            <Badge tone="busy">{aids.sampling === 'include' ? t.dragInclude : t.dragExclude}</Badge>
          ) : null}
        </div>
      ) : null}
      {proposal ? (
        <div
          role="status"
          className="flex flex-col gap-2 rounded-control border border-dashed border-accent-text p-2"
        >
          <p className="text-sm">{t.proposed(summary(proposal.range, exact))}</p>
          <p className="text-xs text-fg-muted">
            {t.keeps(formatNumber(proposal.kept * 100, 0))}
            {proposal.leak !== null ? ` ${t.leaves(formatNumber(proposal.leak * 100, 0))}` : ''}
          </p>
          <div className="flex gap-2">
            <Button
              variant="primary"
              onClick={() => {
                write(proposal.range)
                setProposal(null)
              }}
            >
              {t.apply}
            </Button>
            <Button variant="ghost" onClick={() => setProposal(null)}>
              {t.discard}
            </Button>
          </div>
        </div>
      ) : null}

      <Switch
        checked={hue === null}
        onCheckedChange={(any) => write({ ...range, hue: any ? null : [0, 179] })}
        label={t.anyHue}
        hint={t.anyHueHint}
      />
      {hue ? (
        <div className="flex flex-col gap-1">
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-sm font-medium">{t.hue}</span>
            <span className="font-mono text-sm tabular-nums text-fg-muted">
              {degrees(hue[0])}° – {degrees(hue[1])}°{exact ? ` (${hue[0]} – ${hue[1]})` : ''}
            </span>
          </div>
          <HueBar
            value={hue}
            ghost={proposal?.range.hue ?? null}
            histogram={histogram}
            saturation={Math.round((range.s_min + range.s_max) / 2)}
            brightness={Math.round((range.v_min + range.v_max) / 2)}
            labels={[t.hueFrom, t.hueTo]}
            onChange={(next) => write({ ...range, hue: next })}
          />
          <div className="flex gap-3">
            {([0, 1] as const).map((i) => (
              <NumberField
                key={i}
                aria-label={i === 0 ? t.hueFrom : t.hueTo}
                value={degrees(hue[i])}
                min={0}
                max={358}
                step={2}
                decimals={0}
                unit="°"
                className="w-32"
                onChange={(deg) => {
                  if (deg === null) return
                  const next: [number, number] = [hue[0], hue[1]]
                  next[i] = ticks(deg)
                  write({ ...range, hue: next })
                }}
              />
            ))}
          </div>
        </div>
      ) : null}
      <Slider
        label={t.saturation}
        thumbLabels={[t.saturationMin, t.saturationMax]}
        value={[toUnit(range.s_min), toUnit(range.s_max)]}
        onChange={pair('s')}
        min={0}
        max={unitMax}
        unit={exact ? undefined : '%'}
        decimals={0}
        paint={paintS}
        fields
      />
      <Slider
        label={t.brightness}
        thumbLabels={[t.brightnessMin, t.brightnessMax]}
        value={[toUnit(range.v_min), toUnit(range.v_max)]}
        onChange={pair('v')}
        min={0}
        max={unitMax}
        unit={exact ? undefined : '%'}
        decimals={0}
        paint={paintV}
        fields
      />
      <Slider
        label={t.margin}
        value={[degrees(current.margin)]}
        onChange={([deg]) => {
          const margin = ticks(deg!)
          write(widen(current.base, margin), margin)
        }}
        min={degrees(MARGIN.min)}
        max={degrees(MARGIN.max)}
        step={2}
        decimals={0}
        unit="°"
      />
      <p className="text-xs text-fg-muted">{t.marginHint}</p>
      {aids ? <Switch checked={maskOn} onCheckedChange={setMaskOn} label={t.mask} /> : null}
      {error ? (
        <p role="alert" className="text-xs text-fail-text">
          {error}
        </p>
      ) : null}
    </fieldset>
  )
}

/** A range in words: "matiz 200°–230°, saturação 45–88 %, brilho 62–100 %" (OpenCV's numbers at the Especialista level). */
function summary(r: HsvRange, exact: boolean): string {
  const unit = (v: number) => (exact ? String(v) : String(toPercent(v)))
  const pct = exact ? '' : ' %'
  const hue = r.hue
    ? `${t.hue.toLowerCase()} ${degrees(r.hue[0])}°–${degrees(r.hue[1])}°`
    : t.anyHue.toLowerCase()
  return `${hue}, ${t.saturation.toLowerCase()} ${unit(r.s_min)}–${unit(r.s_max)}${pct}, ${t.brightness.toLowerCase()} ${unit(r.v_min)}–${unit(r.v_max)}${pct}`
}
