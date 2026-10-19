/**
 * Zoom and pan of the image workspace (docs/frontend.md §10.2). The view is the image scaled by `z` (1 = fitted in
 * its box) and moved so that its top-left corner is at (`x`, `y`) in pixels of the box. The picture is never smaller
 * than the box and never moves off it.
 */
export interface View {
  z: number
  x: number
  y: number
}

export interface Box {
  width: number
  height: number
}

export const FIT: View = { z: 1, x: 0, y: 0 }
/** The most the image is magnified: 16 screen pixels for each of its pixels. */
export const MAX_SCALE = 16
/** The mini-map appears above 200 % and the pixel grid above 800 % (screen pixels per image pixel, as a ratio). */
export const MINIMAP_FROM = 2
export const GRID_FROM = 8

/** Screen pixels per image pixel at this zoom: 1 is the image at 100 %. */
export const scaleOf = (z: number, box: Box, imageWidth: number) => (z * box.width) / imageWidth

/** The most `z` can be for this image: the image at `MAX_SCALE`. Never below fitted. */
export const maxZoom = (box: Box, imageWidth: number) =>
  Math.max(1, (MAX_SCALE * imageWidth) / box.width)

export function clampView(view: View, box: Box, imageWidth: number): View {
  const z = Math.min(maxZoom(box, imageWidth), Math.max(1, view.z))
  const minX = box.width - box.width * z
  const minY = box.height - box.height * z
  return { z, x: Math.min(0, Math.max(minX, view.x)), y: Math.min(0, Math.max(minY, view.y)) }
}

/** Zoom by `factor` keeping the image point under (px, py) where it is. */
export function zoomAt(
  view: View,
  factor: number,
  px: number,
  py: number,
  box: Box,
  imageWidth: number,
): View {
  const z = Math.min(maxZoom(box, imageWidth), Math.max(1, view.z * factor))
  const k = z / view.z
  return clampView({ z, x: px - (px - view.x) * k, y: py - (py - view.y) * k }, box, imageWidth)
}

export function panBy(view: View, dx: number, dy: number, box: Box, imageWidth: number): View {
  return clampView({ ...view, x: view.x + dx, y: view.y + dy }, box, imageWidth)
}

/** The image at 100 % (one screen pixel for each image pixel) around the centre of what is shown. */
export function actualSize(view: View, box: Box, imageWidth: number): View {
  const z = imageWidth / box.width
  if (z <= 1) return FIT // the image is smaller than the box: fitted is already its size or more
  return zoomAt(view, z / view.z, box.width / 2, box.height / 2, box, imageWidth)
}

/** What part of the image the box shows, as fractions of the image: where the mini-map draws its frame. */
export function visibleRect(view: View, box: Box): [number, number, number, number] {
  return [
    (0 - view.x) / (box.width * view.z),
    (0 - view.y) / (box.height * view.z),
    (box.width - view.x) / (box.width * view.z),
    (box.height - view.y) / (box.height * view.z),
  ]
}

/** The view that has the image point (fx, fy), fractions of the image, in the middle of the box. */
export function centreOn(view: View, fx: number, fy: number, box: Box, imageWidth: number): View {
  return clampView(
    {
      z: view.z,
      x: box.width / 2 - fx * box.width * view.z,
      y: box.height / 2 - fy * box.height * view.z,
    },
    box,
    imageWidth,
  )
}
