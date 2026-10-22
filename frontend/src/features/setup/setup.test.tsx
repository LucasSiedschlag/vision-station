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
    server.use(http.get('*/api/setup/status', () => HttpResponse.json(status(['first_job']))))
    renderApp('/setup')
    expect(await screen.findByRole('heading', { name: 'Primeiro job' })).toBeInTheDocument()
    expect(screen.getAllByText('falta: first_job')).toHaveLength(2) // under the step and in its panel
    expect(screen.getByRole('link', { name: 'Criar o primeiro job' })).toHaveAttribute(
      'href',
      '/jobs/new/edit',
    )
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
    expect(screen.getByRole('link', { name: 'Criar o primeiro job' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Máquina/ }))
    expect(screen.getByRole('heading', { name: 'Máquina' })).toBeInTheDocument() // an unavailable step can be read too
    expect(screen.getByText('Ainda não disponível')).toBeInTheDocument()
    expect(screen.getAllByText('machine ainda não existe').length).toBeGreaterThan(0) // with its reason, and nothing to press
    expect(screen.queryByRole('link', { name: 'Abrir' })).not.toBeInTheDocument()
  })

  it('points the first job step to the list of jobs once there is one', async () => {
    as('maintainer')
    server.use(http.get('*/api/setup/status', () => HttpResponse.json(status(['camera']))))
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Primeiro job/ }))
    expect(screen.getByText('Já existe um job.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir os jobs' })).toHaveAttribute('href', '/jobs')
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

