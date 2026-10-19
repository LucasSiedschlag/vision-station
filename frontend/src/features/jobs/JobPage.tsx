import {
  ArrowLeft,
  Copy,
  Download,
  GitCompare,
  Pencil,
  Power,
  SlidersHorizontal,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { describeError } from '@/api/mutations'
import { useJob, type VersionInfo } from '@/api/queries/jobs'
import { useSession } from '@/api/session'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { formatDateTime } from '@/lib/datetime'
import { can } from '@/lib/permissions'
import { text, authorName } from '@/texts'
import { ActivateDialog, DiffDialog, DuplicateDialog, exportVersion } from './dialogs'

type Action = { kind: 'activate' | 'diff' | 'duplicate'; version: number } | null

/** One job: its versions as a timeline, newest first, with what can be done with each. */
export function JobPage() {
  const { id = '' } = useParams()
  const job = useJob(id)
  const role = useSession((s) => s.role)
  const navigate = useNavigate()
  const [action, setAction] = useState<Action>(null)
  const editor = can(role, 'editor')
  const close = (open: boolean) => !open && setAction(null)

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <Link
        to="/jobs"
        className="inline-flex items-center gap-2 text-sm text-accent-text hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        {text.jobs.back}
      </Link>
      {job.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : job.isError ? (
        <Card>
          <ErrorState message={describeError(job.error)} onRetry={() => void job.refetch()} />
        </Card>
      ) : (
        <>
          <div className="flex flex-col gap-1">
            <h1 className="text-xl font-semibold">{job.data.name}</h1>
            {job.data.description ? (
              <p className="text-sm text-fg-muted">{job.data.description}</p>
            ) : null}
          </div>
          <ol aria-label={text.jobs.versions} className="flex flex-col gap-3">
            {job.data.versions.map((v: VersionInfo) => (
              <li key={v.version}>
                <Card>
                  <CardContent className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-col gap-1">
                      <p className="flex items-center gap-2 font-medium">
                        <span className="font-mono tabular-nums">
                          {text.jobs.version(v.version)}
                        </span>
                        {v.active ? <Badge tone="ok">{text.jobs.active}</Badge> : null}
                        {v.tuned ? <Badge tone="neutral">{text.editor.tune.tuned}</Badge> : null}
                      </p>
                      <p className="text-sm text-fg-muted">
                        {formatDateTime(v.created_at)} · {authorName(v.author)}
                        {v.parent_version ? ` · ${text.jobs.parent(v.parent_version)}` : ''}
                      </p>
                      <p className="text-sm">
                        {v.notes || <span className="text-fg-muted">{text.jobs.noNotes}</span>}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant={v.active ? 'secondary' : 'primary'}
                        disabled={v.active}
                        onClick={() => setAction({ kind: 'activate', version: v.version })}
                      >
                        <Power aria-hidden className="size-4" />
                        {text.jobs.activate}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => void exportVersion(id, job.data.name, v.version)}
                      >
                        <Download aria-hidden className="size-4" />
                        {text.jobs.export}
                      </Button>
                      {v.version === job.data.versions[0]?.version ? (
                        <Button variant="ghost" onClick={() => void navigate(`/jobs/${id}/tune`)}>
                          <SlidersHorizontal aria-hidden className="size-4" />
                          {text.editor.tune.open}
                        </Button>
                      ) : null}
                      {job.data.versions.length > 1 ? (
                        <Button
                          variant="ghost"
                          onClick={() => setAction({ kind: 'diff', version: v.version })}
                        >
                          <GitCompare aria-hidden className="size-4" />
                          {text.jobs.compare}
                        </Button>
                      ) : null}
                      {editor ? (
                        <>
                          <Button
                            variant="ghost"
                            onClick={() => void navigate(`/jobs/${id}/edit?from=${v.version}`)}
                          >
                            <Pencil aria-hidden className="size-4" />
                            {text.jobs.openInEditor}
                          </Button>
                          <Button
                            variant="ghost"
                            onClick={() => setAction({ kind: 'duplicate', version: v.version })}
                          >
                            <Copy aria-hidden className="size-4" />
                            {text.jobs.duplicate}
                          </Button>
                        </>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ol>
          {action?.kind === 'activate' ? (
            <ActivateDialog
              open
              onOpenChange={close}
              id={id}
              name={job.data.name}
              version={action.version}
            />
          ) : null}
          {action?.kind === 'diff' ? (
            <DiffDialog
              open
              onOpenChange={close}
              id={id}
              version={action.version}
              versions={job.data.versions.map((v) => v.version)}
            />
          ) : null}
          {action?.kind === 'duplicate' ? (
            <DuplicateDialog
              open
              onOpenChange={close}
              id={id}
              name={job.data.name}
              version={action.version}
              onDone={(newId) => void navigate(`/jobs/${newId}`)}
            />
          ) : null}
        </>
      )}
    </main>
  )
}
