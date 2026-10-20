import { text } from '@/texts'
import { draftFiles, locatorOf, type Draft, type JobJson } from './draft'

/**
 * The order of work of the job editor and the state of each step (docs/frontend.md §4.3, FR-UI-11). The sequence guides
 * and never locks: a blocked step can be opened to read, everything can be visited in any order. The state of a step
 * comes from the draft and from what the server said, never from where the person has been, except for the steps
 * whose defaults are valid (they are done once looked at).
 */
export const STEPS = [
  'image',
  'samples',
  'anchor',
  'tools',
  'quality',
  'outputs',
  'validate',
  'save',
] as const
export type StepId = (typeof STEPS)[number]

export type StepState = 'done' | 'todo' | 'attention' | 'blocked'
export interface StepInfo {
  state: StepState
  /** Why a step is blocked or needs attention, or what it still needs; empty when there is nothing to say. */
  reason: string
}

/** Which server field paths belong to which step, to mark a step that has errors. */
export const STEP_FIELDS: Record<StepId, string[]> = {
  image: ['profile', 'job.trigger'],
  samples: ['add_files'],
  anchor: ['job.geometry.fixtures'],
  tools: ['job.tools', 'job.geometry'],
  quality: ['job.quality'],
  outputs: ['job.ui', 'job.decision'],
  validate: [],
  save: ['job.job', 'job.format'],
}

/** The step a server field path belongs to: the most specific prefix wins (`job.geometry.fixtures` is not Ferramentas). */
export function stepOfField(path: string): StepId | null {
  let best: { step: StepId; length: number } | null = null
  for (const step of STEPS)
    for (const prefix of STEP_FIELDS[step])
      if (
        (path === prefix || path.startsWith(`${prefix}.`)) &&
        (!best || prefix.length > best.length)
      )
        best = { step, length: prefix.length }
  return best?.step ?? null
}

/** The result of Validar and what the draft looked like then, to know when it no longer describes the draft. */
export interface Validation {
  ok: boolean
  /** samples that were not as expected */
  failed: number
  total: number
  /** the draft's image and samples at that moment, and the whole draft */
  imageSig: string
  fullSig: string
}

function hash(value: string): string {
  let h = 5381
  for (let i = 0; i < value.length; i++) h = ((h << 5) + h + value.charCodeAt(i)) | 0
  return (h >>> 0).toString(36)
}

const fingerprint = (path: string, data: string) =>
  `${path}:${data.length}:${data.slice(0, 40)}${data.slice(-40)}`

/** What the picture the job learns from is made of: the camera settings, the reference and the samples. */
export function imageSignature(draft: Draft): string {
  const files = Object.entries(draft.addFiles)
    .filter(([path]) => path.startsWith('reference/') || path.startsWith('tests/'))
    .map(([path, data]) => fingerprint(path, data))
    .sort()
  const kept = draftFiles(draft).filter((p) => p.startsWith('reference/') || p.startsWith('tests/'))
  return hash(JSON.stringify([draft.profile, files, kept, draft.expected]))
}

/** Everything that changes a result: the image and samples, and the job's own settings (not its name or notes). */
export function fullSignature(draft: Draft): string {
  const { job: _info, ...rest } = draft.job
  const files = Object.entries(draft.addFiles)
    .filter(([path]) => !path.startsWith('reference/') && !path.startsWith('tests/'))
    .map(([path, data]) => fingerprint(path, data))
    .sort()
  return hash(JSON.stringify([imageSignature(draft), rest, files]))
}

export const hasReference = (draft: Draft) => draftFiles(draft).includes('reference/reference.png')

const tools = (draft: Draft): JobJson[] => draft.job.tools ?? []
const samples = (draft: Draft) => draft.expected?.cases ?? []

/** The state of every step. `visited` are the steps already opened, for those whose defaults are valid. */
export function stepStates(
  draft: Draft,
  fields: Record<string, string>,
  visited: ReadonlySet<StepId>,
  validation: Validation | null,
): Record<StepId, StepInfo> {
  const t = text.editor.sequence
  const wrong = new Set(Object.keys(fields).map((path) => stepOfField(path)))
  const reference = hasReference(draft)
  // a job that already has tools can be edited without a reference image; a new one learns from it first
  const needsReference = reference || tools(draft).length > 0 ? '' : t.needReference
  const needsTool = tools(draft).length > 0 ? '' : t.needTool
  const current = validation
    ? {
        image: validation.imageSig === imageSignature(draft),
        whole: validation.fullSig === fullSignature(draft),
      }
    : null

  const by = (step: StepId, info: StepInfo): StepInfo =>
    wrong.has(step) ? { state: 'attention', reason: t.serverProblem } : info
  const visitedOrTodo = (step: StepId): StepInfo =>
    visited.has(step) ? { state: 'done', reason: '' } : { state: 'todo', reason: '' }

  const info = {} as Record<StepId, StepInfo>
  info.image = by('image', visitedOrTodo('image'))
  info.samples = by(
    'samples',
    reference
      ? {
          state: 'done',
          reason: samples(draft).length === 0 ? t.noSamples : '',
        }
      : { state: 'todo', reason: t.needReferenceHere },
  )
  info.anchor = by(
    'anchor',
    needsReference
      ? { state: 'blocked', reason: needsReference }
      : locatorOf(draft.job) || visited.has('anchor')
        ? { state: 'done', reason: '' }
        : { state: 'todo', reason: '' },
  )
  info.tools = by(
    'tools',
    needsReference
      ? { state: 'blocked', reason: needsReference }
      : current && !current.image
        ? { state: 'attention', reason: t.imageChanged }
        : needsTool
          ? { state: 'todo', reason: needsTool }
          : { state: 'done', reason: '' },
  )
  info.quality = by('quality', visitedOrTodo('quality'))
  info.outputs = by(
    'outputs',
    needsTool ? { state: 'blocked', reason: needsTool } : visitedOrTodo('outputs'),
  )
  info.validate = needsTool
    ? { state: 'blocked', reason: needsTool }
    : !validation
      ? { state: 'todo', reason: samples(draft).length === 0 ? t.noSamples : '' }
      : !current!.whole
        ? { state: 'attention', reason: t.changedSinceValidation }
        : validation.ok
          ? { state: 'done', reason: '' }
          : { state: 'attention', reason: t.samplesFailed(validation.failed, validation.total) }
  info.save = by(
    'save',
    info.validate.state === 'done'
      ? { state: 'todo', reason: '' }
      : { state: 'todo', reason: t.notValidated },
  )
  return info
}
