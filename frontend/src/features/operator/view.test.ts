import { describe, expect, it } from 'vitest'
import type { StateOut } from '@/api/live'
import { stateFixture } from '@/test/render'
import { canMarkWrong, canTrigger, clockTime, connectionOf, percent, verdictOf } from './view'

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
  it('every result has a word and an icon, not only a colour', () => {
    const pass = verdictOf(showing('PASS'), 'connected')
    expect([pass.tone, pass.icon, pass.headline, pass.size]).toEqual([
      'ok',
      'check',
      'APROVADO',
      'display',
    ])
    const fail = verdictOf(showing('FAIL', 'Fita ausente em 40% da emenda'), 'connected')
    expect([fail.tone, fail.icon, fail.headline, fail.reason]).toEqual([
      'fail',
      'cross',
      'REPROVADO',
      'Fita ausente em 40% da emenda',
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
    expect(verdictOf(status(), 'connected').headline).toBe('Aguardando caixa') // the text comes from the job
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
