import { ArrowLeft, Save, Undo2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { describeError } from '@/api/mutations'
import { editorApi, useJobVersion, useTypes, type TuneOut } from '@/api/queries/editor'
import { useActivate, useJob } from '@/api/queries/jobs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Field } from '@/components/ui/field'
import { Textarea } from '@/components/ui/input'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { useBatch } from './batch'
import { ChangeList } from './EditorPage'
import { forgetDraft, toRequest, useDraft, type Draft, type JobJson } from './draft'
import { ToolGauges } from './gauges'
import { imageFromBlob, fetchBlob, base64ToBlob, type EditorImage } from './image'
import { RegionCanvas, type Shape } from './RegionCanvas'
import { useEditorSession } from './session'
import { summarizeChanges } from './summary'
import type { Rect } from './geometry'

const t = text.editor
const tune = t.tune

/**
 * The fine-tune of tolerances (docs/frontend.md §7.12, FR-JOB-14, UC-15): the Supervisor moves the limits of the tools
 * that decide, looking at the live image and at the samples, may add *Boa* and *Ruim* samples, and saves the result as
 * the next version with a note. The server accepts nothing else, so the screen does not offer it: no regions, no camera,
 * no tools, only the Essencial criteria.
 */
export function TunePage() {
  const { id = '' } = useParams()
  const detail = useJob(id)
  const latest = detail.data?.versions[0]?.version ?? null
  const version = useJobVersion(id, latest)
  const draft = useDraft((s) => s.draft)
  const load = useDraft((s) => s.load)

  useEffect(() => {
    if (!version.data || latest === null) return
    const v = version.data
    load({
      key: `tune:${id}`,
      base: { id, version: v.version },
      latest,
      job: v.job,
      profile: v.profile,
      baseFiles: v.files,
      addFiles: {},
      removeFiles: [],
      expected: (v.expected as Draft['expected']) ?? null,
      baseExpected: JSON.stringify(v.expected ?? null),
      baseJob: structuredClone(v.job),
      baseProfile: structuredClone(v.profile),
      notes: '',
    })
  }, [id, version.data, latest, load])
  useEffect(
    () => () => {
      forgetDraft(`tune:${id}`)
      useDraft.getState().clear()
    },
    [id],
  )

  if (detail.isError || version.isError)
    return (
      <main className="p-6">
        <ErrorState message={describeError(detail.error ?? version.error)} />
      </main>
    )
  if (!draft || draft.key !== `tune:${id}`)
    return (
      <main className="flex flex-col gap-2 p-6" aria-busy="true">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-96 w-full" />
      </main>
    )
  return <Tune draft={draft} name={detail.data?.name ?? ''} />
}

function Tune({ draft, name }: { draft: Draft; name: string }) {
  const navigate = useNavigate()
  const types = useTypes()
  const live = useEditorSession(draft, true)
  const limitParams = Object.fromEntries(
    (types.data?.tools ?? []).map((x) => [
      x.name,
      x.criteria.flatMap((c) => Object.values(c.limits)),
    ]),
  )
  const batch = useBatch(draft, true, limitParams)
  const base = draft.base!
  const next = (draft.latest ?? base.version) + 1
  const tools: JobJson[] = draft.job.tools ?? []
  const deciding = tools.filter((tool) => tool.affects_result !== false)
  const [shownSample, setShownSample] = useState<string | null>(null)
  const [image, setImage] = useState<EditorImage | null>(null)
  const [busy, setBusy] = useState<'good' | 'bad' | null>(null)
  const [saveOpen, setSaveOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<TuneOut | null>(null)
  const activate = useActivate()

  // the picture: a sample chosen on a gauge, else what the session sends
  const frame = shownSample ? null : live.frame
  useEffect(() => {
    let alive = true
    const get = async () => {
      await Promise.resolve()
      if (shownSample) {
        const added = draft.addFiles[shownSample]
        const blob = added
          ? base64ToBlob(added)
          : await fetchBlob(`/api/jobs/${base.id}/versions/${base.version}/files/${shownSample}`)
        return imageFromBlob(blob, 'sample')
      }
      return frame ? imageFromBlob(frame, 'live') : null
    }
    get().then(
      (made) => {
        if (!made) return
        if (!alive) return URL.revokeObjectURL(made.url)
        setImage((old) => {
          if (old) URL.revokeObjectURL(old.url)
          return made
        })
      },
      () => {},
    )
    return () => {
      alive = false
    }
  }, [shownSample, frame, base.id, base.version, draft.addFiles])

  const result = shownSample ? null : live.last
  const shapes = useMemo<Shape[]>(
    () =>
      (result?.regions ?? []).map((r) => ({
        id: `result:${r.tool}`,
        label: r.tool,
        rect: [
          r.rect[0]! / result!.width,
          r.rect[1]! / result!.height,
          r.rect[2]! / result!.width,
          r.rect[3]! / result!.height,
        ] as Rect,
        kind: r.passed ? 'pass' : 'fail',
      })),
    [result],
  )

  const newCases = (draft.expected?.cases ?? []).filter(
    (c) => !draft.baseFiles.some((f) => f.path === c.image),
  )
  const goodNew = newCases.filter((c) => c.outcome === 'PASS').length
  const badNew = newCases.filter((c) => c.outcome === 'FAIL').length
  const changes = summarizeChanges(draft, types.data)

  const capture = async (kind: 'good' | 'bad') => {
    setBusy(kind)
    try {
      const taken = new Set((draft.expected?.cases ?? []).map((c) => c.image))
      let n = 1
      const prefix = kind === 'good' ? 'boa' : 'ruim'
      while (taken.has(`tests/images/${prefix}-ajuste-${n}.png`)) n++
      const sampleName = `${prefix}-ajuste-${n}`
      const out = await editorApi.captureCase(toRequest(draft), sampleName)
      useDraft.getState().edit((d) => {
        d.addFiles[out.path] = out.image
        d.expected ??= { tolerance: 0.05, cases: [] }
        d.expected.cases.push({ image: out.path, outcome: kind === 'good' ? 'PASS' : 'FAIL' })
      })
      toast.message(tune.captured(sampleName, t.outcome[out.result.outcome]))
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      setSaved(await editorApi.tune(base.id, toRequest(draft)))
      setSaveOpen(false)
    } catch (e) {
      toast.error(
        e instanceof ApiError && e.fields ? Object.values(e.fields).join('; ') : describeError(e),
      )
    } finally {
      setSaving(false)
    }
  }

  const { undo, past } = useDraft()
  const measuredOf = (id: string) => result?.result.tools?.find((x) => x.id === id) ?? null

  return (
    <main className="flex flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-3">
        <Link
          to={`/jobs/${base.id}`}
          className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"
        >
          <ArrowLeft aria-hidden className="size-4" />
          {text.jobs.back}
        </Link>
        <h1 className="text-lg font-semibold">{tune.title(name, base.version)}</h1>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" aria-label={t.undo} disabled={past.length === 0} onClick={undo}>
            <Undo2 aria-hidden className="size-4" />
          </Button>
          <Button
            variant="ghost"
            disabled={changes.length === 0}
            onClick={() => {
              useDraft.getState().clear()
              void navigate(0)
            }}
          >
            {tune.discardAll}
          </Button>
          <Button
            variant="primary"
            disabled={changes.length === 0}
            onClick={() => setSaveOpen(true)}
          >
            <Save aria-hidden className="size-4" />
            {tune.saveAs(next)}
          </Button>
        </div>
      </header>
      <p className="text-sm text-fg-muted">{tune.intro}</p>

      <div className="grid-tune grid gap-4">
        <section
          aria-label={t.imageLabel}
          className="flex min-w-0 flex-col gap-3 sticky top-4 self-start"
        >
          <div className="flex flex-wrap items-center gap-2">
            {live.status === 'live' ? (
              <Badge tone="ok">{t.liveOn(formatNumber(live.fps, 1))}</Badge>
            ) : (
              <Badge tone="neutral">{t.liveState[live.status]}</Badge>
            )}
            {shownSample ? (
              <Button variant="ghost" onClick={() => setShownSample(null)}>
                {t.sampleBack}
              </Button>
            ) : null}
            <Button
              variant="secondary"
              loading={busy === 'good'}
              disabled={live.camera === false || busy !== null}
              onClick={() => void capture('good')}
            >
              {tune.captureGood}
            </Button>
            <Button
              variant="secondary"
              loading={busy === 'bad'}
              disabled={live.camera === false || busy !== null}
              onClick={() => void capture('bad')}
            >
              {tune.captureBad}
            </Button>
          </div>
          {live.camera === false ? <p className="text-sm text-warn-text">{tune.noCamera}</p> : null}
          {goodNew + badNew > 0 ? (
            <p className="text-sm text-fg-muted">{tune.added(goodNew, badNew)}</p>
          ) : null}
          <RegionCanvas
            image={image}
            shapes={shapes}
            selected={null}
            onSelect={() => {}}
            onChange={() => {}}
            drawing={null}
            emptyText={t.loadingImage}
          />
          {result ? (
            <Card>
              <CardContent className="flex items-center gap-2">
                <Badge
                  tone={
                    result.result.outcome === 'PASS'
                      ? 'ok'
                      : result.result.outcome === 'FAIL'
                        ? 'fail'
                        : 'warn'
                  }
                >
                  {t.outcome[result.result.outcome]}
                </Badge>
                <span className="text-sm">{result.result.reason}</span>
              </CardContent>
            </Card>
          ) : null}
        </section>

        <section aria-label={t.steps.tools} className="flex min-w-0 flex-col gap-3">
          {deciding.length === 0 ? <p className="text-sm text-fg-muted">{tune.noTools}</p> : null}
          {deciding.map((tool) => {
            const index = tools.indexOf(tool)
            const type = types.data?.tools.find((x) => x.name === tool.type)
            const measured = measuredOf(tool.id)
            return (
              <Card key={tool.id}>
                <CardContent className="flex flex-col gap-3">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    {tool.id}
                    {measured ? (
                      <Badge tone={measured.passed ? 'ok' : 'fail'}>
                        {measured.passed ? tune.toolPasses : tune.toolFails}
                      </Badge>
                    ) : null}
                  </h2>
                  {type && type.criteria.some((c) => c.level <= 1) ? (
                    <ToolGauges
                      draft={draft}
                      index={index}
                      type={type}
                      batch={batch.out}
                      stale={batch.stale || batch.loading}
                      measured={measured}
                      selectedSample={shownSample}
                      onShowSample={setShownSample}
                      level={1}
                    />
                  ) : (
                    <p className="text-sm text-fg-muted">{tune.noTools}</p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </section>
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent title={tune.saveTitle(next)} description={tune.saveBody(next)}>
          <ChangeList draft={draft} />
          <Field label={tune.note} hint={tune.noteHint}>
            {(p) => (
              <Textarea
                {...p}
                rows={3}
                value={draft.notes}
                onChange={(e) => useDraft.getState().edit((d) => (d.notes = e.target.value), false)}
              />
            )}
          </Field>
          <DialogFooter>
            <Button onClick={() => setSaveOpen(false)}>{text.ui.cancel}</Button>
            <Button
              variant="primary"
              loading={saving}
              disabled={!draft.notes.trim()}
              onClick={() => void save()}
            >
              {t.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={saved !== null} onOpenChange={(o) => !o && void navigate(`/jobs/${base.id}`)}>
        <DialogContent
          title={tune.saveTitle(saved?.version ?? next)}
          description={
            saved?.verified
              ? tune.verified(saved.version)
              : tune.notVerified(saved?.version ?? next)
          }
        >
          {saved && saved.problems.length > 0 ? (
            <ul className="list-disc pl-5 text-sm text-fail-text">
              {saved.problems.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          ) : null}
          <DialogFooter>
            <Button onClick={() => void navigate(`/jobs/${base.id}`)}>{tune.close}</Button>
            {saved?.verified ? (
              <Button
                variant="primary"
                loading={activate.isPending}
                onClick={() =>
                  activate.mutate(
                    { id: base.id, version: saved.version },
                    {
                      onSuccess: () => {
                        toast.success(tune.activated(saved.version))
                        void navigate(`/jobs/${base.id}`)
                      },
                      onError: (e) => toast.error(describeError(e)),
                    },
                  )
                }
              >
                {tune.activate(saved.version)}
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  )
}
