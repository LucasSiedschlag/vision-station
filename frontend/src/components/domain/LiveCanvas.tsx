import { useEffect, useRef } from 'react'
import { cn } from '@/lib/cn'
import { text } from '@/texts'

/**
 * Draws the newest camera frame (a JPEG blob from the live socket), fitted into its box. With no frame it says so,
 * and never keeps showing a picture that is not coming any more. The overlay of the last inspection is added in the
 * editor task.
 */
export function LiveCanvas({ frame, className }: { frame: Blob | null; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const bitmap = useRef<ImageBitmap | null>(null)

  const draw = () => {
    const c = canvas.current
    const bmp = bitmap.current
    if (!c) return
    const { width, height } = c.getBoundingClientRect()
    const w = Math.round(width)
    const h = Math.round(height)
    if (c.width !== w || c.height !== h) {
      c.width = w
      c.height = h
    }
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, c.width, c.height) // the box behind is the page's own surface colour
    if (!bmp) return
    const scale = Math.min(c.width / bmp.width, c.height / bmp.height)
    ctx.drawImage(
      bmp,
      (c.width - bmp.width * scale) / 2,
      (c.height - bmp.height * scale) / 2,
      bmp.width * scale,
      bmp.height * scale,
    )
  }

  useEffect(() => {
    if (!frame) {
      bitmap.current?.close()
      bitmap.current = null
      draw()
      return
    }
    let current = true
    createImageBitmap(frame)
      .then((bmp) => {
        if (!current) return bmp.close()
        bitmap.current?.close()
        bitmap.current = bmp
        draw()
      })
      .catch(() => undefined)
    return () => {
      current = false
    }
  }, [frame])

  useEffect(() => {
    const c = canvas.current
    if (!c || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(draw)
    observer.observe(c)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      className={cn(
        'relative size-full overflow-hidden rounded-card border border-line bg-surface-0',
        className,
      )}
    >
      <canvas ref={canvas} role="img" aria-label="Imagem ao vivo da câmera" className="size-full" />
      {frame ? null : (
        <div className="absolute inset-0 grid place-items-center text-lg text-fg-muted">
          {text.operator.noImage}
        </div>
      )}
    </div>
  )
}
