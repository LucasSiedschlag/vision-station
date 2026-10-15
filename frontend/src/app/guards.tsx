import { useEffect, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useLoginDialog } from '@/api/auth'
import { useSession, type Role } from '@/api/session'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/feedback'
import { ForbiddenPage } from '@/features/errors/ForbiddenPage'
import { atLeast } from '@/lib/permissions'
import { text } from '@/texts'

/**
 * Opens a screen only for a role that may. The server checks the same thing on every call; this decides what the
 * person sees:
 * - not logged in: back to the station, with the login dialog open and this screen as the place to go afterwards;
 * - the session ended while on the screen: the screen is kept, the login dialog opens over it;
 * - logged in with too few rights: a plain "no permission" page.
 */
export function RequireRole({ min, children }: { min: Role; children: ReactNode }) {
  const role = useSession((s) => s.role)
  const expired = useSession((s) => s.expired)
  const show = useLoginDialog((s) => s.show)
  const location = useLocation()
  const here = location.pathname + location.search

  useEffect(() => {
    if (role === 'operator' && expired) show(here)
  }, [role, expired, show, here])

  if (atLeast(role, min)) return <>{children}</>
  if (role === 'operator' && expired) {
    return (
      <EmptyState
        title={text.errors.expiredTitle}
        description={text.login.expired}
        action={
          <Button variant="primary" onClick={() => show(here)}>
            {text.login.open}
          </Button>
        }
      />
    )
  }
  if (role === 'operator') return <LoginRedirect next={here} />
  return <ForbiddenPage />
}

function LoginRedirect({ next }: { next: string }) {
  const show = useLoginDialog((s) => s.show)
  useEffect(() => show(next), [show, next])
  return <Navigate to="/" replace />
}
