import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { mockApi, server } from '@/test/render'
import { useJob } from './jobs'

mockApi()

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
)

describe('useJob', () => {
  it('asks nothing for the job that does not exist yet (an empty id), so the editor on a new job has no 404 in the console', async () => {
    const asked: string[] = []
    server.use(
      http.get('*/api/jobs/*', ({ request }) => {
        asked.push(request.url)
        return HttpResponse.json({}, { status: 404 })
      }),
    )
    const { result } = renderHook(() => useJob(''), { wrapper })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(result.current.fetchStatus).toBe('idle')
    expect(asked).toEqual([])
  })

  it('asks for a job that has an id', async () => {
    server.use(
      http.get('*/api/jobs/abc', () =>
        HttpResponse.json({ id: 'abc', name: 'x', versions: [] }),
      ),
    )
    const { result } = renderHook(() => useJob('abc'), { wrapper })
    await waitFor(() => expect(result.current.fetchStatus).toBe('idle'))
    expect(result.current.isPending).toBe(false)
  })
})
