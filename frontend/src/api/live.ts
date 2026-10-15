import { create } from 'zustand'
import type { components } from './schema'

export type LiveMessage = components['schemas']['LiveMessage']
export type StateOut = components['schemas']['StateOut']

/** What the screens read: the last status, the newest camera frame, and whether the socket is up. */
interface LiveState {
  status: StateOut | null
  frame: Blob | null
  connected: boolean
  /** true until the first status arrives, so a screen can say "connecting" instead of showing a stale verdict */
  connecting: boolean
  apply: (message: LiveMessage) => void
  setFrame: (frame: Blob | null) => void
  setConnected: (connected: boolean) => void
}

/** Applies one message from the live socket to the status. Pure, so it is tested without a browser. */
export function applyMessage(status: StateOut | null, message: LiveMessage): StateOut | null {
  if (message.type === 'status') {
    const { type: _type, ...rest } = message
    return rest
  }
  if (!status) return status // events before the first full status carry too little to show
  if (message.type === 'state') {
    return { ...status, state: message.state, message: message.message }
  }
  const counters = { ...status.counters }
  counters[message.outcome] += 1
  counters.total += 1
  return {
    ...status,
    counters,
    last_result: {
      outcome: message.outcome,
      reason: message.reason,
      scores: message.scores,
      duration_ms: message.duration_ms,
      at: message.at ?? null,
    },
    last_record_id: message.record_id ?? null,
    recent: [
      ...status.recent,
      { outcome: message.outcome, reason: message.reason, at: message.at ?? '' },
    ].slice(-10),
  }
}

export const useLive = create<LiveState>((set) => ({
  status: null,
  frame: null,
  connected: false,
  connecting: true,
  apply: (message) =>
    set((s) => ({
      status: applyMessage(s.status, message),
      connecting: s.connecting && message.type !== 'status',
    })),
  setFrame: (frame) => set({ frame }),
  setConnected: (connected) =>
    set((s) => ({
      connected,
      connecting: connected ? s.connecting : false,
      frame: connected ? s.frame : null,
    })),
}))

/** Opens the live socket and keeps it open, with growing waits between attempts. Returns a function that closes it. */
export function startLive(url = defaultUrl()): () => void {
  let socket: WebSocket | null = null
  let closed = false
  let delay = 500
  let lastFrame = 0

  const open = () => {
    socket = new WebSocket(url)
    socket.binaryType = 'blob'
    socket.onopen = () => {
      delay = 500
      useLive.getState().setConnected(true)
    }
    socket.onmessage = (event: MessageEvent<string | Blob>) => {
      if (typeof event.data === 'string') {
        useLive.getState().apply(JSON.parse(event.data) as LiveMessage)
      } else {
        lastFrame = Date.now()
        useLive.getState().setFrame(event.data)
      }
    }
    socket.onclose = () => {
      useLive.getState().setConnected(false)
      if (!closed) setTimeout(open, (delay = Math.min(delay * 2, 5000)))
    }
    socket.onerror = () => socket?.close()
  }

  open()
  // no frame for 3 s: show "no image" instead of the last picture
  const staleTimer = setInterval(() => {
    if (lastFrame && Date.now() - lastFrame > 3000) {
      lastFrame = 0
      useLive.getState().setFrame(null)
    }
  }, 1000)

  return () => {
    closed = true
    clearInterval(staleTimer)
    socket?.close()
  }
}

function defaultUrl(): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/live`
}
