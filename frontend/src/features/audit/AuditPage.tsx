import { FileDown } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'
import { downloadFile } from '@/api/download'
import { describeError } from '@/api/mutations'
import { PAGE, useAudit, type AuditEvent } from '@/api/queries/admin'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { formatDateTime } from '@/lib/datetime'
import { text } from '@/texts'

const t = text.audit

/** One line of details: the fields of an event as "name: value", in the order they came. */
function details(event: AuditEvent): string {
  return Object.entries(event.data)
    .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    .join(' · ')
}

/** The audit log (docs/frontend.md §7.8): append-only, newest first. */
export function AuditPage() {
  const [params, setParams] = useSearchParams()
  const kind = params.get('kind') ?? undefined
  const offset = Number(params.get('offset') ?? 0)
  const audit = useAudit({ kind, offset })
  const set = (key: string, value: string | null) =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      if (value) next.set(key, value)
      else next.delete(key)
      if (key !== 'offset') next.delete('offset')
      return next
    })
  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <Button
          onClick={() =>
            void downloadFile(
              `/api/audit.csv${kind ? `?kind=${kind}` : ''}`,
              'auditoria.csv',
            ).catch((e: unknown) => toast.error(describeError(e)))
          }
        >
          <FileDown aria-hidden className="size-4" />
          {t.exportCsv}
        </Button>
      </div>
      <p className="text-sm text-fg-muted">{t.intro}</p>
      <Field label={t.kind} className="max-w-sm">
        {(props) => (
          <Select
            {...props}
            value={kind ?? 'all'}
            onValueChange={(v) => set('kind', v === 'all' ? null : v)}
            options={[
              { value: 'all', label: t.allKinds },
              ...Object.entries(t.kinds).map(([value, label]) => ({ value, label })),
            ]}
          />
        )}
      </Field>
      {audit.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : audit.isError ? (
        <Card>
          <ErrorState
            message={t.loadError}
            detail={describeError(audit.error)}
            onRetry={() => void audit.refetch()}
          />
        </Card>
      ) : audit.data.events.length === 0 ? (
        <Card>
          <EmptyState title={t.empty} heading="h2" />
        </Card>
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>{t.when}</TH>
                <TH>{t.kind}</TH>
                <TH>{t.details}</TH>
              </TR>
            </THead>
            <TBody>
              {audit.data.events.map((e, i) => (
                <TR key={`${e.at}-${i}`}>
                  <TD className="whitespace-nowrap">{formatDateTime(e.at)}</TD>
                  <TD>{t.kinds[e.kind] ?? e.kind}</TD>
                  <TD className="break-all font-mono text-xs">{details(e)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
          <Pagination
            offset={offset}
            page={PAGE}
            total={audit.data.total}
            onOffset={(o) => set('offset', String(o))}
          />
        </>
      )}
    </main>
  )
}
