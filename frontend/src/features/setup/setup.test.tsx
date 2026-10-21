import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSession } from '@/api/session'
import { mockApi, renderApp, server } from '@/test/render'

mockApi()

/* eslint-disable @typescript-eslint/no-explicit-any -- request bodies in the mocks */

type Id =
  | 'maintainer_password'
  | 'camera'
  | 'performance'
  | 'supervisor_password'
  | 'machine'
  | 'backup'
  | 'first_job'
const ORDER: Id[] = [
  'maintainer_password',
  'camera',
  'performance',
  'supervisor_password',
  'machine',
  'backup',
  'first_job',
]

function status(todo: Id[], over: Record<string, unknown> = {}) {
  const steps = ORDER.map((id) => {
    if (id === 'performance' || id === 'machine')
      return { id, state: 'unavailable', detail: `${id} ainda não existe` }
    return todo.includes(id)
      ? { id, state: 'todo', detail: `falta: ${id}` }
      : { id, state: 'done', detail: null }
  })
  return {
    steps,
    needs_setup: todo.some((id) => ['maintainer_password', 'camera', 'first_job'].includes(id)),
    maintainer_password_missing: todo.includes('maintainer_password'),
    ...over,
  }
}

const as = (role: 'supervisor' | 'maintainer') => useSession.getState().signIn('tok', role, 3600)

beforeEach(() => {
  sessionStorage.clear()
})

describe('the notice on the operator screen', () => {
  it('shows the way into the wizard while the first password can be created', async () => {
    server.use(http.get('*/api/setup/open', () => HttpResponse.json({ open: true })))
    renderApp('/')
    const region = await screen.findByRole('region', { name: 'Instalação da estação' })
    expect(region).toHaveTextContent('ainda não foi configurada')
    expect(screen.getByRole('link', { name: 'Configurar agora' })).toHaveAttribute('href', '/setup')
  })

  it('is not there once the Maintainer has a password', async () => {
    server.use(http.get('*/api/setup/open', () => HttpResponse.json({ open: false })))
    renderApp('/')
    await waitFor(() => expect(screen.queryByText('Configurar agora')).not.toBeInTheDocument())
  })
})

