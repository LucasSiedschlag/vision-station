import { Crop, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useTypes, type LocateSample } from '@/api/queries/editor'
import { useLevel } from '@/app/levels'
import { AngleRangeDial } from '@/components/vision/AngleRangeDial'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/cn'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { SchemaForm } from './SchemaForm'
import { useDraft, type JobJson } from './draft'
import { fixturesOf, freeName, isUpright, type FixtureShape } from './fixtures'
import { cropPng } from './image'
import { REFERENCE } from './Filmstrip'
import { useThumbnail } from './thumbnail'
import type { StepProps } from './steps'

const t = text.editor
const a = t.anchor
const KINDS = ['fixed', 'template', 'blob'] as const
type Kind = (typeof KINDS)[number]
const edit = (
  change: (d: ReturnType<typeof useDraft.getState>['draft'] & object) => void,
  history = true,
) => useDraft.getState().edit(change, history)

const prefixed = (fields: Record<string, string>, prefix: string) =>
  Object.fromEntries(
    Object.entries(fields)
      .filter(([k]) => k.startsWith(`${prefix}.`))
      .map(([k, v]) => [k.slice(prefix.length + 1), v]),
  )

/** The newest version of a locator type the server offers. */
function newest(locators: { name: string; version: number }[] | undefined, name: string): number {
  return Math.max(1, ...(locators ?? []).filter((l) => l.name === name).map((l) => l.version))
}

/**
 * The anchor step (docs/frontend.md §7.3, step 3): what finds the object, how far from the taught pose it may be, and where it is
 * on the reference and on every sample. Each fixture is a card; one can be searched inside another (Avançado), so a
 * label on a part is found in the part's own axes. The first one is called `anchor`, and the names are not changed once
 * given, because regions and tools refer to them.
 */
