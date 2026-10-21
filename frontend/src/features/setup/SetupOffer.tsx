import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { useSetupStatus } from '@/api/queries/setup'
import { useSession } from '@/api/session'

const OFFERED = 'vision-station-setup-offered'

/**
 * After the Maintainer logs in to an installation that still needs setting up, the wizard opens once (docs/frontend.md
 * §7.11). Once per session: someone who leaves it goes where they were going and is not taken back. The editor is left alone.
 */
export function SetupOffer() {
  const role = useSession((s) => s.role)
  const status = useSetupStatus(role === 'maintainer')
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const needed = status.data?.needs_setup === true

  useEffect(() => {
    if (!needed || pathname.startsWith('/setup') || pathname.endsWith('/edit')) return
    try {
      if (sessionStorage.getItem(OFFERED)) return
      sessionStorage.setItem(OFFERED, '1')
    } catch {
      /* no storage: offered again at the next load, which is harmless */
    }
    void navigate('/setup')
  }, [needed, pathname, navigate])

  return null
}
