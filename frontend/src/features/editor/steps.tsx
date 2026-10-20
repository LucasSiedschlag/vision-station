import { ArrowDown, ArrowUp, Camera, Crop, Plus, Sun, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import {
  editorApi,
  useTypes,
  type CameraState,
  type DraftTestOut,
  type VerifyOut,
} from '@/api/queries/editor'
import { Badge, StatusIndicator } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { FileDrop } from '@/components/ui/file-drop'
import { Input } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { BilingualField } from './BilingualField'
import {
  useDraft,
  toRequest,
  draftFiles,
  locatorOf,
  setLocator,
  withText,
  type Draft,
  type JobJson,
} from './draft'
import { type Rect } from './geometry'
import { blobToBase64, cropPng, type EditorImage } from './image'
import { useLevel } from '@/app/levels'
import { currentLocale } from '@/app/locale'
import { AidsRegion } from './image-aids'
import { SchemaForm } from './SchemaForm'
import { ToolGauges } from './gauges'
import type { Batch } from './batch'
import type { CameraMetrics } from './session'
import { FocusMeter } from '@/components/vision/FocusMeter'
import { Histogram } from '@/components/vision/Histogram'
import { Slider } from '@/components/ui/slider'

const t = text.editor

/** What every step gets from the editor page. */
export interface StepProps {
  draft: Draft
  image: EditorImage | null
  fields: Record<string, string>
  selected: string | null
  setSelected: (id: string | null) => void
  setDrawing: (id: string | null) => void
  drawing: string | null
  crop: Rect | null
  setCrop: (r: Rect | null) => void
  test: DraftTestOut | null
  /** Validar: the last run on the samples, and how to run it again (docs/frontend.md §4.3). */
  report: VerifyOut | null
  verifying: boolean
  verify: () => Promise<void>
  /** Opens the dialog that saves the draft as the next version. */
  openSave: () => void
  /** The draft on its reference and samples (the dots of the gauges), and whether it is being measured again. */
  batch: Batch
  /** The sample whose picture is on the image, by its path in the job; null: the reference or the live image. */
  shownSample: string | null
  showSample: (path: string | null) => void
  /** The sharpness, histogram and clipping of the newest live frame; null while the session has none. */
  metrics: CameraMetrics | null
}

/** The exposure slider is logarithmic: 100 µs to 1 s over 1000 positions, so each stop of light moves it the same way. */
const EXPOSURE_MIN_US = 100
const EXPOSURE_STEPS = 1000
const EXPOSURE_DECADES = 4
const positionToExposure = (position: number) =>
  Math.round(EXPOSURE_MIN_US * 10 ** ((position / EXPOSURE_STEPS) * EXPOSURE_DECADES))
const exposureToPosition = (us: number) =>
  Math.round(
    Math.min(
      EXPOSURE_STEPS,
      Math.max(0, (Math.log10(us / EXPOSURE_MIN_US) / EXPOSURE_DECADES) * EXPOSURE_STEPS),
    ),
  )

/** The region of a tool on the frame, when it is drawn on the frame (not on the anchor, whose place is only known once it is found). */
function frameRect(roi: string, draft: Draft): Rect | null {
  if (roi === 'frame') return [0, 0, 1, 1]
  const found = draft.job.geometry?.rois?.[roi]
  return found?.relative_to === 'frame' ? found.rect : null
}

const edit = (change: (d: Draft) => void, history = true) =>
  useDraft.getState().edit(change, history)
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null)

// --- 1. camera ---------------------------------------------------------------------------------------

function ModeValue({
  label,
  mode,
  value,
  unit,
  onMode,
  onValue,
  valueLabel,
}: {
  label: string
  mode: string
  value: number | null
  unit?: string
  onMode: (m: string) => void
  onValue: (v: number | null) => void
  valueLabel: string
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium">{label}</legend>
      <Switch
        checked={mode === 'manual'}
        onCheckedChange={(c) => onMode(c ? 'manual' : 'auto')}
        label={t.manual}
        hint={mode === 'manual' ? undefined : t.auto}
      />
      {mode === 'manual' ? (
        <Field label={valueLabel}>
          {(props) => (
            <NumberField
              {...props}
              value={value}
              onChange={onValue}
              unit={unit}
              min={0}
              decimals={0}
            />
          )}
        </Field>
      ) : null}
    </fieldset>
  )
}

