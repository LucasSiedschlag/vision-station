import type { ReactNode } from 'react'
import { useSetupOpen } from '@/api/queries/setup'
import { RequireRole } from '@/app/guards'

/** `/setup` opens with no login while the Maintainer has no password (the first step creates it); the Maintainer's after. */
export function SetupGuard({ children }: { children: ReactNode }) {
  const open = useSetupOpen()
  if (open.isPending) return null
  if (open.data?.open) return <>{children}</>
  return <RequireRole min="maintainer">{children}</RequireRole>
}
