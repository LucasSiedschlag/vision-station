import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { cn } from '@/lib/cn'
import {
  describe,
  fromCorners,
  HANDLES,
  move,
  resize,
  rgbToHsv,
  type Handle,
  type Rect,
} from './geometry'
import { pixelAt, type EditorImage } from './image'
import { tokenRgb } from '@/components/vision/hsv-paint'
import { text } from '@/texts'

/** What is drawn over the image. Only `editable` shapes can be selected, moved and resized. */
export interface Shape {
  id: string
  label: string
  rect: Rect // fractions of the frame
  kind: 'roi' | 'presence' | 'locator' | 'anchor' | 'pass' | 'fail'
  editable?: boolean
}

const colours: Record<Shape['kind'], string> = {
  roi: 'stroke-accent',
  presence: 'stroke-busy-text',
  locator: 'stroke-warn-text',
  anchor: 'stroke-warn-text',
  pass: 'stroke-ok-text',
  fail: 'stroke-fail-text',
}

/** The pixel under the pointer in OpenCV's scale: the way for a reader that knows no level. */
const defaultReadout = (x: number, y: number, [r, g, b]: [number, number, number]) => {
  const [h, s, v] = rgbToHsv(r, g, b)
  return `x ${x}, y ${y} · RGB ${r}, ${g}, ${b} · HSV ${h}, ${s}, ${v}`
}

type Drag =
  | { kind: 'draw'; id: string; x0: number; y0: number }
  | { kind: 'move'; id: string; x: number; y: number; start: Rect }
  | { kind: 'resize'; id: string; handle: Handle; start: Rect }

/**
 * The image with its regions (docs/frontend.md §10). Coordinates are fractions of the image, so the SVG uses a
 * 0–1 view box. `drawing` names the shape a drag on the image creates or redraws; `onChange(id, rect, first)`
 * gets `first = true` at the start of a gesture, so the caller records one undo step per drag.
 */
