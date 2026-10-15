import { KeyRound, LogOut } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { useRevokeSessions, useSetPassword, useUsers } from '@/api/queries/admin'
import { useSession } from '@/api/session'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog, Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Input } from '@/components/ui/input'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatDateTime } from '@/lib/datetime'
import { text } from '@/texts'

const t = text.access
type Protected = 'supervisor' | 'maintainer'

/** Passwords of the two protected roles (docs/frontend.md §7.7). A supervisor changes only their own. */
export function AccessPage() {
  const users = useUsers()
  const role = useSession((s) => s.role)
  const [editing, setEditing] = useState<{ role: Protected; has: boolean } | null>(null)
  const [revoking, setRevoking] = useState(false)
  const revoke = useRevokeSessions()
  const maintainer = role === 'maintainer'
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        {maintainer ? (
          <Button variant="danger" onClick={() => setRevoking(true)}>
            <LogOut aria-hidden className="size-4" />
            {t.revoke}
          </Button>
        ) : null}
      </div>
      <p className="text-sm text-fg-muted">{t.intro}</p>
      {users.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : users.isError ? (
        <Card>
          <ErrorState message={describeError(users.error)} onRetry={() => void users.refetch()} />
        </Card>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>{t.role}</TH>
              <TH>{t.password}</TH>
              <TH>{t.changedAt}</TH>
              <TH>
                <span className="sr-only">{text.jobs.actions}</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {users.data.users.map((u) => {
              const name = text.roles[u.role]
              const mayChange = maintainer || u.role === role
              return (
                <TR key={u.role}>
                  <TD>{name}</TD>
                  <TD>
                    {u.has_password ? (
                      <Badge tone="ok">{t.set}</Badge>
                    ) : (
                      <Badge tone="warn">{t.notSet}</Badge>
                    )}
                  </TD>
                  <TD>{formatDateTime(u.changed_at)}</TD>
                  <TD className="text-right">
                    {mayChange ? (
                      <Button
                        variant="ghost"
                        onClick={() => setEditing({ role: u.role, has: u.has_password })}
                      >
                        <KeyRound aria-hidden className="size-4" />
                        {u.has_password ? t.change(name) : t.define(name)}
                      </Button>
                    ) : null}
                  </TD>
                </TR>
              )
            })}
          </TBody>
        </Table>
      )}
      {editing ? (
        <PasswordDialog
          target={editing.role}
          needsCurrent={!maintainer}
          onClose={() => setEditing(null)}
        />
      ) : null}
      <ConfirmDialog
        open={revoking}
        onOpenChange={setRevoking}
        title={t.revokeTitle}
        description={t.revokeBody}
        confirmLabel={t.revoke}
        tone="danger"
        loading={revoke.isPending}
        onConfirm={() =>
          revoke.mutate(undefined, {
            onSuccess: (out) => {
              toast.success(t.revoked(out.revoked))
              setRevoking(false)
              useSession.getState().expire()
            },
            onError: (e) => toast.error(describeError(e)),
          })
        }
      />
    </main>
  )
}

function PasswordDialog({
  target,
  needsCurrent,
  onClose,
}: {
  target: Protected
  needsCurrent: boolean
  onClose: () => void
}) {
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [current, setCurrent] = useState('')
  const [tried, setTried] = useState(false)
  const setPasswordCall = useSetPassword()
  const name = text.roles[target]
  const short = password.length > 0 && password.length < 8
  const mismatch = again.length > 0 && again !== password
  const ok = password.length >= 8 && again === password && (!needsCurrent || current.length > 0)
  const ownSession = useSession((s) => s.role) === target
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={t.change(name)} description={t.rule}>
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault()
            setTried(true)
            if (!ok) return
            setPasswordCall.mutate(
              { role: target, password, current: needsCurrent ? current : undefined },
              {
                onSuccess: () => {
                  toast.success(t.done(name))
                  onClose()
                  if (ownSession) useSession.getState().expire() // a new password ends this session too
                },
              },
            )
          }}
        >
          {needsCurrent ? (
            <Field label={t.current} required>
              {(p) => (
                <Input
                  {...p}
                  type="password"
                  autoComplete="current-password"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                />
              )}
            </Field>
          ) : null}
          <Field
            label={t.newPassword}
            required
            error={short || (tried && password.length < 8) ? t.tooShort : undefined}
          >
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
          <Field label={t.again} required error={mismatch ? t.mismatch : undefined}>
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
          {setPasswordCall.isError ? (
            <p role="alert" className="text-sm text-fail-text">
              {describeError(setPasswordCall.error)}
            </p>
          ) : null}
          <DialogFooter>
            <Button onClick={onClose}>Cancelar</Button>
            <Button type="submit" variant="primary" loading={setPasswordCall.isPending}>
              {t.change(name).split(' ')[0]}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
