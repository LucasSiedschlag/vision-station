import { CheckCircle2, CircleDashed, TriangleAlert, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchBlob } from '@/api/download'
import { toast } from 'sonner'
import { useLoginDialog } from '@/api/auth'
import { useLive, type ResultOut, type StateOut } from '@/api/live'
import { useMarkWrong, useStationCommand, useTrigger } from '@/api/mutations'
import { can } from '@/lib/permissions'
import { useSession } from '@/api/session'
import { LiveCanvas, type Marking } from '@/components/domain/LiveCanvas'
import { StatusStrip } from '@/components/domain/StatusStrip'
import { VerdictPanel } from '@/components/domain/VerdictPanel'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogFooter } from '@/components/ui/dialog'
import { Tooltip } from '@/components/ui/tooltip'
import { useHideCursor } from '@/lib/cursor'
import { SetupNotice } from '@/features/setup/SetupNotice'
import { text } from '@/texts'
import {
  canMarkWrong,
  canTrigger,
  clockTime,
  connectionOf,
  markingsOn,
  memberOfPassedGroup,
  percent,
  toolRows,
  verdictOf,
  type Connection,
} from './view'

/** How long a result looked at again stays on the image (docs/frontend.md §7.1). */
const FREEZE_MS = 10_000

const outcomeIcon = { PASS: CheckCircle2, FAIL: XCircle, ERROR: TriangleAlert } as const
const outcomeColour = {
  PASS: 'text-ok-text',
  FAIL: 'text-fail-text',
  ERROR: 'text-warn-text',
} as const

type Recent = StateOut['recent'][number]

/** A result's picture, small; the icon of its outcome stays on it, since the colour is never the only signal. */
function Thumb({ result, label }: { result: Recent; label: string }) {
  const [broken, setBroken] = useState(false)
  const Icon = outcomeIcon[result.outcome]
  return (
    <span className="relative block h-12 w-full overflow-hidden rounded-control">
      {result.record_id && !broken ? (
        <img
          src={`/api/results/${result.record_id}/thumb`}
          alt=""
          draggable={false}
          onError={() => setBroken(true)}
          className="size-full object-cover"
        />
      ) : (
        <span aria-hidden className="block size-full bg-surface-2" />
      )}
      <span
        aria-hidden
        className="absolute inset-0 grid place-items-center bg-surface-1/60"
        title={label}
      >
        <Icon className={`size-7 ${outcomeColour[result.outcome]}`} />
      </span>
    </span>
  )
}

