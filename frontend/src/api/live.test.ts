import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useLocale } from '@/app/locale'
import { applyMessage, startLive, useLive, type LiveMessage, type StateOut } from './live'

// the result contract fields every result message carries (TD-22)
const contract = {
  sequence: null,
  error_code: 0,
  reason_codes: [],
  tools: [],
  groups: [],
  fixtures: [],
  trigger: null,
  acquired_at: null,
  decided_at: null,
  simulated: false,
}

const status = (over: Partial<StateOut> = {}): StateOut => ({
  state: 'Ready',
  language: 'pt-BR',
  message: 'Aguardando objeto',
  showing_result: false,
  detail: '',
  warnings: [],
  job: { id: 'j', name: 'Tampa azul', version: 7, number: null, content_hash: null },
  last_result: null,
  last_record_id: null,
  camera: { connected: true, last_frame_age_s: 0.1, last_error: null },
  counters: { PASS: 0, FAIL: 0, ERROR: 0, total: 0 },
  recent: [],
  markings: 'on_fail',
  operator_markings: true,
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
        showing_result: false,
      }),
    ).toBeNull()
  })

  it('follows state events', () => {
    const next = applyMessage(status(), {
      type: 'state',
      state: 'Inspecting',
      previous: 'Ready',
      message: 'Inspecionando…',
      showing_result: false,
    })
    expect(next).toMatchObject({ state: 'Inspecting', message: 'Inspecionando…' })
  })

  it('follows whether the last verdict is still shown, also without a change of state', () => {
    const held = applyMessage(status(), {
      type: 'state',
      state: 'Ready',
      previous: 'ShowingResult',
      message: 'PASS',
      showing_result: true,
    })
    expect(held).toMatchObject({ state: 'Ready', showing_result: true })
    const over = applyMessage(held, {
      type: 'state',
      state: 'Ready',
      previous: 'Ready',
      message: 'Aguardando objeto',
      showing_result: false,
    })
    expect(over).toMatchObject({
      state: 'Ready',
      showing_result: false,
      message: 'Aguardando objeto',
    })
  })

  it('counts a result and keeps the record id, without touching the old status', () => {
    const before = status()
    const after = applyMessage(before, {
      ...contract,
      type: 'result',
      outcome: 'FAIL',
      reason: 'Tampa ausente',
      scores: { tampa: 0.5 },
      duration_ms: 120,
      at: '2026-10-14T14:32:07-03:00',
      job: { id: 'j', name: 'Tampa azul', version: 7, number: null, content_hash: null },
      record_id: 'r1',
    })
    expect(after?.counters).toEqual({ PASS: 0, FAIL: 1, ERROR: 0, total: 1 })
    expect(after?.last_result).toMatchObject({ outcome: 'FAIL', reason: 'Tampa ausente' })
    expect(after?.last_record_id).toBe('r1')
    expect(after?.last_result?.at).toBe('2026-10-14T14:32:07-03:00')
    expect(after?.recent).toEqual([
      {
        outcome: 'FAIL',
        reason: 'Tampa ausente',
        at: '2026-10-14T14:32:07-03:00',
        record_id: 'r1',
      },
    ])
    expect(before.counters.total).toBe(0)
  })

  it('keeps only the last ten results, oldest first', () => {
    let current: StateOut | null = status()
    for (let i = 0; i < 12; i++) {
      current = applyMessage(current, {
        ...contract,
        type: 'result',
        outcome: i % 2 ? 'FAIL' : 'PASS',
        reason: `r${i}`,
        scores: {},
        duration_ms: 1,
        at: `t${i}`,
        job: { id: 'j', name: 'x', version: 1, number: null, content_hash: null },
        record_id: null,
      })
    }
    expect(current?.recent.map((r) => r.reason)).toEqual([
      'r2',
      'r3',
      'r4',
      'r5',
      'r6',
      'r7',
      'r8',
      'r9',
      'r10',
      'r11',
    ])
  })

  it('lets the next full status correct the counters', () => {
    const counted = applyMessage(status(), {
      ...contract,
      type: 'result',
      outcome: 'PASS',
      reason: '',
      scores: {},
      duration_ms: 90,
      at: null,
      job: { id: 'j', name: 'x', version: 1, number: null, content_hash: null },
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

describe('the live socket and the language', () => {
  const sockets: { url: string; close: () => void; onclose?: () => void }[] = []
  class FakeSocket {
    binaryType = ''
    onopen?: () => void
    onclose?: () => void
    constructor(public url: string) {
      sockets.push(this)
    }
    close() {
      this.onclose?.()
    }
  }

  beforeEach(() => {
    sockets.length = 0
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeSocket)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    useLocale.setState({ locale: 'pt-BR' })
  })

  it('says its language in the address, because a browser cannot set a header on a socket', () => {
    useLocale.setState({ locale: 'en' })
    const stop = startLive()
    expect(sockets[0]?.url).toMatch(/\/api\/live\?lang=en$/)
    stop()
  })

  it('opens again at once in the new language when the language changes', () => {
    const stop = startLive()
    expect(sockets).toHaveLength(1)
    useLocale.setState({ locale: 'en' })
    vi.advanceTimersByTime(0)
    expect(sockets).toHaveLength(2)
    expect(sockets[1]?.url).toMatch(/lang=en$/)
    stop()
  })
})
