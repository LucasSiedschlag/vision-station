import { describe, expect, it } from 'vitest'
import type { ResultOut, StateOut } from '@/api/live'
import { stateFixture } from '@/test/render'
import {
  canMarkWrong,
  canTrigger,
  clockTime,
  connectionOf,
  markingsOn,
  percent,
  toolRows,
  verdictOf,
} from './view'

const status = (over: Record<string, unknown> = {}) => stateFixture(over) as StateOut
const showing = (
  outcome: 'PASS' | 'FAIL' | 'ERROR',
  reason = '',
  extra: Record<string, unknown> = {},
) =>
  status({
    state: 'ShowingResult',
    last_result: {
      outcome,
      reason,
      scores: {},
      duration_ms: 310,
      at: '2026-10-14T14:32:07-03:00',
      ...extra,
    },
    last_record_id: 'r1',
  })

describe('verdictOf', () => {
  it('a verdict still shown after the station armed again is the verdict, not "waiting"', () => {
    const held = {
      ...showing('FAIL', 'Código não lido'),
      state: 'Ready',
      showing_result: true,
    } as StateOut
    expect(verdictOf(held, 'connected')).toMatchObject({
      headline: 'REPROVADO',
      reason: 'Código não lido',
    })
    const over = { ...held, showing_result: false, message: 'Aguardando objeto' } as StateOut
    expect(verdictOf(over, 'connected').headline).not.toBe('REPROVADO')
  })

  it('every result has a word and an icon, not only a colour', () => {
    const pass = verdictOf(showing('PASS'), 'connected')
    expect([pass.tone, pass.icon, pass.headline, pass.size]).toEqual([
      'ok',
      'check',
      'APROVADO',
      'display',
    ])
    const fail = verdictOf(showing('FAIL', 'Tampa fora da cor em 40% da área'), 'connected')
    expect([fail.tone, fail.icon, fail.headline, fail.reason]).toEqual([
      'fail',
      'cross',
      'REPROVADO',
      'Tampa fora da cor em 40% da área',
    ])
    const error = verdictOf(showing('ERROR', 'Câmera desconectada durante a inspeção'), 'connected')
    expect([error.tone, error.icon, error.headline]).toEqual(['warn', 'alert', 'ERRO'])
  })

  it('shows the duration of a result, and the time when the server said it', () => {
    expect(verdictOf(showing('PASS'), 'connected').meta).toMatch(/^\d\d:\d\d:\d\d · 310 ms$/)
    expect(verdictOf(showing('PASS', '', { at: null }), 'connected').meta).toBe('310 ms')
  })

  it('an unexpected outcome is never shown as a pass', () => {
    const odd = verdictOf(showing('WHATEVER' as 'PASS'), 'connected')
    expect([odd.tone, odd.headline]).toEqual(['warn', 'ERRO'])
    const noResult = verdictOf(status({ state: 'ShowingResult', last_result: null }), 'connected')
    expect(noResult.headline).toBe('ERRO')
  })

  it('the other states, with a word each', () => {
    expect(verdictOf(status(), 'connected').headline).toBe('Aguardando peça') // the text comes from the job
    expect(verdictOf(status({ state: 'WaitingStill' }), 'connected').tone).toBe('neutral')
    expect(verdictOf(status({ state: 'Inspecting' }), 'connected')).toMatchObject({
      tone: 'busy',
      headline: 'Inspecionando…',
      size: 'title',
    })
    expect(verdictOf(status({ state: 'CameraLost' }), 'connected')).toMatchObject({
      tone: 'warn',
      headline: 'Câmera desconectada',
    })
    expect(
      verdictOf(status({ state: 'Fault', detail: 'ajuste não aplicado: exposure' }), 'connected'),
    ).toMatchObject({ headline: 'Falha na verificação', reason: 'ajuste não aplicado: exposure' })
    expect(verdictOf(status({ state: 'Fault' }), 'connected').reason).toBe('Chamar a manutenção.')
    expect(verdictOf(status({ state: 'Paused' }), 'connected').headline).toBe('Em manutenção')
    expect(verdictOf(status({ state: 'Preparing' }), 'connected').headline).toBe('Preparando…')
  })

  it('while connecting it says so, and without a connection it never shows the old verdict as current', () => {
    expect(verdictOf(null, 'connecting')).toMatchObject({
      tone: 'neutral',
      headline: 'Conectando…',
    })
    const offline = verdictOf(showing('PASS'), 'offline')
    expect([offline.tone, offline.headline]).toEqual(['neutral', 'Sem conexão'])
    expect(offline.stale).toContain('Último resultado: APROVADO')
    expect(offline.stale).toContain('desatualizado')
    expect(verdictOf(null, 'offline').stale).toBe('')
  })
})

describe('actions', () => {
  it('the trigger is for a station that is ready, and only with a connection', () => {
    expect(canTrigger(status(), 'connected')).toBe(true)
    expect(canTrigger(status({ state: 'WaitingStill' }), 'connected')).toBe(true)
    for (const state of [
      'Inspecting',
      'ShowingResult',
      'Fault',
      'Paused',
      'CameraLost',
      'Preparing',
    ])
      expect(canTrigger(status({ state }), 'connected')).toBe(false)
    expect(canTrigger(status(), 'offline')).toBe(false)
    expect(canTrigger(null, 'connected')).toBe(false)
  })

  it('"wrong result?" needs a recorded result on screen', () => {
    expect(canMarkWrong(showing('PASS'), 'connected')).toBe(true)
    expect(
      canMarkWrong(
        status({
          state: 'ShowingResult',
          last_result: showing('PASS').last_result,
          last_record_id: null,
        }),
        'connected',
      ),
    ).toBe(false)
    expect(canMarkWrong(status(), 'connected')).toBe(false)
    expect(canMarkWrong(showing('PASS'), 'offline')).toBe(false)
  })
})

