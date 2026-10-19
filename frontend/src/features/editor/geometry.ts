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

const SHIFT = 12
const half = 1 << (SHIFT - 1)
const rint = (x: number) => {
  const f = Math.floor(x)
  const d = x - f
  return d < 0.5 ? f : d > 0.5 ? f + 1 : f % 2 === 0 ? f : f + 1 // to nearest, ties to even: cv::saturate_cast
}
const sdiv = [0, ...Array.from({ length: 255 }, (_, i) => rint((255 << SHIFT) / (i + 1)))]
const hdiv = [0, ...Array.from({ length: 255 }, (_, i) => rint((180 << SHIFT) / (6 * (i + 1))))]

/**
 * OpenCV's HSV (H 0–179, S and V 0–255), the scale the color tool uses, in the same integer arithmetic as
 * `cv2.cvtColor` for 8-bit images, so a mask drawn here is the mask the tool computes (scripts/make_hsv_fixture.py).
 */
export function rgbToHsv(r: number, g: number, b: number): [number, number, number] {
  const v = Math.max(r, g, b)
  const diff = v - Math.min(r, g, b)
  if (diff === 0) return [0, 0, v]
  const s = (diff * sdiv[v]! + half) >> SHIFT
  let h = v === r ? g - b : v === g ? b - r + 2 * diff : r - g + 4 * diff
  h = (h * hdiv[diff]! + half) >> SHIFT
  return [h < 0 ? h + 180 : h, s, v]
}
