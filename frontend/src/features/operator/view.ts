import { currentLocale } from '@/app/locale'
import type { ResultOut, StateOut } from '@/api/live'
import { decimalsOf, suffixOf } from '@/components/vision/gauge-model'
import { formatNumber, formatPercent } from '@/lib/number'
import { text } from '@/texts'

export type Tone = 'ok' | 'fail' | 'warn' | 'busy' | 'neutral'
export type Size = 'display' | 'title'

/** What the verdict panel shows. The word is always there: colour is never the only signal (NFR-USA-2). */
export interface Verdict {
  tone: Tone
  icon: 'check' | 'cross' | 'alert' | 'busy' | 'wait' | 'offline' | 'camera' | 'wrench'
  headline: string
  /** `display` for the three results, `title` for every other state */
  size: Size
  reason: string
  /** a small line under the reason (time and duration of a result) */
  meta: string
  /** set when what is shown may be out of date: the screen cannot reach the station */
  stale: string
}

export type Connection = 'connecting' | 'connected' | 'offline'

const none = { reason: '', meta: '', stale: '' }

function describeLast(status: StateOut): string {
  const r = status.last_result
  if (!r) return ''
  const word = { PASS: text.live.pass, FAIL: text.live.fail, ERROR: text.live.error }[r.outcome]
  return text.live.lastResult(word)
}