export function CameraStep({ draft, drawing, setDrawing, metrics }: StepProps) {
  const p = draft.profile
  const [level] = useLevel('editor')
  const [measuring, setMeasuring] = useState(false)
  const autoOnce: JobJson = p.exposure?.auto_once ?? {}
  // the measuring parameters belong to the exposure and travel with it, whatever the mode or the value
  const exposureWith = (q: JobJson, exposure: JobJson) =>
    q.exposure?.auto_once ? { ...exposure, auto_once: q.exposure.auto_once } : exposure
  const setAutoOnce = (change: (a: JobJson) => void) =>
    set((q) => {
      q.exposure ??= { mode: 'auto' }
      q.exposure.auto_once ??= {}
      change(q.exposure.auto_once)
      if (Object.keys(q.exposure.auto_once).length === 0) delete q.exposure.auto_once
    })
  const measure = async () => {
    setMeasuring(true)
    try {
      const found = await editorApi.autoExposure(p)
      const value = Math.round(found.value_us)
      set((q) => (q.exposure = exposureWith(q, { mode: 'manual', value_us: value })))
      toast.success(
        found.reached
          ? t.autoOnceDone(value, found.saturated_percent)
          : t.autoOnceLimit(found.limit, value, found.saturated_percent, found.target_percent),
      )
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setMeasuring(false)
    }
  }
  const [state, setState] = useState<CameraState | null>(null)
  const [busy, setBusy] = useState(false)
  const set = (change: (profile: JobJson) => void) => edit((d) => change(d.profile))
  const manualPair = (key: 'gain' | 'focus', field = 'value') => ({
    mode: p[key]?.mode ?? 'auto',
    value: num(p[key]?.[field]),
    onMode: (m: string) =>
      set(
        (q) =>
          (q[key] =
            m === 'manual' ? { mode: 'manual', [field]: q[key]?.[field] ?? 0 } : { mode: 'auto' }),
      ),
    onValue: (v: number | null) => set((q) => (q[key] = { mode: 'manual', [field]: v })),
  })
  const apply = async () => {
    setBusy(true)
    try {
      setState(await editorApi.applyCamera(p))
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.cameraIntro}</p>
      {metrics ? (
        <div className="flex flex-col gap-3 rounded-control border border-line p-3">
          <Histogram
            counts={metrics.histogram}
            clippedLow={metrics.clipped_low}
            clippedHigh={metrics.clipped_high}
          />
          <FocusMeter value={metrics.sharpness} />
        </div>
      ) : (
        <p className="text-sm text-fg-muted">{t.camera.noLive}</p>
      )}
      <div className="flex gap-2">
        <Field label={t.width}>
          {(props) => (
            <NumberField
              {...props}
              value={num(p.resolution?.[0])}
              onChange={(v) => set((q) => (q.resolution = [v ?? 1920, q.resolution?.[1] ?? 1080]))}
              unit="px"
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.height}>
          {(props) => (
            <NumberField
              {...props}
              value={num(p.resolution?.[1])}
              onChange={(v) => set((q) => (q.resolution = [q.resolution?.[0] ?? 1920, v ?? 1080]))}
              unit="px"
              decimals={0}
            />
          )}
        </Field>
      </div>
      <ModeValue
        label={t.exposure}
        valueLabel={t.exposureValue}
        unit="µs"
        mode={p.exposure?.mode ?? 'auto'}
        value={num(p.exposure?.value_us)}
        onMode={(m) =>
          set(
            (q) =>
              (q.exposure = exposureWith(
                q,
                m === 'manual'
                  ? { mode: 'manual', value_us: q.exposure?.value_us ?? 33000 }
                  : { mode: 'auto' },
              )),
          )
        }
        onValue={(v) => set((q) => (q.exposure = exposureWith(q, { mode: 'manual', value_us: v })))}
      />
      {p.exposure?.mode === 'manual' ? (
        <Slider
          label={t.camera.exposureSlider}
          value={[exposureToPosition(num(p.exposure?.value_us) ?? EXPOSURE_MIN_US)]}
          min={0}
          max={EXPOSURE_STEPS}
          format={(position) => `${formatNumber(positionToExposure(position), 0)} µs`}
          onChange={([position]) =>
            set(
              (q) =>
                (q.exposure = exposureWith(q, {
                  mode: 'manual',
                  value_us: positionToExposure(position!),
                })),
            )
          }
        />
      ) : null}
      <div className="flex flex-col gap-2 rounded-control border border-line p-3">
        <Button variant="secondary" loading={measuring} onClick={() => void measure()}>
          <Sun aria-hidden className="size-4" />
          {t.autoOnce}
        </Button>
        <p className="text-sm text-fg-muted">{t.autoOnceHint}</p>
        {level >= 2 ? (
          <>
            <Field label={t.autoTarget} hint={t.autoTargetHint}>
              {(props) => (
                <NumberField
                  {...props}
                  value={num(autoOnce.target_brightness)}
                  placeholder={text.ui.defaultValue(formatNumber(10))}
                  onChange={(v) =>
                    setAutoOnce((a) =>
                      v === null ? delete a.target_brightness : (a.target_brightness = v),
                    )
                  }
                  min={0}
                  max={100}
                  decimals={1}
                  unit="%"
                />
              )}
            </Field>
            <Field label={t.autoMax}>
              {(props) => (
                <NumberField
                  {...props}
                  value={num(autoOnce.max_exposure_us)}
                  placeholder={text.ui.defaultValue(formatNumber(100000))}
                  onChange={(v) =>
                    setAutoOnce((a) =>
                      v === null ? delete a.max_exposure_us : (a.max_exposure_us = v),
                    )
                  }
                  min={100}
                  decimals={0}
                  unit="µs"
                />
              )}
            </Field>
            <Switch
              checked={!!autoOnce.region}
              onCheckedChange={(on) => {
                setAutoOnce((a) => (on ? (a.region = [0.25, 0.25, 0.75, 0.75]) : delete a.region))
                if (!on && drawing === 'autoexp') setDrawing(null)
              }}
              label={t.autoRegion}
              hint={autoOnce.region ? undefined : t.autoRegionAll}
            />
            {autoOnce.region ? (
              <Button
                variant={drawing === 'autoexp' ? 'primary' : 'ghost'}
                onClick={() => setDrawing(drawing === 'autoexp' ? null : 'autoexp')}
              >
                {drawing === 'autoexp' ? t.drawingNow : t.drawAutoRegion}
              </Button>
            ) : null}
          </>
        ) : null}
      </div>
      <ModeValue label={t.gain} valueLabel={t.value} {...manualPair('gain')} />
      <ModeValue
        label={t.whiteBalance}
        valueLabel={t.kelvin}
        unit="K"
        mode={p.white_balance?.mode ?? 'auto'}
        value={num(p.white_balance?.kelvin)}
        onMode={(m) =>
          set(
            (q) =>
              (q.white_balance =
                m === 'manual'
                  ? { mode: 'manual', kelvin: q.white_balance?.kelvin ?? 4500 }
                  : { mode: 'auto' }),
          )
        }
        onValue={(v) => set((q) => (q.white_balance = { mode: 'manual', kelvin: v }))}
      />
      <ModeValue label={t.focus} valueLabel={t.value} {...manualPair('focus')} />
      <Field label={t.powerLine}>
        {(props) => (
          <Select
            {...props}
            value={String(p.power_line_hz ?? 60)}
            onValueChange={(v) => set((q) => (q.power_line_hz = Number(v)))}
            options={[
              { value: '60', label: '60 Hz' },
              { value: '50', label: '50 Hz' },
            ]}
          />
        )}
      </Field>
      <Field label={t.orientation} hint={t.orientationHint}>
        {(props) => (
          <Select
            {...props}
            value={p.orientation ?? 'normal'}
            onValueChange={(v) =>
              set((q) => (v === 'normal' ? delete q.orientation : (q.orientation = v)))
            }
            options={(['normal', 'mirror', 'flip', 'rotate180'] as const).map((value) => ({
              value,
              label: t.orientations[value],
            }))}
          />
        )}
      </Field>
      <Button variant="primary" loading={busy} onClick={() => void apply()}>
        <Camera aria-hidden className="size-4" />
        {t.applyCamera}
      </Button>
      {state ? (
        <div role="status" className="flex flex-col gap-2">
          <p className="text-sm">{state.applied ? t.applied : t.notApplied}</p>
          <ul className="flex flex-col gap-1 text-sm">
            {Object.entries(state.settings).map(([name, r]) => (
              <li key={name}>
                <StatusIndicator
                  tone={r.status === 'applied' ? 'ok' : 'warn'}
                  label={`${name}: ${t.setting[r.status as keyof typeof t.setting] ?? r.status}`}
                  detail={r.detail || undefined}
                />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

// --- 2. trigger --------------------------------------------------------------------------------------

/** The trigger mode, from the step or from the top bar: one place, so both always agree (docs/frontend.md §7.3). */
export function setTriggerMode(mode: string) {
  edit((d) => {
    const tr = (d.job.trigger ??= {})
    tr.mode = mode
    if (mode === 'image_presence') {
      tr.presence_roi ??= [0.1, 0.1, 0.9, 0.9]
      tr.still_ms ??= 500
    }
  })
}

export function TriggerStep({ draft, fields, setDrawing, drawing }: StepProps) {
  const trigger = draft.job.trigger ?? {}
  const set = (change: (tr: JobJson) => void) => edit((d) => change((d.job.trigger ??= {})))
  return (
    <div className="flex flex-col gap-4">
      <Field
        label={t.triggerMode}
        hint={t.triggerModes[trigger.mode as keyof typeof t.triggerModes]?.[1]}
      >
        {(props) => (
          <Select
            {...props}
            value={trigger.mode ?? 'image_presence'}
            onValueChange={setTriggerMode}
            options={Object.entries(t.triggerModes).map(([value, [label]]) => ({ value, label }))}
          />
        )}
      </Field>
      {trigger.mode === 'image_presence' ? (
        <>
          <Button
            variant={drawing === 'presence' ? 'primary' : 'secondary'}
            onClick={() => setDrawing(drawing === 'presence' ? null : 'presence')}
          >
            {drawing === 'presence' ? t.drawingNow : t.drawPresence}
          </Button>
          <Field label={t.stillMs} hint={t.stillHint}>
            {(props) => (
              <NumberField
                {...props}
                value={num(trigger.still_ms)}
                onChange={(v) => set((tr) => (tr.still_ms = v))}
                unit="ms"
                min={1}
                decimals={0}
              />
            )}
          </Field>
          <Field label={t.diffThreshold} hint={t.diffHint}>
            {(props) => (
              <NumberField
                {...props}
                value={num(trigger.diff_threshold)}
                placeholder={text.ui.defaultValue(formatNumber(25))}
                onChange={(v) =>
                  set((tr) => (v === null ? delete tr.diff_threshold : (tr.diff_threshold = v)))
                }
                min={1}
                max={255}
                decimals={0}
              />
            )}
          </Field>
          <Field label={t.minArea} hint={t.minAreaHint}>
            {(props) => (
              <NumberField
                {...props}
                value={num(trigger.min_area)}
                placeholder={text.ui.defaultValue(formatNumber(0.05))}
                onChange={(v) => set((tr) => (v === null ? delete tr.min_area : (tr.min_area = v)))}
                min={0}
                max={1}
                step={0.01}
              />
            )}
          </Field>
        </>
      ) : null}
      {trigger.mode === 'continuous' ? (
        <Field label={t.interval} hint={t.intervalHint} error={fields['job.trigger.interval_ms']}>
          {(props) => (
            <NumberField
              {...props}
              value={num(trigger.interval_ms)}
              placeholder={text.ui.defaultValue(formatNumber(500))}
              onChange={(v) =>
                set((tr) => (v === null ? delete tr.interval_ms : (tr.interval_ms = v)))
              }
              unit="ms"
              min={0}
              max={10000}
              decimals={0}
            />
          )}
        </Field>
      ) : null}
    </div>
  )
}

// --- 3. quality --------------------------------------------------------------------------------------

export function QualityStep({ draft }: StepProps) {
  const q = draft.job.quality ?? {}
  const [measure, setMeasure] = useState<{ brightness: number; sharpness: number } | null>(null)
  const set = (change: (qq: JobJson) => void) => edit((d) => change((d.job.quality ??= {})))
  const measureNow = async () => {
    try {
      const r = await editorApi.captureReference()
      setMeasure({ brightness: r.brightness, sharpness: r.sharpness })
    } catch (e) {
      toast.error(describeError(e))
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.qualityIntro}</p>
      <div className="flex gap-2">
        <Field label={t.brightnessMin}>
          {(props) => (
            <NumberField
              {...props}
              value={num(q.brightness?.min)}
              onChange={(v) => set((qq) => ((qq.brightness ??= {}).min = v))}
              min={0}
              max={255}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.brightnessMax}>
          {(props) => (
            <NumberField
              {...props}
              value={num(q.brightness?.max)}
              onChange={(v) => set((qq) => ((qq.brightness ??= {}).max = v))}
              min={0}
              max={255}
              decimals={0}
            />
          )}
        </Field>
      </div>
      <Field label={t.sharpness} hint={t.sharpnessHint}>
        {(props) => (
          <NumberField
            {...props}
            value={num(q.sharpness_min_ratio)}
            onChange={(v) => set((qq) => (qq.sharpness_min_ratio = v))}
            min={0}
            step={0.05}
          />
        )}
      </Field>
      <Field label={t.similarity} hint={t.similarityHint}>
        {(props) => (
          <NumberField
            {...props}
            value={num(q.similarity_min)}
            placeholder={text.ui.defaultValue(formatNumber(0.6))}
            onChange={(v) =>
              set((qq) => (v === null ? delete qq.similarity_min : (qq.similarity_min = v)))
            }
            min={0}
            max={1}
            step={0.05}
          />
        )}
      </Field>
      <Button onClick={() => void measureNow()}>{t.measure}</Button>
      {measure ? (
        <div role="status" className="flex flex-col gap-2 text-sm">
          <p>
            {t.measured(formatNumber(measure.brightness, 1), formatNumber(measure.sharpness, 1))}
          </p>
          <Button
            variant="ghost"
            onClick={() =>
              set((qq) => {
                qq.brightness = {
                  min: Math.max(0, Math.round(measure.brightness * 0.8)),
                  max: Math.min(255, Math.round(measure.brightness * 1.2)),
                }
              })
            }
          >
            {t.useMeasured}
          </Button>
        </div>
      ) : null}
    </div>
  )
}

// --- 4. anchor and regions ----------------------------------------------------------------------------

export function RegionsStep({
  draft,
  image,
  fields,
  selected,
  setSelected,
  setDrawing,
  drawing,
  crop,
  setCrop,
  part,
}: StepProps & { part: 'anchor' | 'regions' }) {
  const types = useTypes()
  const [level] = useLevel('editor')
  const geometry = draft.job.geometry ?? { rois: {} }
  const locator = locatorOf(draft.job)
  const rois: Record<string, { relative_to: string; rect: Rect }> = geometry.rois ?? {}
  const [newName, setNewName] = useState('')
  const schema = types.data?.locators.find((l) => l.name === locator?.type)?.params_schema
  const setGeometry = (change: (g: JobJson) => void, history = true) =>
    edit((d) => change((d.job.geometry ??= { rois: {} })), history)
  const names = Object.keys(rois)
  const nameError =
    newName &&
    (names.includes(newName) ||
      ['frame', 'anchor'].includes(newName) ||
      !/^[a-z0-9_-]+$/i.test(newName))
      ? t.badName
      : undefined

  const applyCropAsTemplate = async () => {
    if (!image || image.source !== 'reference' || !crop) return
    const path = 'locator/template.png'
    const png = await cropPng(image, crop)
    edit((d) => {
      d.addFiles[path] = png
      d.removeFiles = d.removeFiles.filter((p) => p !== path)
      setLocator(d.job.geometry, {
        type: 'template',
        version: 1,
        params: { ...(locatorOf(d.job)?.params ?? {}), template: path },
      })
    })
    setCrop(null)
    setDrawing(null)
    toast.success(t.templateSaved)
  }

  return (
    <div className="flex flex-col gap-4">
      {part === 'anchor' ? (
        <>
          <Field label={t.locator} hint={t.locatorHint}>
            {(props) => (
              <Select
                {...props}
                value={locator ? `${locator.type}@${locator.version}` : 'none'}
                onValueChange={(v) =>
                  setGeometry((g) => {
                    if (v === 'none') {
                      setLocator(g, null)
                      for (const r of Object.values(g.rois ?? {}) as JobJson[])
                        r.relative_to = 'frame'
                      return
                    }
                    const [type, version] = v.split('@')
                    setLocator(g, {
                      type,
                      version: Number(version),
                      params:
                        type === 'fixed'
                          ? { rect: [0.25, 0.25, 0.75, 0.75] }
                          : type === 'blob'
                            ? { mode: 'dark' }
                            : {},
                    })
                  })
                }
                options={[
                  { value: 'none', label: t.noLocator },
                  ...(types.data?.locators ?? [])
                    .filter(
                      (l) =>
                        // the newest version of each type is offered; an older one only while the job uses it
                        l.version ===
                          Math.max(
                            ...(types.data?.locators ?? [])
                              .filter((x) => x.name === l.name)
                              .map((x) => x.version),
                          ) ||
                        (locator?.type === l.name && locator?.version === l.version),
                    )
                    .map((l) => ({
                      value: `${l.name}@${l.version}`,
                      label: t.locatorNames[l.name as keyof typeof t.locatorNames] ?? l.name,
                    })),
                ]}
              />
            )}
          </Field>
          {locator?.type === 'fixed' ? (
            <Button
              variant={drawing === 'locator' ? 'primary' : 'secondary'}
              onClick={() => setDrawing(drawing === 'locator' ? null : 'locator')}
            >
              {drawing === 'locator' ? t.drawingNow : t.drawLocator}
            </Button>
          ) : null}
          {locator?.type === 'template' ? (
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
                  onClick={() => void applyCropAsTemplate()}
                >
                  {t.useCrop}
                </Button>
              </div>
            </div>
          ) : null}
          {locator && schema && locator.type !== 'fixed' ? (
            <SchemaForm
              schema={schema}
              level={level}
              value={locator.params ?? {}}
              errors={prefixed(fields, 'job.geometry.fixtures.0.locator.params')}
              onChange={(params) =>
                setGeometry((g) => (g.fixtures[0].locator.params = params), false)
              }
            />
          ) : null}
        </>
      ) : (
        <>
          <h3 className="text-sm font-semibold">{t.regions}</h3>
          {names.length === 0 ? <p className="text-sm text-fg-muted">{t.noRegions}</p> : null}
          <ul className="flex flex-col gap-2">
            {names.map((name) => {
              const id = `roi:${name}`
              return (
                <li
                  key={name}
                  className={`flex flex-wrap items-center gap-2 rounded-control border p-2 ${selected === id ? 'border-accent' : 'border-line'}`}
                >
                  <button
                    type="button"
                    className="font-mono text-sm"
                    onClick={() => setSelected(id)}
                  >
                    {name}
                  </button>
                  <Select
                    aria-label={t.relativeTo(name)}
                    value={rois[name]!.relative_to}
                    onValueChange={(v) => setGeometry((g) => (g.rois[name].relative_to = v))}
                    options={[
                      { value: 'frame', label: t.relFrame },
                      { value: 'anchor', label: t.relAnchor, disabled: !locator },
                    ]}
                  />
                  <Button
                    variant={drawing === id ? 'primary' : 'ghost'}
                    onClick={() => setDrawing(drawing === id ? null : id)}
                  >
                    {drawing === id ? t.drawingNow : t.redraw}
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={t.removeRegion(name)}
                    onClick={() => setGeometry((g) => delete g.rois[name])}
                  >
                    <Trash2 aria-hidden className="size-4" />
                  </Button>
                </li>
              )
            })}
          </ul>
          <div className="flex items-end gap-2">
            <Field label={t.newRegion} error={nameError || undefined} hint={t.newRegionHint}>
              {(props) => (
                <Input
                  {...props}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value.trim())}
                />
              )}
            </Field>
            <Button
              disabled={!newName || !!nameError}
              onClick={() => {
                setGeometry(
                  (g) =>
                    ((g.rois ??= {})[newName] = {
                      relative_to: locator ? 'anchor' : 'frame',
                      rect: [0.3, 0.3, 0.7, 0.7],
                    }),
                )
                setSelected(`roi:${newName}`)
                setDrawing(`roi:${newName}`)
                setNewName('')
              }}
            >
              <Plus aria-hidden className="size-4" />
              {t.addRegion}
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function prefixed(fields: Record<string, string>, prefix: string): Record<string, string> {
  return Object.fromEntries(
    Object.entries(fields)
      .filter(([k]) => k.startsWith(`${prefix}.`))
      .map(([k, v]) => [k.slice(prefix.length + 1), v]),
  )
}

// --- 5. tools ----------------------------------------------------------------------------------------

export function ToolsStep({
  draft,
  fields,
  test,
  setSelected,
  batch,
  shownSample,
  showSample,
}: StepProps) {
  const types = useTypes()
  const [level] = useLevel('editor')
  const tools: JobJson[] = draft.job.tools ?? []
  const [open, setOpen] = useState<number | null>(tools.length ? 0 : null)
  const [adding, setAdding] = useState('')
  const roiNames = [
    'frame',
    ...((draft.job.geometry?.fixtures ?? []) as JobJson[]).map((f) => f.name as string),
    ...Object.keys(draft.job.geometry?.rois ?? {}),
  ]
  const setTools = (change: (list: JobJson[]) => void, history = true) =>
    edit((d) => change((d.job.tools ??= [])), history)
  const swap = (i: number, j: number) => setTools((list) => list.splice(j, 0, ...list.splice(i, 1)))

  const addModelFiles = async (i: number, files: File[]) => {
    const read = await Promise.all(
      files.map(async (f) => [`models/${f.name}`, await blobToBase64(f)] as const),
    )
    edit((d) => {
      for (const [path, b64] of read) {
        d.addFiles[path] = b64
        d.removeFiles = d.removeFiles.filter((p) => p !== path)
      }
      const onnx = read.find(([p]) => p.endsWith('.onnx'))
      if (onnx) d.job.tools[i].params = { ...d.job.tools[i].params, model: onnx[0] }
    })
    toast.success(t.modelAdded(read.map(([p]) => p).join(', ')))
  }

  return (
    <div className="flex flex-col gap-4">
      {tools.length === 0 ? <p className="text-sm text-fg-muted">{t.noTools}</p> : null}
      <ol className="flex flex-col gap-2">
        {tools.map((tool, i) => {
          const type = types.data?.tools.find(
            (x) => x.name === tool.type && x.version === tool.version,
          )
          const result = test?.regions.find((r) => r.tool === tool.id)
          const score = test?.result.scores[tool.id]
          const isOpen = open === i
          return (
            <li
              key={`${tool.id}-${i}`}
              className="flex flex-col gap-3 rounded-control border border-line p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="flex-1 text-left font-medium"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : i)}
                >
                  {i + 1}. {tool.id}{' '}
                  <span className="font-mono text-xs text-fg-muted">
                    ({tool.type} v{tool.version})
                  </span>
                </button>
                {result ? (
                  <Badge tone={result.passed ? 'ok' : 'fail'}>
                    {result.passed ? t.passed : t.failed}
                    {score !== undefined ? ` · ${formatNumber(score, 2)}` : ''}
                  </Badge>
                ) : null}
                <Button
                  variant="ghost"
                  aria-label={t.moveUp(tool.id)}
                  disabled={i === 0}
                  onClick={() => swap(i, i - 1)}
                >
                  <ArrowUp aria-hidden className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  aria-label={t.moveDown(tool.id)}
                  disabled={i === tools.length - 1}
                  onClick={() => swap(i, i + 1)}
                >
                  <ArrowDown aria-hidden className="size-4" />
                </Button>
                <Button
                  variant="ghost"
                  aria-label={t.removeTool(tool.id)}
                  onClick={() => setTools((list) => list.splice(i, 1))}
                >
                  <Trash2 aria-hidden className="size-4" />
                </Button>
              </div>
              {isOpen ? (
                <div className="flex flex-col gap-3">
                  {type ? <p className="text-xs text-fg-muted">{type.description}</p> : null}
                  <Field label={t.toolId} hint={t.toolIdHint} error={fields[`job.tools.${i}.id`]}>
                    {(props) => (
                      <Input
                        {...props}
                        value={tool.id}
                        onChange={(e) => setTools((list) => (list[i]!.id = e.target.value), false)}
                      />
                    )}
                  </Field>
                  <Field label={t.toolRoi}>
                    {(props) => (
                      <Select
                        {...props}
                        value={tool.roi}
                        onValueChange={(v) => {
                          setTools((list) => (list[i]!.roi = v))
                          setSelected(v === 'frame' || v === 'anchor' ? null : `roi:${v}`)
                        }}
                        options={roiNames.map((n) => ({
                          value: n,
                          label: n === 'frame' ? t.wholeFrame : n === 'anchor' ? t.wholeAnchor : n,
                        }))}
                      />
                    )}
                  </Field>
                  {tool.type === 'detect' ? (
                    <FileDrop
                      accept=".onnx,.yaml,.yml"
                      multiple
                      label={t.modelDrop}
                      hint={t.modelHint}
                      onFiles={(files) => void addModelFiles(i, files)}
                    />
                  ) : null}
                  {type ? (
                    <AidsRegion rect={frameRect(tool.roi, draft)}>
                      <SchemaForm
                        schema={type.params_schema}
                        level={level}
                        hide={type.criteria
                          .filter((c) => c.level <= level)
                          .flatMap((c) => Object.values(c.limits))}
                        criteriaExtra={
                          <ToolGauges
                            draft={draft}
                            index={i}
                            type={type}
                            batch={batch.out}
                            stale={batch.stale || batch.loading}
                            measured={test?.result.tools?.find((x) => x.id === tool.id) ?? null}
                            selectedSample={shownSample}
                            onShowSample={showSample}
                            level={level}
                          />
                        }
                        value={tool.params ?? {}}
                        errors={prefixed(fields, `job.tools.${i}.params`)}
                        onChange={(params) => setTools((list) => (list[i]!.params = params), false)}
                      />
                    </AidsRegion>
                  ) : (
                    <p className="text-sm text-warn-text">{t.unknownType}</p>
                  )}
                  <BilingualField
                    label={t.reasonFail}
                    hint={t.reasonHint}
                    error={fields[`job.tools.${i}.reason_fail`]}
                    value={tool.reason_fail}
                    onChange={(next) => setTools((list) => (list[i]!.reason_fail = next), false)}
                  />
                </div>
              ) : null}
            </li>
          )
        })}
      </ol>
      <div className="flex items-end gap-2">
        <Field label={t.addTool}>
          {(props) => (
            <Select
              {...props}
              value={adding || undefined}
              placeholder={t.chooseType}
              onValueChange={setAdding}
              options={(types.data?.tools ?? []).map((x) => ({
                value: `${x.name}@${x.version}`,
                label: `${t.toolNames[x.name as keyof typeof t.toolNames] ?? x.name} (${x.name})`,
              }))}
            />
          )}
        </Field>
        <Button
          disabled={!adding}
          onClick={() => {
            const [type, version] = adding.split('@')
            const used = new Set(tools.map((x) => x.id))
            let n = 1
            while (used.has(`${type}${n}`)) n++
            setTools((list) =>
              list.push({
                id: `${type}${n}`,
                type,
                version: Number(version),
                roi: roiNames.at(-1) ?? 'frame',
                params:
                  type === 'color'
                    ? { min_fraction: 0.5 }
                    : type === 'pattern'
                      ? { template: '' }
                      : type === 'detect'
                        ? { model: '' }
                        : {},
                reason_fail: withText(null, currentLocale(), t.defaultReason),
              }),
            )
            setOpen(tools.length)
            setAdding('')
          }}
        >
          <Plus aria-hidden className="size-4" />
          {t.add}
        </Button>
      </div>
    </div>
  )
}

/** For the pattern tool: draw a crop on the reference image and keep it as the tool's template. */
export function PatternCrop({ draft, image, crop, drawing, setDrawing, setCrop }: StepProps) {
  const tools: JobJson[] = draft.job.tools ?? []
  const patterns = tools.map((x, i) => [x, i] as const).filter(([x]) => x.type === 'pattern')
  if (patterns.length === 0) return null
  const save = async (i: number) => {
    if (!image || image.source !== 'reference' || !crop) return
    const path = `patterns/${tools[i]!.id}.png`
    const png = await cropPng(image, crop)
    edit((d) => {
      d.addFiles[path] = png
      d.job.tools[i].params = { ...d.job.tools[i].params, template: path }
    })
    setCrop(null)
    setDrawing(null)
    toast.success(t.templateSaved)
  }
  return (
    <div className="flex flex-col gap-2 rounded-control border border-line p-3">
      <p className="text-sm">
        {image?.source === 'reference' ? t.patternCropHint : t.cropNeedsReference}
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
        {patterns.map(([x, i]) => (
          <Button key={x.id} disabled={!crop} onClick={() => void save(i)}>
            {t.usePatternFor(x.id)}
          </Button>
        ))}
      </div>
    </div>
  )
}

// --- 6. reference --------------------------------------------------------------------------------------

export function ReferenceStep({ draft }: StepProps) {
  const [busy, setBusy] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [outcome, setOutcome] = useState<'PASS' | 'FAIL' | 'ERROR'>('PASS')
  const hasReference = draftFiles(draft).includes('reference/reference.png')
  const cases = draft.expected?.cases ?? []
  const nameError =
    name &&
    (!/^[A-Za-z0-9_-]+$/.test(name) || cases.some((c) => c.image === `tests/images/${name}.png`))
      ? t.badCaseName
      : undefined

  const capture = async () => {
    setBusy('reference')
    try {
      const r = await editorApi.captureReference()
      edit((d) => {
        Object.assign(d.addFiles, r.files)
        d.removeFiles = d.removeFiles.filter((p) => !(p in r.files))
      })
      toast.success(t.referenceSaved(r.width, r.height))
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setBusy(null)
    }
  }
  const addCase = async () => {
    setBusy('case')
    try {
      const r = await editorApi.captureCase(toRequest(draft), name)
      edit((d) => {
        d.addFiles[r.path] = r.image
        d.expected ??= { tolerance: 0.05, cases: [] }
        d.expected.cases.push({ image: r.path, outcome })
      })
      toast.message(t.caseAdded(name, t.outcome[r.result.outcome], t.outcome[outcome]))
      setName('')
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setBusy(null)
    }
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.referenceIntro}</p>
      <Button variant="primary" loading={busy === 'reference'} onClick={() => void capture()}>
        <Camera aria-hidden className="size-4" />
        {hasReference ? t.recaptureReference : t.captureReference}
      </Button>
      <h3 className="text-sm font-semibold">{t.referenceSet}</h3>
      <p className="text-sm text-fg-muted">{t.referenceSetIntro}</p>
      {cases.length === 0 ? (
        <p className="text-sm text-fg-muted">{t.noCases}</p>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>{t.caseImage}</TH>
              <TH>{t.caseExpected}</TH>
              <TH>
                <span className="sr-only">{t.remove}</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {cases.map((c, i) => (
              <TR key={c.image}>
                <TD className="font-mono text-xs">{c.image.replace('tests/images/', '')}</TD>
                <TD>
                  <Select
                    aria-label={t.expectedFor(c.image)}
                    value={c.outcome}
                    onValueChange={(v) =>
                      edit((d) => (d.expected!.cases[i]!.outcome = v as 'PASS'))
                    }
                    options={(['PASS', 'FAIL', 'ERROR'] as const).map((o) => ({
                      value: o,
                      label: t.sampleKind[o],
                    }))}
                  />
                </TD>
                <TD className="text-right">
                  <Button
                    variant="ghost"
                    aria-label={t.removeCase(c.image)}
                    onClick={() =>
                      edit((d) => {
                        d.expected!.cases.splice(i, 1)
                        delete d.addFiles[c.image]
                        if (d.baseFiles.some((f) => f.path === c.image)) d.removeFiles.push(c.image)
                        if (d.expected!.cases.length === 0) d.expected = null
                      })
                    }
                  >
                    <Trash2 aria-hidden className="size-4" />
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}
      <div className="flex flex-wrap items-end gap-2">
        <Field label={t.caseName} error={nameError || undefined}>
          {(props) => (
            <Input {...props} value={name} onChange={(e) => setName(e.target.value.trim())} />
          )}
        </Field>
        <Field label={t.caseExpected}>
          {(props) => (
            <Select
              {...props}
              value={outcome}
              onValueChange={(v) => setOutcome(v as 'PASS')}
              options={(['PASS', 'FAIL', 'ERROR'] as const).map((o) => ({
                value: o,
                label: t.sampleKind[o],
              }))}
            />
          )}
        </Field>
        <Button
          disabled={!name || !!nameError}
          loading={busy === 'case'}
          onClick={() => void addCase()}
        >
          <Plus aria-hidden className="size-4" />
          {t.addCase}
        </Button>
      </div>
    </div>
  )
}
