import { describe, expect, it } from 'vitest'
import type { Draft } from './draft'
import {
  fullSignature,
  imageSignature,
  stepOfField,
  stepStates,
  type StepId,
  type Validation,
} from './sequence'

const draft = (over: Partial<Draft> = {}, job: Record<string, unknown> = {}): Draft => ({
  key: 'j',
  base: null,
  job: { format: 1, job: { name: 'x' }, tools: [], geometry: { rois: {} }, ...job },
  profile: { exposure: { mode: 'manual', value_us: 8000 } },
  baseFiles: [],
  addFiles: {},
  removeFiles: [],
  expected: null,
  baseExpected: 'null',
  notes: '',
  ...over,
})
const withReference = (d: Draft): Draft => ({
  ...d,
  addFiles: { ...d.addFiles, 'reference/reference.png': 'AAAA' },
})
const tool = { id: 'tampa', type: 'color', version: 1, roi: 'frame', params: {} }
const none = new Set<StepId>()

describe('the state of each step', () => {
  it('a new job starts with the image to take: what needs it is blocked, and says why', () => {
    const info = stepStates(draft(), {}, none, null)
    expect(info.anchor).toEqual({
      state: 'blocked',
      reason: 'Capture a imagem de referência primeiro',
    })
    expect(info.tools.state).toBe('blocked')
    expect(info.outputs).toEqual({ state: 'blocked', reason: 'Adicione ao menos uma ferramenta' })
    expect(info.validate.state).toBe('blocked')
    expect(info.samples).toEqual({ state: 'todo', reason: 'Capture a imagem de referência' })
    expect(info.image.state).toBe('todo')
  })

  it('the reference image opens the anchor and the tools; a tool opens outputs and validation', () => {
    const withTool = withReference(draft({}, { tools: [tool] }))
    const info = stepStates(withTool, {}, none, null)
    expect(info.samples).toEqual({ state: 'done', reason: 'Ainda sem amostras Boas e Ruins' })
    expect(info.anchor.state).toBe('todo')
    expect(info.tools.state).toBe('done')
    expect(info.outputs.state).toBe('todo')
    expect(info.validate).toEqual({ state: 'todo', reason: 'Ainda sem amostras Boas e Ruins' })
  })

  it('a job that already has tools is not blocked for lack of a reference image', () => {
    const info = stepStates(draft({}, { tools: [tool] }), {}, none, null)
    expect(info.tools.state).toBe('done')
    expect(info.anchor.state).toBe('todo')
  })

  it('steps whose defaults are valid are done once opened', () => {
    const info = stepStates(
      withReference(draft({}, { tools: [tool] })),
      {},
      new Set(['image', 'quality', 'outputs']),
      null,
    )
    expect([info.image.state, info.quality.state, info.outputs.state]).toEqual([
      'done',
      'done',
      'done',
    ])
  })

  it('what the server refused marks the step it belongs to, and the more specific path wins', () => {
    const info = stepStates(
      withReference(draft({}, { tools: [tool] })),
      {
        'job.quality.brightness.min': 'x',
        'job.geometry.fixtures.0.locator.params.rect': 'x',
        'job.tools.0.params.min_fraction': 'x',
        'profile.exposure': 'x',
      },
      none,
      null,
    )
    expect(info.quality.state).toBe('attention')
    expect(info.anchor.state).toBe('attention')
    expect(info.tools.state).toBe('attention')
    expect(info.image.state).toBe('attention')
    expect(info.outputs.state).toBe('todo')
    expect(stepOfField('job.geometry.fixtures.0.locator.type')).toBe('anchor')
    expect(stepOfField('job.geometry.rois.cap.rect')).toBe('tools')
    expect(stepOfField('add_files')).toBe('samples')
    // the trigger is set with the image (TD-32), the quality gates are their own step
    expect(stepOfField('job.acquisition.trigger.continuous.interval_ms')).toBe('image')
    expect(stepOfField('job.quality.sharpness_min_ratio')).toBe('quality')
    expect(stepOfField('somewhere.else')).toBeNull()
  })
})

describe('Validar and what changes after it', () => {
  const base = withReference(draft({}, { tools: [tool] }))
  const validated = (d: Draft, over: Partial<Validation> = {}): Validation => ({
    ok: true,
    failed: 0,
    total: 3,
    imageSig: imageSignature(d),
    fullSig: fullSignature(d),
    ...over,
  })

  it('done when every sample was as expected and nothing changed since', () => {
    const info = stepStates(base, {}, none, validated(base))
    expect(info.validate).toEqual({ state: 'done', reason: '' })
    expect(info.save.reason).toBe('')
  })

  it('needs attention when samples failed, with how many', () => {
    const info = stepStates(base, {}, none, validated(base, { ok: false, failed: 2 }))
    expect(info.validate).toEqual({
      state: 'attention',
      reason: '2 de 3 amostras não saíram como esperado',
    })
  })

  it('a changed tool makes the validation old, and says so; the image and tools stay as they were', () => {
    const run = validated(base)
    const edited = {
      ...base,
      job: { ...base.job, tools: [{ ...tool, params: { min_fraction: 0.6 } }] },
    }
    const info = stepStates(edited, {}, none, run)
    expect(info.validate).toEqual({
      state: 'attention',
      reason: 'O job mudou depois da validação; rode Validar de novo',
    })
    expect(info.tools.state).toBe('done') // the image did not change
    expect(info.save.reason).toBe('Ainda não validado')
  })

  it('a new picture or camera setting after Validar marks the tools, as the order of work asks', () => {
    const run = validated(base)
    const darker = { ...base, profile: { exposure: { mode: 'manual', value_us: 4000 } } }
    const info = stepStates(darker, {}, none, run)
    expect(info.tools).toEqual({
      state: 'attention',
      reason: 'A imagem mudou depois da última validação; rode Validar',
    })
    expect(info.validate.state).toBe('attention')
    const mirrored = { ...base, profile: { ...base.profile, orientation: 'mirror' } }
    expect(stepStates(mirrored, {}, none, run).tools.state).toBe('attention') // the pictures were taken the other way
    const another = { ...base, addFiles: { ...base.addFiles, 'tests/images/b.png': 'BBBB' } }
    expect(stepStates(another, {}, none, run).tools.state).toBe('attention')
  })

  it('the name, the notes and the description do not make a validation old', () => {
    const run = validated(base)
    const renamed = { ...base, notes: 'n', job: { ...base.job, job: { name: 'outro' } } }
    expect(stepStates(renamed, {}, none, run).validate.state).toBe('done')
  })
})
