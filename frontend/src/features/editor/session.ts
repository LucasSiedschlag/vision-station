import { useEffect, useRef, useState } from 'react'
import { useSession } from '@/api/session'
import type { components } from '@/api/schema'
import { currentLocale } from '@/app/locale'
import type { Draft } from './draft'

/**
 * The editor's live session (docs/frontend.md §9.5, §19.1): one WebSocket that sends the draft and gets back, a few
 * times a second, the result of the draft on the newest camera frame, then that frame. The files of the draft
 * (the reference and the samples weigh megabytes) are sent once; a change of limit sends only the job and the profile.
 */
export type SessionResult = {
  frame_id: number
  width: number
  height: number
  result: components['schemas']['ResultOut']
  regions: components['schemas']['RegionOut'][]
  anchor: number[] | null
  tools: Record<string, unknown>
  timings: Record<string, unknown>
}

/** What the camera controls show of the newest frame, whatever the draft (docs/frontend.md §19.5). */
export type CameraMetrics = {
  frame_id: number
  /** the sharpness the quality gate measures */
  sharpness: number
  /** the pixels of each of the 256 gray levels */
  histogram: number[]
  /** the percentage crushed to black and saturated */
  clipped_low: number
  clipped_high: number
}

export interface SessionState {
  /** connecting; live (the draft is being measured); busy (another editor holds the camera); refused (not a maintainer); ended */
  status: 'connecting' | 'live' | 'busy' | 'refused' | 'ended'
  /** the camera delivers pictures; null until the server says */
  camera: boolean | null
  /** the last measurement, and the picture it was taken on */
  last: SessionResult | null
  frame: Blob | null
  /** measurements per second over the last few seconds */
  fps: number
  /** the draft was refused: why, and which fields */
  draftError: { message: string; fields: Record<string, string> } | null
  /** the session paused the station (and resumes it when it ends) */
  pausedBySession: boolean
  metrics: CameraMetrics | null
}

export const initialSession: SessionState = {
  status: 'connecting',
  camera: null,
  last: null,
  frame: null,
  fps: 0,
  draftError: null,
  pausedBySession: false,
  metrics: null,
}

/** What the session needs of a draft: its files (sent when they change) and its job and profile (sent on each edit). */
export function draftMessage(draft: Draft, withFiles: boolean) {
  return {
    type: 'draft',
    job: draft.job,
    profile: draft.profile,
    ...(withFiles
      ? { base: draft.base, add_files: draft.addFiles, remove_files: draft.removeFiles }
      : {}),
  }
}

const head = (data: string) => `${data.length}:${data.slice(0, 24)}${data.slice(-24)}`
/** Changes when the files of the draft change: which are added or removed, and a cheap fingerprint of each. */
export function filesKey(draft: Draft): string {
  return JSON.stringify([
    draft.base,
    Object.entries(draft.addFiles).map(([path, data]) => [path, head(data)]),
    draft.removeFiles,
  ])
}

type SocketFactory = (url: string) => WebSocket

export class EditorSession {
  state: SessionState = initialSession
  private socket: WebSocket | null = null
  private listeners = new Set<(state: SessionState) => void>()
  private draft: Draft | null = null
  private sentFiles: string | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private retry: ReturnType<typeof setTimeout> | null = null
  private waiting: SessionResult | null = null
  private stamps: number[] = []
  private closed = false
  private delay = 1000
  private ready = false

  constructor(
    private url: string,
    private token: string | null,
    private factory: SocketFactory = (u) => new WebSocket(u),
    private now: () => number = Date.now,
  ) {
    this.open()
  }

