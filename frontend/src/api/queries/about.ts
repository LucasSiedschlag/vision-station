import { useQuery } from '@tanstack/react-query'
import { api, call } from '../client'

export function useAbout() {
  return useQuery({ queryKey: ['about'], queryFn: () => call(api.GET('/api/about')) })
}
