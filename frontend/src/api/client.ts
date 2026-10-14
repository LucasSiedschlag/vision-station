import createClient, { type Middleware } from 'openapi-fetch'
import type { components, paths } from './schema'
import { useSession } from './session'

export type Problem = components['schemas']['Problem']

/** An error answer from the API, in the shape every endpoint uses: a Portuguese message and a machine code. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly problems?: string[]
  readonly fields?: Record<string, string>

  constructor(status: number, problem: Partial<Problem> | undefined) {
    super(problem?.detail ?? `HTTP ${status}`)
    this.status = status
    this.code = problem?.code ?? 'error'
    this.problems = problem?.problems ?? undefined
    this.fields = problem?.fields ?? undefined
  }
}

const auth: Middleware = {
  onRequest({ request }) {
    const { token } = useSession.getState()
    if (token) request.headers.set('Authorization', `Bearer ${token}`)
    return request
  },
  onResponse({ response }) {
    // the server no longer accepts the token (expired, revoked, or a new password): fall back to the operator
    if (response.status === 401 && useSession.getState().token) useSession.getState().clear()
    return response
  },
}

/** The typed client. The paths of the generated schema already start with /api. */
export function createApi(baseUrl = '') {
  // fetch is looked up at call time, so tests can replace it after the client is created
  const client = createClient<paths>({ baseUrl, fetch: (request) => globalThis.fetch(request) })
  client.use(auth)
  return client
}

export const api = createApi()

/** Unwraps a call of the typed client: the data, or an ApiError. */
export async function call<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok) throw new ApiError(response.status, error as Partial<Problem> | undefined)
  return data as T
}
