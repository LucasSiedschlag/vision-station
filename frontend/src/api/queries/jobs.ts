import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api, call } from '../client'
import { describeError } from '../mutations'
import type { components } from '../schema'

export type JobListItem = components['schemas']['JobListItem']
export type VersionInfo = components['schemas']['VersionInfo']
export type ImportOut = components['schemas']['ImportOut']

export function useJobs() {
  return useQuery({ queryKey: ['jobs'], queryFn: () => call(api.GET('/api/jobs')) })
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ['jobs', id],
    queryFn: () => call(api.GET('/api/jobs/{job_id}', { params: { path: { job_id: id } } })),
  })
}

export function useDiff(id: string, version: number, against: number | null) {
  return useQuery({
    queryKey: ['jobs', id, 'diff', version, against],
    enabled: against !== null,
    queryFn: () =>
      call(
        api.GET('/api/jobs/{job_id}/versions/{version}/diff', {
          params: { path: { job_id: id, version }, query: { against: against ?? 1 } },
        }),
      ),
  })
}

export function useBackups(enabled = true) {
  return useQuery({ queryKey: ['backups'], enabled, queryFn: () => call(api.GET('/api/backup')) })
}

function useRefreshJobs() {
  const client = useQueryClient()
  return () => {
    void client.invalidateQueries({ queryKey: ['jobs'] })
    void client.invalidateQueries({ queryKey: ['state'] })
  }
}

/** Activate a version. A verification that fails comes back as an ApiError with `problems`; the dialog shows them. */
export function useActivate() {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: ({
      id,
      version,
      overrideReason,
    }: {
      id: string
      version: number
      overrideReason?: string
    }) =>
      call(
        api.POST('/api/jobs/{job_id}/versions/{version}/activate', {
          params: { path: { job_id: id, version } },
          body: overrideReason ? { override_reason: overrideReason } : {},
        }),
      ),
    onSuccess: refresh,
  })
}

export function useImport() {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: (file: File) =>
      call(
        api.POST('/api/jobs/import', {
          body: file as unknown as undefined,
          bodySerializer: (body: unknown) => body as BodyInit,
          headers: { 'Content-Type': 'application/octet-stream' },
        }),
      ),
    onSuccess: refresh,
  })
}

export function useMakeBackup() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => call(api.POST('/api/backup')),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['backups'] }),
    onError: (error) => toast.error(describeError(error)),
  })
}

export function useDuplicate() {
  const refresh = useRefreshJobs()
  return useMutation({
    mutationFn: ({ id, version, name }: { id: string; version: number; name: string }) =>
      call(
        api.POST('/api/jobs/{job_id}/duplicate', {
          params: { path: { job_id: id } },
          body: { version, name },
        }),
      ),
    onSuccess: refresh,
  })
}
