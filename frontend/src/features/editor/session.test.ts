import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FakeSocket } from '@/test/fake-socket'
import type { Draft } from './draft'
import { EditorSession, filesKey } from './session'

const draft = (over: Partial<Draft> = {}): Draft => ({
  key: 'j',
  base: { id: 'a', version: 2 },
  job: { tools: [{ id: 't', params: { min_fraction: 0.4 } }] },
  profile: { exposure: { mode: 'manual', value_us: 8000 } },
  baseFiles: [],
  addFiles: { 'reference/reference.png': 'AAAA'.repeat(100) },
  removeFiles: [],
  expected: null,
  baseExpected: 'null',
  notes: '',
  ...over,
})

const measurement = (id: number) => ({
  type: 'result',
  frame_id: id,
  width: 640,
  height: 480,
  result: { outcome: 'PASS', tools: [] },
  regions: [],
  anchor: null,
  tools: {},
  timings: {},
})

function start(token: string | null = 'tok') {
  const session = new EditorSession(
    'ws://x/api/editor/live',
    token,
    (u) => new FakeSocket(u) as never,
  )
  const socket = FakeSocket.all.at(-1)!
  return { session, socket }
}

beforeEach(() => {
  FakeSocket.all = []
  vi.useFakeTimers()
})
afterEach(() => vi.useRealTimers())

describe('the editor session', () => {
  it('says who it is first, and sends the files with the draft once it is told it is ready', () => {
    const { session, socket } = start()
    session.setDraft(draft(), 0)
    socket.open()
    expect(socket.sent).toEqual([{ type: 'hello', token: 'tok' }])
    socket.say({ type: 'ready', fps: 4, paused_by_session: true })
    expect(session.state).toMatchObject({ status: 'live', pausedBySession: true })
    expect(socket.sent[1]).toMatchObject({
      type: 'draft',
      base: { id: 'a', version: 2 },
      add_files: { 'reference/reference.png': expect.any(String) },
    })
  })

  it('a change of limit sends only the job and the profile, after a short pause; a new file sends the files again', () => {
    const { session, socket } = start()
    session.setDraft(draft(), 0)
    socket.open()
    socket.say({ type: 'ready', fps: 4, paused_by_session: false })
    const edited = draft({ job: { tools: [{ id: 't', params: { min_fraction: 0.5 } }] } })
    session.setDraft(edited)
    session.setDraft(edited) // a drag is many changes
    expect(socket.sent).toHaveLength(2)
    vi.advanceTimersByTime(130)
    expect(socket.sent).toHaveLength(3)
    expect(socket.sent[2]).not.toHaveProperty('add_files')
    expect(socket.sent[2].job.tools[0].params.min_fraction).toBe(0.5)
    session.setDraft(draft({ addFiles: { 'tests/images/a.png': 'BBBB' } }))
    vi.advanceTimersByTime(130)
    expect(socket.sent[3]).toHaveProperty('add_files')
    expect(filesKey(draft())).not.toBe(filesKey(draft({ addFiles: {} })))
  })

  it('pairs each measurement with the picture that follows it, and counts how many a second', () => {
    let clock = 1000
    const session = new EditorSession(
      'ws://x',
      'tok',
      (u) => new FakeSocket(u) as never,
      () => clock,
    )
    const socket = FakeSocket.all.at(-1)!
    socket.open()
    socket.say({ type: 'ready', fps: 4, paused_by_session: false })
    socket.picture() // a picture with no measurement before it is not shown
    expect(session.state.frame).toBeNull()
    for (let i = 1; i <= 5; i++) {
      socket.say(measurement(i))
      clock += 250
      socket.picture()
    }
    expect(session.state.last?.frame_id).toBe(5)
    expect(session.state.frame).toBeInstanceOf(Blob)
    expect(session.state.fps).toBeCloseTo(4, 1)
  })

  it('a refused draft and a lost camera are states, and the next good draft clears the first', () => {
    const { session, socket } = start()
    socket.open()
    socket.say({ type: 'ready', fps: 4, paused_by_session: false })
    socket.say({
      type: 'draft_error',
      message: 'O job tem campos inválidos',
      fields: { 'job.tools.0.roi': 'x' },
    })
    expect(session.state.draftError).toEqual({
      message: 'O job tem campos inválidos',
      fields: { 'job.tools.0.roi': 'x' },
    })
    socket.say({ type: 'draft_ok' })
    expect(session.state.draftError).toBeNull()
    socket.say({ type: 'camera', connected: false, message: 'Câmera desconectada' })
    expect(session.state.camera).toBe(false)
  })

  it('another editor holding the camera, or not being a maintainer, ends it without trying again', () => {
    const { session, socket } = start()
    socket.open()
    socket.say({ type: 'error', code: 'session_busy' })
    expect(session.state.status).toBe('busy')
    socket.close()
    vi.advanceTimersByTime(20000)
    expect(FakeSocket.all).toHaveLength(1)
    const other = start(null)
    other.socket.open()
    other.socket.say({ type: 'error', code: 'login_required' })
    expect(other.session.state.status).toBe('refused')
  })

  it('a connection that drops is opened again, and the files are sent again', () => {
    const { session, socket } = start()
    session.setDraft(draft(), 0)
    socket.open()
    socket.say({ type: 'ready', fps: 4, paused_by_session: false })
    socket.close() // the server restarted
    expect(session.state.status).toBe('connecting')
    vi.advanceTimersByTime(2100)
    expect(FakeSocket.all).toHaveLength(2)
    const again = FakeSocket.all[1]!
    again.open()
    expect(again.sent[0]).toEqual({ type: 'hello', token: 'tok' })
    again.say({ type: 'ready', fps: 4, paused_by_session: false })
    expect(again.sent[1]).toHaveProperty('add_files')
  })

  it('closing it does not open it again, and an idle end is an end', () => {
    const { session, socket } = start()
    socket.open()
    socket.say({ type: 'ready', fps: 4, paused_by_session: false })
    socket.say({ type: 'idle' })
    expect(session.state.status).toBe('ended')
    session.close()
    vi.advanceTimersByTime(20000)
    expect(FakeSocket.all).toHaveLength(1)
  })
})
