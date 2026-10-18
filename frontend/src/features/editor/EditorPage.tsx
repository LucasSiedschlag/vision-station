import { ArrowLeft, FlaskConical, Redo2, RefreshCw, Save, Undo2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useBlocker, useNavigate, useParams, useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { useLive } from '@/api/live'
import { describeError } from '@/api/mutations'
import {
  editorApi,
  useCameraState,
  useJobVersion,
  useTypes,
  type DraftTestOut,
} from '@/api/queries/editor'
import { useJob } from '@/api/queries/jobs'
import { useLevel } from '@/app/levels'
import { LevelSwitch } from '@/app/shell/LevelSwitch'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ConfirmDialog, Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Textarea } from '@/components/ui/input'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { Stepper } from '@/components/ui/stepper'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import {
  draftFiles,
  forgetDraft,
  newDraft,
  savedDraft,
  toRequest,
  useDraft,
  type Draft,
  type JobJson,
} from './draft'
import { anchorToFrame, frameToAnchor, type Rect } from './geometry'
import { base64ToBlob, fetchBlob, imageFromBlob, type EditorImage } from './image'
import { RegionCanvas, type Shape } from './RegionCanvas'
import { hiddenChanged } from './SchemaForm'
import {
  CameraStep,
  PatternCrop,
  QualityStep,
  ReferenceStep,
  RegionsStep,
  ReviewStep,
  ToolsStep,
  TriggerStep,
  type StepProps,
} from './steps'

const t = text.editor
const STEPS = ['camera', 'trigger', 'quality', 'regions', 'tools', 'reference', 'review'] as const
type StepId = (typeof STEPS)[number]
/** which server field paths belong to which step, to mark a step that has errors */
const STEP_FIELDS: Record<StepId, string[]> = {
  camera: ['profile'],
  trigger: ['job.trigger', 'job.ui'],
  quality: ['job.quality'],
  regions: ['job.geometry'],
  tools: ['job.tools', 'job.decision'],
  reference: ['add_files'],
  review: ['job.job', 'job.format'],
}

/** The job editor (docs/frontend.md §7.3): a draft in this browser until it is saved as a new version. */
export function EditorPage() {
  const { id = 'new' } = useParams()
  const [params] = useSearchParams()
  const isNew = id === 'new'
  const detail = useJob(isNew ? '' : id)
  const latest = detail.data?.versions[0]?.version ?? null
  const from = params.get('from') ? Number(params.get('from')) : latest
  const version = useJobVersion(isNew ? null : id, isNew ? null : from)
  const camera = useCameraState(isNew)
  const { draft, dirty, recovered, forgetRecovered, load, undo, redo, past, future } = useDraft()
  // start from the saved version (or a new job), or from the draft this browser kept for it
  useEffect(() => {
    if (isNew) {
      if (camera.isPending) return
      const kept = savedDraft('new')
      if (kept) {
        load(kept, true)
      } else load(newDraft(camera.data?.profile ?? null))
      return
    }
    if (!version.data || latest === null) return
    const v = version.data
    const kept = savedDraft(id)
    if (kept && kept.base?.version === v.version) {
      load(kept, true)
      return
    }
    load({
      key: id,
      base: { id, version: v.version },
      latest,
      job: v.job,
      profile: v.profile,
      baseFiles: v.files,
      addFiles: {},
      removeFiles: [],
      expected: (v.expected as Draft['expected']) ?? null,
      baseExpected: JSON.stringify(v.expected ?? null),
      notes: '',
    })
  }, [isNew, id, version.data, latest, camera.isPending, camera.data, load])

  useEffect(() => () => useDraft.getState().clear(), [])

  if ((!isNew && (detail.isPending || version.isPending)) || !draft) {
    if (detail.isError || version.isError)
      return (
        <main className="p-6">
          <ErrorState message={describeError(detail.error ?? version.error)} />
        </main>
      )
    return (
      <main className="flex flex-col gap-2 p-6" aria-busy="true">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-96 w-full" />
      </main>
    )
  }
  return (
    <Editor
      draft={draft}
      dirty={dirty}
      isNew={isNew}
      recovered={recovered}
      onForget={forgetRecovered}
      canUndo={past.length > 0}
      canRedo={future.length > 0}
      undo={undo}
      redo={redo}
    />
  )
}

