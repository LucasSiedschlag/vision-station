import type { Rect } from '@/features/editor/geometry'

/**
 * Gray levels and Otsu's threshold the way OpenCV computes them, so the level the editor shows for the automatic
 * threshold of the `blob` tool is the one the server uses (docs/frontend.md §19.5).
 */

/** OpenCV's `FLT_EPSILON`, the margin its Otsu loop uses to skip a class with (almost) no pixels. */
const FLT_EPSILON = 1.1920929e-7

/** OpenCV's `COLOR_BGR2GRAY`, in its integer arithmetic. */
export const grayOf = (r: number, g: number, b: number): number => (9798 * r + 19235 * g + 3735 * b + 16384) >> 15

/** The 256-bin gray histogram of a region (fractions of the image) of its pixels. */
export function grayHistogram(data: ImageData, [x0, y0, x1, y1]: Rect): number[] {
  const counts = new Array<number>(256).fill(0)
  const px0 = Math.min(data.width - 1, Math.max(0, Math.floor(x0 * data.width)))
  const py0 = Math.min(data.height - 1, Math.max(0, Math.floor(y0 * data.height)))
  const px1 = Math.min(data.width, Math.max(px0 + 1, Math.round(x1 * data.width)))
  const py1 = Math.min(data.height, Math.max(py0 + 1, Math.round(y1 * data.height)))
  const px = data.data
  for (let y = py0; y < py1; y++)
    for (let x = px0, i = (y * data.width + px0) * 4; x < px1; x++, i += 4)
      counts[grayOf(px[i]!, px[i + 1]!, px[i + 2]!)]!++
  return counts
}

/** The level `cv2.threshold(..., THRESH_OTSU)` picks: the first one with the largest variance between the two classes (0 on a flat region). */
export function otsu(counts: number[]): number {
  const total = counts.reduce((a, b) => a + b, 0)
  if (total === 0) return 0
  let mean = 0
  counts.forEach((n, i) => (mean += (i * n) / total))
  let q1 = 0
  let mu1 = 0
  let best = 0
  let level = 0
  for (let i = 0; i < 256; i++) {
    const p = counts[i]! / total
    mu1 *= q1
    q1 += p
    const q2 = 1 - q1
    if (Math.min(q1, q2) < FLT_EPSILON || Math.max(q1, q2) > 1 - FLT_EPSILON) continue
    mu1 = (mu1 + i * p) / q1
    const mu2 = (mean - q1 * mu1) / q2
    const sigma = q1 * q2 * (mu1 - mu2) ** 2
    if (sigma > best) {
      best = sigma
      level = i
    }
  }
  return level
}

/** The share of the pixels the threshold takes as object: `dark` is gray <= level, `light` is gray > level. */
export function objectShare(counts: number[], level: number, mode: 'dark' | 'light'): number {
  const total = counts.reduce((a, b) => a + b, 0)
  if (total === 0) return 0
  const dark = counts.slice(0, level + 1).reduce((a, b) => a + b, 0)
  return (mode === 'dark' ? dark : total - dark) / total
}
