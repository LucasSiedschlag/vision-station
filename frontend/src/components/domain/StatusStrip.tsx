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

/**
 * The machine link (architecture §16), present in the status only while a machine connector is
 * enabled. The core does not send it yet (R3): the indicator stays hidden until it does. The
 * contract is written in document 05 §9.6 (`machine` in the state message).
 */
export interface MachineStatus {
  connected: boolean
  heartbeat_age_s: number | null
  last_error: string | null
}

function machineOf(status: StateOut | null): MachineStatus | null {
  return (status as (StateOut & { machine?: MachineStatus | null }) | null)?.machine ?? null
}

/** The named indicators of what the screen knows: the link to the system, the camera, the results log. */
export function indicators(status: StateOut | null, connection: Connection): Item[] {
  const s = text.status
  const system: Item =
    connection === 'connected'
      ? {
          id: 'system',
          label: s.system,
          tone: 'ok',
          word: s.connected,
          detail: [text.live.systemConnected],
        }
      : connection === 'connecting'
        ? {
            id: 'system',
            label: s.system,
            tone: 'busy',
            word: s.connecting,
            detail: [text.live.systemConnecting],
          }
        : {
            id: 'system',
            label: s.system,
            tone: 'fail',
            word: s.offline,
            detail: [text.live.systemOffline],
          }

  const machine = machineOf(status)
  const unknownMachine: Item[] = machine
    ? [
        {
          id: 'machine',
          label: s.machine,
          tone: 'unknown',
          word: s.unknown,
          detail: [text.live.machineUnknown],
        },
      ]
    : []

  // without a status the camera and the log are unknown: never shown as fine
  if (!status || connection !== 'connected') {
    return [
      system,
      {
        id: 'camera',
        label: s.camera,
        tone: 'unknown',
        word: s.unknown,
        detail: [text.live.cameraUnknown],
      },
      ...unknownMachine,
      {
        id: 'log',
        label: s.log,
        tone: 'unknown',
        word: s.unknown,
        detail: [text.live.logUnknown],
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
        detail: [status.camera.last_error ?? text.live.reconnecting],
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
          detail: [text.live.logOk],
        }
  // a link counts as fine only with a heartbeat seen: an open socket alone says nothing (E601, §16)
  const machineItems: Item[] = !machine
    ? []
    : machine.connected === true && machine.heartbeat_age_s !== null
      ? [
          {
            id: 'machine',
            label: s.machine,
            tone: 'ok',
            word: s.machineConnected,
            detail: [s.heartbeat(machine.heartbeat_age_s)],
          },
        ]
      : machine.connected === true
        ? [
            {
              id: 'machine',
              label: s.machine,
              tone: 'unknown',
              word: s.awaitingHeartbeat,
              detail: [text.live.machineAwaiting],
            },
          ]
        : [
            {
              id: 'machine',
              label: s.machine,
              tone: 'fail',
              word: s.noSignal,
              detail: [machine.last_error ?? text.live.machineSilent],
            },
          ]
  return [system, camera, ...machineItems, log]
}

export function StatusStrip({
  status,
  connection,
}: {
  status: StateOut | null
  connection: Connection
}) {
  return (
    <ul aria-label={text.live.statusLabel} className="flex flex-wrap items-center gap-x-6 gap-y-1">
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
