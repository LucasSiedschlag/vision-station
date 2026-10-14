import { beforeEach, describe, expect, it } from 'vitest'
import { applyMessage, useLive, type LiveMessage, type StateOut } from './live'

const status = (over: Partial<StateOut> = {}): StateOut => ({
  state: 'Ready',
  message: 'Aguardando objeto',
  detail: '',
  warnings: [],
  job: { id: 'j', name: 'Caixa M', version: 7 },
  last_result: null,
  last_record_id: null,
  camera: { connected: true, last_frame_age_s: 0.1, last_error: null },
  counters: { PASS: 0, FAIL: 0, ERROR: 0, total: 0 },
  recording_failures: 0,
  version: '0.1.0',
  ...over,
})

const statusMessage = (over: Partial<StateOut> = {}): LiveMessage => ({
  type: 'status',
  ...status(over),
})

describe('applyMessage', () => {
  it('takes a full status as it is, without the message type', () => {
    const next = applyMessage(null, statusMessage())
    expect(next?.state).toBe('Ready')
    expect(next).not.toHaveProperty('type')
  })

  it('ignores events that arrive before the first full status', () => {
    expect(
      applyMessage(null, {
        type: 'state',
        state: 'Inspecting',
        previous: 'Ready',
        message: 'Inspecionando…',
      }),
    ).toBeNull()
  })

  it('follows state events', () => {
    const next = applyMessage(status(), {
      type: 'state',
      state: 'Inspecting',
      previous: 'Ready',
      message: 'Inspecionando…',
    })
    expect(next).toMatchObject({ state: 'Inspecting', message: 'Inspecionando…' })
  })

  it('counts a result and keeps the record id, without touching the old status', () => {
    const before = status()
    const after = applyMessage(before, {
      type: 'result',
      outcome: 'FAIL',
      reason: 'Fita ausente',
      scores: { fita: 0.5 },
      duration_ms: 120,
      job: { id: 'j', name: 'Caixa M', version: 7 },
      record_id: 'r1',
    })
    expect(after?.counters).toEqual({ PASS: 0, FAIL: 1, ERROR: 0, total: 1 })
    expect(after?.last_result).toMatchObject({ outcome: 'FAIL', reason: 'Fita ausente' })
    expect(after?.last_record_id).toBe('r1')
    expect(before.counters.total).toBe(0)
  })

  it('lets the next full status correct the counters', () => {
    const counted = applyMessage(status(), {
      type: 'result',
      outcome: 'PASS',
      reason: '',
      scores: {},
      duration_ms: 90,
      job: { id: 'j', name: 'x', version: 1 },
      record_id: null,
    })
    const refreshed = applyMessage(
      counted,
      statusMessage({ counters: { PASS: 5, FAIL: 1, ERROR: 0, total: 6 } }),
    )
    expect(refreshed?.counters.total).toBe(6)
  })
})

describe('the live store', () => {
  beforeEach(() =>
    useLive.setState({ status: null, frame: null, connected: false, connecting: true }),
  )

  it('says "connecting" until the first status, then not', () => {
    expect(useLive.getState().connecting).toBe(true)
    useLive.getState().apply(statusMessage())
    expect(useLive.getState().connecting).toBe(false)
  })

  it('drops the picture when the socket closes, so no stale image is shown', () => {
    useLive.getState().setConnected(true)
    useLive.getState().setFrame(new Blob(['x']))
    useLive.getState().setConnected(false)
    expect(useLive.getState().frame).toBeNull()
    expect(useLive.getState().connecting).toBe(false)
  })
})
