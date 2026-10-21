import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { text } from '@/texts'

const t = text.setup

/** A new password asked twice, with the same rule the server has (at least 8 characters). Nothing is sent if it fails. */
export function PasswordForm({
  label,
  help,
  submitLabel,
  pending,
  error,
  onSubmit,
}: {
  label: string
  help: string
  submitLabel: string
  pending: boolean
  error: string | null
  onSubmit: (password: string) => void
}) {
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [tried, setTried] = useState(false)
  const short = password.length < 8
  const mismatch = again.length > 0 && again !== password
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault()
        setTried(true)
        if (short || again !== password) return
        onSubmit(password)
      }}
    >
      <p className="text-sm text-fg-muted">{help}</p>
      <Field label={label} required error={tried && short ? t.tooShort : undefined}>
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
      {error ? (
        <p role="alert" className="text-sm text-fail-text">
          {error}
        </p>
      ) : null}
      <div>
        <Button type="submit" variant="primary" loading={pending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
