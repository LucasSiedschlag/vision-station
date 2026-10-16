import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, call, ApiError } from './client'

/** Plain Portuguese for a failed call: the server's own message when it sent one. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Não foi possível falar com o programa da estação.'
}

export function useTrigger() {
  return useMutation({
    mutationFn: () => call(api.POST('/api/trigger')),
    onError: (error) => toast.error(describeError(error)),
  })
}

/** The maintainer's station commands: retry after a fault, resume after a pause (e.g. camera tuning). */
export function useStationCommand() {
  return useMutation({
    mutationFn: (command: 'retry' | 'resume' | 'pause') =>
      call(api.POST('/api/station/{command}', { params: { path: { command } } })),
    onError: (error) => toast.error(describeError(error)),
  })
}

export function useMarkWrong() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ recordId, correct }: { recordId: string; correct: 'PASS' | 'FAIL' }) =>
      call(
        api.POST('/api/results/{record_id}/incorrect', {
          params: { path: { record_id: recordId } },
          body: { correct, by: '' },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['results'] }),
    onError: (error) => toast.error(describeError(error)),
  })
}