describe('the wizard before there is a password', () => {
  beforeEach(() => {
    server.use(
      http.get('*/api/setup/open', () => HttpResponse.json({ open: true })),
      http.get('*/api/setup/status', () =>
        HttpResponse.json(
          status(['maintainer_password', 'camera', 'supervisor_password', 'backup', 'first_job']),
        ),
      ),
    )
  })

  it('opens without a login on the first step and locks the others', async () => {
    renderApp('/setup')
    expect(await screen.findByRole('heading', { name: 'Senha do Mantenedor' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^Senha do Mantenedor/)).toBeInTheDocument()
    expect(screen.getAllByText('Crie primeiro a senha do Mantenedor').length).toBeGreaterThan(0)
  })

  it('refuses a short password and two different ones, and sends nothing', async () => {
    let sent = 0
    server.use(
      http.put('*/api/setup/maintainer-password', () => {
        sent++
        return HttpResponse.json({})
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^Senha do Mantenedor/), 'curta')
    await user.type(screen.getByLabelText(/^Repita a senha/), 'outra')
    await user.click(screen.getByRole('button', { name: 'Criar senha e continuar' }))
    expect(await screen.findByText('Use pelo menos 8 caracteres.')).toBeInTheDocument()
    expect(screen.getByText('As duas senhas não são iguais.')).toBeInTheDocument()
    expect(sent).toBe(0)
  })

  it('creates the password, logs in with it and goes on to the next step', async () => {
    let body: any
    let created = false
    server.use(
      http.put('*/api/setup/maintainer-password', async ({ request }) => {
        body = await request.json()
        created = true
        return HttpResponse.json({ role: 'maintainer', has_password: true, changed_at: null })
      }),
      http.post('*/api/login', () =>
        HttpResponse.json({ token: 'tok', role: 'maintainer', expires_in_s: 3600 }),
      ),
      http.get('*/api/setup/open', () => HttpResponse.json({ open: !created })),
      http.get('*/api/setup/status', () =>
        HttpResponse.json(
          created
            ? status(['camera', 'supervisor_password', 'backup', 'first_job'])
            : status([
                'maintainer_password',
                'camera',
                'supervisor_password',
                'backup',
                'first_job',
              ]),
        ),
      ),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^Senha do Mantenedor/), 'uma-boa-senha')
    await user.type(screen.getByLabelText(/^Repita a senha/), 'uma-boa-senha')
    await user.click(screen.getByRole('button', { name: 'Criar senha e continuar' }))
    expect(await screen.findByRole('heading', { name: 'Câmera' })).toBeInTheDocument()
    expect(body).toEqual({ password: 'uma-boa-senha' })
    expect(useSession.getState().role).toBe('maintainer')
  })

  it('shows the reason when the server refuses', async () => {
    server.use(
      http.put('*/api/setup/maintainer-password', () =>
        HttpResponse.json(
          {
            detail: 'A senha inicial só pode ser criada no próprio PC da estação',
            code: 'not_local',
          },
          { status: 403 },
        ),
      ),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^Senha do Mantenedor/), 'uma-boa-senha')
    await user.type(screen.getByLabelText(/^Repita a senha/), 'uma-boa-senha')
    await user.click(screen.getByRole('button', { name: 'Criar senha e continuar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('só pode ser criada no próprio PC')
  })
})

describe('the wizard of an installation with a password', () => {
  beforeEach(() => {
    server.use(http.get('*/api/setup/open', () => HttpResponse.json({ open: false })))
  })

  it('asks for the Maintainer login', async () => {
    renderApp('/setup')
    expect(await screen.findByRole('dialog')).toBeInTheDocument() // back to the station with the login open
  })

  it('gives a Supervisor no access', async () => {
    as('supervisor')
    renderApp('/setup')
    expect(await screen.findByRole('heading', { name: 'Sem permissão' })).toBeInTheDocument()
  })

  it('opens on the first step to do, with the state the server gave, and a way to do it', async () => {
    as('maintainer')
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json(status(['camera', 'first_job']))),
    )
    renderApp('/setup')
    expect(await screen.findByRole('heading', { name: 'Câmera' })).toBeInTheDocument()
    expect(screen.getAllByText('falta: camera')).toHaveLength(2) // under the step and in its panel
    expect(screen.getByRole('link', { name: 'Abrir' })).toHaveAttribute('href', '/settings')
    expect(screen.getAllByText('performance ainda não existe').length).toBeGreaterThan(0) // an unavailable step says why
  })

  it('lets someone read another step', async () => {
    as('maintainer')
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json(status(['camera', 'first_job']))),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Primeiro job/ }))
    expect(screen.getByRole('heading', { name: 'Primeiro job' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir' })).toHaveAttribute('href', '/jobs')
  })

  it('says it is ready when nothing is missing', async () => {
    as('maintainer')
    server.use(http.get('*/api/setup/status', () => HttpResponse.json(status([]))))
    renderApp('/setup')
    expect(await screen.findByText(/Instalação pronta/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ir para a estação' })).toBeInTheDocument()
  })

  it('shows a way to read the state again when it cannot be read', async () => {
    as('maintainer')
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json({ detail: 'x' }, { status: 500 })),
    )
    renderApp('/setup')
    expect(
      await screen.findByText('Não foi possível ler o estado da instalação'),
    ).toBeInTheDocument()
  })
})

describe('after the Maintainer logs in', () => {
  beforeEach(() => {
    server.use(http.get('*/api/setup/open', () => HttpResponse.json({ open: false })))
  })

  it('opens the wizard once when the installation still needs it', async () => {
    as('maintainer')
    server.use(http.get('*/api/setup/status', () => HttpResponse.json(status(['camera']))))
    const { router } = renderApp('/jobs')
    await waitFor(() => expect(router.state.location.pathname).toBe('/setup'))
    await router.navigate('/jobs') // the person leaves it and is not taken back
    await new Promise((r) => setTimeout(r, 50))
    expect(router.state.location.pathname).toBe('/jobs')
  })

  it('leaves alone an installation that is ready', async () => {
    as('maintainer')
    server.use(http.get('*/api/setup/status', () => HttpResponse.json(status([]))))
    const { router } = renderApp('/jobs')
    await new Promise((r) => setTimeout(r, 100))
    expect(router.state.location.pathname).toBe('/jobs')
  })
})