export function RegionCanvas({
  image,
  shapes,
  selected,
  onSelect,
  onChange,
  onDelete,
  drawing,
  emptyText,
  pixels,
  readout: readoutOf,
  mask,
  onGestureEnd,
}: {
  image: EditorImage | null
  shapes: Shape[]
  selected: string | null
  onSelect: (id: string | null) => void
  onChange: (id: string, rect: Rect, first: boolean) => void
  onDelete?: (id: string) => void
  drawing: string | null
  emptyText: string
  /** The pixels of `image`, for the readout under the pointer and the mask. */
  pixels?: ImageData | null
  /** How the colour under the pointer is written, so it follows the settings level (docs/frontend.md §17). */
  readout?: (x: number, y: number, rgb: [number, number, number], size: [number, number]) => string
  /** Pixels (1) to hatch over the image, on the grid of `width` × `height`. */
  mask?: { cells: Uint8Array; width: number; height: number } | null
  /** A drag that drew a shape has ended. */
  onGestureEnd?: (id: string) => void
}) {
  const box = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const [readout, setReadout] = useState<string>('')
  const [size, setSize] = useState({ width: 800, height: 450 })

  useEffect(() => {
    const el = box.current
    if (!el) return
    const observer = new ResizeObserver(
      ([entry]) =>
        entry &&
        setSize({ width: entry.contentRect.width || 800, height: entry.contentRect.height || 450 }),
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [image])

  const point = (e: PointerEvent) => {
    const r = box.current!.getBoundingClientRect()
    return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height }
  }

  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    if (!image || e.button !== 0) return
    const { x, y } = point(e)
    const target = (e.target as Element).closest('[data-shape],[data-handle]')
    const id = target?.getAttribute('data-shape') ?? target?.getAttribute('data-for') ?? null
    const handle = target?.getAttribute('data-handle') as Handle | null
    // a drag that samples colours draws over whatever region is under it: it never moves one
    const shape = drawing === 'sample' ? undefined : shapes.find((s) => s.id === id && s.editable)
    ;(e.currentTarget as Element).setPointerCapture?.(e.pointerId)
    if (shape && handle) {
      setDrag({ kind: 'resize', id: shape.id, handle, start: shape.rect })
      onSelect(shape.id)
    } else if (shape) {
      setDrag({ kind: 'move', id: shape.id, x, y, start: shape.rect })
      onSelect(shape.id)
    } else if (drawing) {
      setDrag({ kind: 'draw', id: drawing, x0: x, y0: y })
      onChange(drawing, fromCorners(x, y, x + 0.001, y + 0.001), true)
      onSelect(drawing)
    } else onSelect(null)
  }

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const { x, y } = point(e)
    if (pixels && x >= 0 && x <= 1 && y >= 0 && y <= 1) {
      const [r, g, b] = pixelAt(pixels, x, y)
      setReadout(
        readoutOf?.(
          Math.round(x * pixels.width),
          Math.round(y * pixels.height),
          [r, g, b],
          [pixels.width, pixels.height],
        ) ?? defaultReadout(Math.round(x * pixels.width), Math.round(y * pixels.height), [r, g, b]),
      )
    }
    if (!drag) return
    const first = false
    if (drag.kind === 'draw') onChange(drag.id, fromCorners(drag.x0, drag.y0, x, y), first)
    else if (drag.kind === 'move')
      onChange(drag.id, move(drag.start, x - drag.x, y - drag.y), first)
    else onChange(drag.id, resize(drag.start, drag.handle, x, y), first)
  }

  const onUp = () => {
    if (drag?.kind === 'draw') onGestureEnd?.(drag.id)
    setDrag(null)
  }

  const onKey = (e: KeyboardEvent, shape: Shape) => {
    if (!image) return
    const px = (e.shiftKey ? 10 : 1) / image.width
    const py = (e.shiftKey ? 10 : 1) / image.height
    const delta: Record<string, [number, number]> = {
      ArrowLeft: [-px, 0],
      ArrowRight: [px, 0],
      ArrowUp: [0, -py],
      ArrowDown: [0, py],
    }
    if (e.key in delta) {
      e.preventDefault()
      const [dx, dy] = delta[e.key]!
      onChange(shape.id, move(shape.rect, dx, dy), true)
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && onDelete) {
      e.preventDefault()
      onDelete(shape.id)
    } else if (e.key === 'Escape') {
      onSelect(null)
    }
  }

  if (!image) {
    return (
      <div className="grid aspect-video w-full place-items-center rounded-card border border-dashed border-line-control text-sm text-fg-muted">
        {emptyText}
      </div>
    )
  }
  const hx = 8 / Math.max(1, size.width)
  const hy = 8 / Math.max(1, size.height)
  return (
    <div className="flex flex-col gap-1">
      <div
        ref={box}
        className="relative w-full select-none overflow-hidden rounded-card border border-line bg-surface-2"
        style={{ aspectRatio: `${image.width} / ${image.height}` }}
      >
        <img src={image.url} alt="" className="absolute inset-0 size-full" draggable={false} />
        {mask ? <MaskLayer mask={mask} /> : null}
        <svg
          role="group"
          aria-label={text.ui.regionsLabel}
          className={cn(
            'absolute inset-0 size-full touch-none',
            drawing ? 'cursor-crosshair' : 'cursor-default',
          )}
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          onPointerLeave={() => setReadout('')}
        >
          {shapes.map((shape) => {
            const [x0, y0, x1, y1] = shape.rect
            const isSelected = shape.id === selected
            return (
              <g
                key={shape.id}
                data-shape={shape.id}
                tabIndex={shape.editable ? 0 : -1}
                role={shape.editable ? 'button' : 'img'}
                aria-label={`${shape.label}: ${describe(shape.rect, image.width, image.height)}`}
                aria-pressed={shape.editable ? isSelected : undefined}
                onFocus={() => shape.editable && onSelect(shape.id)}
                onKeyDown={(e) => shape.editable && onKey(e, shape)}
                className={cn(
                  shape.editable ? 'cursor-move' : 'pointer-events-none',
                  'outline-none',
                )}
              >
                <rect
                  x={x0}
                  y={y0}
                  width={x1 - x0}
                  height={y1 - y0}
                  className={cn(
                    'fill-transparent',
                    colours[shape.kind],
                    isSelected && 'fill-accent/10',
                  )}
                  strokeWidth={isSelected ? 3 : 2}
                  strokeDasharray={
                    shape.kind === 'presence' || shape.kind === 'anchor' ? '6 4' : undefined
                  }
                  vectorEffect="non-scaling-stroke"
                />
                {isSelected && shape.editable
                  ? HANDLES.map((h) => {
                      const cx = h.includes('w') ? x0 : h.includes('e') ? x1 : (x0 + x1) / 2
                      const cy = h.includes('n') ? y0 : h.includes('s') ? y1 : (y0 + y1) / 2
                      return (
                        <rect
                          key={h}
                          data-handle={h}
                          data-for={shape.id}
                          x={cx - hx}
                          y={cy - hy}
                          width={2 * hx}
                          height={2 * hy}
                          className="fill-surface-1 stroke-accent"
                          strokeWidth={1.5}
                          vectorEffect="non-scaling-stroke"
                          style={{ cursor: `${h}-resize` }}
                        />
                      )
                    })
                  : null}
              </g>
            )
          })}
        </svg>
        {shapes
          .filter((s) => s.kind === 'roi' || s.kind === 'locator' || s.kind === 'presence')
          .map((s) => (
            <span
              key={s.id}
              aria-hidden
              className="pointer-events-none absolute -translate-y-full rounded-control bg-surface-1/80 px-1 text-xs"
              style={{ left: `${s.rect[0] * 100}%`, top: `${s.rect[1] * 100}%` }}
            >
              {s.label}
            </span>
          ))}
      </div>
      <p aria-live="off" className="min-h-5 font-mono text-xs text-fg-muted tabular-nums">
        {readout ||
          text.ui.imageSize(
            image.width,
            image.height,
            image.source === 'reference' ? text.ui.referenceImage : text.ui.liveImageReduced,
          )}
      </p>
    </div>
  )
}

/** The pixels a colour range takes in, hatched in the overlay colour over the image (docs/frontend.md §19.4). */
function MaskLayer({ mask }: { mask: { cells: Uint8Array; width: number; height: number } }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    el.width = mask.width
    el.height = mask.height
    const [r, g, b] = tokenRgb('--ov-mask', el)
    const out = ctx.createImageData(mask.width, mask.height)
    for (let y = 0, i = 0; y < mask.height; y++)
      for (let x = 0; x < mask.width; x++, i++) {
        if (!mask.cells[i]) continue
        // a diagonal hatch with a faint fill between the lines: the image stays readable under it
        out.data.set([r, g, b, (x + y) % 6 < 3 ? 200 : 70], i * 4)
      }
    ctx.putImageData(out, 0, 0)
  }, [mask])
  return (
    <canvas ref={canvas} aria-hidden className="pointer-events-none absolute inset-0 size-full" />
  )
}
