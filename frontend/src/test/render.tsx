import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { useLoginDialog } from '@/api/auth'
import { useLive } from '@/api/live'
import { useSession } from '@/api/session'
import { Toaster } from '@/components/ui/toaster'
import { activate, LocaleProvider, useLocale } from '@/app/locale'
import { routes } from '@/app/routes'

// One mock API for a test file: call server.use(http.get('*/api/about', ...)) inside a test.
export const server = setupServer()

export function mockApi() {
  beforeAll(() => server.listen())
  afterEach(async () => {
    cleanup() // unmount first, so a dialog that is open closes with its page and not with the stores below
    server.resetHandlers()
    useSession.getState().clear()
    useLoginDialog.setState({ open: false, opened: false, next: null })
    useLive.setState({ status: null, frame: null, connected: false, connecting: true })
    // every test starts in Portuguese with no language chosen (TD-30)
    localStorage.removeItem('vision-station-language')
    localStorage.removeItem('vision-station-station-language')
    useLocale.setState({ station: 'pt-BR', choice: null })
    await activate('pt-BR')
    // a modal that was open leaves the page marked inert/aria-hidden; start every test from a clean page
    document.body.removeAttribute('style')
    document.body.removeAttribute('data-scroll-locked')
    document.body.querySelectorAll('[aria-hidden],[inert],[data-aria-hidden]').forEach((el) => {
      el.removeAttribute('aria-hidden')
      el.removeAttribute('inert')
      el.removeAttribute('data-aria-hidden')
    })
  })
  afterAll(() => server.close())
}

/** The whole app (routes, layout, dialogs) at a path, with a fresh query cache. */
export function renderApp(path = '/') {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const result = render(
    <LocaleProvider>
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
        <Toaster />
      </QueryClientProvider>
    </LocaleProvider>,
  )
  return { router, ...result }
}

export const stateFixture = (over: Record<string, unknown> = {}) => ({
  state: 'Ready' as const,
  language: 'pt-BR' as const,
  message: 'Aguardando peça',
  showing_result: false,
  detail: '',
  warnings: [],
  job: {
    id: 'j',
    name: 'Tampa azul — etiqueta de lote',
    version: 7,
    number: null,
    content_hash: null,
  },
  last_result: null,
  last_record_id: null,
  camera: { connected: true, last_frame_age_s: 0.2, last_error: null },
  counters: { PASS: 0, FAIL: 0, ERROR: 0, total: 0 },
  recent: [],
  markings: 'on_fail' as const,
  operator_markings: true,
  recording_failures: 0,
  version: '0.1.0',
  ...over,
})

/** Put the live store in a given state, as if the socket had delivered it. */
export function setLive(over: Record<string, unknown> = {}, connected = true) {
  useLive.setState({ status: stateFixture(over), connected, connecting: false, frame: null })
}
