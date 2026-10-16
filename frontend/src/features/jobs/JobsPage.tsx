import { Archive, FileUp, MoreHorizontal, Plus, Save } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { describeError } from '@/api/mutations'
import { useJobs, type JobListItem } from '@/api/queries/jobs'
import { useSession } from '@/api/session'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatDateTime } from '@/lib/datetime'
import { can } from '@/lib/permissions'
import { text, authorName } from '@/texts'
import {
  BackupsDialog,
  DuplicateDialog,
  exportVersion,
  ImportDialog,
  useBackupNow,
} from './dialogs'

/** The list of jobs (docs/frontend.md §7.2): which is active, import, export, backups. */
export function JobsPage() {
  const jobs = useJobs()
  const role = useSession((s) => s.role)
  const navigate = useNavigate()
  const [importing, setImporting] = useState(false)
  const [backups, setBackups] = useState(false)
  const [duplicating, setDuplicating] = useState<JobListItem | null>(null)
  const backupNow = useBackupNow()
  const editor = can(role, 'editor')

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{text.jobs.title}</h1>
        <div className="flex flex-wrap gap-2">
          {editor ? (
            <Button variant="primary" onClick={() => void navigate('/jobs/new/edit')}>
              <Plus aria-hidden className="size-4" />
              {text.jobs.newJob}
            </Button>
          ) : null}
          <Button onClick={() => setImporting(true)}>
            <FileUp aria-hidden className="size-4" />
            {text.jobs.import}
          </Button>
          <Button loading={backupNow.pending} onClick={backupNow.run}>
            <Save aria-hidden className="size-4" />
            {text.jobs.backup}
          </Button>
          <Button variant="ghost" onClick={() => setBackups(true)}>
            <Archive aria-hidden className="size-4" />
            {text.jobs.backups}
          </Button>
        </div>
      </div>

      {jobs.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : jobs.isError ? (
        <Card>
          <ErrorState
            message={text.jobs.loadError}
            detail={describeError(jobs.error)}
            onRetry={() => void jobs.refetch()}
          />
        </Card>
      ) : jobs.data.jobs.length === 0 ? (
        <Card>
          <EmptyState title={text.jobs.empty} description={text.jobs.emptyBody} heading="h2" />
        </Card>
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>{text.jobs.name}</TH>
              <TH>{text.jobs.active}</TH>
              <TH className="text-right">{text.jobs.versions}</TH>
              <TH>{text.jobs.updated}</TH>
              <TH>{text.jobs.author}</TH>
              <TH>
                <span className="sr-only">{text.jobs.actions}</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {jobs.data.jobs.map((job) => {
              const active = jobs.data.active?.id === job.id ? jobs.data.active.version : null
              return (
                <TR key={job.id}>
                  <TD>
                    <Link
                      to={`/jobs/${job.id}`}
                      className="font-medium text-accent-text hover:underline"
                    >
                      {job.name}
                    </Link>
                  </TD>
                  <TD>
                    {active !== null ? (
                      <Badge tone="ok">{text.jobs.activeVersion(active)}</Badge>
                    ) : null}
                  </TD>
                  <TD numeric>{job.versions.length}</TD>
                  <TD>{formatDateTime(job.updated_at)}</TD>
                  <TD>{authorName(job.author)}</TD>
                  <TD className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" aria-label={text.jobs.actionsOf(job.name)}>
                          <MoreHorizontal aria-hidden className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem onSelect={() => void navigate(`/jobs/${job.id}`)}>
                          {text.jobs.open}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() => void exportVersion(job.id, job.name, job.latest)}
                        >
                          {text.jobs.export}
                        </DropdownMenuItem>
                        {editor ? (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onSelect={() => void navigate(`/jobs/${job.id}/edit`)}
                            >
                              {text.jobs.edit}
                            </DropdownMenuItem>
                            <DropdownMenuItem onSelect={() => setDuplicating(job)}>
                              {text.jobs.duplicate}
                            </DropdownMenuItem>
                          </>
                        ) : null}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TD>
                </TR>
              )
            })}
          </TBody>
        </Table>
      )}

      <ImportDialog open={importing} onOpenChange={setImporting} />
      <BackupsDialog open={backups} onOpenChange={setBackups} />
      {duplicating ? (
        <DuplicateDialog
          open
          onOpenChange={(o) => !o && setDuplicating(null)}
          id={duplicating.id}
          name={duplicating.name}
          version={duplicating.latest}
          onDone={(id) => void navigate(`/jobs/${id}`)}
        />
      ) : null}
    </main>
  )
}
