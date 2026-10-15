import { Info, Layers, MonitorPlay, type LucideIcon } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import type { RouteObject } from 'react-router'
import type { Role } from '@/api/session'
import { NotFoundPage } from '@/features/errors/NotFoundPage'
import { RouteError } from '@/features/errors/RouteError'
import { OperatorPage } from '@/features/operator/OperatorPage'
import { text } from '@/texts'
import { RequireRole } from './guards'
import { RootLayout } from './RootLayout'

// the gallery is loaded only when opened, so it costs the operator screen nothing; it is not in the menu
const AboutPage = lazy(() =>
  import('@/features/about/AboutPage').then((m) => ({ default: m.AboutPage })),
)
const JobsPage = lazy(() =>
  import('@/features/jobs/JobsPage').then((m) => ({ default: m.JobsPage })),
)
const JobPage = lazy(() => import('@/features/jobs/JobPage').then((m) => ({ default: m.JobPage })))
const EditorPage = lazy(() =>
  import('@/features/editor/EditorPage').then((m) => ({ default: m.EditorPage })),
)
const DesignPage = lazy(() =>
  import('@/features/design/DesignPage').then((m) => ({ default: m.DesignPage })),
)

/** A screen in the menu. Screens that are built later are added here: the menu, the guard and the route follow. */
export interface Screen {
  path: string
  label: string
  icon: LucideIcon
  /** the lowest role that may open it */
  min: Role
  element: ReactNode
}

export const screens: Screen[] = [
  {
    path: '/',
    label: text.nav.station,
    icon: MonitorPlay,
    min: 'operator',
    element: <OperatorPage />,
  },
  {
    path: '/jobs',
    label: text.nav.jobs,
    icon: Layers,
    min: 'supervisor',
    element: (
      <Suspense fallback={null}>
        <JobsPage />
      </Suspense>
    ),
  },
  {
    path: '/about',
    label: text.nav.about,
    icon: Info,
    min: 'supervisor',
    element: (
      <Suspense fallback={null}>
        <AboutPage />
      </Suspense>
    ),
  },
]

const inner: { path: string; min: Role; element: ReactNode }[] = [
  { path: '/jobs/:id', min: 'supervisor', element: <JobPage /> },
  { path: '/jobs/:id/edit', min: 'maintainer', element: <EditorPage /> },
]

export const routes: RouteObject[] = [
  {
    element: <RootLayout />,
    errorElement: <RouteError />,
    children: [
      ...screens.map((screen): RouteObject => ({
        path: screen.path,
        element:
          screen.min === 'operator' ? (
            screen.element
          ) : (
            <RequireRole min={screen.min}>{screen.element}</RequireRole>
          ),
      })),
      // screens reached from another screen, not from the menu
      ...inner.map((route): RouteObject => ({
        path: route.path,
        element: (
          <RequireRole min={route.min}>
            <Suspense fallback={null}>{route.element}</Suspense>
          </RequireRole>
        ),
      })),
      {
        path: '/design',
        element: (
          <Suspense fallback={null}>
            <DesignPage />
          </Suspense>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
