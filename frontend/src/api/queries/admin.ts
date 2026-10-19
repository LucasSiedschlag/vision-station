import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, call } from '../client'
import type { components } from '../schema'

export type RecordOut = components['schemas']['RecordOut']
export type SystemConfig = components['schemas']['SystemConfig']
export type SystemOut = components['schemas']['SystemOut']
export type AuditEvent = components['schemas']['AuditEvent']

export interface ResultsFilter {
  since?: string
  job_id?: string
  outcome?: 'PASS' | 'FAIL' | 'ERROR'
  incorrect_only?: boolean
  reason_code?: string
  offset: number
}

export const PAGE = 100

export function useResults(filter: ResultsFilter) {
  return useQuery({
    queryKey: ['results', filter],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET('/api/results', { params: { query: { ...filter, limit: PAGE } } })),
  })
}

/** The reason codes the other filters leave, with how many results each has: the options of the code filter. */
export function useReasonCodes(filter: Omit<ResultsFilter, 'offset' | 'reason_code'>) {
  return useQuery({
    queryKey: ['results', 'reason-codes', filter],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET('/api/results/reason-codes', { params: { query: filter } })),
  })
}

export function useMarkIncorrect() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, correct }: { id: string; correct: 'PASS' | 'FAIL' }) =>
      call(
        api.POST('/api/results/{record_id}/incorrect', {
          params: { path: { record_id: id } },
          body: { correct, by: 'supervisor' },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['results'] }),
  })
}

export function useDataset() {
  return useQuery({ queryKey: ['dataset'], queryFn: () => call(api.GET('/api/dataset')) })
}

export type DatasetImage = components['schemas']['DatasetImage']

export const IMAGES_PAGE = 48

export function useDatasetImages(jobId: string | null, offset: number) {
  return useQuery({
    queryKey: ['dataset', jobId, 'images', offset],
    enabled: jobId !== null,
    queryFn: () =>
      call(
        api.GET('/api/dataset/{job_id}/images', {
          params: {
            path: { job_id: jobId! },
            query: { limit: IMAGES_PAGE, offset },
          },
        }),
      ),
  })
}

export function useSetCollection() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, enabled }: { jobId: string; enabled: boolean }) =>
      call(
        api.POST('/api/collection/{job_id}', {
          params: { path: { job_id: jobId } },
          body: { enabled },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['dataset'] }),
  })
}

export function useExportDataset() {
  return useMutation({
    mutationFn: (jobId: string | null) =>
      call(api.POST('/api/dataset/export', { body: { job_id: jobId } })),
  })
}

export function useSystem() {
  return useQuery({ queryKey: ['system'], queryFn: () => call(api.GET('/api/system')) })
}

export function useSaveSystem() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (config: SystemConfig) => call(api.PUT('/api/system', { body: config })),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['system'] }),
  })
}

export const systemChecks = {
  folder: (path: string) => call(api.POST('/api/system/test-folder', { body: { path } })),
  camera: (camera: SystemConfig['camera']) =>
    call(api.POST('/api/system/test-camera', { body: camera })),
}

export function useUsers() {
  return useQuery({ queryKey: ['users'], queryFn: () => call(api.GET('/api/users')) })
}

export function useSetPassword() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      role,
      password,
      current,
    }: {
      role: 'supervisor' | 'maintainer'
      password: string
      current?: string
    }) =>
      call(
        api.PUT('/api/users/{role}/password', {
          params: { path: { role } },
          body: { password, current_password: current ?? null },
        }),
      ),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useRevokeSessions() {
  return useMutation({ mutationFn: () => call(api.POST('/api/users/sessions/revoke')) })
}

export function useAudit(filter: { kind?: string; job_id?: string; offset: number }) {
  return useQuery({
    queryKey: ['audit', filter],
    placeholderData: keepPreviousData,
    queryFn: () => call(api.GET('/api/audit', { params: { query: { ...filter, limit: PAGE } } })),
  })
}
