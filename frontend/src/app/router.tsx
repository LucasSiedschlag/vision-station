import { createBrowserRouter } from 'react-router'
import { OperatorPage } from '@/features/operator/OperatorPage'
import { NotFoundPage } from '@/features/errors/NotFoundPage'
import { lazy, Suspense } from 'react'

// the gallery is loaded only when opened, so it costs the operator screen nothing
const DesignPage = lazy(() =>
  import('@/features/design/DesignPage').then((m) => ({ default: m.DesignPage })),
)

// Routes by role are added here (docs/frontend.md §4.1); the shell, guards and the real screens come in VIA-0033.
export const router = createBrowserRouter([
  { path: '/', element: <OperatorPage /> },
  {
    path: '/design',
    element: (
      <Suspense fallback={null}>
        <DesignPage />
      </Suspense>
    ),
  },
  { path: '*', element: <NotFoundPage /> },
])
