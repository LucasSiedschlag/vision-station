import { useMutation, useQuery } from '@tanstack/react-query'
import { api, call } from '../client'
import type { components } from '../schema'

export type TypeInfo = components['schemas']['TypeInfo']
export type DraftTestOut = components['schemas']['DraftTestOut']
export type CameraState = components['schemas']['CameraStateOut']
export type VerifyOut = components['schemas']['VerifyOut']
export type JobDraftBody = components['schemas']['JobDraft']

export function useTypes() {
  return useQuery({
    queryKey: ['types'],
    staleTime: Infinity,
    queryFn: () => call(api.GET('/api/tools')),
  })
}

export function useJobVersion(id: string | null, version: number | null) {
  return useQuery({
    queryKey: ['jobs', id, 'versions', version],
    enabled: id !== null && version !== null,
    queryFn: () =>
      call(
        api.GET('/api/jobs/{job_id}/versions/{version}', {
          params: { path: { job_id: id!, version: version! } },
        }),
      ),
  })
}

export function useCameraState(enabled = true) {
  return useQuery({
    queryKey: ['camera'],
    enabled,
    queryFn: () => call(api.GET('/api/camera/state')),
  })
}

export const editorApi = {
  validate: (body: JobDraftBody) => call(api.POST('/api/jobs/validate', { body })),
  verify: (body: JobDraftBody) => call(api.POST('/api/jobs/verify', { body })),
  test: (draft: JobDraftBody, image?: string | null) =>
    call(api.POST('/api/jobs/test', { body: { draft, image: image ?? null } })),
  create: (body: JobDraftBody) => call(api.POST('/api/jobs', { body })),
  saveVersion: (id: string, body: JobDraftBody) =>
    call(api.POST('/api/jobs/{job_id}/versions', { params: { path: { job_id: id } }, body })),
  autoExposure: (profile: Record<string, unknown>) =>
    call(api.POST('/api/camera/auto-exposure', { body: profile })),
  applyCamera: (profile: Record<string, unknown>) =>
    call(api.POST('/api/camera/apply', { params: { query: { wait_s: 5 } }, body: profile })),
  resumeStation: () =>
    call(api.POST('/api/station/{command}', { params: { path: { command: 'resume' } } })),
  captureReference: () => call(api.POST('/api/reference/capture', { body: { image: null } })),
  captureCase: (draft: JobDraftBody, name: string) =>
    call(api.POST('/api/reference/cases', { body: { draft, name, image: null } })),
}

export function useEditorMutation<A, R>(fn: (args: A) => Promise<R>) {
  return useMutation({ mutationFn: fn })
}