describe('helpers', () => {
  it('connectionOf', () => {
    expect(connectionOf(false, true)).toBe('connecting')
    expect(connectionOf(true, false)).toBe('connected')
    expect(connectionOf(false, false)).toBe('offline')
  })
  it('percent and clockTime', () => {
    expect(percent(1, 4)).toBe(25)
    expect(percent(1, 0)).toBe(0)
    expect(clockTime(null)).toBe('')
    expect(clockTime('not a date')).toBe('')
    expect(clockTime('2026-10-14T14:32:07-03:00')).toMatch(/^\d\d:\d\d:\d\d$/)
  })
})

// --- the lines under the verdict, and the markings (VIA-0063) ------------------------------------------

const tool = (id: string, passed: boolean, over: Record<string, unknown> = {}) => ({
  id,
  type: 'color',
  version: 1,
  passed,
  score: passed ? 1 : 0.2,
  margin: null,
  values: { fraction: 0.12 },
  units: { fraction: 'fraction' },
  criteria: [
    {
      code: 'min_fraction',
      kind: 'min',
      measure: 'fraction',
      value: 0.12,
      limit: 0.4,
      passed,
      score: 1,
    },
  ],
  affects_result: true,
  error: '',
  error_code: 0,
  region: [0.1, 0.1, 0.3, 0.3],
  ...over,
})
const resultWith = (tools: unknown[], outcome: 'PASS' | 'FAIL' = 'FAIL', groups?: unknown[]) =>
  ({ outcome, reason: '', scores: {}, duration_ms: 1, tools, groups }) as unknown as ResultOut

describe('toolRows', () => {
  it('lists the deciding tools with the value that decided each, in the language of the interface', () => {
    const { rows, more } = toolRows(
      resultWith([
        tool('tampa', false),
        tool('lote', true, {
          units: { matching: 'count' },
          criteria: [
            { code: 'min_count', kind: 'min', measure: 'matching', value: 1, passed: true },
          ],
        }),
        tool('logo', true, { affects_result: false }), // informative: not a line
      ]),
    )
    expect(rows).toEqual([
      { id: 'tampa', passed: false, value: '12%' },
      { id: 'lote', passed: true, value: '1' },
    ])
    expect(more).toBe(0)
  })

  it('a group is one line (any member is enough), not one line per member', () => {
    const { rows } = toolRows(
      resultWith(
        [
          tool('logo', false, { group: 'marca' }),
          tool('texto', true, { group: 'marca' }),
          tool('tampa', true),
        ],
        'PASS',
        [{ id: 'marca', passed: true, members: ['logo', 'texto'] }],
      ),
    )
    expect(rows).toEqual([
      { id: 'logo / texto', passed: true, value: '1/2' }, // at its first member, like the reasons
      { id: 'tampa', passed: true, value: '12%' },
    ])
  })

  it('a failed group comes first, like any failing line', () => {
    const { rows } = toolRows(
      resultWith(
        [
          tool('tampa', true),
          tool('logo', false, { group: 'marca' }),
          tool('texto', false, { group: 'marca' }),
        ],
        'FAIL',
        [{ id: 'marca', passed: false, members: ['logo', 'texto'] }],
      ),
    )
    expect(rows.map((r) => [r.id, r.passed])).toEqual([
      ['logo / texto', false],
      ['tampa', true],
    ])
  })

  it('shows at most six, the failing ones first, and counts the others', () => {
    const tools = Array.from({ length: 8 }, (_, i) => tool(`t${i}`, i !== 7))
    const { rows, more } = toolRows(resultWith(tools))
    expect(rows).toHaveLength(6)
    expect(rows.map((r) => r.id)).toContain('t7') // the one that failed is never the one left out
    expect(rows.map((r) => r.id)).toEqual(['t7', 't0', 't1', 't2', 't3', 't4'])
    expect(more).toBe(2)
  })

  it('has no line for a result without tools, and none for a rule with no measure', () => {
    expect(toolRows(null)).toEqual({ rows: [], more: 0 })
    const rule = tool('classe', false, {
      criteria: [{ code: 'class', kind: 'rule', measure: null, value: null, passed: false }],
    })
    expect(toolRows(resultWith([rule])).rows).toEqual([{ id: 'classe', passed: false, value: '' }])
  })
})

describe('markingsOn', () => {
  const fail = resultWith([], 'FAIL')
  const pass = resultWith([], 'PASS')

  it('follows the station default: always, only on a failure, never', () => {
    expect(markingsOn('always', true, null, pass)).toBe(true)
    expect(markingsOn('on_fail', true, null, pass)).toBe(false)
    expect(markingsOn('on_fail', true, null, fail)).toBe(true)
    expect(markingsOn('never', true, null, fail)).toBe(false)
  })

  it('the operator choice wins, unless the station does not allow it', () => {
    expect(markingsOn('never', true, true, fail)).toBe(true)
    expect(markingsOn('always', true, false, fail)).toBe(false)
    expect(markingsOn('never', false, true, fail)).toBe(false)
  })

  it('draws nothing when there is no result on screen', () => {
    expect(markingsOn('always', true, true, null)).toBe(false)
  })
})