function Editor({
  draft,
  dirty,
  isNew,
  recovered,
  onForget,
  canUndo,
  canRedo,
  undo,
  redo,
}: {
  draft: Draft
  dirty: boolean
  isNew: boolean
  recovered: boolean
  onForget: () => void
  canUndo: boolean
  canRedo: boolean
  undo: () => void
  redo: () => void
}) {
  const navigate = useNavigate()
  const [step, setStep] = useState<StepId>(isNew ? 'camera' : 'regions')
  const types = useTypes()
  const [level] = useLevel('editor')
  // every setting the level hides that was changed, in all the tools and the locator
  const hidden = (draft.job.tools ?? []).reduce(
    (sum: number, tool: JobJson) =>
      sum +
      hiddenChanged(
        types.data?.tools.find((t) => t.name === tool.type)?.params_schema ?? {},
        tool.params ?? {},
        level,
      ).length,
    hiddenChanged(
      types.data?.locators.find((l) => l.name === draft.job.geometry?.locator?.type)
        ?.params_schema ?? {},
      draft.job.geometry?.locator?.params ?? {},
      level,
    ).length,
  )

  const [selected, setSelected] = useState<string | null>(null)
  const [drawing, setDrawing] = useState<string | null>(null)
  const [crop, setCrop] = useState<Rect | null>(null)
  const [test, setTest] = useState<DraftTestOut | null>(null)
  const [testing, setTesting] = useState(false)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [source, setSource] = useState<'reference' | 'live'>('reference')
  const [image, setImage] = useState<EditorImage | null>(null)
  const [imageError, setImageError] = useState('')
  const paused = useLive((s) => s.status?.state === 'Paused')

  const hasReference = draftFiles(draft).includes('reference/reference.png')
  const referenceKey =
    draft.addFiles['reference/reference.png']?.slice(0, 64) ??
    (draft.base ? `${draft.base.id}@${draft.base.version}` : '')

  // the image: the job's reference (full size) when there is one, else a live snapshot
  const [reload, setReload] = useState(0)
  const useReference = source === 'reference' && hasReference
  useEffect(() => {
    let alive = true
    const added = draft.addFiles['reference/reference.png']
    const base = draft.base
    const fetchImage = async () => {
      await Promise.resolve() // state changes only after this tick, never during the effect
      const blob = useReference
        ? added
          ? base64ToBlob(added)
          : await fetchBlob(
              `/api/jobs/${base!.id}/versions/${base!.version}/files/reference/reference.png`,
            )
        : await fetchBlob('/api/snapshot.jpg')
      return imageFromBlob(blob, useReference ? 'reference' : 'live')
    }
    fetchImage().then(
      (next) => {
        if (!alive) return URL.revokeObjectURL(next.url)
        setImageError('')
        setImage((old) => {
          if (old) URL.revokeObjectURL(old.url)
          return next
        })
      },
      (e: unknown) => {
        if (!alive) return
        setImage(null)
        setImageError(
          e instanceof ApiError && e.code === 'no_frame' ? text.operator.noImage : describeError(e),
        )
      },
    )
    return () => {
      alive = false
    }
    // referenceKey: reload when the reference image changes; reload: the button
  }, [useReference, referenceKey, reload]) // eslint-disable-line react-hooks/exhaustive-deps

  // Ctrl+Z / Ctrl+Y, unless typing in a field
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement | null)?.closest('input,textarea,[contenteditable]')
      if (typing || !(e.ctrlKey || e.metaKey)) return
      if (e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      } else if (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey)) {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      // read the store, not this render's values: saving and discarding clear it just before they navigate
      useDraft.getState().dirty && currentLocation.pathname !== nextLocation.pathname,
  )

  // --- what is drawn over the image ------------------------------------------------------------------
  const geometry = draft.job.geometry ?? {}
  const locator = geometry.locator
  const anchor: Rect | null =
    locator?.type === 'fixed'
      ? (locator.params?.rect ?? null)
      : ((test?.anchor as Rect | undefined) ?? null)
  const shapes = useMemo<Shape[]>(() => {
    const out: Shape[] = []
    const editRegions = step === 'regions'
    if (
      step === 'trigger' &&
      draft.job.trigger?.mode === 'image_presence' &&
      draft.job.trigger.presence_roi
    )
      out.push({
        id: 'presence',
        label: t.presenceArea,
        rect: draft.job.trigger.presence_roi,
        kind: 'presence',
        editable: true,
      })
    if (locator?.type === 'fixed' && locator.params?.rect)
      out.push({
        id: 'locator',
        label: t.anchorLabel,
        rect: locator.params.rect,
        kind: 'locator',
        editable: editRegions,
      })
    else if (anchor) out.push({ id: 'anchor', label: t.anchorLabel, rect: anchor, kind: 'anchor' })
    if (step !== 'camera' && step !== 'trigger')
      for (const [name, roi] of Object.entries(
        (geometry.rois ?? {}) as Record<string, { relative_to: string; rect: Rect }>,
      )) {
        if (roi.relative_to === 'anchor' && !anchor) continue
        out.push({
          id: `roi:${name}`,
          label: name,
          rect: roi.relative_to === 'anchor' ? anchorToFrame(roi.rect, anchor!) : roi.rect,
          kind: 'roi',
          editable: editRegions,
        })
      }
    if (crop)
      out.push({ id: 'crop', label: t.cropLabel, rect: crop, kind: 'presence', editable: true })
    if (test && (step === 'tools' || step === 'review'))
      for (const r of test.regions)
        out.push({
          id: `result:${r.tool}`,
          label: r.tool,
          rect: [
            r.rect[0]! / test.width,
            r.rect[1]! / test.height,
            r.rect[2]! / test.width,
            r.rect[3]! / test.height,
          ],
          kind: r.passed ? 'pass' : 'fail',
        })
    return out
  }, [draft, step, anchor, locator, geometry.rois, crop, test])
  const hiddenAnchored =
    Object.values((geometry.rois ?? {}) as Record<string, { relative_to: string }>).some(
      (r) => r.relative_to === 'anchor',
    ) && !anchor

  const onShapeChange = (shapeId: string, rect: Rect, first: boolean) => {
    if (shapeId === 'crop') {
      setCrop(rect)
      return
    }
    const edit = useDraft.getState().edit
    edit((d) => {
      if (shapeId === 'presence') d.job.trigger.presence_roi = rect
      else if (shapeId === 'locator')
        d.job.geometry.locator.params = { ...d.job.geometry.locator.params, rect }
      else if (shapeId.startsWith('roi:')) {
        const roi = d.job.geometry.rois[shapeId.slice(4)]
        roi.rect = roi.relative_to === 'anchor' && anchor ? frameToAnchor(rect, anchor) : rect
      }
    }, first)
  }
  const onShapeDelete = (shapeId: string) => {
    if (shapeId.startsWith('roi:'))
      useDraft.getState().edit((d) => delete d.job.geometry.rois[shapeId.slice(4)])
    setSelected(null)
  }

  // --- test and save ------------------------------------------------------------------------------------
  const runTest = async () => {
    setTesting(true)
    try {
      setTest(await editorApi.test(toRequest(draft)))
      setFields({})
    } catch (e) {
      if (e instanceof ApiError && e.fields) setFields(e.fields)
      toast.error(describeError(e))
    } finally {
      setTesting(false)
    }
  }
  const save = async () => {
    setSaving(true)
    try {
      const body = toRequest(draft)
      const saved = isNew
        ? await editorApi.create(body)
        : await editorApi.saveVersion(draft.base!.id, body)
      forgetDraft(draft.key)
      useDraft.setState({ dirty: false })
      toast.success(t.saved(saved.version))
      void navigate(`/jobs/${saved.id}`)
    } catch (e) {
      if (e instanceof ApiError && e.fields) setFields(e.fields)
      toast.error(describeError(e))
      setSaving(false)
      setSaveOpen(false) // back to the editor, where the steps with problems are marked
    }
  }
  const discard = () => {
    forgetDraft(draft.key)
    useDraft.setState({ dirty: false })
    void navigate(draft.base ? `/jobs/${draft.base.id}` : '/jobs')
  }

  const props: StepProps = {
    draft,
    image,
    fields,
    selected,
    setSelected,
    drawing,
    setDrawing: (d) => (setDrawing(d), d !== 'crop' && setCrop(null)),
    crop,
    setCrop,
    test,
  }
  const errorIn = (s: StepId) =>
    Object.keys(fields).some((k) => STEP_FIELDS[s].some((p) => k === p || k.startsWith(`${p}.`)))
  const steps = STEPS.map((s) => ({
    id: s,
    label: t.steps[s],
    status: s === step ? ('current' as const) : errorIn(s) ? ('error' as const) : ('todo' as const),
  }))

  return (
    <main className="flex flex-col gap-4 p-4">
      <header className="flex flex-wrap items-center gap-3">
        <Link
          to={draft.base ? `/jobs/${draft.base.id}` : '/jobs'}
          className="inline-flex items-center gap-1 text-sm text-accent-text hover:underline"
        >
          <ArrowLeft aria-hidden className="size-4" />
          {text.jobs.back}
        </Link>
        <h1 className="text-lg font-semibold">{draft.job.job?.name}</h1>
        <Badge tone="neutral">{draft.base ? t.draftOf(draft.base.version) : t.newJob}</Badge>
        {dirty ? <Badge tone="warn">{t.unsaved}</Badge> : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <LevelSwitch family="editor" hidden={hidden} />
          <Button variant="ghost" aria-label={t.undo} disabled={!canUndo} onClick={undo}>
            <Undo2 aria-hidden className="size-4" />
          </Button>
          <Button variant="ghost" aria-label={t.redo} disabled={!canRedo} onClick={redo}>
            <Redo2 aria-hidden className="size-4" />
          </Button>
          <Button variant="ghost" onClick={() => setDiscardOpen(true)}>
            {t.discard}
          </Button>
          <Button loading={testing} onClick={() => void runTest()}>
            <FlaskConical aria-hidden className="size-4" />
            {t.test}
          </Button>
          <Button variant="primary" onClick={() => setSaveOpen(true)}>
            <Save aria-hidden className="size-4" />
            {t.save}
          </Button>
        </div>
      </header>

      {recovered ? (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-control border border-warn-text/40 bg-warn-surface px-3 py-2 text-sm text-warn-text"
        >
          {t.recovered}
          <Button variant="ghost" onClick={() => (onForget(), setDiscardOpen(true))}>
            {t.discardRecovered}
          </Button>
        </div>
      ) : null}
      {paused ? (
        <div
          role="status"
          className="flex flex-wrap items-center gap-3 rounded-control border border-busy-text/40 bg-busy-surface px-3 py-2 text-sm text-busy-text"
        >
          {t.stationPaused}
          <Button
            variant="ghost"
            onClick={() =>
              void editorApi.resumeStation().catch((e: unknown) => toast.error(describeError(e)))
            }
          >
            {t.resume}
          </Button>
        </div>
      ) : null}

      <div className="grid-editor grid gap-4">
        <nav aria-label={t.stepsLabel}>
          <Stepper
            steps={steps}
            onSelect={(s) => (setStep(s as StepId), setDrawing(null), setCrop(null))}
          />
        </nav>

        <section aria-label={t.imageLabel} className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <SegmentedControl
              label={t.imageSource}
              value={useReference ? 'reference' : 'live'}
              onValueChange={(v) => setSource(v as 'reference' | 'live')}
              options={[
                { value: 'reference', label: t.sourceReference, disabled: !hasReference },
                { value: 'live', label: t.sourceLive },
              ]}
            />
            <Button variant="ghost" onClick={() => setReload((n) => n + 1)}>
              <RefreshCw aria-hidden className="size-4" />
              {t.refreshImage}
            </Button>
            {drawing ? <Badge tone="busy">{t.drawingHint}</Badge> : null}
          </div>
          {hiddenAnchored && step !== 'camera' && step !== 'trigger' ? (
            <p className="text-sm text-warn-text">{t.noAnchor}</p>
          ) : null}
          <RegionCanvas
            image={image}
            shapes={shapes}
            selected={selected}
            onSelect={setSelected}
            onChange={onShapeChange}
            onDelete={onShapeDelete}
            drawing={drawing}
            emptyText={imageError || t.loadingImage}
          />
          {test ? (
            <Card>
              <CardContent className="flex flex-col gap-2">
                <p role="status" className="flex flex-wrap items-center gap-2">
                  <Badge
                    tone={
                      test.result.outcome === 'PASS'
                        ? 'ok'
                        : test.result.outcome === 'FAIL'
                          ? 'fail'
                          : 'warn'
                    }
                  >
                    {t.outcome[test.result.outcome]}
                  </Badge>
                  <span className="text-sm">{test.result.reason}</span>
                  <span className="ml-auto font-mono text-xs text-fg-muted tabular-nums">
                    {test.result.duration_ms} ms
                  </span>
                </p>
                {Object.keys(test.result.scores).length ? (
                  <p className="font-mono text-xs tabular-nums">
                    {Object.entries(test.result.scores)
                      .map(([k, v]) => `${k}: ${formatNumber(v, 2)}`)
                      .join(' · ')}
                  </p>
                ) : null}
                <p className="text-xs text-fg-muted">{t.testNote}</p>
              </CardContent>
            </Card>
          ) : null}
        </section>

        <section aria-labelledby="inspector-title" className="flex min-w-0 flex-col gap-4">
          <h2 id="inspector-title" className="text-base font-semibold">
            {t.steps[step]}
          </h2>
          {step === 'camera' ? <CameraStep {...props} /> : null}
          {step === 'trigger' ? <TriggerStep {...props} /> : null}
          {step === 'quality' ? <QualityStep {...props} /> : null}
          {step === 'regions' ? <RegionsStep {...props} /> : null}
          {step === 'tools' ? (
            <>
              <ToolsStep {...props} />
              <PatternCrop {...props} />
            </>
          ) : null}
          {step === 'reference' ? <ReferenceStep {...props} /> : null}
          {step === 'review' ? <ReviewStep {...props} /> : null}
        </section>
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent
          title={
            draft.base ? t.saveTitle((draft.latest ?? draft.base.version) + 1) : t.saveNewTitle
          }
          description={t.saveBody}
        >
          <Field label={t.notes} hint={t.notesHint}>
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
            <Button variant="primary" loading={saving} onClick={() => void save()}>
              {t.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={discardOpen}
        onOpenChange={setDiscardOpen}
        title={t.discardTitle}
        description={t.discardBody}
        confirmLabel={t.discard}
        tone="danger"
        onConfirm={discard}
      />
      <ConfirmDialog
        open={blocker.state === 'blocked'}
        onOpenChange={(o) => !o && blocker.reset?.()}
        title={t.leaveTitle}
        description={t.leaveBody}
        confirmLabel={t.leave}
        onConfirm={() => blocker.proceed?.()}
      />
    </main>
  )
}