  subscribe(listener: (state: SessionState) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** The draft as it is now. It goes out after a short pause, so a drag of a limit is one message. */
  setDraft(draft: Draft, pause = 120): void {
    this.draft = draft
    if (!this.ready) return // it goes with the greeting's answer
    if (this.timer) clearTimeout(this.timer)
    this.timer = setTimeout(() => this.sendDraft(), pause)
  }

  close(): void {
    this.closed = true
    if (this.timer) clearTimeout(this.timer)
    if (this.retry) clearTimeout(this.retry)
    this.socket?.close()
  }

  private publish(next: Partial<SessionState>): void {
    this.state = { ...this.state, ...next }
    for (const listener of this.listeners) listener(this.state)
  }

  private sendDraft(force = false): void {
    if (!this.draft || this.socket?.readyState !== 1) return
    const key = filesKey(this.draft)
    const withFiles = force || key !== this.sentFiles
    this.sentFiles = key
    this.socket.send(JSON.stringify(draftMessage(this.draft, withFiles)))
  }

  private open(): void {
    const socket = this.factory(this.url)
    this.socket = socket
    socket.binaryType = 'blob'
    this.ready = false
    socket.onopen = () => socket.send(JSON.stringify({ type: 'hello', token: this.token }))
    socket.onmessage = (event: MessageEvent<string | Blob>) => {
      if (typeof event.data !== 'string') {
        // the picture of the measurement that came just before it
        if (this.waiting) {
          const stamp = this.now()
          this.stamps = [...this.stamps.filter((t) => stamp - t < 3000), stamp]
          this.publish({
            last: this.waiting,
            frame: event.data,
            fps:
              this.stamps.length > 1
                ? (this.stamps.length - 1) / ((stamp - this.stamps[0]!) / 1000)
                : 0,
          })
          this.waiting = null
        }
        return
      }
      const message = JSON.parse(event.data) as { type: string } & Record<string, unknown>
      switch (message.type) {
        case 'ready':
          this.ready = true
          this.delay = 1000
          this.publish({ status: 'live', pausedBySession: Boolean(message.paused_by_session) })
          this.sendDraft(true) // the files go once per connection
          break
        case 'draft_ok':
          this.publish({ draftError: null })
          break
        case 'draft_error':
          this.publish({
            draftError: {
              message: String(message.message ?? ''),
              fields: (message.fields as Record<string, string>) ?? {},
            },
          })
          break
        case 'camera':
          this.publish({ camera: Boolean(message.connected) })
          break
        case 'metrics':
          this.publish({ metrics: message as unknown as CameraMetrics })
          break
        case 'result':
          this.waiting = message as unknown as SessionResult
          break
        case 'error':
          this.closed = true
          this.publish({ status: message.code === 'session_busy' ? 'busy' : 'refused' })
          break
        case 'idle':
          this.closed = true
          this.publish({ status: 'ended' })
          break
      }
    }
    socket.onclose = () => {
      this.ready = false
      if (this.closed) {
        if (this.state.status === 'live' || this.state.status === 'connecting')
          this.publish({ status: 'ended' })
        return
      }
      // an unexpected end (the server restarted, the network): try again, and say so meanwhile
      this.publish({ status: 'connecting', camera: null })
      this.retry = setTimeout(() => this.open(), (this.delay = Math.min(this.delay * 2, 8000)))
    }
    socket.onerror = () => socket.close()
  }
}

/** The editor's session as React state: opened while `enabled`, closed (and the station resumed) when it is not. */
export function useEditorSession(draft: Draft, enabled: boolean): SessionState {
  const [state, setState] = useState<SessionState>(initialSession)
  const session = useRef<EditorSession | null>(null)
  const token = useSession((s) => s.token)
  const draftRef = useRef(draft)
  useEffect(() => {
    draftRef.current = draft
  })

  useEffect(() => {
    if (!enabled) return
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/editor/live?lang=${currentLocale()}`
    const next = new EditorSession(url, token)
    session.current = next
    const unsubscribe = next.subscribe(setState)
    next.setDraft(draftRef.current, 0)
    return () => {
      unsubscribe()
      next.close()
      session.current = null
      setState(initialSession)
    }
  }, [enabled, token])

  useEffect(() => {
    session.current?.setDraft(draft)
  }, [draft])

  return enabled ? state : initialSession
}
