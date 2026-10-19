import { ArrowLeft, ArrowRight, FlaskConical, Redo2, RefreshCw, Save, Undo2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  type VerifyOut,
} from '@/api/queries/editor'
import { useJob } from '@/api/queries/jobs'
import { useLevel } from '@/app/levels'
import { Select } from '@/components/ui/select'
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
import { anchorToFrame, frameToAnchor, fromCorners, type Rect } from './geometry'
import {
  base64ToBlob,
  cropPng,
  fetchBlob,
  imageFromBlob,
  pixelsOf,
  type EditorImage,
} from './image'
import { ImageAidsProvider, type ImageAids } from './image-aids'
import { maskGrid, type HsvRange } from '@/components/vision/hsv-model'
import { describeHsv } from '@/components/vision/hsv-model'
import { RegionCanvas, type Shape } from './RegionCanvas'
import { hiddenChanged } from './SchemaForm'
import {
  CameraStep,
  PatternCrop,
  QualityStep,
  ReferenceStep,
  RegionsStep,
  ToolsStep,
  TriggerStep,
  setTriggerMode,
  type StepProps,
} from './steps'
import { OutputsStep, SaveStep, ValidateStep } from './steps-end'
import {
  STEPS,
  fullSignature,
  imageSignature,
  stepStates,
  type StepId,
  type Validation,
} from './sequence'
import { summarizeChanges } from './summary'
import { useBatch } from './batch'
import { useEditorSession } from './session'

