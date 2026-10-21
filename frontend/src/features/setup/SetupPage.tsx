import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { describeError } from '@/api/mutations'
import { useCreateMaintainerPassword, useSetupStatus, type SetupStep } from '@/api/queries/setup'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Stepper, type Step } from '@/components/ui/stepper'
import { text } from '@/texts'

const t = text.setup

/** Where each step is done today. The steps of the wizard that do it on this screen replace these links (VIA-0068). */
const WHERE: Partial<Record<SetupStep['id'], string>> = {
  camera: '/settings',
  supervisor_password: '/access',
  backup: '/settings',
  first_job: '/jobs',
}

/**
 * The commissioning wizard (docs/frontend.md §7.11, FR-ADM-8): a fresh installation taken to its first job, in
 * order. What is done and what is not comes from the server, never from this screen. While the Maintainer has no
 * password the page opens without a login and only the first step can be used.
 */
export function SetupPage() {
  const status = useSetupStatus()
  const [chosen, setChosen] = useState<SetupStep['id'] | null>(null)

  if (status.isPending) {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6" aria-busy="true">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <Skeleton className="h-64 w-full" />
        <span className="sr-only">{t.loading}</span>
      </main>
    )
  }
  if (status.isError) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Card>
          <ErrorState
            message={t.loadError}
            detail={describeError(status.error)}
            onRetry={() => void status.refetch()}
          />
        </Card>
      </main>
    )
  }

  const { steps, needs_setup, maintainer_password_missing } = status.data
  const firstTodo = steps.find((s) => s.state === 'todo')
  const currentId = chosen ?? firstTodo?.id ?? steps[0]!.id
  const current = steps.find((s) => s.id === currentId)!
  const items: Step[] = steps.map((s) => {
    const locked = maintainer_password_missing && s.id !== 'maintainer_password'
    return {
      id: s.id,
      label: t.steps[s.id],
      status: locked || s.state === 'unavailable' ? 'blocked' : s.state,
      current: s.id === currentId,
      reason: locked ? t.createFirst : (s.detail ?? undefined),
    }
  })

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <p className="text-sm text-fg-muted">{t.intro}</p>
      </div>
      <div className="grid gap-6 md:grid-wizard">
        <nav aria-label={t.stepsLabel}>
          <Stepper steps={items} onSelect={(id) => setChosen(id as SetupStep['id'])} />
        </nav>
        <Card>
          <CardHeader>
            <CardTitle>{t.steps[current.id]}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {current.id === 'maintainer_password' && maintainer_password_missing ? (
              <MaintainerPasswordForm />
            ) : (
              <StepBody step={current} locked={maintainer_password_missing} />
            )}
            {!needs_setup ? <Finished /> : null}
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

function StepBody({ step, locked }: { step: SetupStep; locked: boolean }) {
  const where = WHERE[step.id]
  return (
    <>
      <p role="status">
        {locked ? t.createFirst : (step.detail ?? (step.state === 'done' ? t.done : ''))}
      </p>
      {where && !locked && step.state === 'todo' ? (
        <div>
          <Link to={where} className={buttonVariants({ variant: 'primary' })}>
            {t.openIn}
          </Link>
        </div>
      ) : null}
    </>
  )
}

function Finished() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col gap-3 border-t border-line pt-4">
      <p role="status" className="font-medium">
        {t.allDone}
      </p>
      <div>
        <Button variant="primary" onClick={() => void navigate('/')}>
          {t.goStation}
        </Button>
      </div>
    </div>
  )
}

/** The first step with no login: the Maintainer's password is created here and the session starts with it. */
function MaintainerPasswordForm() {
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [tried, setTried] = useState(false)
  const create = useCreateMaintainerPassword()
  const short = password.length < 8
  const mismatch = again.length > 0 && again !== password
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setTried(true)
        if (short || again !== password) return
        create.mutate(password)
      }}
    >
      <p className="text-sm text-fg-muted">{t.passwordHelp}</p>
      <Field label={t.password} required error={tried && short ? t.tooShort : undefined}>
        {(p) => (
          <Input
            {...p}
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
      </Field>
      <Field
        label={t.again}
        required
        error={mismatch || (tried && again !== password) ? t.mismatch : undefined}
      >
        {(p) => (
          <Input
            {...p}
            type="password"
            autoComplete="new-password"
            value={again}
            onChange={(e) => setAgain(e.target.value)}
          />
        )}
      </Field>
      {create.isError ? (
        <p role="alert" className="text-sm text-fail-text">
          {describeError(create.error)}
        </p>
      ) : null}
      <div>
        <Button type="submit" variant="primary" loading={create.isPending}>
          {t.create}
        </Button>
      </div>
    </form>
  )
}
