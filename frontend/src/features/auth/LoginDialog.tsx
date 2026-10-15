import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { login, useLoginDialog } from '@/api/auth'
import { useSession } from '@/api/session'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { text } from '@/texts'

/** The one login dialog. It opens from the lock button, from a protected link, or when the session ends; the page behind is kept. */
export function LoginDialog() {
  const { open, next, hide } = useLoginDialog()
  const expired = useSession((s) => s.expired)
  const navigate = useNavigate()
  const [role, setRole] = useState<'supervisor' | 'maintainer'>('supervisor')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(role, password)
      toast.success(text.login.welcome(text.roles[role]))
      const destination = next
      hide()
      if (destination) void navigate(destination)
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 429
          ? text.login.locked
          : e instanceof ApiError && e.status === 401
            ? text.login.wrong
            : e instanceof Error
              ? e.message
              : text.login.wrong,
      )
    } finally {
      setBusy(false)
      setPassword('')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && hide()}>
      <DialogContent
        title={text.login.title}
        description={expired ? text.login.expired : undefined}
      >
        <form onSubmit={submit} className="flex flex-col gap-4">
          <Field label={text.login.role}>
            {(p) => (
              <Select
                {...p}
                value={role}
                onValueChange={(v) => setRole(v as 'supervisor' | 'maintainer')}
                options={[
                  { value: 'supervisor', label: text.roles.supervisor },
                  { value: 'maintainer', label: text.roles.maintainer },
                ]}
              />
            )}
          </Field>
          <Field label={text.login.password} error={error || undefined}>
            {(p) => (
              <Input
                {...p}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </Field>
          <DialogFooter>
            <Button onClick={hide}>{text.login.cancel}</Button>
            <Button type="submit" variant="primary" loading={busy} disabled={!password}>
              {text.login.submit}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