describe('the camera step', () => {
  const system = {
    config: {
      format: 1,
      station: {
        name: 'Linha 2',
        shift_starts: ['06:00'],
        idle_logout_min: 10,
        fail_sound: false,
        result_min_s: 2,
      },
      camera: {
        driver: 'uvc',
        connection: {},
        keyring_entry: null,
        settle_ms: 500,
        dead_after_s: 2,
      },
      recording: {
        pass_sample_every: 1,
        unsampled_pass_hours: null,
        retention_days: null,
        min_free_gb: null,
      },
      backup: { folder: null, every_hours: 24, keep: 30, include: 'all' },
      network: { host: '127.0.0.1', port: 8765, allowed_hosts: [], allowed_origins: [] },
    },
    data_root: 'C:/ProgramData/VisionSystem',
    restart_pending: [],
    camera_drivers: ['file', 'uvc'],
    last_backup_error: null,
  }
  const found = {
    available: true,
    cameras: [
      {
        name: 'HD Pro Webcam C920',
        driver: 'uvc',
        connection: { device_name: 'HD Pro Webcam C920' },
        model: 'c920',
        validated: true,
      },
      {
        name: 'Integrated Camera',
        driver: 'uvc',
        connection: { device_name: 'Integrated Camera' },
        model: null,
        validated: false,
      },
    ],
  }

  beforeEach(() => {
    as('maintainer')
    server.use(
      http.get('*/api/setup/open', () => HttpResponse.json({ open: false })),
      http.get('*/api/setup/status', () => HttpResponse.json(status(['camera', 'first_job']))),
      http.get('*/api/setup/cameras', () => HttpResponse.json(found)),
      http.get('*/api/system', () => HttpResponse.json(system)),
    )
  })

  it('lists the cameras to choose from, and says only validated or not validated', async () => {
    renderApp('/setup')
    expect(await screen.findByRole('radio', { name: /HD Pro Webcam C920/ })).toBeInTheDocument()
    expect(screen.getByText('Validada')).toBeInTheDocument()
    expect(screen.getByText('Não validada')).toBeInTheDocument() // the badge of the other one
    const pictures = Array.from(document.querySelectorAll('img')).map((img) =>
      img.getAttribute('src'),
    )
    expect(pictures[0]).toContain('c920') // the validated model has its own picture
    expect(pictures[1]).toContain('generic')
  })

  it('warns that a camera that is not validated needs the bench trial first', async () => {
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Integrated Camera/ }))
    expect(screen.getByText(/ensaio de bancada/)).toBeInTheDocument()
  })

  it('tests the chosen camera with its driver and device', async () => {
    let body: any
    server.use(
      http.post('*/api/system/test-camera', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({
          ok: true,
          message: 'Imagem de 1920×1080',
          width: 1920,
          height: 1080,
        })
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /HD Pro Webcam C920/ }))
    await user.click(screen.getByRole('button', { name: 'Testar câmera' }))
    expect(await screen.findByText('Imagem de 1920×1080')).toBeInTheDocument()
    expect(body.driver).toBe('uvc')
    expect(body.connection).toEqual({ device_name: 'HD Pro Webcam C920' })
  })

  it('saves the choice in the system configuration and says it needs a restart', async () => {
    let put: any
    server.use(
      http.put('*/api/system', async ({ request }) => {
        put = await request.json()
        return HttpResponse.json({ changed: ['camera'], restart_required: ['camera'] })
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /HD Pro Webcam C920/ }))
    await user.click(screen.getByRole('button', { name: 'Usar esta câmera' }))
    expect(await screen.findByText(/só vale depois de reiniciar o programa/)).toBeInTheDocument()
    expect(put.camera.driver).toBe('uvc')
    expect(put.camera.connection).toEqual({ device_name: 'HD Pro Webcam C920' })
    expect(put.station.name).toBe('Linha 2') // the rest of the configuration goes back as it was
  })

  it('picks the camera the installation already has', async () => {
    server.use(
      http.get('*/api/system', () =>
        HttpResponse.json({
          ...system,
          config: {
            ...system.config,
            camera: { ...system.config.camera, connection: { device_name: 'Integrated Camera' } },
          },
        }),
      ),
    )
    renderApp('/setup')
    expect(await screen.findByRole('radio', { name: /Integrated Camera/ })).toBeChecked()
  })

  it('says so when no camera is connected and offers to look again', async () => {
    let asked = 0
    server.use(
      http.get('*/api/setup/cameras', () => {
        asked++
        return HttpResponse.json({ available: true, cameras: [] })
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    expect(await screen.findByText(/Nenhuma câmera USB encontrada/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Procurar de novo' }))
    await waitFor(() => expect(asked).toBeGreaterThan(1))
  })

  it('sends a PC that cannot list cameras to the settings', async () => {
    server.use(
      http.get('*/api/setup/cameras', () => HttpResponse.json({ available: false, cameras: [] })),
    )
    renderApp('/setup')
    expect(await screen.findByText(/não consegue listar as câmeras/)).toBeInTheDocument()
  })
})

describe('the passwords and backup steps', () => {
  const system = {
    config: {
      format: 1,
      station: {
        name: 'Linha 2',
        shift_starts: ['06:00'],
        idle_logout_min: 10,
        fail_sound: false,
        result_min_s: 2,
      },
      camera: {
        driver: 'uvc',
        connection: {},
        keyring_entry: null,
        settle_ms: 500,
        dead_after_s: 2,
      },
      recording: {
        pass_sample_every: 1,
        unsampled_pass_hours: null,
        retention_days: null,
        min_free_gb: null,
      },
      backup: { folder: null, every_hours: 24, keep: 30, include: 'all' },
      network: { host: '127.0.0.1', port: 8765, allowed_hosts: [], allowed_origins: [] },
    },
    data_root: 'C:/ProgramData/VisionSystem',
    restart_pending: [],
    camera_drivers: ['file', 'uvc'],
    last_backup_error: null,
  }

  beforeEach(() => {
    as('maintainer')
    server.use(
      http.get('*/api/setup/open', () => HttpResponse.json({ open: false })),
      http.get('*/api/system', () => HttpResponse.json(system)),
    )
  })

  it('sets the Supervisor password and the step becomes done', async () => {
    let body: any
    let set = false
    server.use(
      http.get('*/api/setup/status', () =>
        HttpResponse.json(
          set
            ? status(['backup', 'first_job'])
            : status(['supervisor_password', 'backup', 'first_job']),
        ),
      ),
      http.put('*/api/users/supervisor/password', async ({ request }) => {
        body = await request.json()
        set = true
        return HttpResponse.json({ role: 'supervisor', has_password: true, changed_at: null })
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    expect(await screen.findByRole('heading', { name: 'Senha do Supervisor' })).toBeInTheDocument()
    await user.type(screen.getByLabelText(/^Senha do Supervisor/), 'outra-senha-boa')
    await user.type(screen.getByLabelText(/^Repita a senha/), 'outra-senha-boa')
    await user.click(screen.getByRole('button', { name: 'Definir a senha do Supervisor' }))
    await waitFor(() => expect(body?.password).toBe('outra-senha-boa'))
    // the wizard moves on to the next step to do, as the server now reports it
    expect(await screen.findByRole('heading', { name: 'Backup' })).toBeInTheDocument()
  })

  it('refuses two different Supervisor passwords before sending anything', async () => {
    let sent = 0
    server.use(
      http.get('*/api/setup/status', () =>
        HttpResponse.json(status(['supervisor_password', 'first_job'])),
      ),
      http.put('*/api/users/supervisor/password', () => {
        sent++
        return HttpResponse.json({})
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText(/^Senha do Supervisor/), 'uma-senha-boa')
    await user.type(screen.getByLabelText(/^Repita a senha/), 'uma-senha-diferente')
    await user.click(screen.getByRole('button', { name: 'Definir a senha do Supervisor' }))
    expect(await screen.findByText('As duas senhas não são iguais.')).toBeInTheDocument()
    expect(sent).toBe(0)
  })

  it('says the Supervisor password is set when it is', async () => {
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json(status(['backup', 'first_job']))),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Senha do Supervisor/ }))
    expect(
      (await screen.findAllByText('A senha do Supervisor está definida.')).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getByRole('link', { name: 'Para trocar uma senha depois, use Acessos.' }),
    ).toHaveAttribute('href', '/access')
  })

  it('tests the backup folder first and saves it with how often', async () => {
    let put: any
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json(status(['backup', 'first_job']))),
      http.post('*/api/system/test-folder', () =>
        HttpResponse.json({ ok: true, message: 'Pasta gravável, 120,5 GB livres', free_gb: 120.5 }),
      ),
      http.put('*/api/system', async ({ request }) => {
        put = await request.json()
        return HttpResponse.json({ changed: ['backup'], restart_required: [] })
      }),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Pasta de backup'), 'E:/backups')
    expect(screen.getByRole('button', { name: 'Salvar a pasta de backup' })).toBeDisabled() // not before the test
    await user.click(screen.getByRole('button', { name: 'Testar pasta' }))
    expect(await screen.findByText('Pasta gravável, 120,5 GB livres')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar a pasta de backup' }))
    await waitFor(() => expect(put?.backup.folder).toBe('E:/backups'))
    expect(put.backup.every_hours).toBe(24)
    expect(put.backup.keep).toBe(30) // what the step does not ask goes back as it was
    expect(put.station.name).toBe('Linha 2')
  })

  it('does not let a folder that failed the test be saved', async () => {
    server.use(
      http.get('*/api/setup/status', () => HttpResponse.json(status(['backup', 'first_job']))),
      http.post('*/api/system/test-folder', () =>
        HttpResponse.json({
          ok: false,
          message: 'Não foi possível gravar na pasta: acesso negado',
        }),
      ),
    )
    renderApp('/setup')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Pasta de backup'), 'Z:/rede')
    await user.click(screen.getByRole('button', { name: 'Testar pasta' }))
    expect(await screen.findByText(/acesso negado/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar a pasta de backup' })).toBeDisabled()
  })
})
