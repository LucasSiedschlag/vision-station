import { CheckCircle2, CircleDashed, TriangleAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useLoginDialog } from '@/api/auth'
import { useLive } from '@/api/live'
import { useMarkWrong, useTrigger } from '@/api/mutations'
import { useSession } from '@/api/session'
import { LiveCanvas } from '@/components/domain/LiveCanvas'
import { StatusStrip } from '@/components/domain/StatusStrip'
import { VerdictPanel } from '@/components/domain/VerdictPanel'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Tooltip } from '@/components/ui/tooltip'
import { useHideCursor } from '@/lib/cursor'
import { text } from '@/texts'
import {
  canMarkWrong,
  canTrigger,
  clockTime,
  connectionOf,
  percent,
  verdictOf,
  type Connection,
} from './view'

const outcomeIcon = { PASS: CheckCircle2, FAIL: XCircle, ERROR: TriangleAlert } as const
const outcomeColour = {
  PASS: 'text-ok-text',
  FAIL: 'text-fail-text',
  ERROR: 'text-warn-text',
} as const

function RecentResults({
  results,
}: {
  results: { outcome: 'PASS' | 'FAIL' | 'ERROR'; reason: string; at: string }[]
}) {
  const slots = Array.from({ length: 10 }, (_, i) => results[results.length - 10 + i])
  return (
    <div>
      <p className="mb-1 text-sm text-fg-muted">{text.operator.recent}</p>
      <ul className="flex gap-1" aria-label={text.operator.recent}>
        {slots.map((r, i) => {
          if (!r)
            return (
              <li key={i} className="grid size-9 place-items-center text-fg-muted">
                <CircleDashed aria-hidden className="size-5 opacity-40" />
              </li>
            )
          const Icon = outcomeIcon[r.outcome]
          const label = `${text.operator.outcome[r.outcome]}${clockTime(r.at) ? ` às ${clockTime(r.at)}` : ''}${r.reason ? `: ${r.reason}` : ''}`
          return (
            <li key={i}>
              <Tooltip content={label}>
                <button
                  type="button"
                  aria-label={label}
                  className="grid size-9 min-w-control place-items-center rounded-control hover:bg-surface-3"
                >
                  <Icon aria-hidden className={`size-6 ${outcomeColour[r.outcome]}`} />
                </button>
              </Tooltip>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Counters({
  counters,
}: {
  counters: { PASS: number; FAIL: number; ERROR: number; total: number }
}) {
  const cell = (label: string, value: number, extra?: string) => (
    <div className="flex flex-col items-center rounded-card border border-line bg-surface-1 px-2 py-2">
      <span className="font-mono text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-fg-muted">{label}</span>
      {extra ? <span className="font-mono text-xs text-fg-muted tabular-nums">{extra}</span> : null}
    </div>
  )
  const t = counters.total
  return (
    <div>
      <p className="mb-1 text-sm text-fg-muted">{text.operator.today}</p>
      <div className="grid grid-cols-4 gap-2">
        {cell(text.operator.total, t)}
        {cell(text.operator.pass, counters.PASS, `${percent(counters.PASS, t)}%`)}
        {cell(text.operator.fail, counters.FAIL, `${percent(counters.FAIL, t)}%`)}
        {cell(text.operator.error, counters.ERROR, `${percent(counters.ERROR, t)}%`)}
      </div>
    </div>
  )
}

function WrongResultDialog({
  open,
  onOpenChange,
  said,
  recordId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  said: string
  recordId: string
}) {
  const mark = useMarkWrong()
  const send = (correct: 'PASS' | 'FAIL') =>
    mark.mutate(
      { recordId, correct },
      {
        onSuccess: () => {
          toast.success(text.operator.wrongDone)
          onOpenChange(false)
        },
      },
    )
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={text.operator.wrongTitle} description={text.operator.wrongBody(said)}>
        <DialogFooter>
          <Button
            variant="primary"
            loading={mark.isPending}
            onClick={() => send('PASS')}
            className="min-h-14 px-6 text-lg"
          >
            {text.operator.wasOk}
          </Button>
          <Button
            variant="danger"
            loading={mark.isPending}
            onClick={() => send('FAIL')}
            className="min-h-14 px-6 text-lg"
          >
            {text.operator.wasNotOk}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/**
 * The operator screen (docs/frontend.md §7.1): the verdict is the figure; everything else is quiet. It always uses kiosk
 * density, and the cursor hides itself after a few seconds without movement.
 */
export function OperatorPage() {
  const status = useLive((s) => s.status)
  const frame = useLive((s) => s.frame)
  const connected = useLive((s) => s.connected)
  const connecting = useLive((s) => s.connecting)
  const role = useSession((s) => s.role)
  const showLogin = useLoginDialog((s) => s.show)
  const trigger = useTrigger()
  const [asking, setAsking] = useState(false)
  // without a login the screen stands alone (kiosk): its own header and footer, a hidden cursor, no selection or context menu
  const bare = role === 'operator'
  const hidden = useHideCursor(5000, bare)

  const connection: Connection = connectionOf(connected, connecting)
  const verdict = verdictOf(status, connection)
  const markable = canMarkWrong(status, connection)
  const said = status?.last_result
    ? { PASS: 'APROVADO', FAIL: 'REPROVADO', ERROR: 'ERRO' }[status.last_result.outcome]
    : ''

  return (
    <div
      data-density="kiosk"
      className={`flex size-full min-h-0 flex-col bg-surface-0 ${bare ? 'select-none' : ''} ${hidden ? 'cursor-none' : ''}`}
      onContextMenu={bare ? (e) => e.preventDefault() : undefined}
    >
      {bare ? (
        <header className="flex items-center justify-between gap-4 px-6 py-3">
          <h1 className="min-w-0 truncate text-xl font-semibold">
            {status?.job.name || text.shell.noJob}
            {status?.job.name ? (
              <span className="ml-2 font-normal text-fg-muted">v{status.job.version}</span>
            ) : null}
          </h1>
          {role === 'operator' ? (
            <Button variant="ghost" onClick={() => showLogin()}>
              {text.login.open}
            </Button>
          ) : null}
        </header>
      ) : (
        <h1 className="sr-only">{text.nav.station}</h1>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 px-6 pb-4 lg:grid-operator">
        <div className="min-h-64">
          <LiveCanvas frame={connection === 'connected' ? frame : null} />
        </div>
        <aside className="flex min-h-0 flex-col gap-4">
          <div className="min-h-64 flex-1">
            <VerdictPanel verdict={verdict} />
          </div>
          <RecentResults results={status?.recent ?? []} />
          {status ? <Counters counters={status.counters} /> : null}
          <div className="flex flex-wrap gap-2">
            <Button
              className="flex-1"
              disabled={!canTrigger(status, connection)}
              loading={trigger.isPending}
              onClick={() => trigger.mutate()}
            >
              {text.operator.trigger}
            </Button>
            {markable ? (
              <Button variant="ghost" onClick={() => setAsking(true)}>
                {text.operator.wrong}
              </Button>
            ) : null}
          </div>
        </aside>
      </main>

      {bare ? (
        <footer className="border-t border-line px-6 py-2">
          <StatusStrip status={status} connection={connection} />
        </footer>
      ) : null}

      {markable && status?.last_record_id ? (
        <WrongResultDialog
          open={asking}
          onOpenChange={setAsking}
          said={said}
          recordId={status.last_record_id}
        />
      ) : null}
    </div>
  )
}
