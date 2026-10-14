import { useLive } from '@/api/live'
import { texts } from '@/texts'

/**
 * Skeleton of the operator screen: proves the typed client, the live socket and the build end to end.
 * The real, designed screen replaces it in VIA-0033 (docs/frontend.md §7.1).
 */
export function OperatorPage() {
  const status = useLive((s) => s.status)
  const connected = useLive((s) => s.connected)
  const connecting = useLive((s) => s.connecting)

  const connection = connecting
    ? texts.connection.connecting
    : connected
      ? texts.connection.online
      : texts.connection.offline

  return (
    <main className="p-8">
      <h1 className="text-xl">{texts.app.name}</h1>
      <p role="status">{connection}</p>
      {status ? (
        <>
          <p>{status.job.name || texts.app.noJob}</p>
          <p className="text-3xl">{status.message}</p>
          <p>
            {status.counters.total} · {status.counters.PASS} · {status.counters.FAIL} ·{' '}
            {status.counters.ERROR}
          </p>
        </>
      ) : null}
    </main>
  )
}