export function AnchorStep({
  draft,
  image,
  fields,
  drawing,
  setDrawing,
  crop,
  setCrop,
  locating,
  shownSample,
  showSample,
}: StepProps) {
  const types = useTypes()
  const [level] = useLevel('editor')
  const fixtures = fixturesOf(draft.job)
  const locators = types.data?.locators
  const picture = shownSample ?? REFERENCE
  const onPicture = locating.out?.samples.find((s) => s.image === picture)

  const setGeometry = (change: (g: JobJson) => void, history = true) =>
    edit((d) => change((d.job.geometry ??= { rois: {} })), history)

  const choose = (i: number, kind: Kind | 'none') =>
    setGeometry((g) => {
      if (kind === 'none') return removeFrom(g, d2names(g, i))
      const locator: JobJson =
        kind === 'fixed'
          ? { type: 'fixed', version: 1, params: { rect: [0.25, 0.25, 0.75, 0.75] } }
          : kind === 'template'
            ? { type: 'template', version: 1, params: {} }
            : { type: 'blob', version: newest(locators, 'blob'), params: { mode: 'dark' } }
      const list = (g.fixtures ??= []) as JobJson[]
      list[i] = { ...(list[i] ?? { name: i === 0 ? 'anchor' : freeName(draft.job) }), locator }
    })

  /** The names of fixture `i` and of every fixture searched inside it, directly or not: they go together. */
  const d2names = (g: JobJson, i: number): string[] => {
    const gone = [g.fixtures[i].name as string]
    for (const f of g.fixtures as JobJson[])
      if (f.inside && gone.includes(f.inside)) gone.push(f.name)
    return gone
  }
  /** Takes fixtures out; regions and tools that referred to them go back to the whole frame. */
  const removeFrom = (g: JobJson, names: string[]) => {
    g.fixtures = (g.fixtures as JobJson[]).filter((f) => !names.includes(f.name))
    for (const r of Object.values(g.rois ?? {}) as JobJson[])
      if (names.includes(r.relative_to)) r.relative_to = 'frame'
    edit((d) => {
      for (const tool of (d.job.tools ?? []) as JobJson[])
        if (names.includes(tool.roi)) tool.roi = 'frame'
    })
  }

  const setRange = (i: number, change: (r: JobJson) => void, history = false) =>
    setGeometry((g) => {
      const f = g.fixtures[i]
      f.range ??= { angle: [-15, 15], scale: [0.9, 1.1], position: null }
      change(f.range)
    }, history)

  const applyCrop = async () => {
    if (!image || image.source !== 'reference' || !crop) return
    const path = 'locator/template.png'
    const png = await cropPng(image, crop)
    edit((d) => {
      d.addFiles[path] = png
      d.removeFiles = d.removeFiles.filter((p) => p !== path)
      const f = (d.job.geometry.fixtures[0] ??= { name: 'anchor' })
      f.locator = {
        type: 'template',
        version: 1,
        params: { ...(f.locator?.params ?? {}), template: path },
      }
    })
    setCrop(null)
    setDrawing(null)
    toast.success(t.templateSaved)
  }

  /** The taught size from what the anchor found on the reference picture, in its pixels. */
  const teachSize = () => {
    const reference = locating.out?.samples.find((s) => s.kind === 'reference')
    const found = reference?.fixtures[0]
    if (!reference || !found?.taught) return void toast.error(a.teachNeedsReference)
    const [x0, y0, x1, y1] = found.taught as [number, number, number, number]
    const w = Math.round((x1 - x0) * reference.width)
    const h = Math.round((y1 - y0) * reference.height)
    setGeometry((g) => (g.fixtures[0].locator.params.taught_size = [w, h]), true)
    toast.success(a.taught(formatNumber(w, 0), formatNumber(h, 0)))
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.locatorHint}</p>
      {fixtures.length === 0 ? (
        <KindCards value="none" onChange={(kind) => choose(0, kind)} first />
      ) : null}
      {fixtures.map((fixture, i) => {
        const locator = fixture.locator as JobJson
        const kind = locator.type as Kind
        const schema = locators?.find(
          (l) => l.name === locator.type && l.version === locator.version,
        )?.params_schema
        const range = fixture.range ?? { angle: [-15, 15], scale: [0.9, 1.1], position: null }
        const foundHere = onPicture?.fixtures.find((f) => f.name === fixture.name)
        const first = i === 0
        return (
          <section
            key={fixture.name as string}
            aria-label={`${t.anchorLabel}: ${fixture.name}`}
            className="flex flex-col gap-3 rounded-control border border-line p-3"
          >
            <header className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">
                {first ? a.title : `${a.title}: ${fixture.name}`}
              </h3>
              {first ? null : (
                <Button
                  variant="ghost"
                  className="ml-auto"
                  aria-label={a.remove(fixture.name)}
                  onClick={() => setGeometry((g) => removeFrom(g, d2names(g, i)))}
                >
                  <Trash2 aria-hidden className="size-4" />
                </Button>
              )}
            </header>
            <KindCards value={kind} onChange={(k) => choose(i, k)} first={first} />
            {!first && level >= 2 ? (
              <Field label={a.inside}>
                {(props) => (
                  <Select
                    {...props}
                    value={fixture.inside ?? 'frame'}
                    onValueChange={(v) =>
                      setGeometry((g) => {
                        if (v === 'frame') delete g.fixtures[i].inside
                        else g.fixtures[i].inside = v
                      })
                    }
                    options={[
                      { value: 'frame', label: a.insideFrame },
                      ...fixtures
                        .slice(0, i)
                        .map((f) => ({ value: f.name as string, label: f.name as string })),
                    ]}
                  />
                )}
              </Field>
            ) : null}

            {first && kind === 'fixed' ? (
              <Button
                variant={drawing === 'locator:0' ? 'primary' : 'secondary'}
                onClick={() => setDrawing(drawing === 'locator:0' ? null : 'locator:0')}
              >
                {drawing === 'locator:0' ? t.drawingNow : t.drawLocator}
              </Button>
            ) : null}
            {first && kind === 'template' ? (
              <div className="flex flex-col gap-2 rounded-control border border-line p-3">
                <p className="text-sm">
                  {image?.source === 'reference' ? t.cropHint : t.cropNeedsReference}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    disabled={image?.source !== 'reference'}
                    variant={drawing === 'crop' ? 'primary' : 'secondary'}
                    onClick={() => setDrawing(drawing === 'crop' ? null : 'crop')}
                  >
                    <Crop aria-hidden className="size-4" />
                    {t.drawCrop}
                  </Button>
                  <Button
                    disabled={!crop || image?.source !== 'reference'}
                    onClick={() => void applyCrop()}
                  >
                    {t.useCrop}
                  </Button>
                </div>
              </div>
            ) : null}
            {kind === 'blob' && first ? (
              <div className="flex flex-col gap-1">
                <Button variant="secondary" className="self-start" onClick={teachSize}>
                  {a.teachSize}
                </Button>
                <p className="text-xs text-fg-muted">{a.teachSizeHint}</p>
              </div>
            ) : null}
            {schema && !(first && kind === 'fixed') ? (
              <SchemaForm
                schema={schema}
                level={level}
                value={locator.params ?? {}}
                errors={prefixed(fields, `job.geometry.fixtures.${i}.locator.params`)}
                onChange={(params) =>
                  setGeometry((g) => (g.fixtures[i].locator.params = params), false)
                }
              />
            ) : null}

            <fieldset className="flex flex-col gap-3 border-t border-line pt-3">
              <legend className="text-sm font-semibold">{a.rangeTitle}</legend>
              <p className="text-xs text-fg-muted">{a.rangeHint}</p>
              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium">{a.angle}</span>
                <AngleRangeDial
                  value={range.angle}
                  found={foundHere?.angle ?? null}
                  labels={[a.angleMin, a.angleMax]}
                  onChange={(angle) => setRange(i, (r) => (r.angle = angle))}
                />
                <div className="flex gap-3">
                  {([0, 1] as const).map((k) => (
                    <NumberField
                      key={k}
                      aria-label={k === 0 ? a.angleMin : a.angleMax}
                      value={range.angle[k]}
                      min={-180}
                      max={180}
                      decimals={1}
                      unit="°"
                      className="w-32"
                      onChange={(v) =>
                        v !== null &&
                        setRange(
                          i,
                          (r) =>
                            (r.angle =
                              k === 0
                                ? [v, Math.max(v, r.angle[1])]
                                : [Math.min(v, r.angle[0]), v]),
                        )
                      }
                    />
                  ))}
                </div>
                <p className="text-xs text-fg-muted">
                  {a.angleHint}
                  {foundHere ? ` ${a.found(formatNumber(foundHere.angle, 1))}` : ''}
                </p>
              </div>
              {level >= 2 ? (
                <>
                  <div className="flex gap-3">
                    {([0, 1] as const).map((k) => (
                      <Field key={k} label={k === 0 ? a.scaleMin : a.scaleMax}>
                        {(props) => (
                          <NumberField
                            {...props}
                            value={range.scale[k]}
                            min={0.01}
                            step={0.05}
                            decimals={2}
                            unit="×"
                            onChange={(v) =>
                              v !== null &&
                              setRange(
                                i,
                                (r) =>
                                  (r.scale =
                                    k === 0
                                      ? [v, Math.max(v, r.scale[1])]
                                      : [Math.min(v, r.scale[0]), v]),
                              )
                            }
                          />
                        )}
                      </Field>
                    ))}
                  </div>
                  <Switch
                    checked={range.position !== null && range.position !== undefined}
                    onCheckedChange={(on) => {
                      setRange(i, (r) => (r.position = on ? [0.1, 0.1, 0.9, 0.9] : null), true)
                      if (!on && drawing === `position:${i}`) setDrawing(null)
                    }}
                    label={a.position}
                    hint={a.positionHint}
                  />
                  {range.position ? (
                    <Button
                      variant={drawing === `position:${i}` ? 'primary' : 'secondary'}
                      className="self-start"
                      onClick={() =>
                        setDrawing(drawing === `position:${i}` ? null : `position:${i}`)
                      }
                    >
                      {drawing === `position:${i}` ? t.drawingNow : a.drawPosition}
                    </Button>
                  ) : null}
                </>
              ) : null}
            </fieldset>
          </section>
        )
      })}
      {fixtures.length > 0 && level >= 2 ? (
        <div className="flex flex-col gap-1">
          <Button
            variant="secondary"
            className="self-start"
            onClick={() =>
              setGeometry((g) => {
                const list = g.fixtures as JobJson[]
                list.push({
                  name: freeName(draft.job),
                  inside: list.at(-1)!.name,
                  locator: {
                    type: 'blob',
                    version: newest(locators, 'blob'),
                    params: { mode: 'dark' },
                  },
                })
              })
            }
          >
            <Plus aria-hidden className="size-4" />
            {a.addInside}
          </Button>
          <p className="text-xs text-fg-muted">{a.addInsideHint}</p>
        </div>
      ) : null}

      <Results
        samples={locating.out?.samples ?? []}
        stale={locating.stale || locating.loading}
        draft={draft}
        shown={picture}
        onShow={(path) => showSample(path === REFERENCE ? REFERENCE : path)}
        fixtures={fixtures.length}
        error={locating.error}
      />
    </div>
  )
}

