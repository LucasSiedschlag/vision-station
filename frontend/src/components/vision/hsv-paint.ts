/**
 * The real colours behind the colour picker's bars (docs/frontend.md §19.4), painted on small canvases that the
 * page stretches: the bars show what a handle will take in, not a stand-in gradient. All in OpenCV's scale.
 */

/** OpenCV's H (0–179), S and V (0–255) as 0–255 red, green and blue. */
export function hsvToRgb(h: number, s: number, v: number): [number, number, number] {
  const hue = (h / 180) * 6
  const sat = s / 255
  const c = v * sat
  const x = c * (1 - Math.abs((hue % 2) - 1))
  const m = v - c
  const sector = Math.floor(hue) % 6
  const [r, g, b] = ([
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ][sector] ?? [c, 0, x]) as [number, number, number]
  return [Math.round(r + m), Math.round(g + m), Math.round(b + m)]
}

/** A bar of `width` columns, each coloured by `colour(i / (width - 1))`. */
export function paintBar(
  canvas: HTMLCanvasElement,
  width: number,
  colour: (at: number) => [number, number, number],
) {
  canvas.width = width
  canvas.height = 1
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const image = ctx.createImageData(width, 1)
  for (let i = 0; i < width; i++) {
    const [r, g, b] = colour(i / (width - 1))
    image.data.set([r, g, b, 255], i * 4)
  }
  ctx.putImageData(image, 0, 0)
}

export const paintHue = (c: HTMLCanvasElement, s: number, v: number) =>
  paintBar(c, 180, (at) => hsvToRgb(at * 179, s, v))
export const paintSaturation = (c: HTMLCanvasElement, h: number, v: number) =>
  paintBar(c, 64, (at) => hsvToRgb(h, at * 255, v))
export const paintValue = (c: HTMLCanvasElement, h: number, s: number) =>
  paintBar(c, 64, (at) => hsvToRgb(h, s, at * 255))

/** The colour of the overlay token (`--ov-mask`) as red, green and blue, for the mask drawn on a canvas. */
export function tokenRgb(name: string, from: Element): [number, number, number] {
  const raw = getComputedStyle(from).getPropertyValue(name).trim()
  const hex = /^#([0-9a-f]{6})$/i.exec(raw)?.[1]
  if (!hex) return [230, 25, 154]
  const n = parseInt(hex, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
