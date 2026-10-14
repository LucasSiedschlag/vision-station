import { createBrowserRouter } from 'react-router'
import { OperatorPage } from '@/features/operator/OperatorPage'
import { NotFoundPage } from '@/features/errors/NotFoundPage'

// Routes by role are added here (docs/frontend.md §4.1); the shell, guards and the real screens come in VIA-0033.
export const router = createBrowserRouter([
  { path: '/', element: <OperatorPage /> },
  { path: '*', element: <NotFoundPage /> },
])