/** The kinds of locator as cards: a word, a line of use and a small picture; one is chosen at a time. */
function KindCards({
  value,
  onChange,
  first,
}: {
  value: Kind | 'none'
  onChange: (kind: Kind | 'none') => void
  first: boolean
}) {
  const items: (Kind | 'none')[] = first ? ['none', ...KINDS] : [...KINDS]
  const move = (e: React.KeyboardEvent, i: number) => {
    const to =
      e.key === 'ArrowRight' || e.key === 'ArrowDown'
        ? i + 1
        : e.key === 'ArrowLeft' || e.key === 'ArrowUp'
          ? i - 1
          : null
    if (to === null) return
    e.preventDefault()
    const next = items[(to + items.length) % items.length]!
    onChange(next)
    ;(
      e.currentTarget.parentElement?.children[(to + items.length) % items.length] as
        HTMLElement | undefined
    )?.focus()
  }
  return (
    <div role="radiogroup" aria-label={a.kindsLabel} className="grid grid-cols-2 gap-2">
      {items.map((kind, i) => (
        <button
          key={kind}
          type="button"
          role="radio"
          aria-checked={value === kind}
          tabIndex={value === kind ? 0 : -1}
          onClick={() => onChange(kind)}
          onKeyDown={(e) => move(e, i)}
          className={cn(
            'flex flex-col items-start gap-1 rounded-control border p-2 text-left',
            value === kind ? 'border-accent bg-accent/10' : 'border-line hover:bg-surface-3',
          )}
        >
          <Diagram kind={kind} />
          <span className="text-sm font-medium">{a.kinds[kind]}</span>
          <span className="text-xs text-fg-muted">{a.uses[kind]}</span>
        </button>
      ))}
    </div>
  )
}

