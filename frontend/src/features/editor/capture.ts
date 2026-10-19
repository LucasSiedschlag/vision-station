import { editorApi } from '@/api/queries/editor'
import { text } from '@/texts'
import { toRequest, useDraft, type Draft } from './draft'

const t = text.editor

/**
 * A sample from the camera, now: the picture with the verdict the draft gives it, recorded in the draft as a *Boa*
 * (expected PASS) or a *Ruim* (expected FAIL) of the reference set (docs/frontend.md §7.3). The name is the next free
 * `boa-n` or `ruim-n`. It returns what to tell the person.
 */
export async function captureSample(draft: Draft, kind: 'good' | 'bad'): Promise<string> {
  const prefix = kind === 'good' ? 'boa' : 'ruim'
  const taken = new Set([
    ...(draft.expected?.cases ?? []).map((c) => c.image),
    ...Object.keys(draft.addFiles),
  ])
  let n = 1
  while (taken.has(`tests/images/${prefix}-${n}.png`)) n++
  const name = `${prefix}-${n}`
  const out = await editorApi.captureCase(toRequest(draft), name)
  useDraft.getState().edit((d) => {
    d.addFiles[out.path] = out.image
    d.expected ??= { tolerance: 0.05, cases: [] }
    d.expected.cases.push({ image: out.path, outcome: kind === 'good' ? 'PASS' : 'FAIL' })
  })
  return t.caseAdded(
    name,
    t.outcome[out.result.outcome],
    t.outcome[kind === 'good' ? 'PASS' : 'FAIL'],
  )
}
