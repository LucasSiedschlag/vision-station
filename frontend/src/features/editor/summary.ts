import { formatNumber, formatPercent } from '@/lib/number'
import { text } from '@/texts'
import type { TypeInfo } from '@/api/queries/editor'
import { type Draft, type JobJson } from './draft'
import type { Schema } from './SchemaForm'

const c = text.editor.change
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

/** A parameter value as a person reads it: a fraction as a percentage, a list with commas, "nenhum" for nothing. */
function show(value: unknown, unit?: string): string {
  if (value === null || value === undefined || value === '') return c.nothing
  if (typeof value === 'number')
    return unit === 'fraction' ? formatPercent(value) : formatNumber(value)
  if (typeof value === 'boolean') return value ? c.on : c.off
  if (Array.isArray(value)) return value.map((v) => show(v)).join(', ')
  if (typeof value === 'object')
    return Object.entries(value as Record<string, unknown>)
      .map(([key, v]) => `${key} ${show(v)}`)
      .join(', ')
  return String(value)
}

/** A camera setting as a person reads it: the orientation by its name, the others by their values. */
function profileValue(key: string, value: unknown): string {
  if (key === 'orientation')
    return text.editor.orientations[(value ?? 'normal') as keyof typeof text.editor.orientations]
  return show(value)
}

function paramChanges(
  id: string,
  before: JobJson,
  after: JobJson,
  schema: Schema | undefined,
): string[] {
  const properties = (schema?.properties ?? {}) as Record<string, Schema>
  return [...new Set([...Object.keys(before), ...Object.keys(after)])]
    .filter((key) => !same(before[key], after[key]))
    .map((key) => {
      const prop = properties[key]
      const title = prop?.title ?? key
      const unit = prop?.['x-unit'] as string | undefined
      return c.param(id, title, show(before[key], unit), show(after[key], unit))
    })
}

/**
 * What the draft changes against the version it started from, in words, for the person who saves it (docs/frontend.md
 * §4.3). It reads the job and the files as the editor holds them; names come from the schemas the server sent, in the
 * language on screen. A new job, or a draft kept by an older build, has no version to compare with.
 */
export function summarizeChanges(
  draft: Draft,
  types: { tools: Pick<TypeInfo, 'name' | 'params_schema'>[] } | undefined,
): string[] {
  const out: string[] = []
  const job = draft.job
  if (!draft.base) {
    const n = (job.tools ?? []).length
    return [c.newJob(job.job?.name ?? '', n)]
  }
  const baseJob = draft.baseJob
  const baseProfile = draft.baseProfile
  if (!baseJob) return out

  if (job.job?.name !== baseJob.job?.name)
    out.push(c.name(baseJob.job?.name ?? '', job.job?.name ?? ''))
  if ((job.job?.description ?? '') !== (baseJob.job?.description ?? '')) out.push(c.description)

  for (const key of Object.keys({ ...baseProfile, ...draft.profile }))
    if (!same(baseProfile?.[key], draft.profile[key]))
      out.push(
        c.camera(
          c.settings[key] ?? key,
          profileValue(key, baseProfile?.[key]),
          profileValue(key, draft.profile[key]),
        ),
      )

  if ('reference/reference.png' in draft.addFiles) out.push(c.reference)
  const before = new Set(
    (JSON.parse(draft.baseExpected) as Draft['expected'])?.cases.map((x) => x.image),
  )
  const cases = draft.expected?.cases ?? []
  const added = cases.filter((x) => !before.has(x.image))
  const kept = new Set(cases.map((x) => x.image))
  const removed = [...before].filter((image) => !kept.has(image as string))
  if (added.length)
    out.push(
      c.samplesAdded(
        added.filter((x) => x.outcome === 'PASS').length,
        added.filter((x) => x.outcome !== 'PASS').length,
      ),
    )
  if (removed.length) out.push(c.samplesRemoved(removed.length))

  const wasLocator = baseJob.geometry?.locator
  const locator = job.geometry?.locator
  if (!same(wasLocator, locator))
    out.push(
      !wasLocator
        ? c.anchorAdded(locator.type)
        : !locator
          ? c.anchorRemoved
          : c.anchorChanged(locator.type),
    )
  const rois = (job.geometry?.rois ?? {}) as Record<string, unknown>
  const wasRois = (baseJob.geometry?.rois ?? {}) as Record<string, unknown>
  for (const name of Object.keys(rois))
    if (!(name in wasRois)) out.push(c.regionAdded(name))
    else if (!same(rois[name], wasRois[name])) out.push(c.regionChanged(name))
  for (const name of Object.keys(wasRois)) if (!(name in rois)) out.push(c.regionRemoved(name))

  const tools: JobJson[] = job.tools ?? []
  const wasTools: JobJson[] = baseJob.tools ?? []
  for (const tool of tools) {
    const was = wasTools.find((x) => x.id === tool.id)
    if (!was) {
      out.push(c.toolAdded(tool.id, tool.type))
      continue
    }
    const schema = types?.tools.find((x) => x.name === tool.type)?.params_schema as
      Schema | undefined
    out.push(...paramChanges(tool.id, was.params ?? {}, tool.params ?? {}, schema))
    if (tool.roi !== was.roi) out.push(c.toolRegion(tool.id, was.roi, tool.roi))
    if ((tool.affects_result ?? true) !== (was.affects_result ?? true))
      out.push(tool.affects_result === false ? c.toolInformative(tool.id) : c.toolDecides(tool.id))
    if ((tool.reason_fail ?? '') !== (was.reason_fail ?? '')) out.push(c.toolReason(tool.id))
  }
  for (const was of wasTools)
    if (!tools.some((x) => x.id === was.id)) out.push(c.toolRemoved(was.id))

  if (!same(job.trigger, baseJob.trigger)) out.push(c.trigger)
  if (!same(job.quality, baseJob.quality)) out.push(c.quality)
  if (!same(job.ui, baseJob.ui)) out.push(c.texts)
  if (!same(job.decision, baseJob.decision)) out.push(c.decision)
  return out
}
