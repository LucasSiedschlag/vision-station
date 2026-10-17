import { lazy, Suspense } from 'react'
import { Outlet, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { logout } from '@/api/auth'
import { useSession } from '@/api/session'
import { useLoginDialog } from '@/api/auth'
import { useIdle } from '@/lib/idle'
import { text } from '@/texts'

// the menu shell and the login dialog are needed only after a login: they are loaded then, so the station screen stays light
const AppShell = lazy(() => import('./shell/AppShell').then((m) => ({ default: m.AppShell })))
const LoginDialog = lazy(() =>
  import('@/features/auth/LoginDialog').then((m) => ({ default: m.LoginDialog })),
)

/** A person with a login who stops touching the screen is logged out and the station is shown again (docs/frontend.md §4.2). */
export const IDLE_LOGOUT_MS = 10 * 60 * 1000

export function RootLayout() {
  const role = useSession((s) => s.role)
  const navigate = useNavigate()
  const loginOpened = useLoginDialog((s) => s.opened)

  useIdle(
    IDLE_LOGOUT_MS,
    () => {
      void logout().then(() => {
        toast(text.login.idleLogout)
        void navigate('/')
      })
    },
    role !== 'operator',
  )

  return (
    <>
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface-1 focus:px-4 focus:py-2"
      >
        {text.ui.skipToContent}
      </a>
      {role === 'operator' ? (
        <div id="content" tabIndex={-1} className="h-full outline-none">
          <Outlet />
        </div>
      ) : (
        <Suspense fallback={null}>
          <AppShell />
        </Suspense>
      )}
      {loginOpened ? (
        <Suspense fallback={null}>
          <LoginDialog />
        </Suspense>
      ) : null}
    </>
  )
}
