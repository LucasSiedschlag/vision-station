import { CheckCircle2, Download, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { downloadFile } from '@/api/download'
import { describeError } from '@/api/mutations'
import {
  useActivate,
  useBackups,
  useDiff,
  useDuplicate,
  useImport,
  useMakeBackup,
  type ImportOut,
} from '@/api/queries/jobs'
import { useSession } from '@/api/session'
import { Button } from '@/components/ui/button'
import { ConfirmDialog, Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { FileDrop } from '@/components/ui/file-drop'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Input, Textarea } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatDateTime, formatSize } from '@/lib/datetime'
import { can } from '@/lib/permissions'
import { text } from '@/texts'

type Open = { open: boolean; onOpenChange: (open: boolean) => void }

/**
 * Activate a version: the server verifies it on its reference set first. If it fails, the report is shown and
 * the maintainer may still activate it with a written reason (audited).
 */
export function ActivateDialog({
  open,
  onOpenChange,
  id,
  name,
  version,
}: Open & { id: string; name: string; version: number }) {
  const role = useSession((s) => s.role)
  const activate = useActivate()
  const [problems, setProblems] = useState<string[] | null>(null)
  const [reason, setReason] = useState('')

  const close = (next: boolean) => {
    if (!next) {
      setProblems(null)
      setReason('')
      activate.reset()
    }
    onOpenChange(next)
  }
  const run = (overrideReason?: string) =>
    activate.mutate(
      { id, version, overrideReason },
      {
        onSuccess: (out) => {
          if (out.warnings.length > 0)
            toast.warning(`${text.jobs.activatedWithWarnings} ${out.warnings.join('; ')}`)
          else toast.success(text.jobs.activated(version, name))
          close(false)
        },
        onError: (error) => {
          if (error instanceof ApiError && error.code === 'verification_failed')
            setProblems(error.problems ?? [])
          else toast.error(describeError(error))
        },
      },
    )

  if (problems === null) {
    return (
      <ConfirmDialog
        open={open}
        onOpenChange={close}
        title={text.jobs.activateTitle(version, name)}
        description={text.jobs.activateBody}
        confirmLabel={text.jobs.activateConfirm}
        loading={activate.isPending}
        onConfirm={() => run()}
      />
    )
  }
  const mayOverride = can(role, 'overrideVerification')
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent title={text.jobs.activateTitle(version, name)}>
        <div role="alert" className="flex flex-col gap-2">
          <p className="font-medium text-fail-text">{text.jobs.verificationFailed}</p>
          <ul className="flex flex-col gap-1 text-sm">
            {problems.map((p) => (
              <li key={p} className="flex items-start gap-2">
                <XCircle aria-hidden className="mt-0.5 size-4 shrink-0 text-fail-text" />
                {p}
              </li>
            ))}
          </ul>
        </div>
        {mayOverride ? (
          <Field label={text.jobs.overrideReason} hint={text.jobs.overrideHint} required>
            {(props) => (
              <Textarea
                {...props}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
              />
            )}
          </Field>
        ) : null}
        <DialogFooter>
          <Button onClick={() => close(false)}>{text.ui.close}</Button>
          {mayOverride ? (
            <Button
              variant="danger"
              disabled={reason.trim().length === 0}
              loading={activate.isPending}
              onClick={() => run(reason.trim())}
            >
              {text.jobs.overrideConfirm}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function ImportDialog({ open, onOpenChange }: Open) {
  const importFile = useImport()
  const [done, setDone] = useState<ImportOut | null>(null)
  const close = (next: boolean) => {
    if (!next) {
      setDone(null)
      importFile.reset()
    }
    onOpenChange(next)
  }
  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent title={text.jobs.importTitle} description={text.jobs.importBody}>
        {done ? (
          <div role="status" className="flex flex-col gap-2">
            <p className="flex items-center gap-2 font-medium text-ok-text">
              <CheckCircle2 aria-hidden className="size-4" />
              {text.jobs.importDone}
            </p>
            <ul className="flex flex-col gap-1 font-mono text-sm">
              {done.imported.map((item) => (
                <li key={`${item.id}-${item.version}`}>
                  {item.id.slice(0, 8)} ·{' '}
                  {text.jobs.importItem(
                    item.version,
                    text.jobs.importStatus[item.status],
                    item.original_version,
                  )}
                </li>
              ))}
            </ul>
            {done.has_system_config ? (
              <p className="text-sm text-fg-muted">{text.jobs.importBackupNote}</p>
            ) : null}
            {done.active_was ? (
              <p className="text-sm text-fg-muted">
                {text.jobs.importActiveWas(done.active_was.version)}
              </p>
            ) : null}
          </div>
        ) : (
          <>
            <FileDrop
              accept=".vjob,.vbak"
              label={text.jobs.importDrop}
              onFiles={([file]) => file && importFile.mutate(file, { onSuccess: setDone })}
            />
            {importFile.isPending ? (
              <Skeleton className="h-6 w-full" aria-label={text.ui.importing} />
            ) : null}
            {importFile.isError ? (
              <p role="alert" className="text-sm text-fail-text">
                {describeError(importFile.error)}
              </p>
            ) : null}
          </>
        )}
        <DialogFooter>
          <Button onClick={() => close(false)}>{text.ui.close}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function BackupsDialog({ open, onOpenChange }: Open) {
  const backups = useBackups(open)
  const save = (name: string) =>
    downloadFile(`/api/backup/${encodeURIComponent(name)}`, name).catch((e: unknown) =>
      toast.error(describeError(e)),
    )
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={text.jobs.backupsTitle}
        description={
          backups.data?.folder ? text.jobs.backupsFolder(backups.data.folder) : undefined
        }
        className="w-wide"
      >
        {backups.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : backups.isError ? (
          <ErrorState
            message={describeError(backups.error)}
            onRetry={() => void backups.refetch()}
          />
        ) : backups.data.folder === null ? (
          <p className="text-sm text-fg-muted">{text.jobs.backupsNoFolder}</p>
        ) : backups.data.backups.length === 0 ? (
          <p className="text-sm text-fg-muted">{text.jobs.backupsNone}</p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>{text.ui.fileColumn}</TH>
                <TH>{text.ui.dateColumn}</TH>
                <TH className="text-right">Tamanho</TH>
                <TH>
                  <span className="sr-only">{text.jobs.download}</span>
                </TH>
              </TR>
            </THead>
            <TBody>
              {backups.data.backups.map((b) => (
                <TR key={b.name}>
                  <TD className="font-mono">{b.name}</TD>
                  <TD>{formatDateTime(b.created_at)}</TD>
                  <TD numeric>{formatSize(b.size)}</TD>
                  <TD className="text-right">
                    <Button
                      variant="ghost"
                      aria-label={text.jobs.downloadOf(b.name)}
                      onClick={() => void save(b.name)}
                    >
                      <Download aria-hidden className="size-4" />
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>{text.ui.close}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function useBackupNow() {
  const make = useMakeBackup()
  return {
    pending: make.isPending,
    run: () =>
      make.mutate(undefined, {
        onSuccess: (b) => toast.success(text.jobs.backupDone(b.name, formatSize(b.size))),
      }),
  }
}

export function DiffDialog({
  open,
  onOpenChange,
  id,
  version,
  versions,
}: Open & { id: string; version: number; versions: number[] }) {
  const others = versions.filter((v) => v !== version)
  const [against, setAgainst] = useState<number | null>(
    others.includes(version - 1) ? version - 1 : (others[0] ?? null),
  )
  const diff = useDiff(id, version, open ? against : null)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={text.jobs.diffTitle(version)} className="w-wide">
        <Field label={text.jobs.diffAgainst}>
          {(props) => (
            <Select
              {...props}
              value={against === null ? undefined : String(against)}
              onValueChange={(v) => setAgainst(Number(v))}
              options={others.map((v) => ({ value: String(v), label: text.jobs.version(v) }))}
            />
          )}
        </Field>
        {diff.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : diff.isError ? (
          <ErrorState message={describeError(diff.error)} />
        ) : diff.data.diff === '' ? (
          <p className="text-sm text-fg-muted">{text.jobs.diffSame}</p>
        ) : (
          <pre
            aria-label={text.ui.differences}
            className="max-h-[50vh] overflow-auto rounded-control bg-surface-2 p-3 font-mono text-xs"
          >
            {diff.data.diff.split('\n').map((line, i) => (
              <span
                key={i}
                className={
                  line.startsWith('+') && !line.startsWith('+++')
                    ? 'block text-ok-text'
                    : line.startsWith('-') && !line.startsWith('---')
                      ? 'block text-fail-text'
                      : 'block'
                }
              >
                {line || ' '}
              </span>
            ))}
          </pre>
        )}
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>{text.ui.close}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function DuplicateDialog({
  open,
  onOpenChange,
  id,
  name,
  version,
  onDone,
}: Open & { id: string; name: string; version: number; onDone?: (newId: string) => void }) {
  const duplicate = useDuplicate()
  const [newName, setNewName] = useState(text.jobs.copyOf(name))
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={text.jobs.duplicateTitle}
        description={text.jobs.duplicateBody(version)}
      >
        <Field label={text.jobs.duplicateName} required>
          {(props) => (
            <Input {...props} value={newName} onChange={(e) => setNewName(e.target.value)} />
          )}
        </Field>
        {duplicate.isError ? (
          <p role="alert" className="text-sm text-fail-text">
            {describeError(duplicate.error)}
          </p>
        ) : null}
        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>{text.ui.cancel}</Button>
          <Button
            variant="primary"
            disabled={newName.trim() === ''}
            loading={duplicate.isPending}
            onClick={() =>
              duplicate.mutate(
                { id, version, name: newName.trim() },
                {
                  onSuccess: (saved) => {
                    toast.success(text.jobs.duplicateDone(newName.trim()))
                    onOpenChange(false)
                    onDone?.(saved.id)
                  },
                },
              )
            }
          >
            {text.jobs.duplicate}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function exportVersion(id: string, name: string, version: number) {
  const safe = name.replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/^_+|_+$/g, '') || 'job'
  return downloadFile(
    `/api/jobs/${id}/versions/${version}/export`,
    `${safe}_v${version}.vjob`,
  ).catch((e: unknown) => toast.error(describeError(e)))
}