/** Local time of a result as HH:MM:SS, or empty when the server did not say. */
export function clockTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString(currentLocale(), {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
}

export function verdictOf(status: StateOut | null, connection: Connection): Verdict {
  if (connection === 'connecting' && !status) {
    return { tone: 'neutral', icon: 'wait', headline: text.live.connecting, size: 'title', ...none }
  }
  if (connection !== 'connected' || !status) {
    return {
      tone: 'neutral',
      icon: 'offline',
      headline: text.live.offline,
      size: 'title',
      reason: text.live.reconnecting,
      meta: '',
      stale: status ? describeLast(status) : '',
    }
  }
  const r = status.last_result
  // the station may already be armed again (Ready) while its last verdict is still to be shown (VIA-0049)
  const held =
    status.showing_result && (status.state === 'Ready' || status.state === 'WaitingStill')
  switch (held ? 'ShowingResult' : status.state) {
    case 'ShowingResult': {
      const meta = [clockTime(r?.at), r ? `${r.duration_ms} ms` : ''].filter(Boolean).join(' · ')
      if (r?.outcome === 'PASS')
        return {
          tone: 'ok',
          icon: 'check',
          headline: text.live.pass,
          size: 'display',
          reason: r.reason,
          meta,
          stale: '',
        }
      if (r?.outcome === 'FAIL')
        return {
          tone: 'fail',
          icon: 'cross',
          headline: text.live.fail,
          size: 'display',
          reason: r.reason,
          meta,
          stale: '',
        }
      // an error, and anything that is not recognised: never shown as a pass
      return {
        tone: 'warn',
        icon: 'alert',
        headline: text.live.error,
        size: 'display',
        reason: r?.reason || text.live.couldNotInspect,
        meta,
        stale: '',
      }
    }
    case 'Inspecting':
      return { tone: 'busy', icon: 'busy', headline: text.live.inspecting, size: 'title', ...none }
    case 'CameraLost':
      return {
        tone: 'warn',
        icon: 'camera',
        headline: text.live.cameraLost,
        size: 'title',
        reason: text.live.reconnecting,
        meta: '',
        stale: '',
      }
    case 'Fault':
      return {
        tone: 'warn',
        icon: 'wrench',
        headline: text.live.fault,
        size: 'title',
        reason: status.detail || text.live.callMaintenance,
        meta: '',
        stale: '',
      }
    case 'Paused':
      return {
        tone: 'warn',
        icon: 'wrench',
        headline: text.live.maintenance,
        size: 'title',
        ...none,
      }
    case 'Starting':
    case 'Preparing':
      return { tone: 'busy', icon: 'busy', headline: text.live.preparing, size: 'title', ...none }
    default:
      return {
        tone: 'neutral',
        icon: 'wait',
        headline: status.message || text.live.waiting,
        size: 'title',
        ...none,
      }
  }
}

export function canTrigger(status: StateOut | null, connection: Connection): boolean {
  return (
    connection === 'connected' &&
    !!status &&
    (status.state === 'Ready' || status.state === 'WaitingStill')
  )
}

/** The "wrong result?" action needs a result on screen that was recorded (with its image). */
export function canMarkWrong(status: StateOut | null, connection: Connection): boolean {
  return (
    connection === 'connected' &&
    status?.state === 'ShowingResult' &&
    !!status.last_record_id &&
    !!status.last_result
  )
}

export function connectionOf(connected: boolean, connecting: boolean): Connection {
  return connecting ? 'connecting' : connected ? 'connected' : 'offline'
}

export function percent(part: number, total: number): number {
  return total ? Math.round((100 * part) / total) : 0
}

/** One tool's line under the verdict: its name, whether it passed, and the value that decided it. */
export interface ToolRow {
  id: string
  passed: boolean
  value: string
}

type Tool = ResultOut['tools'][number]

/** The measure that decided a tool, written with its unit: the failing criterion, else the one nearest its limit. */
function valueOf(tool: Tool): string {
  const criterion =
    tool.criteria.find((c) => !c.passed && c.measure) ?? tool.criteria.find((c) => c.measure)
  if (!criterion?.measure || criterion.value === null || criterion.value === undefined) return ''
  const unit = tool.units[criterion.measure]
  if (unit === 'fraction') return formatPercent(criterion.value, 0)
  return `${formatNumber(criterion.value, decimalsOf(unit))}${suffixOf(unit) ? ` ${suffixOf(unit)}` : ''}`
}

/** At most this many tools are listed; the rest are counted (docs/frontend.md §7.1). */
export const MAX_TOOL_ROWS = 6

/**
 * The tools that decide the result, as lines: the failing ones first (the operator must see which), then the others,
 * each group in the job's order. The lines past the sixth are only counted.
 */
export function toolRows(result: ResultOut | null | undefined): {
  rows: ToolRow[]
  more: number
} {
  const deciding = (result?.tools ?? []).filter((t) => t.affects_result)
  const groups = new Map((result?.groups ?? []).map((g) => [g.id, g]))
  const seen = new Set<string>()
  const lines: ToolRow[] = []
  for (const t of deciding) {
    if (!t.group) {
      lines.push({ id: t.id, passed: t.passed, value: valueOf(t) })
      continue
    }
    if (seen.has(t.group)) continue // a group is one line: any member is enough (TD-33)
    seen.add(t.group)
    const members = deciding.filter((x) => x.group === t.group)
    const matching = members.filter((x) => x.passed).length
    lines.push({
      id: members.map((x) => x.id).join(' / '),
      passed: groups.get(t.group)?.passed ?? matching > 0,
      value: `${matching}/${members.length}`,
    })
  }
  const ordered = [...lines.filter((l) => !l.passed), ...lines.filter((l) => l.passed)]
  return {
    rows: ordered.slice(0, MAX_TOOL_ROWS),
    more: Math.max(0, ordered.length - MAX_TOOL_ROWS),
  }
}

/** A member that did not match is no failure when its group passed: one was enough, so it is drawn as a warning (TD-33). */
export function memberOfPassedGroup(result: ResultOut, tool: Tool): boolean {
  return !!tool.group && (result.groups ?? []).some((g) => g.id === tool.group && g.passed)
}

export type Markings = 'always' | 'on_fail' | 'never'

/**
 * Whether the regions are drawn on the image (FR-UI-9, docs/frontend.md §18): what the operator chose with the
 * button, else the station's default for this result. Never on when no result is being shown.
 */
export function markingsOn(
  setting: Markings,
  operatorMay: boolean,
  chosen: boolean | null,
  result: ResultOut | null | undefined,
): boolean {
  if (!result) return false
  if (operatorMay && chosen !== null) return chosen
  return setting === 'always' || (setting === 'on_fail' && result.outcome === 'FAIL')
}
