import { useQuery } from '@tanstack/react-query'
import { api, call } from '../client'

/** The station state over REST (the live socket keeps it fresh; this is for a first paint and for tests). */
export function useStateQuery() {
  return useQuery({ queryKey: ['state'], queryFn: () => call(api.GET('/api/state')) })
}
