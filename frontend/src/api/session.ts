import { create } from 'zustand'
import type { components } from './schema'

export type Role = components['schemas']['WhoAmI']['role']
const KEY = 'vision-station-session'

interface Stored {
  token: string | null
  role: Role
  expires: number
}

const anonymous: Stored = { token: null, role: 'operator', expires: 0 }

function load(): Stored {
  try {
    const stored = JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as Stored | null
    if (stored && stored.expires > Date.now()) return stored
  } catch {
    /* no storage: the session lasts until the page is reloaded */
  }
  return anonymous
}

interface SessionState extends Stored {
  /** true when the server stopped accepting the token (it expired or was revoked), as opposed to the person leaving. */
  expired: boolean
  /** Called when the server says the token is no longer good. The page is kept and a login dialog opens. */
  expire: () => void
  /** Called after a successful login. */
  signIn: (token: string, role: Role, expiresInSeconds: number) => void
  /** Called on logout, and when the server says the token expired. */
  clear: () => void
}

function save(next: Stored) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* ignore */
  }
}

/** The role is only what the screens show; the server decides what is allowed (docs/frontend.md §8). */
export const useSession = create<SessionState>((set) => ({
  ...load(),
  expired: false,
  signIn: (token, role, expiresInSeconds) => {
    const next = { token, role, expires: Date.now() + expiresInSeconds * 1000 }
    save(next)
    set({ ...next, expired: false })
  },
  clear: () => {
    save(anonymous)
    set({ ...anonymous, expired: false })
  },
  expire: () => {
    save(anonymous)
    set({ ...anonymous, expired: true })
  },
}))