/** A small drawing of what each kind does; decorative, the card says it in words. */
function Diagram({ kind }: { kind: Kind | 'none' }) {
  return (
    <svg aria-hidden viewBox="0 0 48 32" className="h-8 w-12 text-fg-muted">
      <rect
        x="1"
        y="1"
        width="46"
        height="30"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeDasharray={kind === 'none' ? '3 2' : undefined}
      />
      {kind === 'fixed' ? (
        <rect
          x="14"
          y="8"
          width="20"
          height="16"
          fill="none"
          className="stroke-accent"
          strokeWidth="2"
        />
      ) : null}
      {kind === 'template' ? (
        <>
          <rect
            x="10"
            y="9"
            width="14"
            height="14"
            fill="none"
            className="stroke-accent"
            strokeWidth="2"
          />
          <path d="M31 12h10M36 7v10" className="stroke-fg" strokeWidth="1.5" />
        </>
      ) : null}
      {kind === 'blob' ? (
        <polygon
          points="14,20 28,8 36,16 22,28"
          fill="none"
          className="stroke-accent"
          strokeWidth="2"
        />
      ) : null}
    </svg>
  )
}

/** The anchor on the reference and every sample: the picture with the found outline, the score and the turn; not found is amber, with the reason. */
function Results({
  samples,
  stale,
  draft,
  shown,
  onShow,
  fixtures,
  error,
}: {
  samples: LocateSample[]
  stale: boolean
  draft: Parameters<typeof useThumbnail>[0]
  shown: string
  onShow: (path: string) => void
  fixtures: number
  error: string
}) {
  return (
    <section aria-label={a.resultsTitle} className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{a.resultsTitle}</h3>
      {error ? (
        <p role="alert" className="text-sm text-fail-text">
          {error}
        </p>
      ) : null}
      {fixtures === 0 || samples.length === 0 ? (
        <p className="text-sm text-fg-muted">{a.resultsNone}</p>
      ) : null}
      {stale && samples.length > 0 ? (
        <p className="text-xs text-fg-muted">{a.resultsStale}</p>
      ) : null}
      <ul className="grid grid-cols-2 gap-2">
        {samples.map((s) => (
          <li key={s.image}>
            <ResultTile
              sample={s}
              draft={draft}
              current={shown === s.image}
              onShow={() => onShow(s.image)}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}

function ResultTile({
  sample,
  draft,
  current,
  onShow,
}: {
  sample: LocateSample
  draft: Parameters<typeof useThumbnail>[0]
  current: boolean
  onShow: () => void
}) {
  const { ref, url } = useThumbnail<HTMLButtonElement>(draft, sample.image, 240)
  const name =
    sample.kind === 'reference'
      ? t.strip.reference
      : sample.image.replace('tests/images/', '').replace(/\.png$/, '')
  const first = sample.fixtures[0]
  const state = sample.found
    ? first
      ? a.pose(
          formatNumber(first.score * 100, 0) + '%',
          formatNumber(first.angle, 1),
          formatNumber(first.scale, 2),
        )
      : ''
    : sample.error_code === 202
      ? a.outOfRange
      : a.notFound
  return (
    <button
      ref={ref}
      type="button"
      aria-pressed={current}
      aria-label={a.tile(name, `${state}${sample.reason ? `. ${sample.reason}` : ''}`)}
      onClick={onShow}
      className={cn(
        'flex w-full flex-col gap-1 rounded-control border p-1 text-left',
        sample.found ? 'border-line' : 'border-warn-text/60 bg-warn-surface',
        current && 'outline-2 outline-accent',
      )}
    >
      <span className="relative block aspect-video overflow-hidden rounded-control bg-surface-2">
        {url ? <img src={url} alt="" draggable={false} className="size-full object-cover" /> : null}
        <svg
          aria-hidden
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          className="absolute inset-0 size-full"
        >
          {sample.fixtures.map((f) => (
            <polygon
              key={f.name}
              points={outlineOf(f, sample)
                .map(([x, y]) => `${x},${y}`)
                .join(' ')}
              className={cn(
                'fill-transparent',
                sample.found ? 'stroke-ok-text' : 'stroke-warn-text',
              )}
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      </span>
      <span className="flex items-center gap-1 text-xs">
        <span className="font-medium">{name}</span>
        {sample.found ? null : (
          <Badge tone="warn">{sample.error_code ? `E${sample.error_code}` : a.notFound}</Badge>
        )}
      </span>
      <span className={cn('text-xs', sample.found ? 'text-fg-muted' : 'text-warn-text')}>
        {sample.found ? state : sample.reason || state}
      </span>
    </button>
  )
}

/** The outline of a found fixture, fractions of the picture: the turned one when it has it, else its box. */
function outlineOf(f: FixtureShape, sample: { width: number; height: number }): [number, number][] {
  if (f.corners && !isUpright(f))
    return f.corners.map(([x, y]) => [x! / sample.width, y! / sample.height])
  const [x0, y0, x1, y1] = f.rect as [number, number, number, number]
  return [
    [x0, y0],
    [x1, y0],
    [x1, y1],
    [x0, y1],
  ]
}
