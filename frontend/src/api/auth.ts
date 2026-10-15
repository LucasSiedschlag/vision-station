import { create } from 'zustand'
import { api, call } from './client'
import { useSession } from './session'

/** The login dialog is one for the whole app: anything can open it, and it remembers where to go afterwards. */
interface LoginDialogState {
  open: boolean
  /** true from the first time it was opened, so the dialog's code is loaded once and then kept */
  opened: boolean
  /** the path to open once the login succeeds */
  next: string | null
  show: (next?: string) => void
  hide: () => void
}

export const useLoginDialog = create<LoginDialogState>((set) => ({
  open: false,
  opened: false,
  next: null,
  show: (next) => set({ open: true, opened: true, next: next ?? null }),
  hide: () => set({ open: false, next: null }),
}))

export async function login(role: 'supervisor' | 'maintainer', password: string) {
  const out = await call(api.POST('/api/login', { body: { role, password } }))
  useSession.getState().signIn(out.token, out.role, out.expires_in_s)
  return out.role
}

/** Ends the session on the server, then here. The server call is best effort: leaving always works. */
export async function logout() {
  try {
    await call(api.POST('/api/logout'))
  } catch {
    /* already out, or the server is not reachable: the local session ends anyway */
  }
  useSession.getState().clear()
}
