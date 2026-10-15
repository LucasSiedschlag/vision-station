import { FolderDown } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { useDataset, useExportDataset, useSetCollection } from '@/api/queries/admin'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { text } from '@/texts'

const t = text.dataset

/** Collection mode per job and the export of training images (docs/frontend.md §7.5). */
export function DatasetPage() {
  const dataset = useDataset()
  const collect = useSetCollection()
  const exportDataset = useExportDataset()
  const [last, setLast] = useState('')
  const run = (jobId: string | null) =>
    exportDataset.mutate(jobId, {
      onSuccess: (out) => {
        setLast(t.exported(out.dataset_id, out.count, out.folder))
        toast.success(t.exported(out.dataset_id, out.count, out.folder))
      },
      onError: (e) => toast.error(describeError(e)),
    })
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <Button
          loading={exportDataset.isPending && exportDataset.variables === null}
          onClick={() => run(null)}
        >
          <FolderDown aria-hidden className="size-4" />
          {t.exportAll}
        </Button>
      </div>
      <p className="text-sm text-fg-muted">{t.intro}</p>
      {last ? (
        <p role="status" className="font-mono text-sm">
          {last}
        </p>
      ) : null}
      {dataset.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : dataset.isError ? (
        <Card>
          <ErrorState
            message={t.loadError}
            detail={describeError(dataset.error)}
            onRetry={() => void dataset.refetch()}
          />
        </Card>
      ) : dataset.data.jobs.length === 0 ? (
        <Card>
          <EmptyState title={t.empty} heading="h2" />
        </Card>
      ) : (
        <>
          <p className="text-sm">{t.total(dataset.data.total)}</p>
          <Table>
            <THead>
              <TR>
                <TH>{text.jobs.name}</TH>
                <TH>{t.collecting}</TH>
                <TH className="text-right">{t.images}</TH>
                <TH>
                  <span className="sr-only">{t.export}</span>
                </TH>
              </TR>
            </THead>
            <TBody>
              {dataset.data.jobs.map((job) => (
                <TR key={job.job_id}>
                  <TD>{job.name}</TD>
                  <TD>
                    <Switch
                      checked={job.collecting}
                      onCheckedChange={(enabled) =>
                        collect.mutate(
                          { jobId: job.job_id, enabled },
                          { onError: (e) => toast.error(describeError(e)) },
                        )
                      }
                      label={t.collectingOf(job.name)}
                      hint={job.collecting ? t.collectingHint : undefined}
                    />
                  </TD>
                  <TD numeric>{job.images}</TD>
                  <TD className="text-right">
                    <Button
                      variant="ghost"
                      disabled={job.images === 0}
                      aria-label={t.exportOf(job.name)}
                      onClick={() => run(job.job_id)}
                    >
                      <FolderDown aria-hidden className="size-4" />
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </>
      )}
    </main>
  )
}
