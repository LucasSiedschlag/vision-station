import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest'
import { useLocale } from '@/app/locale'
import { ApiError, call, createApi } from './client'
import { useSession } from './session'

const server = setupServer()
beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
  useSession.getState().clear()
})
afterAll(() => server.close())

const api = createApi('http://station.test')

describe('the typed client', () => {
  it('returns the data of a successful call', async () => {
    server.use(
      http.get('http://station.test/api/whoami', () => HttpResponse.json({ role: 'operator' })),
    )
    expect(await call(api.GET('/api/whoami'))).toEqual({ role: 'operator' })
  })

  it('asks for the texts of the server in the language on screen', async () => {
    const asked: (string | null)[] = []
    server.use(
      http.get('http://station.test/api/whoami', ({ request }) => {
        asked.push(request.headers.get('Accept-Language'))
        return HttpResponse.json({ role: 'operator' })
      }),
    )
    try {
      await call(api.GET('/api/whoami'))
      useLocale.setState({ locale: 'en' })
      await call(api.GET('/api/whoami'))
    } finally {
      useLocale.setState({ locale: 'pt-BR' })
    }
    expect(asked).toEqual(['pt-BR', 'en'])
  })

  it('turns an error answer into an ApiError with the message and the code', async () => {
    server.use(
      http.post('http://station.test/api/trigger', () =>
        HttpResponse.json(
          { detail: 'A estação não está pronta', code: 'station_not_ready' },
          { status: 409 },
        ),
      ),
    )
    const error = await call(api.POST('/api/trigger')).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'station_not_ready',
      message: 'A estação não está pronta',
    })
  })

  it('carries the field messages of a validation error', async () => {
    server.use(
      http.post('http://station.test/api/login', () =>
        HttpResponse.json(
          {
            detail: 'Dados inválidos',
            code: 'validation_error',
            fields: { password: 'Field required' },
          },
          { status: 422 },
        ),
      ),
    )
    const error = (await call(
      api.POST('/api/login', { body: { role: 'supervisor', password: '' } }),
    ).catch((e: unknown) => e)) as ApiError
    expect(error.fields).toEqual({ password: 'Field required' })
  })

  it('sends the token, and signs out when the server stops accepting it', async () => {
    let sent: string | null = null
    server.use(
      http.get('http://station.test/api/jobs', ({ request }) => {
        sent = request.headers.get('authorization')
        return HttpResponse.json(
          { detail: 'É preciso entrar', code: 'login_required' },
          { status: 401 },
        )
      }),
    )
    useSession.getState().signIn('tok123', 'supervisor', 3600)
    await call(api.GET('/api/jobs')).catch(() => undefined)
    expect(sent).toBe('Bearer tok123')
    expect(useSession.getState()).toMatchObject({ token: null, role: 'operator', expired: true })
  })
})

describe('the session store', () => {
  it('keeps the role and the token until it is cleared', () => {
    useSession.getState().signIn('t', 'maintainer', 60)
    expect(useSession.getState()).toMatchObject({ token: 't', role: 'maintainer' })
    useSession.getState().clear()
    expect(useSession.getState()).toMatchObject({ token: null, role: 'operator' })
  })
})
