import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { startLive } from '@/api/live'
import { Toaster } from '@/components/ui/toaster'
import { LocaleProvider, useLocale } from './locale'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } }),
  )
  useEffect(() => startLive(), []) // one live socket for the whole app
  // texts that came from the server are in the old language: ask again for what is on screen
  const locale = useLocale((s) => s.locale)
  useEffect(() => {
    void queryClient.invalidateQueries()
  }, [locale, queryClient])
  return (
    <LocaleProvider>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster />
      </QueryClientProvider>
    </LocaleProvider>
  )
}
