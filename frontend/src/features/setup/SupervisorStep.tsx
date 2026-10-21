import { useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { useSetPassword } from '@/api/queries/admin'
import type { SetupStep } from '@/api/queries/setup'
import { text } from '@/texts'
import { PasswordForm } from './PasswordForm'

const t = text.setup

/** The Supervisor's password, set by the Maintainer who is commissioning the station (docs/frontend.md §7.11). */
export function SupervisorStep({ step }: { step: SetupStep }) {
  const client = useQueryClient()
  const set = useSetPassword()
  if (step.state === 'done')
    return (
      <>
        <p role="status">{t.supervisorDone}</p>
        <p className="text-xs text-fg-muted">
          <Link to="/access" className="underline">
            {t.changeInAccess}
          </Link>
        </p>
      </>
    )
  return (
    <PasswordForm
      label={t.supervisorPassword}
      help={t.supervisorHelp}
      submitLabel={t.supervisorSet}
      pending={set.isPending}
      error={set.isError ? describeError(set.error) : null}
      onSubmit={(password) =>
        set.mutate(
          { role: 'supervisor', password },
          {
            onSuccess: () => {
              toast.success(t.supervisorDone)
              void client.invalidateQueries({ queryKey: ['setup'] })
            },
          },
        )
      }
    />
  )
}
