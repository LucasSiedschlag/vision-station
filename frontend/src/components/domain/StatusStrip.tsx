import { StatusIndicator, type Tone } from '@/components/ui/badge'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { StateOut } from '@/api/live'
import type { Connection } from '@/features/operator/view'
import { text } from '@/texts'

interface Item {
  id: string
  label: string
  tone: Tone
  word: string
  detail: string[]
}

/** The three named indicators of what the screen knows: the link to the system, the camera, the results log. */
export function indicators(status: StateOut | null, connection: Connection): Item[] {
  const s = text.status
  const system: Item =
    connection === 'connected'
      ? {
          id: 'system',
          label: s.system,
          tone: 'ok',
          word: s.connected,
          detail: ['Esta tela está ligada ao programa da estação.'],
        }
      : connection === 'connecting'
        ? {
            id: 'system',
            label: s.system,
            tone: 'busy',
            word: s.connecting,
            detail: ['Ligando esta tela ao programa da estação.'],
          }
        : {
            id: 'system',
            label: s.system,
            tone: 'fail',
            word: s.offline,
            detail: ['Esta tela perdeu a ligação com o programa e tenta de novo sozinha.'],
          }

  // without a status the camera and the log are unknown: never shown as fine
  if (!status || connection !== 'connected') {
    return [
      system,
      {
        id: 'camera',
        label: s.camera,
        tone: 'unknown',
        word: s.unknown,
        detail: ['Sem ligação com o sistema, o estado da câmera não é conhecido.'],
      },
      {
        id: 'log',
        label: s.log,
        tone: 'unknown',
        word: s.unknown,
        detail: ['Sem ligação com o sistema, não se sabe se os resultados estão sendo gravados.'],
      },
    ]
  }

  const camera: Item = status.camera.connected
    ? {
        id: 'camera',
        label: s.camera,
        tone: 'ok',
        word: s.ok,
        detail:
          status.camera.last_frame_age_s === null
            ? []
            : [s.lastFrame(status.camera.last_frame_age_s)],
      }
    : {
        id: 'camera',
        label: s.camera,
        tone: 'fail',
        word: s.disconnected,
        detail: [status.camera.last_error ?? 'Reconectando automaticamente.'],
      }
  const log: Item =
    status.recording_failures > 0
      ? {
          id: 'log',
          label: s.log,
          tone: 'fail',
          word: s.failing,
          detail: [s.failures(status.recording_failures)],
        }
      : {
          id: 'log',
          label: s.log,
          tone: 'ok',
          word: s.ok,
          detail: ['Os resultados estão sendo gravados.'],
        }
  return [system, camera, log]
}

export function StatusStrip({
  status,
  connection,
}: {
  status: StateOut | null
  connection: Connection
}) {
  return (
    <ul aria-label="Estado do sistema" className="flex flex-wrap items-center gap-x-6 gap-y-1">
      {indicators(status, connection).map((item) => (
        <li key={item.id}>
          <Popover>
            <PopoverTrigger
              className="flex min-h-control items-center rounded-control px-1 text-left hover:bg-surface-3"
              aria-label={`${item.label}: ${item.word}`}
            >
              <StatusIndicator tone={item.tone} label={item.label} detail={item.word} />
            </PopoverTrigger>
            <PopoverContent>
              <p className="mb-1 font-medium">{item.label}</p>
              {item.detail.map((line) => (
                <p key={line} className="text-fg-muted">
                  {line}
                </p>
              ))}
            </PopoverContent>
          </Popover>
        </li>
      ))}
    </ul>
  )
}
