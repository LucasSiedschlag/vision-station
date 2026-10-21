import { describe, expect, it } from 'vitest'
import schemas from '@/test/tool-schemas.json'
import type { Draft } from './draft'
import { summarizeChanges } from './summary'

const types = { tools: [{ name: 'color', params_schema: schemas.color }] }
const tool = (params: Record<string, unknown>, over: Record<string, unknown> = {}) => ({
  id: 'tampa',
  type: 'color',
  version: 1,
  roi: 'cap',
  params,
  reason_fail: 'Tampa ausente',
  ...over,
})
const job = (tools: unknown[], over: Record<string, unknown> = {}) => ({
  job: { name: 'Tampa azul', description: '' },
  geometry: { rois: { cap: { relative_to: 'frame', rect: [0.1, 0.1, 0.5, 0.5] } } },
  acquisition: { trigger: { type: 'manual' } },
  quality: { sharpness_min_ratio: 0.5 },
  ui: { waiting: null },
  decision: 'all_pass',
  tools,
  ...over,
})
const from = (
  before: ReturnType<typeof job>,
  after: ReturnType<typeof job>,
  over: Partial<Draft> = {},
): Draft => ({
  key: 'j',
  base: { id: 'j', version: 2 },
  job: structuredClone(after),
  profile: { exposure: { value_us: 8000 } },
  baseFiles: [],
  addFiles: {},
  removeFiles: [],
  expected: null,
  baseExpected: 'null',
  baseJob: structuredClone(before),
  baseProfile: { exposure: { value_us: 8000 } },
  notes: '',
  ...over,
})

describe('what changed, in words', () => {
  it('says nothing when nothing changed', () => {
    const j = job([tool({ min_fraction: 0.4 })])
    expect(summarizeChanges(from(j, j), types)).toEqual([])
  })

  it('names a changed parameter by its title, with a fraction as a percentage', () => {
    const lines = summarizeChanges(
      from(job([tool({ min_fraction: 0.4 })]), job([tool({ min_fraction: 0.6, s_min: 90 })])),
      types,
    )
    expect(lines).toContain('tampa: Fração mínima da área, 40% → 60%')
    expect(lines).toContain('tampa: Saturação mínima, nenhum → 90')
  })

  it('tools, regions, the anchor, the trigger and the texts', () => {
    const before = job([tool({ min_fraction: 0.4 }), tool({}, { id: 'lote', type: 'code' })])
    const after = job(
      [
        tool({ min_fraction: 0.4 }, { affects_result: false }),
        tool({}, { id: 'novo', type: 'code' }),
      ],
      {
        geometry: {
          rois: { outra: { relative_to: 'frame', rect: [0, 0, 1, 1] } },
          fixtures: [{ name: 'anchor', locator: { type: 'blob', version: 1, params: {} } }],
        },
        acquisition: { trigger: { type: 'continuous' } },
        ui: { waiting: 'Aguardando peça' },
      },
    )
    const lines = summarizeChanges(from(before, after), types)
    expect(lines).toEqual(
      expect.arrayContaining([
        'Âncora nova (blob)',
        'Região nova: outra',
        'Região removida: cap',
        'tampa passou a só informar, sem reprovar',
        'Ferramenta nova: novo (code)',
        'Ferramenta removida: lote',
        'O disparo mudou',
        'Os textos do operador mudaram',
      ]),
    )
  })

  it('the camera, the reference image and the samples', () => {
    const j = job([tool({})])
    const draft = from(j, j, {
      profile: { exposure: { value_us: 4000 }, orientation: 'mirror' },
      addFiles: { 'reference/reference.png': 'AAAA' },
      expected: {
        cases: [
          { image: 'tests/images/a.png', outcome: 'PASS' },
          { image: 'tests/images/b.png', outcome: 'FAIL' },
          { image: 'tests/images/c.png', outcome: 'FAIL' },
        ],
      },
      baseExpected: JSON.stringify({
        cases: [
          { image: 'tests/images/a.png', outcome: 'PASS' },
          { image: 'tests/images/old.png', outcome: 'PASS' },
        ],
      }),
    })
    expect(summarizeChanges(draft, types)).toEqual([
      'Câmera, exposição: value_us 8000 → value_us 4000',
      'Câmera, orientação: Normal → Espelhada',
      'Nova imagem de referência',
      'Amostras novas: 0 Boas e 2 Ruins',
      '1 amostra removida',
    ])
  })

  it('a new job is described whole; a draft kept by an older build has no version to compare', () => {
    const j = job([tool({}), tool({}, { id: 'b' })])
    expect(summarizeChanges({ ...from(j, j), base: null }, types)).toEqual([
      'Job novo Tampa azul: 2 ferramentas',
    ])
    expect(summarizeChanges({ ...from(j, j), baseJob: undefined }, types)).toEqual([])
  })
})
