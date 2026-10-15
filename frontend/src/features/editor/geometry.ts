/** Regions as the jobs store them: [x0, y0, x1, y1] as fractions (0–1) of the frame or of the anchor (docs/frontend.md §10). */
export type Rect = [number, number, number, number]
export type Handle = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))

/** Four decimals: about 0.2 px on a 4K frame, and a job file that stays readable. */
export const round = (v: number) => Math.round(v * 10_000) / 10_000

export function normalize([a, b, c, d]: Rect): Rect {
  return [
    round(clamp01(Math.min(a, c))),
    round(clamp01(Math.min(b, d))),
    round(clamp01(Math.max(a, c))),
    round(clamp01(Math.max(b, d))),
  ]
}

/** A rectangle from two corners, kept inside the image. */
export function fromCorners(x0: number, y0: number, x1: number, y1: number): Rect {
  return normalize([x0, y0, x1, y1])
}

/** Moved by (dx, dy), stopping at the edges without changing size. */
export function move([x0, y0, x1, y1]: Rect, dx: number, dy: number): Rect {
  const w = x1 - x0
  const h = y1 - y0
  const nx = Math.min(1 - w, Math.max(0, x0 + dx))
  const ny = Math.min(1 - h, Math.max(0, y0 + dy))
  return [round(nx), round(ny), round(nx + w), round(ny + h)]
}

/** One edge or corner dragged to (x, y); the opposite side stays. Never smaller than `min` (a fraction). */
export function resize(rect: Rect, handle: Handle, x: number, y: number, min = 0.005): Rect {
  let [x0, y0, x1, y1] = rect
  const px = clamp01(x)
  const py = clamp01(y)
  if (handle.includes('w')) x0 = Math.min(px, x1 - min)
  if (handle.includes('e')) x1 = Math.max(px, x0 + min)
  if (handle.includes('n')) y0 = Math.min(py, y1 - min)
  if (handle.includes('s')) y1 = Math.max(py, y0 + min)
  return normalize([x0, y0, x1, y1])
}

/** A region stored relative to the anchor, placed on the frame. */
export function anchorToFrame([x0, y0, x1, y1]: Rect, [ax0, ay0, ax1, ay1]: Rect): Rect {
  const w = ax1 - ax0
  const h = ay1 - ay0
  return [round(ax0 + x0 * w), round(ay0 + y0 * h), round(ax0 + x1 * w), round(ay0 + y1 * h)]
}

/** A region drawn on the frame, stored relative to the anchor. */
export function frameToAnchor([x0, y0, x1, y1]: Rect, [ax0, ay0, ax1, ay1]: Rect): Rect {
  const w = ax1 - ax0 || 1
  const h = ay1 - ay0 || 1
  return [
    round((x0 - ax0) / w),
    round((y0 - ay0) / h),
    round((x1 - ax0) / w),
    round((y1 - ay0) / h),
  ]
}

export function inside(rect: Rect, x: number, y: number): boolean {
  return x >= rect[0] && x <= rect[2] && y >= rect[1] && y <= rect[3]
}

/** Size and position in pixels of an image, for the readouts and the screen reader. */
export function describe([x0, y0, x1, y1]: Rect, width: number, height: number): string {
  const px = (v: number, n: number) => Math.round(v * n)
  return `x ${px(x0, width)}, y ${px(y0, height)}, ${px(x1 - x0, width)} × ${px(y1 - y0, height)} px`
}

/** OpenCV's HSV (H 0–179, S and V 0–255), the scale the color tool uses. */
export function rgbToHsv(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  let h = 0
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
  }
  const deg = (h * 60 + 360) % 360
  return [Math.round(deg / 2) % 180, max === 0 ? 0 : Math.round((d / max) * 255), max]
}

/**
 * A hue range for the color tool from sampled pixels: the hues of the saturated ones, around their circular
 * middle, wide enough for 90 % of them (at least ±8). Gray pixels are ignored; null if there are too few.
 */
export function suggestHue(
  pixels: [number, number, number][],
): { hue: [number, number]; s_min: number; v_min: number } | null {
  const hsv = pixels.map(([r, g, b]) => rgbToHsv(r, g, b)).filter(([, s, v]) => s >= 60 && v >= 40)
  if (hsv.length < Math.max(10, pixels.length * 0.1)) return null
  const angles = hsv.map(([h]) => (h / 180) * 2 * Math.PI)
  const mean = Math.atan2(
    angles.reduce((a, t) => a + Math.sin(t), 0),
    angles.reduce((a, t) => a + Math.cos(t), 0),
  )
  const centre = Math.round(((((mean / (2 * Math.PI)) * 180) % 180) + 180) % 180)
  const dist = hsv
    .map(([h]) => Math.min(Math.abs(h - centre), 180 - Math.abs(h - centre)))
    .sort((a, b) => a - b)
  const half = Math.max(8, dist[Math.floor(dist.length * 0.9)] ?? 8)
  const sorted = (i: number) => hsv.map((p) => p[i]!).sort((a, b) => a - b)
  const pct = (list: number[], q: number) => list[Math.floor(list.length * q)] ?? 0
  return {
    hue: [(centre - half + 180) % 180, (centre + half) % 180],
    s_min: Math.max(0, Math.round(pct(sorted(1), 0.05) * 0.8)),
    v_min: Math.max(0, Math.round(pct(sorted(2), 0.05) * 0.8)),
  }
}