const t = text.editor

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
      baseJob: structuredClone(v.job),
      baseProfile: structuredClone(v.profile),
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
  // editing an existing job opens where most edits happen: the tools (docs/frontend.md §4.3)
  const [step, setStepNow] = useState<StepId>(isNew ? 'image' : 'tools')
  const [visited, setVisited] = useState<ReadonlySet<StepId>>(
    () => new Set([isNew ? 'image' : 'tools']),
  )
  const setStep = (next: StepId) => {
    setStepNow(next)
    setVisited((now) => new Set(now).add(next))
  }
  const [validation, setValidation] = useState<Validation | null>(null)
  const [report, setReport] = useState<VerifyOut | null>(null)
  const [verifying, setVerifying] = useState(false)
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
  const [tested, setTested] = useState<DraftTestOut | null>(null) // the last *Testar*
  const live = useEditorSession(draft, true) // the draft on every new frame, with the station paused (§9.5)
  const [testing, setTesting] = useState(false)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saveOpen, setSaveOpen] = useState(false)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [source, setSource] = useState<'reference' | 'live'>('reference')
  // the sample whose picture is on the image because its dot was chosen on a gauge
  const [shownSample, setShownSample] = useState<string | null>(null)
  const limitParams = Object.fromEntries(
    (types.data?.tools ?? []).map((x) => [
      x.name,
      x.criteria.flatMap((c) => Object.values(c.limits)),
    ]),
  )
  const batch = useBatch(draft, step === 'tools' || step === 'validate', limitParams)
  const showSample = (path: string | null) => {
    if (path === 'reference/reference.png') {
      setSource('reference')
      setShownSample(null)
    } else setShownSample(path)
  }
  const [image, setImage] = useState<EditorImage | null>(null)
  const [imageError, setImageError] = useState('')
  const [decoded, setDecoded] = useState<{ url: string; data: ImageData | null } | null>(null)
  const pixels = decoded && image && decoded.url === image.url ? decoded.data : null
  useEffect(() => {
    let alive = true
    if (image) void pixelsOf(image).then((data) => alive && setDecoded({ url: image.url, data }))
    return () => {
      alive = false
    }
  }, [image])
  // colour aids (docs/frontend.md §19.4): a drag on the image that samples colours, and a mask drawn over it
  const [sampling, setSampling] = useState<'include' | 'exclude' | null>(null)
  const pending = useRef<((png: string | null) => void) | null>(null)
  const [sampleRect, setSampleRect] = useState<Rect | null>(null)
  const latestSample = useRef<Rect | null>(null)
  const finishSample = useCallback((png: string | null) => {
    const done = pending.current
    pending.current = null
    latestSample.current = null
    setSampling(null)
    setSampleRect(null)
    setDrawing(null)
    done?.(png)
  }, [])
  const startSample = useCallback(
    (mode: 'include' | 'exclude') =>
      new Promise<string | null>((resolve) => {
        pending.current?.(null)
        pending.current = resolve
        latestSample.current = null
        setSampleRect(null)
        setSampling(mode)
        setDrawing('sample')
      }),
    [],
  )
  // leaving the drag mode any other way (another step, another tool) ends it: the wait is dropped at the next one
  const activeSampling = drawing === 'sample' ? sampling : null
  const [maskRange, setMaskRange] = useState<HsvRange | null>(null)
  const mask = useMemo(
    () => (pixels && maskRange ? maskGrid(pixels, maskRange) : null),
    [pixels, maskRange],
  )
  const paused = useLive((s) => s.status?.state === 'Paused')

  const hasReference = draftFiles(draft).includes('reference/reference.png')
  const referenceKey =
    draft.addFiles['reference/reference.png']?.slice(0, 64) ??
    (draft.base ? `${draft.base.id}@${draft.base.version}` : '')

  // the image: the job's reference (full size) when there is one, else a live snapshot
  const [reload, setReload] = useState(0)
  const useReference = source === 'reference' && hasReference
  // the picture on screen is the camera's, so the session's measurements are of what is shown; on the reference or a
  // sample the last *Testar* is what there is (it runs once per change, on that image)
  const showsLive = !shownSample && !useReference
  const sessionFeeds = showsLive && live.status === 'live' && live.camera !== false
  const measurement = sessionFeeds ? live.last : null
  const test = useMemo<DraftTestOut | null>(
    () =>
      measurement
        ? {
            result: measurement.result,
            regions: measurement.regions,
            anchor: measurement.anchor,
            tools: measurement.tools,
            timings: measurement.timings,
            width: measurement.width,
            height: measurement.height,
            overlay: '',
          }
        : tested,
    [measurement, tested],
  )
  const problems = live.draftError ? { ...fields, ...live.draftError.fields } : fields
  useEffect(() => {
    let alive = true
    // a sample chosen on a gauge shows instead of the reference or the live image
    const path = shownSample ?? (useReference ? 'reference/reference.png' : null)
    const added = path ? draft.addFiles[path] : undefined
    const base = draft.base
    const fetchImage = async () => {
      await Promise.resolve() // state changes only after this tick, never during the effect
      if (sessionFeeds) return null // the session sends the pictures
      const blob = path
        ? added
          ? base64ToBlob(added)
          : await fetchBlob(`/api/jobs/${base!.id}/versions/${base!.version}/files/${path}`)
        : await fetchBlob('/api/snapshot.jpg')
      return imageFromBlob(blob, shownSample ? 'sample' : useReference ? 'reference' : 'live')
    }
    fetchImage().then(
      (next) => {
        if (!next) return
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
  }, [useReference, referenceKey, reload, shownSample, sessionFeeds]) // eslint-disable-line react-hooks/exhaustive-deps

  // the pictures of the live session, as they come
  const sessionFrame = sessionFeeds ? live.frame : null
  useEffect(() => {
    if (!sessionFrame) return
    let alive = true
    void imageFromBlob(sessionFrame, 'live').then((next) => {
      if (!alive) return URL.revokeObjectURL(next.url)
      setImageError('')
      setImage((old) => {
        if (old) URL.revokeObjectURL(old.url)
        return next
      })
    })
    return () => {
      alive = false
    }
  }, [sessionFrame])

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
    const editAnchor = step === 'anchor'
    const editRegions = step === 'tools'
    if (
      step === 'image' &&
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
    if (step === 'image' && draft.profile.exposure?.auto_once?.region)
      out.push({
        id: 'autoexp',
        label: t.autoRegionLabel,
        rect: draft.profile.exposure.auto_once.region,
        kind: 'presence',
        editable: true,
      })
    if (locator?.type === 'fixed' && locator.params?.rect)
      out.push({
        id: 'locator',
        label: t.anchorLabel,
        rect: locator.params.rect,
        kind: 'locator',
        editable: editAnchor,
      })
    else if (anchor) out.push({ id: 'anchor', label: t.anchorLabel, rect: anchor, kind: 'anchor' })
    if (step !== 'image')
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
    if (sampleRect)
      out.push({ id: 'sample', label: t.colour.sampleLabel, rect: sampleRect, kind: 'presence' })
    if (crop)
      out.push({ id: 'crop', label: t.cropLabel, rect: crop, kind: 'presence', editable: true })
    if (test && (step === 'tools' || step === 'validate' || step === 'save'))
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
  }, [draft, step, anchor, locator, geometry.rois, crop, test, sampleRect])
  const hiddenAnchored =
    Object.values((geometry.rois ?? {}) as Record<string, { relative_to: string }>).some(
      (r) => r.relative_to === 'anchor',
    ) && !anchor

  const onShapeChange = (shapeId: string, rect: Rect, first: boolean) => {
    if (shapeId === 'crop') {
      setCrop(rect)
      return
    }
    if (shapeId === 'sample') {
      latestSample.current = rect
      setSampleRect(rect)
      return
    }
    const edit = useDraft.getState().edit
    edit((d) => {
      if (shapeId === 'presence') d.job.trigger.presence_roi = rect
      else if (shapeId === 'autoexp') d.profile.exposure.auto_once.region = rect
      else if (shapeId === 'locator')
        d.job.geometry.locator.params = { ...d.job.geometry.locator.params, rect }
      else if (shapeId.startsWith('roi:')) {
        const roi = d.job.geometry.rois[shapeId.slice(4)]
        roi.rect = roi.relative_to === 'anchor' && anchor ? frameToAnchor(rect, anchor) : rect
      }
    }, first)
  }
  /** The end of a drag that sampled colours: the dragged part (at least a few pixels wide) as the PNG the picker asked for. */
  const onGestureEnd = (id: string) => {
    if (id !== 'sample') return
    const rect = latestSample.current
    if (!rect || !image) return finishSample(null)
    const [x0, y0, x1, y1] = rect
    const grow = (a: number, b: number, size: number) => {
      const need = 7 / size
      return b - a >= need
        ? [a, b]
        : [Math.max(0, (a + b) / 2 - need / 2), Math.min(1, (a + b) / 2 + need / 2)]
    }
    const [ax, bx] = grow(x0, x1, image.width)
    const [ay, by] = grow(y0, y1, image.height)
    cropPng(image, fromCorners(ax!, ay!, bx!, by!)).then(finishSample, () => finishSample(null))
  }
  const aids: ImageAids = useMemo(
    () => ({
      pixels,
      region: null,
      sampling: activeSampling,
      sample: startSample,
      cancelSample: () => finishSample(null),
      showMask: setMaskRange,
    }),
    [pixels, activeSampling, startSample, finishSample],
  )
  const onShapeDelete = (shapeId: string) => {
    if (shapeId.startsWith('roi:'))
      useDraft.getState().edit((d) => delete d.job.geometry.rois[shapeId.slice(4)])
    setSelected(null)
  }

  // --- test and save ------------------------------------------------------------------------------------
  const runTest = async () => {
    setTesting(true)
    try {
      setTested(await editorApi.test(toRequest(draft)))
      setFields({})
    } catch (e) {
      if (e instanceof ApiError && e.fields) setFields(e.fields)
      toast.error(describeError(e))
    } finally {
      setTesting(false)
    }
  }
  // Validar: the same run activation does, on every sample; what it says goes to the rail (design rule 4)
  const verify = async () => {
    setVerifying(true)
    try {
      const out = await editorApi.verify(toRequest(draft))
      setReport(out)
      setFields(out.fields)
      setValidation(
        out.cases.length === 0
          ? null
          : {
              ok: out.ok,
              failed: out.cases.filter((c) => !c.ok).length,
              total: out.cases.length,
              imageSig: imageSignature(draft),
              fullSig: fullSignature(draft),
            },
      )
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setVerifying(false)
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
    fields: problems,
    selected,
    setSelected,
    drawing,
    setDrawing: (d) => (setDrawing(d), d !== 'crop' && setCrop(null)),
    crop,
    setCrop,
    test,
    report,
    verifying,
    verify,
    openSave: () => setSaveOpen(true),
    batch,
    shownSample,
    showSample,
    metrics: live.metrics,
  }
  const info = stepStates(draft, problems, visited, validation)
  const steps = STEPS.map((s) => ({
    id: s,
    label: t.steps[s],
    status: info[s].state,
    current: s === step,
    reason: info[s].reason,
  }))
  const blocked = info[step].state === 'blocked'
  const next = STEPS[STEPS.indexOf(step) + 1]

  return (
    <ImageAidsProvider value={aids}>
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
            <div className="flex items-center gap-2">
              <span id="trigger-bar" className="text-sm text-fg-muted">
                {t.triggerBar}
              </span>
              <Select
                aria-labelledby="trigger-bar"
                value={draft.job.trigger?.mode ?? 'image_presence'}
                onValueChange={setTriggerMode}
                options={Object.entries(t.triggerModes).map(([value, [label]]) => ({
                  value,
                  label,
                }))}
              />
            </div>
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
            {live.pausedBySession ? t.stationPausedBySession : t.stationPaused}
            {live.pausedBySession ? null : (
              // a pause of the session ends with it; this one (Aplicar, Auto uma vez) is ended here
              <Button
                variant="ghost"
                onClick={() =>
                  void editorApi
                    .resumeStation()
                    .catch((e: unknown) => toast.error(describeError(e)))
                }
              >
                {t.resume}
              </Button>
            )}
          </div>
        ) : null}

        <div className="grid-editor grid gap-4">
          <nav aria-label={t.stepsLabel}>
            <Stepper
              steps={steps}
              onSelect={(s) => (setStep(s as StepId), setDrawing(null), setCrop(null))}
            />
          </nav>

          <section
            aria-label={t.imageLabel}
            // the image stays in view while the inspector scrolls: sampling a colour needs both at once
            className="sticky top-4 flex min-w-0 flex-col gap-3 self-start"
          >
            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl
                label={t.imageSource}
                value={useReference ? 'reference' : 'live'}
                onValueChange={(v) => {
                  setShownSample(null)
                  setSource(v as 'reference' | 'live')
                }}
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
              {shownSample ? (
                <div role="status" className="flex items-center gap-2">
                  <Badge tone="neutral">
                    {t.sampleShown(shownSample.replace('tests/images/', ''))}
                  </Badge>
                  <Button variant="ghost" onClick={() => setShownSample(null)}>
                    {t.sampleBack}
                  </Button>
                </div>
              ) : null}
            </div>
            <div role="status" className="flex flex-wrap items-center gap-2">
              {live.status === 'live' ? (
                <Badge tone={sessionFeeds ? 'ok' : 'neutral'}>
                  {t.liveOn(formatNumber(live.fps, 1))}
                </Badge>
              ) : (
                <Badge tone={live.status === 'connecting' ? 'busy' : 'warn'}>
                  {t.liveState[live.status]}
                </Badge>
              )}
              {live.camera === false ? (
                <span className="text-sm text-warn-text">{t.liveCameraLost}</span>
              ) : null}
            </div>
            {live.draftError ? (
              <p role="alert" className="text-sm text-fail-text">
                {t.liveDraftRefused(live.draftError.message)}
              </p>
            ) : null}
            {hiddenAnchored && step !== 'image' ? (
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
              pixels={pixels}
              mask={mask}
              readout={(x, y, rgb) =>
                `x ${x}, y ${y} · RGB ${rgb.join(', ')} · ${describeHsv(rgb, level >= 3)}`
              }
              onGestureEnd={onGestureEnd}
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
                  <p className="text-xs text-fg-muted">
                    {sessionFeeds && live.last ? t.liveNote : t.testNote}
                  </p>
                </CardContent>
              </Card>
            ) : null}
          </section>

          <section aria-labelledby="inspector-title" className="flex min-w-0 flex-col gap-4">
            <h2 id="inspector-title" className="text-base font-semibold">
              {t.steps[step]}
            </h2>
            {blocked ? (
              <p role="status" className="text-sm text-fg-muted">
                {t.sequence.blockedBanner} {info[step].reason}
              </p>
            ) : null}
            <fieldset disabled={blocked} className="flex min-w-0 flex-col gap-4 border-0 p-0">
              {step === 'image' ? (
                <>
                  <CameraStep {...props} />
                  <h3 className="text-sm font-semibold">{t.triggerTitle}</h3>
                  <TriggerStep {...props} />
                </>
              ) : null}
              {step === 'samples' ? <ReferenceStep {...props} /> : null}
              {step === 'anchor' ? <RegionsStep {...props} part="anchor" /> : null}
              {step === 'tools' ? (
                <>
                  <RegionsStep {...props} part="regions" />
                  <ToolsStep {...props} />
                  <PatternCrop {...props} />
                </>
              ) : null}
              {step === 'quality' ? <QualityStep {...props} /> : null}
              {step === 'outputs' ? <OutputsStep {...props} /> : null}
              {step === 'validate' ? <ValidateStep {...props} /> : null}
              {step === 'save' ? <SaveStep {...props} /> : null}
            </fieldset>
            {next ? (
              <Button
                variant="secondary"
                className="self-start"
                onClick={() => (setStep(next), setDrawing(null), setCrop(null))}
              >
                {t.sequence.next}: {t.steps[next]}
                <ArrowRight aria-hidden className="size-4" />
              </Button>
            ) : null}
          </section>
        </div>

        <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
          <DialogContent
            title={
              draft.base ? t.saveTitle((draft.latest ?? draft.base.version) + 1) : t.saveNewTitle
            }
            description={t.saveBody}
          >
            <ChangeList draft={draft} />
            <Field label={t.notes} hint={t.notesHint}>
              {(p) => (
                <Textarea
                  {...p}
                  rows={3}
                  value={draft.notes}
                  onChange={(e) =>
                    useDraft.getState().edit((d) => (d.notes = e.target.value), false)
                  }
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
    </ImageAidsProvider>
  )
}

/** What the draft changes against its version, in words, above the note that is written for the version. */
export function ChangeList({ draft }: { draft: Draft }) {
  const types = useTypes()
  const changes = summarizeChanges(draft, types.data)
  return (
    <section aria-label={t.changes} className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold">{t.changes}</h3>
      {changes.length === 0 ? (
        <p className="text-sm text-fg-muted">{t.noChanges}</p>
      ) : (
        <ul className="max-h-48 list-disc overflow-y-auto pl-5 text-sm">
          {changes.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
