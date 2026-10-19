import { CheckCircle2, ChevronDown, ChevronUp, Radio, Star, XCircle } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { BatchOut } from '@/api/queries/editor'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import type { Draft } from './draft'
import { base64ToBlob, fetchBlob } from './image'

const s = text.editor.strip
export const REFERENCE = 'reference/reference.png'

/** One picture of the strip: the reference, a sample of the reference set, or the live image. */
interface Item {
  path: string | null // null: the live image
  kind: 'reference' | 'good' | 'bad' | 'live'
  /** whether the job agrees with the label, after a measurement; undefined: not measured */
  agrees?: boolean
}

/**
 * The strip of pictures under the image (docs/frontend.md §10.1): the reference, the *Boa* and *Ruim* samples with a
 * ✓ or ✕ for whether the job agrees with the label, and the live image; with *+ Boa* and *+ Ruim* to take a sample
 * from the camera. The arrows move between them, and a picture is only asked for when it comes near the screen.
 */
export function Filmstrip({
  draft,
  batch,
  shown,
  live,
  onShow,
  onLive,
  onCapture,
  capturing,
  canCapture,
  open,
  onToggle,
}: {
  draft: Draft
  batch: BatchOut | null
  /** The sample on the image; null: the reference or the live image. */
  shown: string | null
  /** The image on screen is the camera's. */
  live: boolean
  onShow: (path: string) => void
  onLive: () => void
  onCapture: (kind: 'good' | 'bad') => void
  capturing: 'good' | 'bad' | null
  canCapture: boolean
  open: boolean
  onToggle: () => void
}) {
  const hasReference =
    draft.addFiles[REFERENCE] !== undefined || draft.baseFiles.some((f) => f.path === REFERENCE)
  const measured = new Map((batch?.samples ?? []).map((x) => [x.image, x]))
  const items: Item[] = [
    ...(hasReference ? [{ path: REFERENCE, kind: 'reference' as const }] : []),
    ...(draft.expected?.cases ?? [])
      .filter((c) => c.outcome !== 'ERROR')
      .map((c) => ({
        path: c.image,
        kind: c.outcome === 'PASS' ? ('good' as const) : ('bad' as const),
        agrees: measured.get(c.image)?.ok,
      })),
    { path: null, kind: 'live' as const },
  ]
  const row = useRef<HTMLUListElement>(null)
  const move = (e: KeyboardEvent) => {
    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End']
    if (!keys.includes(e.key)) return
    const tiles = [...(row.current?.querySelectorAll<HTMLButtonElement>('button[data-tile]') ?? [])]
    const at = tiles.indexOf(document.activeElement as HTMLButtonElement)
    const to =
      e.key === 'Home'
        ? 0
        : e.key === 'End'
          ? tiles.length - 1
          : at + (e.key === 'ArrowRight' ? 1 : -1)
    e.preventDefault()
    tiles[Math.min(tiles.length - 1, Math.max(0, to))]?.focus()
  }
  const noSamples = !items.some((i) => i.kind === 'good' || i.kind === 'bad')

  return (
    <section aria-label={s.label} className="flex flex-col gap-1 border-t border-line pt-2">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">{s.label}</h3>
        <Button
          variant="ghost"
          aria-label={open ? s.hide : s.show}
          aria-expanded={open}
          onClick={onToggle}
        >
          {open ? (
            <ChevronDown aria-hidden className="size-4" />
          ) : (
            <ChevronUp aria-hidden className="size-4" />
          )}
        </Button>
        <div className="ml-auto flex gap-2">
          <Button
            variant="secondary"
            aria-label={s.addGoodLong}
            loading={capturing === 'good'}
            disabled={!canCapture || capturing !== null}
            onClick={() => onCapture('good')}
          >
            + {s.addGood}
          </Button>
          <Button
            variant="secondary"
            aria-label={s.addBadLong}
            loading={capturing === 'bad'}
            disabled={!canCapture || capturing !== null}
            onClick={() => onCapture('bad')}
          >
            + {s.addBad}
          </Button>
        </div>
      </div>
      {open ? (
        <>
          {noSamples ? <p className="text-xs text-fg-muted">{s.none}</p> : null}
          <div role="toolbar" aria-label={s.label} aria-orientation="horizontal" onKeyDown={move}>
            <ul ref={row} className="flex gap-2 overflow-x-auto pb-1">
              {items.map((item) => (
                <li key={item.path ?? 'live'} className="shrink-0">
                  <Tile
                    item={item}
                    draft={draft}
                    current={item.path === null ? live && shown === null : item.path === shown}
                    onClick={() => (item.path === null ? onLive() : onShow(item.path))}
                  />
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </section>
  )
}

function Tile({
  item,
  draft,
  current,
  onClick,
}: {
  item: Item
  draft: Draft
  current: boolean
  onClick: () => void
}) {
  const box = useRef<HTMLButtonElement>(null)
  const [near, setNear] = useState(typeof IntersectionObserver === 'undefined')
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    const el = box.current
    if (near || !el) return
    const watcher = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setNear(true),
      { rootMargin: '200px' },
    )
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [near])
  const added = item.path ? draft.addFiles[item.path] : undefined
  const base = draft.base
  useEffect(() => {
    if (!near || !item.path) return
    let alive = true
    let made: string | null = null
    const get = async () =>
      added
        ? base64ToBlob(added)
        : await fetchBlob(
            `/api/jobs/${base!.id}/versions/${base!.version}/files/${item.path}?width=160`,
          )
    get().then(
      (blob) => {
        if (!alive) return
        made = URL.createObjectURL(blob)
        setUrl(made)
      },
      () => {},
    )
    return () => {
      alive = false
      if (made) URL.revokeObjectURL(made)
    }
  }, [near, item.path, added, base])

  const name = item.path ? item.path.replace('tests/images/', '').replace(/\.png$/, '') : s.live
  const kindWord = { reference: s.reference, good: s.good, bad: s.bad, live: s.live }[item.kind]
  const verdict = item.agrees === undefined ? s.untested : item.agrees ? s.agrees : s.disagrees
  return (
    <button
      ref={box}
      type="button"
      data-tile
      aria-pressed={current}
      aria-label={
        item.kind === 'reference' || item.kind === 'live'
          ? kindWord
          : s.sample(name, kindWord, verdict)
      }
      title={name}
      onClick={onClick}
      className={cn(
        'relative grid aspect-video h-16 place-items-center overflow-hidden rounded-control border bg-surface-2',
        current ? 'border-accent outline-2 outline-accent' : 'border-line',
      )}
    >
      {url ? (
        <img src={url} alt="" draggable={false} className="size-full object-cover" />
      ) : item.kind === 'live' ? (
        <Radio aria-hidden className="size-5 text-fg-muted" />
      ) : null}
      <span
        aria-hidden
        className="absolute left-1 top-1 flex items-center gap-0.5 rounded-control bg-surface-1/90 px-1 text-xs"
      >
        {item.kind === 'reference' ? <Star className="size-3" /> : null}
        {item.kind === 'live' ? s.live : null}
        {item.kind === 'good' ? s.good : null}
        {item.kind === 'bad' ? s.bad : null}
      </span>
      {item.agrees === undefined || item.kind === 'reference' || item.kind === 'live' ? null : (
        <span aria-hidden className="absolute bottom-1 right-1 rounded-pill bg-surface-1/90 p-0.5">
          {item.agrees ? (
            <CheckCircle2 className="size-4 text-ok-text" />
          ) : (
            <XCircle className="size-4 text-fail-text" />
          )}
        </span>
      )}
    </button>
  )
}
