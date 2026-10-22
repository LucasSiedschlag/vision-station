import { useState } from 'react'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { describeError } from '@/api/mutations'
import { useSaveSystem, useSystem } from '@/api/queries/admin'
import type { SetupStep } from '@/api/queries/setup'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { FolderField } from '@/components/domain/FolderField'
import { Skeleton } from '@/components/ui/feedback'
import { NumberField } from '@/components/ui/number-field'
import { text } from '@/texts'

const t = text.setup
const settings = text.settings

/**
 * The backup folder and how often (docs/frontend.md §7.11). The folder starts as the data folder of the program; the
 * person may choose another with the PC's own chooser, and never has to type or test a path: the server refuses a
 * folder it cannot write to when it is saved. The rest of the backup settings stay in Configurações.
 */
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
      fallback={system.data.default_backup_folder}
      done={step.state === 'done'}
    />
  )
}

function BackupForm({
  config,
  fallback,
  done,
}: {
  config: NonNullable<ReturnType<typeof useSystem>['data']>['config']
  fallback: string
  done: boolean
}) {
  const client = useQueryClient()
  const save = useSaveSystem()
  const [folder, setFolder] = useState(config.backup.folder ?? fallback)
  const [every, setEvery] = useState<number | null>(config.backup.every_hours ?? null)
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
      <FolderField
        label={settings.backupFolder}
        hint={t.backupHelp}
        value={folder}
        onChange={setFolder}
      />
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
        <Button variant="primary" disabled={!folder} loading={save.isPending} onClick={submit}>
          {t.backupSave}
        </Button>
      </div>
    </div>
  )
}
