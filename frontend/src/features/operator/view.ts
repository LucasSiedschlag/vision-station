import type { StateOut } from '@/api/live'

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
  const word = { PASS: 'APROVADO', FAIL: 'REPROVADO', ERROR: 'ERRO' }[r.outcome]
  return `Último resultado: ${word}. Pode estar desatualizado.`
}

/** Local time of a result as HH:MM:SS, or empty when the server did not say. */
export function clockTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function verdictOf(status: StateOut | null, connection: Connection): Verdict {
  if (connection === 'connecting' && !status) {
    return { tone: 'neutral', icon: 'wait', headline: 'Conectando…', size: 'title', ...none }
  }
  if (connection !== 'connected' || !status) {
    return {
      tone: 'neutral',
      icon: 'offline',
      headline: 'Sem conexão',
      size: 'title',
      reason: 'Reconectando automaticamente.',
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
          headline: 'APROVADO',
          size: 'display',
          reason: r.reason,
          meta,
          stale: '',
        }
      if (r?.outcome === 'FAIL')
        return {
          tone: 'fail',
          icon: 'cross',
          headline: 'REPROVADO',
          size: 'display',
          reason: r.reason,
          meta,
          stale: '',
        }
      // an error, and anything that is not recognised: never shown as a pass
      return {
        tone: 'warn',
        icon: 'alert',
        headline: 'ERRO',
        size: 'display',
        reason: r?.reason || 'Não foi possível inspecionar.',
        meta,
        stale: '',
      }
    }
    case 'Inspecting':
      return { tone: 'busy', icon: 'busy', headline: 'Inspecionando…', size: 'title', ...none }
    case 'CameraLost':
      return {
        tone: 'warn',
        icon: 'camera',
        headline: 'Câmera desconectada',
        size: 'title',
        reason: 'Reconectando automaticamente.',
        meta: '',
        stale: '',
      }
    case 'Fault':
      return {
        tone: 'warn',
        icon: 'wrench',
        headline: 'Falha na verificação',
        size: 'title',
        reason: status.detail || 'Chamar a manutenção.',
        meta: '',
        stale: '',
      }
    case 'Paused':
      return { tone: 'warn', icon: 'wrench', headline: 'Em manutenção', size: 'title', ...none }
    case 'Starting':
    case 'Preparing':
      return { tone: 'busy', icon: 'busy', headline: 'Preparando…', size: 'title', ...none }
    default:
      return {
        tone: 'neutral',
        icon: 'wait',
        headline: status.message || 'Aguardando objeto',
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
