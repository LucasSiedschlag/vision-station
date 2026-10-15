import { Download, FileDown } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { downloadFile, fetchBlob } from '@/api/download'
import {
  PAGE,
  useMarkIncorrect,
  useResults,
  type RecordOut,
  type ResultsFilter,
} from '@/api/queries/admin'
import { useJobs } from '@/api/queries/jobs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Sheet } from '@/components/ui/dialog'
import { Field } from '@/components/ui/field'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { Pagination } from '@/components/ui/pagination'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatDateTime } from '@/lib/datetime'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'

const t = text.results
type Period = keyof typeof t.periods
const tone = { PASS: 'ok', FAIL: 'fail', ERROR: 'warn' } as const

function since(period: Period): string | undefined {
  const now = new Date()
  if (period === 'all') return undefined
  const start = new Date(now)
  if (period === 'today') start.setHours(0, 0, 0, 0)
  else start.setDate(now.getDate() - (period === 'd7' ? 7 : 30))
  return start.toISOString()
}

/** Results (docs/frontend.md §7.4): filters live in the URL, so a view can be shared or reloaded. */
export function ResultsPage() {
  const [params, setParams] = useSearchParams()
  const period = (params.get('period') as Period | null) ?? 'today'
  const outcome = (params.get('outcome') as ResultsFilter['outcome'] | null) ?? undefined
  const jobId = params.get('job') ?? undefined
  const incorrect = params.get('incorrect') === '1'
  const offset = Number(params.get('offset') ?? 0)
  const filter: ResultsFilter = {
    since: since(period),
    job_id: jobId,
    outcome,
    incorrect_only: incorrect || undefined,
    offset,
  }
  const results = useResults(filter)
  const jobs = useJobs()
  const [open, setOpen] = useState<RecordOut | null>(null)

  const set = (key: string, value: string | null) =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
      if (key !== 'offset') next.delete('offset')
      return next
    })

  const exportCsv = () => {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(filter))
      if (v !== undefined && k !== 'offset') q.set(k, String(v))
    void downloadFile(`/api/results.csv?${q}`, 'resultados.csv').catch((e: unknown) =>
      toast.error(describeError(e)),
    )
  }

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <Button onClick={exportCsv}>
          <FileDown aria-hidden className="size-4" />
          {t.exportCsv}
        </Button>
      </div>
      <div role="search" aria-label="Filtros" className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t.period}</span>
          <SegmentedControl
            label={t.period}
            value={period}
            onValueChange={(v) => set('period', v)}
            options={Object.entries(t.periods).map(([value, label]) => ({ value, label }))}
          />
        </div>
        <Field label={t.job} className="min-w-56">
          {(props) => (
            <Select
              {...props}
              value={jobId ?? 'all'}
              onValueChange={(v) => set('job', v === 'all' ? null : v)}
              options={[
                { value: 'all', label: t.allJobs },
                ...(jobs.data?.jobs ?? []).map((j) => ({ value: j.id, label: j.name })),
              ]}
            />
          )}
        </Field>
        <Field label={t.outcome} className="min-w-40">
          {(props) => (
            <Select
              {...props}
              value={outcome ?? 'all'}
              onValueChange={(v) => set('outcome', v === 'all' ? null : v)}
              options={Object.entries(t.outcomes).map(([value, label]) => ({ value, label }))}
            />
          )}
        </Field>
        <Switch
          checked={incorrect}
          onCheckedChange={(c) => set('incorrect', c ? '1' : null)}
          label={t.incorrectOnly}
        />
      </div>

      {results.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : results.isError ? (
        <Card>
          <ErrorState
            message={t.loadError}
            detail={describeError(results.error)}
            onRetry={() => void results.refetch()}
          />
        </Card>
      ) : results.data.results.length === 0 ? (
        <Card>
          <EmptyState title={t.empty} description={t.emptyBody} heading="h2" />
        </Card>
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>{t.when}</TH>
                <TH>{t.job}</TH>
                <TH>{t.outcome}</TH>
                <TH>{t.reason}</TH>
                <TH className="text-right">{t.duration}</TH>
              </TR>
            </THead>
            <TBody>
              {results.data.results.map((r) => (
                <TR key={r.id}>
                  <TD>
                    <button
                      type="button"
                      className="text-accent-text hover:underline"
                      aria-label={t.open(formatDateTime(r.at))}
                      onClick={() => setOpen(r)}
                    >
                      {formatDateTime(r.at)}
                    </button>
                  </TD>
                  <TD>{t.jobVersion(r.job_name, r.job_version)}</TD>
                  <TD>
                    <Badge tone={tone[r.outcome]}>{text.operator.outcome[r.outcome]}</Badge>
                    {r.correct_outcome ? (
                      <Badge tone="warn" className="ml-1">
                        {t.shouldBe(text.operator.outcome[r.correct_outcome])}
                      </Badge>
                    ) : null}
                  </TD>
                  <TD className="max-w-md truncate">{r.reason}</TD>
                  <TD numeric>{formatNumber(r.duration_ms, 0)} ms</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <Pagination
            offset={offset}
            page={PAGE}
            total={results.data.total}
            onOffset={(o) => set('offset', String(o))}
          />
        </>
      )}
      {open ? <ResultSheet record={open} onClose={() => setOpen(null)} /> : null}
    </main>
  )
}

function ResultSheet({ record, onClose }: { record: RecordOut; onClose: () => void }) {
  const [marked, setMarked] = useState(Boolean(record.overlay_path))
  const [image, setImage] = useState<{ url: string; key: string } | null>(null)
  const [missing, setMissing] = useState(false)
  const mark = useMarkIncorrect()
  const key = `${record.id}:${marked}`
  const hasImage = Boolean(record.image_path)

  useEffect(() => {
    let alive = true
    if (!hasImage) return
    fetchBlob(`/api/results/${record.id}/image${marked ? '?overlay=true' : ''}`).then(
      (blob) => alive && setImage({ url: URL.createObjectURL(blob), key }),
      () => alive && setMissing(true),
    )
    return () => {
      alive = false
    }
  }, [record.id, marked, hasImage, key])

  const correct = record.outcome === 'PASS' ? 'FAIL' : 'PASS'
  return (
    <Sheet
      open
      onOpenChange={(o) => !o && onClose()}
      title={t.detail}
      description={`${formatDateTime(record.at)} · ${t.jobVersion(record.job_name, record.job_version)}`}
    >
      <div className="flex flex-col gap-4">
        <p className="flex flex-wrap items-center gap-2">
          <Badge tone={tone[record.outcome]}>{text.operator.outcome[record.outcome]}</Badge>
          <span className="text-sm">{record.reason}</span>
        </p>
        {hasImage && !missing ? (
          <>
            {record.overlay_path ? (
              <SegmentedControl
                label={t.imageView}
                value={marked ? 'marked' : 'original'}
                onValueChange={(v) => setMarked(v === 'marked')}
                options={[
                  { value: 'original', label: t.imageOriginal },
                  { value: 'marked', label: t.imageMarked },
                ]}
              />
            ) : null}
            {image?.key === key ? (
              <img
                src={image.url}
                alt={`${t.detail} ${formatDateTime(record.at)}`}
                className="w-full rounded-card border border-line"
              />
            ) : (
              <Skeleton className="aspect-video w-full" />
            )}
            <Button
              variant="ghost"
              onClick={() =>
                void downloadFile(`/api/results/${record.id}/image`, `${record.id}.jpg`).catch(
                  (e: unknown) => toast.error(describeError(e)),
                )
              }
            >
              <Download aria-hidden className="size-4" />
              {t.downloadImage}
            </Button>
          </>
        ) : (
          <p className="text-sm text-fg-muted">{t.noImage}</p>
        )}
        {Object.keys(record.scores).length ? (
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold">{t.scores}</h3>
            <p className="font-mono text-sm tabular-nums">
              {Object.entries(record.scores)
                .map(([k, v]) => `${k}: ${formatNumber(v, 2)}`)
                .join(' · ')}
            </p>
          </div>
        ) : null}
        {Object.keys(record.timings).length ? (
          <div className="flex flex-col gap-1">
            <h3 className="text-sm font-semibold">{t.timings}</h3>
            <p className="font-mono text-xs tabular-nums text-fg-muted">
              {Object.entries(record.timings)
                .filter(([, v]) => typeof v === 'number')
                .map(([k, v]) => `${k}: ${formatNumber(v * 1000, 0)} ms`)
                .join(' · ')}
            </p>
          </div>
        ) : null}
        {record.correct_outcome ? (
          <p className="text-sm text-warn-text">
            {t.corrected(text.operator.outcome[record.correct_outcome], record.corrected_by ?? '')}
          </p>
        ) : record.outcome !== 'ERROR' && hasImage ? (
          <div className="flex flex-col gap-2">
            <Button
              loading={mark.isPending}
              onClick={() =>
                mark.mutate(
                  { id: record.id, correct },
                  {
                    onSuccess: () => {
                      toast.success(t.marked)
                      onClose()
                    },
                    onError: (e) => toast.error(describeError(e)),
                  },
                )
              }
            >
              {t.markIncorrect}: {t.shouldBe(text.operator.outcome[correct])}
            </Button>
            <p className="text-xs text-fg-muted">{t.markHint}</p>
          </div>
        ) : null}
      </div>
    </Sheet>
  )
}
