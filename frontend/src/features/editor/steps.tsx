import { ArrowDown, ArrowUp, Camera, Crop, Pipette, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { editorApi, useTypes, type CameraState, type DraftTestOut } from '@/api/queries/editor'
import { Badge, StatusIndicator } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { FileDrop } from '@/components/ui/file-drop'
import { Input, Textarea } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { useDraft, toRequest, draftFiles, type Draft, type JobJson } from './draft'
import { suggestHue, type Rect } from './geometry'
import { blobToBase64, cropPng, pixelsOf, sample, type EditorImage } from './image'
import { SchemaForm } from './SchemaForm'

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

export function CameraStep({ draft }: StepProps) {
  const p = draft.profile
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
              (q.exposure =
                m === 'manual'
                  ? { mode: 'manual', value_us: q.exposure?.value_us ?? 33000 }
                  : { mode: 'auto' }),
          )
        }
        onValue={(v) => set((q) => (q.exposure = { mode: 'manual', value_us: v }))}
      />
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

export function TriggerStep({ draft, setDrawing, drawing }: StepProps) {
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
            onValueChange={(mode) =>
              set((tr) => {
                tr.mode = mode
                if (mode === 'image_presence') {
                  tr.presence_roi ??= [0.1, 0.1, 0.9, 0.9]
                  tr.still_ms ??= 500
                }
              })
            }
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
                placeholder="padrão: 25"
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
                placeholder="padrão: 0,05"
                onChange={(v) => set((tr) => (v === null ? delete tr.min_area : (tr.min_area = v)))}
                min={0}
                max={1}
                step={0.01}
              />
            )}
          </Field>
        </>
      ) : null}
      <Field label={t.waiting} hint={t.waitingHint}>
        {(props) => (
          <Input
            {...props}
            value={draft.job.ui?.waiting ?? ''}
            onChange={(e) =>
              edit((d) => ((d.job.ui ??= {}).waiting = e.target.value || null), false)
            }
          />
        )}
      </Field>
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
            placeholder="padrão: 0,6"
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
}: StepProps) {
  const types = useTypes()
  const geometry = draft.job.geometry ?? { rois: {} }
  const locator = geometry.locator ?? null
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
      d.job.geometry.locator = {
        type: 'template',
        version: 1,
        params: { ...(d.job.geometry.locator?.params ?? {}), template: path },
      }
    })
    setCrop(null)
    setDrawing(null)
    toast.success(t.templateSaved)
  }

  return (
    <div className="flex flex-col gap-4">
      <Field label={t.locator} hint={t.locatorHint}>
        {(props) => (
          <Select
            {...props}
            value={locator ? `${locator.type}@${locator.version}` : 'none'}
            onValueChange={(v) =>
              setGeometry((g) => {
                if (v === 'none') {
                  delete g.locator
                  for (const r of Object.values(g.rois ?? {}) as JobJson[]) r.relative_to = 'frame'
                  return
                }
                const [type, version] = v.split('@')
                g.locator = {
                  type,
                  version: Number(version),
                  params:
                    type === 'fixed'
                      ? { rect: [0.25, 0.25, 0.75, 0.75] }
                      : type === 'blob'
                        ? { mode: 'dark' }
                        : {},
                }
              })
            }
            options={[
              { value: 'none', label: t.noLocator },
              ...(types.data?.locators ?? []).map((l) => ({
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
          value={locator.params ?? {}}
          errors={prefixed(fields, 'job.geometry.locator.params')}
          onChange={(params) => setGeometry((g) => (g.locator.params = params), false)}
        />
      ) : null}

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
              <button type="button" className="font-mono text-sm" onClick={() => setSelected(id)}>
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
            <Input {...props} value={newName} onChange={(e) => setNewName(e.target.value.trim())} />
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

export function ToolsStep({ draft, image, fields, test, setSelected }: StepProps) {
  const types = useTypes()
  const tools: JobJson[] = draft.job.tools ?? []
  const [open, setOpen] = useState<number | null>(tools.length ? 0 : null)
  const [adding, setAdding] = useState('')
  const roiNames = [
    'frame',
    ...(draft.job.geometry?.locator ? ['anchor'] : []),
    ...Object.keys(draft.job.geometry?.rois ?? {}),
  ]
  const setTools = (change: (list: JobJson[]) => void, history = true) =>
    edit((d) => change((d.job.tools ??= [])), history)
  const swap = (i: number, j: number) => setTools((list) => list.splice(j, 0, ...list.splice(i, 1)))

  const proposeColour = async (i: number) => {
    const roi = tools[i]!.roi
    const rect: Rect | undefined =
      roi === 'frame'
        ? [0, 0, 1, 1]
        : draft.job.geometry?.rois?.[roi]?.relative_to === 'frame'
          ? draft.job.geometry.rois[roi].rect
          : undefined
    if (!image || !rect) {
      toast.error(t.colourNeedsFrameRegion)
      return
    }
    const pixels = await pixelsOf(image)
    const s = pixels ? suggestHue(sample(pixels, rect)) : null
    if (!s) {
      toast.error(t.colourNone)
      return
    }
    setTools(
      (list) =>
        (list[i]!.params = {
          ...list[i]!.params,
          mode: 'range',
          hue: s.hue,
          s_min: s.s_min,
          v_min: s.v_min,
        }),
    )
    toast.success(t.colourProposed(s.hue[0], s.hue[1]))
  }

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
                  {tool.type === 'color' ? (
                    <Button variant="ghost" onClick={() => void proposeColour(i)}>
                      <Pipette aria-hidden className="size-4" />
                      {t.proposeColour}
                    </Button>
                  ) : null}
                  {type ? (
                    <SchemaForm
                      schema={type.params_schema}
                      value={tool.params ?? {}}
                      errors={prefixed(fields, `job.tools.${i}.params`)}
                      onChange={(params) => setTools((list) => (list[i]!.params = params), false)}
                    />
                  ) : (
                    <p className="text-sm text-warn-text">{t.unknownType}</p>
                  )}
                  <Field
                    label={t.reasonFail}
                    hint={t.reasonHint}
                    error={fields[`job.tools.${i}.reason_fail`]}
                  >
                    {(props) => (
                      <Input
                        {...props}
                        value={tool.reason_fail ?? ''}
                        onChange={(e) =>
                          setTools((list) => (list[i]!.reason_fail = e.target.value), false)
                        }
                      />
                    )}
                  </Field>
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
                reason_fail: t.defaultReason,
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
                      label: t.outcome[o],
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
                label: t.outcome[o],
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

// --- 7. review --------------------------------------------------------------------------------------

export function ReviewStep({ draft, fields }: StepProps & { onSave?: () => void }) {
  const [check, setCheck] = useState<{
    ok: boolean
    message?: string | null
    fields: Record<string, string>
  } | null>(null)
  const run = async () => {
    try {
      const r = await editorApi.validate(toRequest(draft))
      setCheck({ ok: r.ok, message: r.message, fields: r.fields })
    } catch (e) {
      toast.error(describeError(e))
    }
  }
  const all = { ...fields, ...(check?.fields ?? {}) }
  return (
    <div className="flex flex-col gap-4">
      <Field label={t.jobName}>
        {(props) => (
          <Input
            {...props}
            value={draft.job.job?.name ?? ''}
            onChange={(e) => edit((d) => (d.job.job.name = e.target.value), false)}
          />
        )}
      </Field>
      <Field label={t.description}>
        {(props) => (
          <Textarea
            {...props}
            rows={2}
            value={draft.job.job?.description ?? ''}
            onChange={(e) => edit((d) => (d.job.job.description = e.target.value), false)}
          />
        )}
      </Field>
      <Button onClick={() => void run()}>{t.validate}</Button>
      {check ? (
        <div role="status" className="flex flex-col gap-1 text-sm">
          {check.ok ? (
            <StatusIndicator tone="ok" label={t.valid} />
          ) : (
            <StatusIndicator tone="fail" label={check.message ?? t.invalid} />
          )}
        </div>
      ) : null}
      {Object.keys(all).length > 0 ? (
        <ul aria-label={t.fieldErrors} className="flex flex-col gap-1 text-sm text-fail-text">
          {Object.entries(all).map(([k, v]) => (
            <li key={k}>
              <span className="font-mono">{k}</span>: {v}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-sm text-fg-muted">{t.files(draftFiles(draft).length)}</p>
    </div>
  )
}
