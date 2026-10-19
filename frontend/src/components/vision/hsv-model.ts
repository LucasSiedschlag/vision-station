import { rgbToHsv } from '@/features/editor/geometry'

/**
 * The colour range of the color tool in OpenCV's scale (hue 0–179, saturation and value 0–255), and what the
 * picker shows of it (docs/frontend.md §19.4). The job keeps the OpenCV numbers; the display converts, and a
 * value is only written when the person moves its handle (levels never change values, §17).
 */
export interface HsvRange {
  /** `null`: any hue (black, white, grays, found by value alone). `lo > hi` wraps through red. */
  hue: [number, number] | null
  s_min: number
  s_max: number
  v_min: number
  v_max: number
}

export const FULL: HsvRange = { hue: null, s_min: 0, s_max: 255, v_min: 0, v_max: 255 }

/** The range as the tool's parameters hold it, with the defaults of the tool for what is missing. */
export function rangeOf(params: Record<string, unknown>): HsvRange {
  const hue = params.hue
  const num = (v: unknown, d: number) => (typeof v === 'number' ? v : d)
  return {
    hue:
      Array.isArray(hue) && hue.length === 2 && hue.every((v) => typeof v === 'number')
        ? [hue[0] as number, hue[1] as number]
        : null,
    s_min: num(params.s_min, 0),
    s_max: num(params.s_max, 255),
    v_min: num(params.v_min, 0),
    v_max: num(params.v_max, 255),
  }
}

export function inRange(h: number, s: number, v: number, r: HsvRange): boolean {
  if (s < r.s_min || s > r.s_max || v < r.v_min || v > r.v_max) return false
  if (r.hue === null) return true
  const [lo, hi] = r.hue
  return lo <= hi ? h >= lo && h <= hi : h >= lo || h <= hi
}

/** Pixels of an image inside a range: 1 where inside. */
export function maskOf(data: ImageData, r: HsvRange): Uint8Array {
  const out = new Uint8Array(data.width * data.height)
  const px = data.data
  for (let i = 0, p = 0; i < out.length; i++, p += 4) {
    const [h, s, v] = rgbToHsv(px[p]!, px[p + 1]!, px[p + 2]!)
    out[i] = inRange(h, s, v, r) ? 1 : 0
  }
  return out
}

/**
 * The mask of an image on a grid no wider than `maxWidth` (every n-th pixel), to hatch over the image while the
 * range changes: a full-size frame at four a second would be work for nothing, the hatch is stretched anyway.
 */
export function maskGrid(
  data: ImageData,
  r: HsvRange,
  maxWidth = 640,
): { cells: Uint8Array; width: number; height: number } {
  const step = Math.max(1, Math.ceil(data.width / maxWidth))
  const width = Math.ceil(data.width / step)
  const height = Math.ceil(data.height / step)
  const cells = new Uint8Array(width * height)
  const px = data.data
  for (let gy = 0; gy < height; gy++)
    for (let gx = 0; gx < width; gx++) {
      const p = (gy * step * data.width + gx * step) * 4
      const [h, s, v] = rgbToHsv(px[p]!, px[p + 1]!, px[p + 2]!)
      cells[gy * width + gx] = inRange(h, s, v, r) ? 1 : 0
    }
  return { cells, width, height }
}

/** The band a hue range covers, as 1 or 2 intervals of 0–179 (two when it wraps through red). */
export function hueSpans(hue: [number, number]): [number, number][] {
  const [lo, hi] = hue
  return lo <= hi
    ? [[lo, hi]]
    : [
        [lo, 179],
        [0, hi],
      ]
}

/** The hues a range leaves out, as intervals of 0–179. */
export function outsideSpans([lo, hi]: [number, number]): [number, number][] {
  if (lo <= hi)
    return [lo > 0 ? [0, lo - 1] : null, hi < 179 ? [hi + 1, 179] : null].filter(
      (x) => x !== null,
    ) as [number, number][]
  return hi + 1 <= lo - 1 ? [[hi + 1, lo - 1]] : []
}

/** How many of the 180 hues a range covers. */
export function hueWidth(hue: [number, number]): number {
  return hueSpans(hue).reduce((n, [a, b]) => n + b - a + 1, 0)
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

/** The levels of saturation and value one hue tick (2°) is worth: the same share of the whole scale. */
const LEVELS_PER_TICK = 255 / 180

/**
 * *Folga*: the range widened (or narrowed, when negative) by `ticks` hue steps on each side, and by the same
 * share of the scale on saturation and value. It is always taken from the range as the person last set it,
 * never from the previous widening, so moving the slider back and forth does not drift.
 */
export function widen(base: HsvRange, ticks: number): HsvRange {
  const levels = Math.round(ticks * LEVELS_PER_TICK)
  const hue: [number, number] | null = base.hue ? widenHue(base.hue, ticks) : null
  const lim = (lo: number, hi: number): [number, number] => {
    const a = clamp(lo - levels, 0, 255)
    const b = clamp(hi + levels, 0, 255)
    return a <= b ? [a, b] : [Math.round((lo + hi) / 2), Math.round((lo + hi) / 2)]
  }
  const [s_min, s_max] = lim(base.s_min, base.s_max)
  const [v_min, v_max] = lim(base.v_min, base.v_max)
  return { hue, s_min, s_max, v_min, v_max }
}

function widenHue([lo, hi]: [number, number], ticks: number): [number, number] {
  const width = hueWidth([lo, hi])
  if (ticks >= 0 && width + 2 * ticks >= 180) return [0, 179]
  if (ticks < 0 && width + 2 * ticks < 1) {
    const mid = Math.round((lo + (lo <= hi ? (hi - lo) / 2 : (hi + 180 - lo) / 2)) % 180)
    return [mid, mid]
  }
  return [(((lo - ticks) % 180) + 180) % 180, (((hi + ticks) % 180) + 180) % 180]
}

/** How many pixels have each of the 180 hues, for the saturated, not-too-dark ones (grays have no hue). */
export function hueHistogram(pixels: [number, number, number][]): number[] {
  const bins = new Array<number>(180).fill(0)
  for (const [r, g, b] of pixels) {
    const [h, s, v] = rgbToHsv(r, g, b)
    if (s >= 40 && v >= 40) bins[h]!++
  }
  return bins
}

/** A hue, in degrees on the 0–359 circle (a tick is 2°). */
export const degrees = (tick: number) => tick * 2
export const ticks = (deg: number) => Math.round(deg / 2) % 180

/** Saturation and value as a percentage, and back. The percentage is only for display and typing. */
export const toPercent = (level: number) => Math.round((level / 255) * 100)
export const fromPercent = (pct: number) => Math.round((clamp(pct, 0, 100) / 100) * 255)

/** The colour under the pointer in HSV: degrees and percent, or OpenCV's numbers at the Especialista level (§17). */
export function describeHsv([r, g, b]: [number, number, number], exact: boolean): string {
  const [h, s, v] = rgbToHsv(r, g, b)
  return exact ? `HSV ${h}, ${s}, ${v}` : `HSV ${degrees(h)}°, ${toPercent(s)} %, ${toPercent(v)} %`
}
