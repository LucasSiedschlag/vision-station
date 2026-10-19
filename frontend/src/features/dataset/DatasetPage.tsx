import { FolderDown, Images } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { fetchBlob } from '@/api/download'
import {
  IMAGES_PAGE,
  useDataset,
  useDatasetImages,
  useExportDataset,
  useSetCollection,
  type DatasetImage,
} from '@/api/queries/admin'
import { Badge } from '@/components/ui/badge'
import { Pagination } from '@/components/ui/pagination'
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
  const [viewing, setViewing] = useState<{ id: string; name: string } | null>(null)
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
                  <TD className="whitespace-nowrap text-right">
                    <Button
                      variant="ghost"
                      disabled={job.images === 0}
                      aria-pressed={viewing?.id === job.job_id}
                      onClick={() =>
                        setViewing(
                          viewing?.id === job.job_id ? null : { id: job.job_id, name: job.name },
                        )
                      }
                    >
                      <Images aria-hidden className="size-4" />
                      {viewing?.id === job.job_id ? t.hideImages : t.viewImages}
                    </Button>
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
          {viewing ? <ImageGrid key={viewing.id} jobId={viewing.id} name={viewing.name} /> : null}
        </>
      )}
    </main>
  )
}

/** The images of one job, a page at a time, with what each one is: collected, or corrected with the right label. */
function ImageGrid({ jobId, name }: { jobId: string; name: string }) {
  const [offset, setOffset] = useState(0)
  const images = useDatasetImages(jobId, offset)
  return (
    <section aria-label={t.imagesOf(name)} className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">{t.imagesOf(name)}</h2>
      {images.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : images.isError ? (
        <ErrorState
          message={t.loadError}
          detail={describeError(images.error)}
          onRetry={() => void images.refetch()}
        />
      ) : images.data.images.length === 0 ? (
        <p className="text-sm text-fg-muted">{t.imagesEmpty}</p>
      ) : (
        <>
          <ul className="grid-swatches grid gap-3">
            {images.data.images.map((image) => (
              <li key={image.id}>
                <Tile jobId={jobId} image={image} />
              </li>
            ))}
          </ul>
          <Pagination
            offset={offset}
            page={IMAGES_PAGE}
            total={images.data.total}
            onOffset={setOffset}
          />
        </>
      )}
    </section>
  )
}

/** What the tile says about the image. */
function describe(image: DatasetImage): string {
  return image.source === 'corrected' && image.label
    ? t.corrected(text.operator.outcome[image.label])
    : t.collected
}

/**
 * One thumbnail. The picture is fetched with the login (an `<img>` cannot send it) and only once the tile comes near
 * the screen, so a page of 48 does not ask for 48 pictures at once.
 */
function Tile({ jobId, image }: { jobId: string; image: DatasetImage }) {
  const box = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(typeof IntersectionObserver === 'undefined')
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    const el = box.current
    if (near || !el) return
    const watcher = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setNear(true),
      { rootMargin: '200px' },
    )
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [near])
  useEffect(() => {
    if (!near) return
    let alive = true
    let made: string | null = null
    fetchBlob(`/api/dataset/${jobId}/images/${image.id}.jpg?width=320`).then(
      (blob) => {
        if (!alive) return
        made = URL.createObjectURL(blob)
        setUrl(made)
      },
      () => {},
    )
    return () => {
      alive = false
      if (made) URL.revokeObjectURL(made)
    }
  }, [near, jobId, image.id])
  const what = describe(image)
  return (
    <figure className="flex flex-col gap-1">
      <div
        ref={box}
        className="aspect-video overflow-hidden rounded-control border border-line bg-surface-2"
      >
        {url ? (
          <img src={url} alt={t.imageAlt(image.id, what)} className="size-full object-cover" />
        ) : null}
      </div>
      <figcaption className="flex flex-wrap items-center gap-1 text-xs">
        <Badge tone={image.source === 'corrected' ? 'warn' : 'neutral'}>{what}</Badge>
        {image.result ? (
          <span className="text-fg-muted">
            {text.operator.outcome[image.result as 'PASS' | 'FAIL' | 'ERROR']}
          </span>
        ) : null}
      </figcaption>
    </figure>
  )
}
