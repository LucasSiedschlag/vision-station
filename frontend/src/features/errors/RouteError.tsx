import { useRouteError } from 'react-router'
import { ErrorState } from '@/components/ui/feedback'
import { text } from '@/texts'

/** What a screen shows when it fails while it is being built: the plain message, a retry, the detail folded away. */
export function RouteError() {
  const error = useRouteError()
  const detail = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
  return (
    <main className="grid min-h-full place-items-center">
      <ErrorState
        title={text.errors.routeTitle}
        message={text.errors.routeBody}
        detail={detail}
        onRetry={() => window.location.reload()}
      />
    </main>
  )
}
