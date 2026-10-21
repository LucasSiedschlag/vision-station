import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { login } from '../auth'
import { api, call } from '../client'

export type SetupStatus = Awaited<ReturnType<typeof getStatus>>
export type SetupStep = SetupStatus['steps'][number]

const getStatus = () => call(api.GET('/api/setup/status'))

/** Whether the first password can be created now. Public: it is what the operator screen's notice asks. */
export function useSetupOpen() {
  return useQuery({
    queryKey: ['setup', 'open'],
    queryFn: () => call(api.GET('/api/setup/open')),
    staleTime: 30_000,
  })
}

/** The wizard's seven steps, derived by the server. Open while the Maintainer has no password, the Maintainer's after. */
export function useSetupStatus(enabled = true) {
  return useQuery({ queryKey: ['setup', 'status'], queryFn: getStatus, enabled })
}

/** The first Maintainer password, then straight into the session with it: the wizard goes on logged in. */
export function useCreateMaintainerPassword() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async (password: string) => {
      await call(api.PUT('/api/setup/maintainer-password', { body: { password } }))
      await login('maintainer', password)
    },
    onSettled: () => void client.invalidateQueries({ queryKey: ['setup'] }),
  })
}

export type SetupCamera = Awaited<ReturnType<typeof getCameras>>['cameras'][number]

const getCameras = () => call(api.GET('/api/setup/cameras'))

/** The USB cameras connected to this PC. Asked again with `refetch` when someone plugs one in. */
export function useSetupCameras() {
  return useQuery({ queryKey: ['setup', 'cameras'], queryFn: getCameras, staleTime: 0, gcTime: 0 })
}
