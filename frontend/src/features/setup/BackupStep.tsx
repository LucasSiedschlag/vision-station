import { CheckCircle2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { describeError } from '@/api/mutations'
import { systemChecks, useSaveSystem, useSystem } from '@/api/queries/admin'
import type { SetupStep } from '@/api/queries/setup'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Skeleton } from '@/components/ui/feedback'
import { Input } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { cn } from '@/lib/cn'
import { text } from '@/texts'

const t = text.setup
const settings = text.settings

type Check = { ok: boolean; message: string } | null

/** The backup folder and how often, tested before it is saved (docs/frontend.md §7.11). The rest of the backup settings stay in Configurações. */
export function BackupStep({ step }: { step: SetupStep }) {
  const system = useSystem()
  if (system.isPending) return <Skeleton className="h-40 w-full" />
  if (system.isError)
    return (
      <p role="alert" className="text-sm text-fail-text">
        {describeError(system.error)}
      </p>
    )
  const backup = system.data.config.backup
  // keyed by the saved folder, so what is on the screen starts again from what the server has after a save
  return (
    <BackupForm
      key={`${backup.folder}|${backup.every_hours}`}
      config={system.data.config}
      done={step.state === 'done'}
    />
  )
}

function BackupForm({
  config,
  done,
}: {
  config: NonNullable<ReturnType<typeof useSystem>['data']>['config']
  done: boolean
}) {
  const client = useQueryClient()
  const save = useSaveSystem()
  const [folder, setFolder] = useState(config.backup.folder ?? '')
  const [every, setEvery] = useState<number | null>(config.backup.every_hours ?? null)
  const [check, setCheck] = useState<Check>(null)
  const [testing, setTesting] = useState(false)

  const test = async () => {
    setTesting(true)
    try {
      const out = await systemChecks.folder(folder)
      setCheck({ ok: out.ok, message: out.message })
    } catch (error) {
      setCheck({ ok: false, message: describeError(error) })
    } finally {
      setTesting(false)
    }
  }
  const submit = () =>
    save.mutate(
      { ...config, backup: { ...config.backup, folder: folder || null, every_hours: every } },
      {
        onSuccess: () => {
          toast.success(t.backupSaved)
          void client.invalidateQueries({ queryKey: ['setup'] })
        },
        onError: (error) => toast.error(describeError(error)),
      },
    )

  return (
    <div className="flex flex-col gap-4">
      {done ? <p role="status">{t.backupDone(config.backup.folder ?? '')}</p> : null}
      <Field label={settings.backupFolder} hint={settings.backupFolderHint}>
        {(p) => (
          <Input
            {...p}
            value={folder}
            onChange={(e) => {
              setFolder(e.target.value)
              setCheck(null)
            }}
          />
        )}
      </Field>
      <Field label={settings.every} hint={settings.everyHint}>
        {(p) => (
          <NumberField
            {...p}
            value={every}
            onChange={setEvery}
            unit={settings.hours}
            min={1}
            decimals={0}
          />
        )}
      </Field>
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!folder} loading={testing} onClick={() => void test()}>
          {settings.testFolder}
        </Button>
        <Button
          variant="primary"
          disabled={!folder || !check?.ok}
          loading={save.isPending}
          onClick={submit}
        >
          {t.backupSave}
        </Button>
      </div>
      {!check?.ok && folder ? <p className="text-xs text-fg-muted">{t.backupTestFirst}</p> : null}
      {check ? (
        <p
          role="status"
          className={cn(
            'flex items-center gap-2 text-sm',
            check.ok ? 'text-ok-text' : 'text-fail-text',
          )}
        >
          {check.ok ? (
            <CheckCircle2 aria-hidden className="size-4" />
          ) : (
            <XCircle aria-hidden className="size-4" />
          )}
          {check.message}
        </p>
      ) : null}
    </div>
  )
}
