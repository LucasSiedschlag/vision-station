import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSession } from '@/api/session'
import { mockApi, renderApp, server } from '@/test/render'

mockApi()

/* eslint-disable @typescript-eslint/no-explicit-any -- request bodies in the mocks */

const as = (role: 'supervisor' | 'maintainer') => useSession.getState().signIn('tok', role, 3600)
const record = (over: Record<string, unknown> = {}) => ({
  id: 'r1',
  at: '2026-10-15T14:32:07-03:00',
  job_id: 'j1',
  job_name: 'Tampa azul',
  job_version: 3,
  outcome: 'FAIL',
  reason: 'Tampa ausente',
  scores: { tampa: 0.2 },
  timings: { quality: 0.01, tools: 0.2, total: 0.25 },
  duration_ms: 250,
  image_path: 'results/images/r1.jpg',
  overlay_path: 'results/images/r1.overlay.jpg',
  sampled: true,
  correct_outcome: null,
  corrected_at: null,
  corrected_by: null,
  ...over,
})

beforeEach(() => {
  server.use(
    http.get('*/api/jobs', () =>
      HttpResponse.json({
        jobs: [
          { id: 'j1', name: 'Tampa azul', versions: [3], latest: 3, updated_at: '', author: '' },
        ],
        active: null,
      }),
    ),
  )
  vi.stubGlobal(
    'URL',
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() }),
  )
})

