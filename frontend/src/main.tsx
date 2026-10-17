import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { activate, initialLocale } from '@/app/locale'
import { Providers } from '@/app/providers'
import { router } from '@/app/router'
import { initTheme } from '@/lib/theme'
import './styles/globals.css'

initTheme()

// the texts of the language the station spoke last, before the first status says it again (TD-30)
await activate(initialLocale())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
)
