import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import { MarkShapes, textMarks, toolMarks, type MarkOut } from './MarkShapes'

/**
 * Draws the newest camera frame (a JPEG blob from the live socket), fitted into its box. With no frame it says so,
 * and never keeps showing a picture that is not coming any more.
 *
 * `regions` are the markings of a result (FR-UI-9, docs/frontend.md §18): each tool's region as fractions of the frame,
 * drawn over the picture as vectors, so they follow its size and turning them on or off asks for nothing. A region
 * that failed is thicker and crossed, an informative tool's is dashed: the colour is never the only signal.
 */
export interface Marking {
  id: string
  rect: readonly number[]
  passed: boolean
  informative: boolean
  /** What the tool measured (VIA-0124): drawn with its region, as fractions of the frame. */
  marks?: readonly MarkOut[]
}

export function LiveCanvas({
  frame,
  regions = [],
  empty,
  className,
}: {
  frame: Blob | null
  regions?: Marking[]
  /** What to say with no picture; the camera's own message by default. */
  empty?: string
  className?: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const bitmap = useRef<ImageBitmap | null>(null)
  // the size of the picture that was decoded, kept with it: a newer picture of another size replaces it
  const [decoded, setDecoded] = useState<{ of: Blob; width: number; height: number } | null>(null)
  const size = decoded && decoded.of === frame ? decoded : null

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
        setDecoded({ of: frame, width: bmp.width, height: bmp.height })
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
      <canvas ref={canvas} role="img" aria-label={text.live.imageLabel} className="size-full" />
      {frame && size && regions.length > 0 ? (
        <svg
          viewBox={`0 0 ${size.width} ${size.height}`}
          preserveAspectRatio="xMidYMid meet"
          className="pointer-events-none absolute inset-0 size-full"
          aria-label={text.operator.markings}
        >
          {regions.map((r) => (
            <RegionMark key={r.id} region={r} width={size.width} height={size.height} />
          ))}
          <MarkShapes tools={toolMarks(regions)} width={size.width} height={size.height} />
          {textMarks(toolMarks(regions)).map((m) => (
            <text
              key={m.key}
              x={m.x * size.width}
              y={m.y * size.height}
              fontSize={Math.max(14, size.height * 0.03)}
              fontWeight={600}
              className={cn(
                'stroke-surface-0',
                m.fail ? (m.informative ? 'fill-warn' : 'fill-fail') : 'fill-ok',
              )}
              strokeWidth={3}
              paintOrder="stroke"
            >
              {m.text}
            </text>
          ))}
        </svg>
      ) : null}
      {frame ? null : (
        <div className="absolute inset-0 grid place-items-center text-lg text-fg-muted">
          {empty ?? text.operator.noImage}
        </div>
      )}
    </div>
  )
}

/** One region: an outline in the verdict's colour, with a dark edge so it shows on any picture. */
function RegionMark({ region, width, height }: { region: Marking; width: number; height: number }) {
  const [x0 = 0, y0 = 0, x1 = 0, y1 = 0] = region.rect
  const x = x0 * width
  const y = y0 * height
  const w = (x1 - x0) * width
  const h = (y1 - y0) * height
  const stroke = region.passed ? 'stroke-ok' : 'stroke-fail'
  const cross = Math.min(w, h, width * 0.06) // the ✕ in the corner of a failed region
  const line = { vectorEffect: 'non-scaling-stroke' as const, fill: 'none' }
  return (
    <g role="img" aria-label={text.operator.regionLabel(region.id, region.passed)}>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        className="stroke-surface-0"
        strokeWidth={region.passed ? 6 : 8}
        {...line}
      />
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        className={stroke}
        strokeWidth={region.passed ? 3 : 5}
        strokeDasharray={region.informative ? '8 6' : undefined}
        {...line}
      />
      {region.passed ? null : (
        <path
          d={`M${x} ${y}l${cross} ${cross}M${x + cross} ${y}l${-cross} ${cross}`}
          className="stroke-fail"
          strokeWidth={5}
          {...line}
        />
      )}
    </g>
  )
}