describe('results', () => {
  it('lists the results with the filters in the address, and asks the server with them', async () => {
    const queries: URLSearchParams[] = []
    server.use(
      http.get('*/api/results', ({ request }) => {
        queries.push(new URL(request.url).searchParams)
        return HttpResponse.json({ total: 1, results: [record()] })
      }),
    )
    as('supervisor')
    const { router } = renderApp('/results')
    expect(await screen.findByText('Tampa ausente')).toBeInTheDocument()
    expect(screen.getByText('Tampa azul · v3')).toBeInTheDocument()
    expect(queries[0]!.get('since')).toBeTruthy() // today by default
    await userEvent.click(screen.getByRole('combobox', { name: 'Resultado' }))
    await userEvent.click(screen.getByRole('option', { name: 'Reprovadas' }))
    await waitFor(() => expect(queries.at(-1)!.get('outcome')).toBe('FAIL'))
    expect(router.state.location.search).toContain('outcome=FAIL')
    await userEvent.click(screen.getByRole('radio', { name: 'Tudo' }))
    await waitFor(() => expect(queries.at(-1)!.get('since')).toBeNull())
  })

  it('opens a result: the image with the regions, the scores, and marks it as wrong', async () => {
    let image = ''
    let marked: any = null
    server.use(
      http.get('*/api/results', () => HttpResponse.json({ total: 1, results: [record()] })),
      http.get('*/api/results/r1/image', ({ request }) => {
        image = request.url
        return new HttpResponse(new Uint8Array([1]), { headers: { 'Content-Type': 'image/jpeg' } })
      }),
      http.post('*/api/results/r1/incorrect', async ({ request }) => {
        marked = await request.json()
        return HttpResponse.json(record({ correct_outcome: 'PASS' }))
      }),
    )
    as('supervisor')
    renderApp('/results')
    await userEvent.click(await screen.findByRole('button', { name: /^Abrir o resultado de/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Resultado' })
    await waitFor(() => expect(image).toContain('overlay=true'))
    expect(within(sheet).getByText('tampa: 0,2')).toBeInTheDocument()
    await userEvent.click(within(sheet).getByRole('radio', { name: 'Original' }))
    await waitFor(() => expect(image).not.toContain('overlay'))
    await userEvent.click(
      within(sheet).getByRole('button', { name: /Marcar como incorreto: Estava Aprovado/ }),
    )
    await waitFor(() => expect(marked).toEqual({ correct: 'PASS', by: 'supervisor' }))
  })

  it('says when the image was not kept, and when there is nothing', async () => {
    server.use(
      http.get('*/api/results', () =>
        HttpResponse.json({
          total: 1,
          results: [record({ image_path: null, overlay_path: null })],
        }),
      ),
    )
    as('supervisor')
    const { unmount } = renderApp('/results')
    await userEvent.click(await screen.findByRole('button', { name: /^Abrir o resultado de/ }))
    expect(await screen.findByText(/não foi guardada/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Marcar como incorreto/ })).not.toBeInTheDocument()
    unmount()
    server.use(http.get('*/api/results', () => HttpResponse.json({ total: 0, results: [] })))
    renderApp('/results')
    expect(
      await screen.findByRole('heading', { name: 'Nenhum resultado neste período' }),
    ).toBeInTheDocument()
  })

  it('pages through the results', async () => {
    const offsets: (string | null)[] = []
    server.use(
      http.get('*/api/results', ({ request }) => {
        offsets.push(new URL(request.url).searchParams.get('offset'))
        return HttpResponse.json({ total: 250, results: [record()] })
      }),
    )
    as('supervisor')
    renderApp('/results')
    expect(await screen.findByText('1–100 de 250')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Próxima página' }))
    expect(await screen.findByText('101–200 de 250')).toBeInTheDocument()
    expect(offsets.at(-1)).toBe('100')
  })
})

describe('dataset', () => {
  it('turns collection on for a job and exports its images', async () => {
    let collection: any = null
    server.use(
      http.get('*/api/dataset', () =>
        HttpResponse.json({
          jobs: [{ job_id: 'j1', name: 'Tampa azul', collecting: false, images: 12 }],
          total: 12,
        }),
      ),
      http.post('*/api/collection/j1', async ({ request }) => {
        collection = await request.json()
        return HttpResponse.json({ job_id: 'j1', enabled: true, dataset_images: 12 })
      }),
      http.post('*/api/dataset/export', () =>
        HttpResponse.json({ dataset_id: 'ds-1', folder: 'C:/dados/exports/ds-1', count: 12 }),
      ),
    )
    as('maintainer')
    renderApp('/dataset')
    await userEvent.click(
      await screen.findByRole('switch', { name: 'Modo de coleta de Tampa azul' }),
    )
    await waitFor(() => expect(collection).toEqual({ enabled: true }))
    await userEvent.click(screen.getByRole('button', { name: 'Exportar o dataset de Tampa azul' }))
    expect(
      await screen.findByText('Dataset ds-1: 12 imagens em C:/dados/exports/ds-1', {
        selector: 'p',
      }),
    ).toBeInTheDocument()
  })
})

describe('settings', () => {
  const system = {
    config: {
      format: 1,
      station: { name: 'Linha 2', shift_starts: ['06:00'], idle_logout_min: 10, fail_sound: false },
      camera: { driver: 'uvc', connection: { device_name: 'C920' }, keyring_entry: null },
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
    restart_pending: ['camera'],
    camera_drivers: ['file', 'uvc'],
    last_backup_error: null,
  }

  it('shows what needs a restart, saves the changes and tests a folder', async () => {
    let put: any = null
    server.use(
      http.get('*/api/system', () => HttpResponse.json(system)),
      http.put('*/api/system', async ({ request }) => {
        put = await request.json()
        return HttpResponse.json({ changed: ['station', 'backup'], restart_required: [] })
      }),
      http.post('*/api/system/test-folder', () =>
        HttpResponse.json({ ok: true, message: 'Pasta gravável, 120,5 GB livres', free_gb: 120.5 }),
      ),
    )
    as('maintainer')
    renderApp('/settings')
    expect(
      await screen.findByText(/só valem depois de reiniciar o programa: câmera/),
    ).toBeInTheDocument()
    expect(screen.getByText('Pasta de dados: C:/ProgramData/VisionSystem')).toBeInTheDocument()
    expect(screen.getByLabelText('Nome do dispositivo')).toHaveValue('C920')
    await userEvent.clear(screen.getByLabelText('Nome da estação'))
    await userEvent.type(screen.getByLabelText('Nome da estação'), 'Embalagem')
    await userEvent.type(screen.getByLabelText('Pasta de backup'), 'E:/backups')
    await userEvent.click(screen.getByRole('button', { name: 'Testar pasta' }))
    expect(await screen.findByText('Pasta gravável, 120,5 GB livres')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar configurações' }))
    await waitFor(() => expect(put?.station.name).toBe('Embalagem'))
    expect(put.backup.folder).toBe('E:/backups')
    expect(await screen.findByText('Configurações salvas: estação, backup.')).toBeInTheDocument()
  })
})

describe('access', () => {
  const users = {
    users: [
      { role: 'supervisor', has_password: true, changed_at: '2026-10-15T10:00:00-03:00' },
      { role: 'maintainer', has_password: true, changed_at: null },
    ],
  }

  it('a supervisor changes only their own password, confirming the old one', async () => {
    let body: any = null
    server.use(
      http.get('*/api/users', () => HttpResponse.json(users)),
      http.put('*/api/users/supervisor/password', async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(users.users[0])
      }),
    )
    as('supervisor')
    renderApp('/access')
    expect(
      await screen.findByRole('button', { name: 'Trocar a senha do Supervisor' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Trocar a senha do Mantenedor' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Encerrar todas as sessões' }),
    ).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Trocar a senha do Supervisor' }))
    const dialog = screen.getByRole('dialog')
    await userEvent.type(within(dialog).getByLabelText(/Senha atual/), 'velha-senha')
    await userEvent.type(within(dialog).getByLabelText(/^Senha nova/), 'nova-senha-1')
    await userEvent.type(within(dialog).getByLabelText(/Repita/), 'nova-senha-2')
    expect(within(dialog).getByText('As duas senhas não são iguais.')).toBeInTheDocument()
    await userEvent.clear(within(dialog).getByLabelText(/Repita/))
    await userEvent.type(within(dialog).getByLabelText(/Repita/), 'nova-senha-1')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Trocar' }))
    await waitFor(() =>
      expect(body).toEqual({ password: 'nova-senha-1', current_password: 'velha-senha' }),
    )
    await waitFor(() => expect(useSession.getState().role).toBe('operator')) // a new password ends the own session
  })

  it('the maintainer ends every session', async () => {
    server.use(
      http.get('*/api/users', () => HttpResponse.json(users)),
      http.post('*/api/users/sessions/revoke', () => HttpResponse.json({ revoked: 3 })),
    )
    as('maintainer')
    renderApp('/access')
    await userEvent.click(await screen.findByRole('button', { name: 'Encerrar todas as sessões' }))
    await userEvent.click(
      within(screen.getByRole('alertdialog')).getByRole('button', {
        name: 'Encerrar todas as sessões',
      }),
    )
    expect(await screen.findByText('3 sessões encerradas.')).toBeInTheDocument()
    expect(useSession.getState().expired).toBe(true)
  })
})

describe('audit', () => {
  it('lists events in plain words and filters by kind', async () => {
    const kinds: (string | null)[] = []
    server.use(
      http.get('*/api/audit', ({ request }) => {
        kinds.push(new URL(request.url).searchParams.get('kind'))
        return HttpResponse.json({
          total: 1,
          events: [
            {
              at: '2026-10-15T14:00:00-03:00',
              kind: 'activate_override',
              data: { job_id: 'j1', version: 3, reason: 'conferido na bancada' },
            },
          ],
        })
      }),
    )
    as('supervisor')
    renderApp('/audit')
    expect(await screen.findByText('Job ativado sem passar na verificação')).toBeInTheDocument()
    expect(screen.getByText(/reason: conferido na bancada/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('combobox', { name: 'Evento' }))
    await userEvent.click(screen.getByRole('option', { name: 'Senha definida' }))
    await waitFor(() => expect(kinds.at(-1)).toBe('password_set'))
  })
})
