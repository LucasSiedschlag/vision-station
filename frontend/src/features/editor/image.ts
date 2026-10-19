import { fetchBlob } from '@/api/download'
import type { Rect } from './geometry'

export { fetchBlob }

/** An image the editor draws on: a URL the <img> can show, and its size in pixels. */
export interface EditorImage {
  url: string
  width: number
  height: number
  /** where it came from: the job's reference image (full size) or a live snapshot (reduced) */
  source: 'reference' | 'live' | 'sample'
}

export function base64ToBlob(b64: string, type = 'image/png'): Blob {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
  return new Blob([bytes], { type })
}

export async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  let text = ''
  for (let i = 0; i < bytes.length; i += 0x8000)
    text += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(text)
}

export function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('the image could not be decoded'))
    img.src = url
  })
}

export async function imageFromBlob(
  blob: Blob,
  source: EditorImage['source'],
): Promise<EditorImage> {
  const url = URL.createObjectURL(blob)
  const img = await loadImage(url)
  return { url, width: img.naturalWidth, height: img.naturalHeight, source }
}

/** The pixels of an image, to read colours under the pointer and to sample a region. */
export async function pixelsOf(image: EditorImage): Promise<ImageData | null> {
  try {
    const img = await loadImage(image.url)
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    ctx.drawImage(img, 0, 0)
    return ctx.getImageData(0, 0, canvas.width, canvas.height)
  } catch {
    return null
  }
}

export function pixelAt(data: ImageData, x: number, y: number): [number, number, number] {
  const px = Math.min(data.width - 1, Math.max(0, Math.floor(x * data.width)))
  const py = Math.min(data.height - 1, Math.max(0, Math.floor(y * data.height)))
  const i = (py * data.width + px) * 4
  return [data.data[i]!, data.data[i + 1]!, data.data[i + 2]!]
}

/** Up to `max` pixels spread over a region. */
export function sample(
  data: ImageData,
  [x0, y0, x1, y1]: Rect,
  max = 4000,
): [number, number, number][] {
  const w = Math.max(1, Math.round((x1 - x0) * data.width))
  const h = Math.max(1, Math.round((y1 - y0) * data.height))
  const step = Math.max(1, Math.ceil(Math.sqrt((w * h) / max)))
  const out: [number, number, number][] = []
  for (let y = 0; y < h; y += step)
    for (let x = 0; x < w; x += step)
      out.push(pixelAt(data, x0 + x / data.width, y0 + y / data.height))
  return out
}

/** A region of a full-size image as a PNG (base64), e.g. a template for the template locator or the pattern tool. */
export async function cropPng(image: EditorImage, [x0, y0, x1, y1]: Rect): Promise<string> {
  const img = await loadImage(image.url)
  const sx = Math.round(x0 * img.naturalWidth)
  const sy = Math.round(y0 * img.naturalHeight)
  const sw = Math.max(1, Math.round((x1 - x0) * img.naturalWidth))
  const sh = Math.max(1, Math.round((y1 - y0) * img.naturalHeight))
  const canvas = document.createElement('canvas')
  canvas.width = sw
  canvas.height = sh
  canvas.getContext('2d')!.drawImage(img, sx, sy, sw, sh, 0, 0, sw, sh)
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('recorte falhou'))), 'image/png'),
  )
  return blobToBase64(blob)
}