function RecentResults({
  results,
  frozen,
  onPick,
}: {
  results: Recent[]
  frozen: string | null
  onPick: (result: Recent) => void
}) {
  const slots = Array.from({ length: 10 }, (_, i) => results[results.length - 10 + i])
  return (
    <div>
      <p className="mb-1 text-sm text-fg-muted">{text.operator.recent}</p>
      <ul className="grid grid-cols-10 gap-1" aria-label={text.operator.recent}>
        {slots.map((r, i) => {
          if (!r)
            return (
              <li key={i} className="grid h-12 min-w-0 place-items-center text-fg-muted">
                <CircleDashed aria-hidden className="size-5 opacity-40" />
              </li>
            )
          const label = text.operator.resultAt(
            text.operator.outcome[r.outcome],
            clockTime(r.at),
            r.reason,
          )
          const pickable = !!r.record_id
          return (
            <li key={i} className="min-w-0">
              <Tooltip content={label}>
                <button
                  type="button"
                  aria-label={label}
                  aria-pressed={pickable ? frozen === r.record_id : undefined}
                  disabled={!pickable}
                  onClick={() => onPick(r)}
                  className={`w-full rounded-control border-2 hover:border-line-control ${frozen === r.record_id ? 'border-accent' : 'border-transparent'}`}
                >
                  <Thumb result={r} label={label} />
                </button>
              </Tooltip>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** The tools that decide the result, one line each with the value that decided it (docs/frontend.md §7.1). */
function ToolRows({ result }: { result: ResultOut }) {
  const { rows, more } = toolRows(result)
  if (rows.length === 0) return null
  return (
    <ul aria-label={text.operator.tools} className="flex flex-col gap-1 text-lg">
      {rows.map((row) => {
        const Icon = row.passed ? CheckCircle2 : XCircle
        return (
          <li key={row.id} className="flex items-center gap-2">
            <Icon
              aria-hidden
              className={`size-6 shrink-0 ${row.passed ? 'text-ok-text' : 'text-fail-text'}`}
            />
            <span className="sr-only">
              {row.passed ? text.operator.outcome.PASS : text.operator.outcome.FAIL}
            </span>
            <span className="min-w-0 flex-1 truncate">{row.id}</span>
            <span className="font-mono tabular-nums">{row.value}</span>
          </li>
        )
      })}
      {more > 0 ? <li className="text-fg-muted">{text.operator.moreTools(more)}</li> : null}
    </ul>
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
  const command = useStationCommand()
  const stationCommand = can(role, 'stationCommands')
    ? status?.state === 'Fault'
      ? 'retry'
      : status?.state === 'Paused'
        ? 'resume'
        : null
    : null
  const [asking, setAsking] = useState(false)
  const results = useLive((s) => s.results)
  // a past result looked at again: its picture and markings take the image for a while (docs/frontend.md §7.1)
  const [pick, setPick] = useState<{ recent: Recent; newest: string | null } | null>(null)
  const [chosen, setChosen] = useState<boolean | null>(null) // the operator's own choice for the markings
  // without a login the screen stands alone (kiosk): its own header and footer, a hidden cursor, no selection or context menu
  const bare = role === 'operator'
  const hidden = useHideCursor(5000, bare)

  const connection: Connection = connectionOf(connected, connecting)
  const verdict = verdictOf(status, connection)
  const live = connection === 'connected'
  const newest = status?.last_record_id ?? null
  // a new result, or a lost connection, ends it: what is on screen is never an old picture taken for the present
  const frozen = pick && pick.newest === newest && live ? pick.recent : null
  useEffect(() => {
    if (!pick) return
    const timer = setTimeout(() => setPick(null), FREEZE_MS)
    return () => clearTimeout(timer)
  }, [pick])
  const picture = useQuery({
    queryKey: ['result-picture', frozen?.record_id],
    enabled: !!frozen?.record_id,
    staleTime: Infinity,
    retry: false,
    queryFn: () => fetchBlob(`/api/results/${frozen!.record_id}/thumb?width=1280`),
  })
  // the result whose markings and lines are on screen: the one looked at again, else the one the verdict is about
  const shown: ResultOut | null | undefined = frozen
    ? frozen.record_id
      ? results[frozen.record_id]
      : null
    : verdict.size === 'display'
      ? status?.last_result
      : null
  const markings: Marking[] =
    shown &&
    markingsOn(status?.markings ?? 'on_fail', status?.operator_markings ?? true, chosen, shown)
      ? (shown.tools ?? []).flatMap((t) =>
          t.region
            ? [
                {
                  id: t.id,
                  rect: t.region,
                  passed: t.passed,
                  informative: !t.affects_result || memberOfPassedGroup(shown, t),
                  marks: t.marks,
                },
              ]
            : [],
        )
      : []
  const markingsButton = status?.operator_markings ? (
    <Button
      variant="ghost"
      aria-pressed={markingsOn(status.markings, true, chosen, shown ?? status.last_result)}
      onClick={() =>
        setChosen(!markingsOn(status.markings, true, chosen, shown ?? status.last_result))
      }
    >
      {text.operator.markings}
    </Button>
  ) : null
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
          <div className="flex items-center gap-2">
            {markingsButton}
            <Button variant="ghost" onClick={() => showLogin()}>
              {text.login.open}
            </Button>
          </div>
        </header>
      ) : (
        <h1 className="sr-only">{text.nav.station}</h1>
      )}
      <SetupNotice />

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 px-6 pb-4 lg:grid-operator">
        <div className="relative min-h-64">
          <LiveCanvas
            frame={!live ? null : frozen ? (picture.data ?? null) : frame}
            regions={markings}
            empty={frozen && picture.isError ? text.operator.noSavedImage : undefined}
          />
          {frozen ? (
            <div
              role="status"
              className="absolute inset-x-0 top-0 flex items-center justify-between gap-2 rounded-t-card bg-surface-1/90 px-4 py-2"
            >
              <span className="text-lg font-medium">
                {text.operator.resultOf(clockTime(frozen.at))}
              </span>
              <Button variant="primary" onClick={() => setPick(null)}>
                {text.operator.backToLive}
              </Button>
            </div>
          ) : null}
        </div>
        <aside className="flex min-h-0 flex-col gap-4">
          <div className="min-h-64 flex-1">
            <VerdictPanel verdict={verdict} />
          </div>
          {shown ? <ToolRows result={shown} /> : null}
          <RecentResults
            results={status?.recent ?? []}
            frozen={frozen?.record_id ?? null}
            onPick={(r) =>
              setPick((now) =>
                now?.recent.record_id === r.record_id ? null : { recent: r, newest },
              )
            }
          />
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
            {stationCommand ? (
              <Button
                variant="primary"
                loading={command.isPending}
                onClick={() => command.mutate(stationCommand)}
              >
                {stationCommand === 'retry' ? text.operator.retry : text.operator.resume}
              </Button>
            ) : null}
            {bare ? null : markingsButton}
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
