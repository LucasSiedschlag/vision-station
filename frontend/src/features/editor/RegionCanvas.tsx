import { Maximize, Minus, Plus, ScanSearch } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { Button } from '@/components/ui/button'
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
import { MarkShapes, textMarks, type ToolMarks } from '@/components/domain/MarkShapes'
import type { Layer } from './layers'
import {
  FIT,
  GRID_FROM,
  MINIMAP_FROM,
  actualSize,
  centreOn,
  clampView,
  panBy,
  scaleOf,
  visibleRect,
  zoomAt,
  type View,
} from './viewport'
import { tokenRgb } from '@/components/vision/hsv-paint'
import { text } from '@/texts'

/** What is drawn over the image. Only `editable` shapes can be selected, moved and resized. */
export interface Shape {
  id: string
  label: string
  rect: Rect // fractions of the frame
  kind: 'roi' | 'presence' | 'locator' | 'anchor' | 'pass' | 'fail'
  editable?: boolean
  /** The outline of a shape that is turned, fractions of the frame: drawn instead of the rectangle. */
  outline?: [number, number][]
  /** The layer it belongs to; `null`: a working aid (a crop, a sample being dragged) that no layer hides. */
  layer?: Layer | null
}

/** The layer a shape is in when it does not say: the kind of what it draws (docs/frontend.md §18). */
export function layerOf(shape: Shape): Layer | null {
  if (shape.layer !== undefined) return shape.layer
  return {
    roi: 'regions',
    pass: 'regions',
    fail: 'regions',
    locator: 'anchors',
    anchor: 'anchors',
    presence: 'presence',
  }[shape.kind] as Layer
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
  layers,
  caption,
  marks,
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
  /** Which layers are drawn (§18); all of them when not given. */
  layers?: Record<Layer, boolean>
  /** What the image is, over its top-left corner: *Ao vivo*, *Referência*, *Amostra 4 (Ruim)*, *Resultado 14:32:07* (§10.2). */
  caption?: string
  /** What the tools of the last result measured (*Medições*, §18). */
  marks?: readonly ToolMarks[]
}) {
  const on = (layer: Layer | null) => layer === null || (layers?.[layer] ?? true)
  const box = useRef<HTMLDivElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const [view, setView] = useState<View>(FIT)
  const [pan, setPan] = useState<{ x: number; y: number; view: View } | null>(null)
  const [spaceDown, setSpaceDown] = useState(false)
  const [over, setOver] = useState(false)
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

  const imageWidth = image?.width ?? 1
  const imageKey = image ? `${image.width}x${image.height}` : ''
  const [seenKey, setSeenKey] = useState(imageKey)
  if (seenKey !== imageKey) {
    // another picture of another size starts fitted; the live frames of one size keep the zoom the person chose
    setSeenKey(imageKey)
    setView(FIT)
  }
  const sized = { width: size.width, height: size.height }
  const fitted = clampView(view, sized, imageWidth) // a window that was resized keeps the picture covering it

  // the wheel zooms around the pointer; it needs a listener that may cancel the page's own scroll
  useEffect(() => {
    const el = frame.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const factor = Math.exp(-e.deltaY * 0.0015)
      setView((v) => zoomAt(v, factor, e.clientX - r.left, e.clientY - r.top, sized, imageWidth))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [image, size.width, size.height, imageWidth]) // eslint-disable-line react-hooks/exhaustive-deps -- `sized` is made of the two sizes

  // Space (to move), Ctrl+0 (fit) and 1 (100 %) while the pointer is over the image and nothing is being typed
  useEffect(() => {
    if (!over) return
    // typing in a field keeps its keys; Space also belongs to a button or a slider that has the focus
    const typing = (t: EventTarget | null) =>
      t instanceof HTMLElement &&
      (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))
    const holdsSpace = (t: EventTarget | null) =>
      t instanceof HTMLElement && (t.tagName === 'BUTTON' || t.getAttribute('role') === 'slider')
    const down = (e: globalThis.KeyboardEvent) => {
      if (typing(e.target)) return
      if (e.code === 'Space') {
        if (holdsSpace(e.target)) return
        e.preventDefault()
        setSpaceDown(true)
      } else if (e.key === '0' && e.ctrlKey) {
        e.preventDefault()
        setView(FIT)
      } else if (e.key === '1' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        setView((v) => actualSize(v, sized, imageWidth))
      }
    }
    const up = (e: globalThis.KeyboardEvent) => e.code === 'Space' && setSpaceDown(false)
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
    }
  }, [over, size.width, size.height, imageWidth]) // eslint-disable-line react-hooks/exhaustive-deps -- `sized` is made of the two sizes

  const point = (e: PointerEvent) => {
    const r = box.current!.getBoundingClientRect()
    return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height }
  }

  const onDown = (e: PointerEvent<SVGSVGElement>) => {
    if (!image || (e.button !== 0 && e.button !== 1)) return
    if (spaceDown || e.button === 1) {
      ;(e.currentTarget as Element).setPointerCapture?.(e.pointerId)
      setPan({ x: e.clientX, y: e.clientY, view: fitted })
      return
    }
    const { x, y } = point(e)
    const target = (e.target as Element).closest('[data-shape],[data-handle]')
    const id = target?.getAttribute('data-shape') ?? target?.getAttribute('data-for') ?? null
    const handle = target?.getAttribute('data-handle') as Handle | null
    // a drag that samples colours, or cuts a crop for a template, draws over whatever region is under it: it never moves one
    const shape = drawing === 'sample' || drawing === 'crop' ? undefined : shapes.find((s) => s.id === id && s.editable)
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
    if (pan) {
      setView(panBy(pan.view, e.clientX - pan.x, e.clientY - pan.y, sized, imageWidth))
      return
    }
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
    if (pan) return setPan(null)
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
  const hx = 8 / Math.max(1, size.width) / fitted.z
  const hy = 8 / Math.max(1, size.height) / fitted.z
  const scale = scaleOf(fitted.z, sized, imageWidth)
  const zoomBy = (factor: number) =>
    setView(zoomAt(fitted, factor, sized.width / 2, sized.height / 2, sized, imageWidth))
  return (
    <div className="flex flex-col gap-1">
      <div
        ref={frame}
        className="relative w-full select-none overflow-hidden rounded-card border border-line bg-surface-2"
        style={{ aspectRatio: `${image.width} / ${image.height}` }}
        onPointerEnter={() => setOver(true)}
        onPointerLeave={() => (setOver(false), setSpaceDown(false))}
      >
        <div
          ref={box}
          className="absolute inset-0 origin-top-left"
          style={{ transform: `translate(${fitted.x}px, ${fitted.y}px) scale(${fitted.z})` }}
        >
          <img src={image.url} alt="" className="absolute inset-0 size-full" draggable={false} />
          {mask && on('mask') ? <MaskLayer mask={mask} /> : null}
          {on('grid') && scale >= GRID_FROM ? (
            <PixelGrid width={image.width} height={image.height} />
          ) : null}
          <svg
            role="group"
            aria-label={text.ui.regionsLabel}
            className={cn(
              'absolute inset-0 size-full touch-none',
              pan
                ? 'cursor-grabbing'
                : spaceDown
                  ? 'cursor-grab'
                  : drawing
                    ? 'cursor-crosshair'
                    : 'cursor-default',
            )}
            viewBox="0 0 1 1"
            preserveAspectRatio="none"
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerCancel={onUp}
            onPointerLeave={() => setReadout('')}
          >
            {shapes
              .filter((shape) => on(layerOf(shape)))
              .map((shape) => {
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
                    {shape.outline ? (
                      <polygon
                        points={shape.outline.map(([px, py]) => `${px},${py}`).join(' ')}
                        className={cn('fill-transparent', colours[shape.kind])}
                        strokeWidth={2}
                        strokeDasharray={shape.kind === 'anchor' ? '6 4' : undefined}
                        vectorEffect="non-scaling-stroke"
                      />
                    ) : (
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
                    )}
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
          {marks && marks.length > 0 && on('measures') ? (
            <MeasuresLayer marks={marks} image={image} zoom={fitted.z} />
          ) : null}
          {on('labels')
            ? shapes
                .filter(
                  (s) =>
                    (s.kind === 'roi' || s.kind === 'locator' || s.kind === 'presence') &&
                    on(layerOf(s)),
                )
                .map((s) => (
                  <span
                    key={s.id}
                    aria-hidden
                    className="pointer-events-none absolute origin-bottom-left rounded-control bg-surface-1/80 px-1 text-xs"
                    // the text keeps its size when the picture is magnified
                    style={{
                      left: `${s.rect[0] * 100}%`,
                      top: `${s.rect[1] * 100}%`,
                      transform: `translateY(-100%) scale(${1 / fitted.z})`,
                    }}
                  >
                    {s.label}
                  </span>
                ))
            : null}
        </div>
        {caption ? (
          <span className="pointer-events-none absolute left-2 top-2 rounded-control bg-surface-1/90 px-2 py-0.5 text-xs font-medium">
            {caption}
          </span>
        ) : null}
        <div
          title={text.editor.view.hint}
          className="absolute right-2 top-2 flex items-center gap-1 rounded-control bg-surface-1/90 p-0.5"
        >
          <Button
            variant="ghost"
            aria-label={text.editor.view.zoomOut}
            onClick={() => zoomBy(1 / 1.5)}
          >
            <Minus aria-hidden className="size-4" />
          </Button>
          <span
            aria-label={text.editor.view.zoom(String(Math.round(scale * 100)))}
            className="min-w-12 text-center font-mono text-xs tabular-nums"
          >
            {Math.round(scale * 100)} %
          </span>
          <Button variant="ghost" aria-label={text.editor.view.zoomIn} onClick={() => zoomBy(1.5)}>
            <Plus aria-hidden className="size-4" />
          </Button>
          <Button variant="ghost" aria-label={text.editor.view.fit} onClick={() => setView(FIT)}>
            <Maximize aria-hidden className="size-4" />
          </Button>
          <Button
            variant="ghost"
            aria-label={text.editor.view.actual}
            onClick={() => setView(actualSize(fitted, sized, imageWidth))}
          >
            <ScanSearch aria-hidden className="size-4" />
          </Button>
        </div>
        {scale >= MINIMAP_FROM ? (
          <MiniMap
            image={image}
            rect={visibleRect(fitted, sized)}
            onGo={(fx, fy) => setView(centreOn(fitted, fx, fy, sized, imageWidth))}
          />
        ) : null}
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

/** The whole picture, small, with the part that is on show framed; a click goes there (docs/frontend.md §10.2). */
function MiniMap({
  image,
  rect,
  onGo,
}: {
  image: EditorImage
  rect: [number, number, number, number]
  onGo: (fx: number, fy: number) => void
}) {
  const [x0, y0, x1, y1] = rect
  return (
    <button
      type="button"
      aria-label={text.editor.view.minimap}
      className="absolute bottom-2 right-2 w-28 overflow-hidden rounded-control border border-line-strong bg-surface-1"
      style={{ aspectRatio: `${image.width} / ${image.height}` }}
      onClick={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        onGo((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height)
      }}
    >
      <img src={image.url} alt="" draggable={false} className="size-full" />
      <span
        aria-hidden
        className="absolute border-2 border-accent"
        style={{
          left: `${x0 * 100}%`,
          top: `${y0 * 100}%`,
          width: `${(x1 - x0) * 100}%`,
          height: `${(y1 - y0) * 100}%`,
        }}
      />
    </button>
  )
}

/** The pixel grid above 800 %: one line between two pixels of the image (docs/frontend.md §10.2). */
function PixelGrid({ width, height }: { width: number; height: number }) {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0"
      style={{
        backgroundImage:
          'linear-gradient(to right, var(--line-strong) 1px, transparent 1px), linear-gradient(to bottom, var(--line-strong) 1px, transparent 1px)',
        backgroundSize: `calc(100% / ${width}) calc(100% / ${height})`,
      }}
    />
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

/** What the tools measured: shapes in an SVG over the picture, texts that keep their size when it is magnified. */
function MeasuresLayer({
  marks,
  image,
  zoom,
}: {
  marks: readonly ToolMarks[]
  image: { width: number; height: number }
  zoom: number
}) {
  return (
    <>
      <svg
        role="group"
        aria-label={text.editor.view.layers.measures}
        className="pointer-events-none absolute inset-0 size-full"
        viewBox={`0 0 ${image.width} ${image.height}`}
        preserveAspectRatio="none"
      >
        <MarkShapes tools={marks} width={image.width} height={image.height} />
      </svg>
      {textMarks(marks).map((m) => (
        <span
          key={m.key}
          aria-hidden
          className={cn(
            'pointer-events-none absolute origin-bottom-left rounded-control bg-surface-1/80 px-1 text-xs',
            m.fail ? (m.informative ? 'text-warn-text' : 'text-fail-text') : 'text-ok-text',
          )}
          style={{
            left: `${m.x * 100}%`,
            top: `${m.y * 100}%`,
            transform: `translateY(-100%) scale(${1 / zoom})`,
          }}
        >
          {m.text}
        </span>
      ))}
    </>
  )
}
