import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSession } from '@/api/session'
import { mockApi, renderApp, server } from '@/test/render'

mockApi()

const JOB = 'a1b2c3d4-0000-4000-8000-000000000001'
const jobsList = {
  jobs: [
    {
      id: JOB,
      name: 'Tampa azul',
      versions: [1, 2],
      latest: 2,
      updated_at: '2026-10-15T14:32:00-03:00',
      author: 'maintainer',
    },
    {
      id: 'other',
      name: 'Suporte — furos',
      versions: [1],
      latest: 1,
      updated_at: '2026-10-10T09:12:00-03:00',
      author: 'lucas',
    },
  ],
  active: { id: JOB, version: 1 },
}
const jobDetail = {
  id: JOB,
  name: 'Tampa azul',
  description: '',
  versions: [
    {
      version: 2,
      created_at: '2026-10-15T14:32:00-03:00',
      author: 'maintainer',
      notes: 'luz nova',
      parent_version: 1,
      active: false,
    },
    {
      version: 1,
      created_at: '2026-10-14T10:00:00-03:00',
      author: 'maintainer',
      notes: '',
      parent_version: null,
      active: true,
    },
  ],
}

async function firstVersion() {
  return within(await screen.findByRole('list', { name: 'Versões' })).getAllByRole('listitem')[0]!
}

function as(role: 'supervisor' | 'maintainer') {
  useSession.getState().signIn('tok', role, 3600)
}

beforeEach(() => {
  server.use(
    http.get('*/api/jobs', () => HttpResponse.json(jobsList)),
    http.get(`*/api/jobs/${JOB}`, () => HttpResponse.json(jobDetail)),
  )
})

describe('the jobs list', () => {
  it('shows each job with its active version, versions, last change and author', async () => {
    as('supervisor')
    renderApp('/jobs')
    const row = (await screen.findByRole('link', { name: 'Tampa azul' })).closest('tr')!
    expect(within(row).getByText('ativo: v1')).toBeInTheDocument()
    expect(within(row).getByText('2')).toBeInTheDocument()
    expect(within(row).getByText('15/10/2026, 14:32')).toBeInTheDocument()
    expect(within(row).getByText('Mantenedor')).toBeInTheDocument() // the role, not its id
    const other = screen.getByRole('link', { name: 'Suporte — furos' }).closest('tr')!
    expect(within(other).getByText('lucas')).toBeInTheDocument() // any other author as written
    expect(screen.getByRole('link', { name: 'Jobs' })).toHaveAttribute('aria-current', 'page')
  })

  it('a supervisor has no editor actions; a maintainer has them', async () => {
    as('supervisor')
    const { unmount } = renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Ações de Tampa azul' }))
    expect(screen.getByRole('menuitem', { name: 'Exportar .vjob' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: 'Editar' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Novo job' })).not.toBeInTheDocument()
    unmount()
    as('maintainer')
    renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Ações de Tampa azul' }))
    expect(screen.getByRole('menuitem', { name: 'Editar' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Duplicar' })).toBeInTheDocument()
  })

  it('says so when there are no jobs, and when the list cannot be read', async () => {
    as('supervisor')
    server.use(http.get('*/api/jobs', () => HttpResponse.json({ jobs: [], active: null })))
    const { unmount } = renderApp('/jobs')
    expect(await screen.findByRole('heading', { name: 'Nenhum job ainda' })).toBeInTheDocument()
    unmount()
    server.use(
      http.get('*/api/jobs', () =>
        HttpResponse.json({ detail: 'falhou', code: 'x' }, { status: 500 }),
      ),
    )
    renderApp('/jobs')
    expect(await screen.findByText('Não foi possível ler a lista de jobs.')).toBeInTheDocument()
  })

  it('imports a file and lists what it added; activating stays a separate step', async () => {
    let body = 0
    server.use(
      http.post('*/api/jobs/import', async ({ request }) => {
        body = (await request.arrayBuffer()).byteLength
        return HttpResponse.json({
          kind: 'backup',
          imported: [{ id: JOB, version: 3, status: 'renumbered', original_version: 2 }],
          active_was: { id: JOB, version: 3 },
          has_system_config: true,
        })
      }),
    )
    as('supervisor')
    renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Importar arquivo' }))
    const dialog = screen.getByRole('dialog', { name: 'Importar arquivo' })
    await userEvent.upload(
      within(dialog).getByLabelText('Solte o arquivo aqui ou escolha um'),
      new File(['abcd'], 'b.vbak'),
    )
    expect(await within(dialog).findByText('Arquivo importado')).toBeInTheDocument()
    expect(body).toBe(4)
    expect(within(dialog).getByText(/v3 \(era v2\) · renumerada/)).toBeInTheDocument()
    expect(within(dialog).getByText(/ative-a aqui depois de conferir/)).toBeInTheDocument()
  })

  it('a refused file shows the reason', async () => {
    server.use(
      http.post('*/api/jobs/import', () =>
        HttpResponse.json(
          { detail: 'Arquivo recusado: checksum', code: 'file_refused' },
          { status: 400 },
        ),
      ),
    )
    as('supervisor')
    renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Importar arquivo' }))
    await userEvent.upload(
      screen.getByLabelText('Solte o arquivo aqui ou escolha um'),
      new File(['x'], 'a.vjob'),
    )
    expect(await screen.findByRole('alert')).toHaveTextContent('Arquivo recusado: checksum')
  })

  it('makes a backup and lists the backups', async () => {
    server.use(
      http.post('*/api/backup', () =>
        HttpResponse.json({ name: 'backup_2026-10-15_1432.vbak', size: 2_500_000 }),
      ),
      http.get('*/api/backup', () =>
        HttpResponse.json({
          folder: 'E:/backups',
          backups: [
            {
              name: 'backup_2026-10-15_1432.vbak',
              size: 2_500_000,
              created_at: '2026-10-15T14:32:00-03:00',
            },
          ],
        }),
      ),
    )
    as('supervisor')
    renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Fazer backup' }))
    expect(
      await screen.findByText('Backup backup_2026-10-15_1432.vbak (2,4 MB) gravado.'),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Backups…' }))
    const dialog = await screen.findByRole('dialog', { name: 'Backups' })
    expect(within(dialog).getByText('Pasta: E:/backups')).toBeInTheDocument()
    expect(
      within(dialog).getByRole('button', { name: 'Baixar backup_2026-10-15_1432.vbak' }),
    ).toBeInTheDocument()
  })

  it('exports with the login, as a file download', async () => {
    let auth = ''
    server.use(
      http.get(`*/api/jobs/${JOB}/versions/2/export`, ({ request }) => {
        auth = request.headers.get('authorization') ?? ''
        return new HttpResponse(new Uint8Array([1, 2, 3]), {
          headers: { 'Content-Type': 'application/octet-stream' },
        })
      }),
    )
    const created = vi.fn(() => 'blob:x')
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }))
    as('supervisor')
    renderApp('/jobs')
    await userEvent.click(await screen.findByRole('button', { name: 'Ações de Tampa azul' }))
    await userEvent.click(screen.getByRole('menuitem', { name: 'Exportar .vjob' }))
    await waitFor(() => expect(created).toHaveBeenCalled())
    expect(auth).toBe('Bearer tok')
  })
})

describe('one job', () => {
  it('lists the versions newest first, with notes and the active one marked', async () => {
    as('supervisor')
    renderApp(`/jobs/${JOB}`)
    expect(await screen.findByRole('heading', { level: 1, name: 'Tampa azul' })).toBeInTheDocument()
    const items = within(screen.getByRole('list', { name: 'Versões' })).getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('v2')
    expect(items[0]).toHaveTextContent('luz nova')
    expect(items[0]).toHaveTextContent('a partir da v1')
    expect(items[0]).toHaveTextContent('Mantenedor')
    expect(items[0]).not.toHaveTextContent('maintainer')
    expect(within(items[1]!).getByText('Ativo')).toBeInTheDocument()
    expect(within(items[1]!).getByRole('button', { name: 'Ativar' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Abrir no editor' })).not.toBeInTheDocument()
  })

  it('activates a version after the verification', async () => {
    let sent: unknown = null
    server.use(
      http.post(`*/api/jobs/${JOB}/versions/2/activate`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ activated: true, verified: true, warnings: [], override: false })
      }),
    )
    as('supervisor')
    renderApp(`/jobs/${JOB}`)
    const v2 = await firstVersion()
    await userEvent.click(within(v2).getByRole('button', { name: 'Ativar' }))
    const confirm = screen.getByRole('alertdialog', { name: 'Ativar versão 2 de Tampa azul?' })
    await userEvent.click(within(confirm).getByRole('button', { name: 'Verificar e ativar' }))
    expect(await screen.findByText('Versão 2 de Tampa azul ativada.')).toBeInTheDocument()
    expect(sent).toEqual({})
  })

  it('a failed verification shows the report; only the maintainer may activate anyway, with a reason', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post(`*/api/jobs/${JOB}/versions/2/activate`, async ({ request }) => {
        const body = (await request.json()) as { override_reason?: string }
        bodies.push(body)
        if (!body.override_reason)
          return HttpResponse.json(
            {
              detail: 'O job não passou na verificação',
              code: 'verification_failed',
              problems: ['caso ok2.png: resultado FAIL, esperado PASS'],
              verified: false,
            },
            { status: 409 },
          )
        return HttpResponse.json({ activated: true, verified: false, warnings: [], override: true })
      }),
    )
    as('supervisor')
    const { unmount } = renderApp(`/jobs/${JOB}`)
    await userEvent.click(within(await firstVersion()).getByRole('button', { name: 'Ativar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Verificar e ativar' }))
    const report = await screen.findByRole('dialog', { name: 'Ativar versão 2 de Tampa azul?' })
    expect(
      within(report).getByText('caso ok2.png: resultado FAIL, esperado PASS'),
    ).toBeInTheDocument()
    expect(
      within(report).queryByRole('button', { name: 'Ativar mesmo assim' }),
    ).not.toBeInTheDocument()
    unmount()

    as('maintainer')
    renderApp(`/jobs/${JOB}`)
    await userEvent.click(within(await firstVersion()).getByRole('button', { name: 'Ativar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Verificar e ativar' }))
    const again = await screen.findByRole('dialog', { name: 'Ativar versão 2 de Tampa azul?' })
    const override = within(again).getByRole('button', { name: 'Ativar mesmo assim' })
    expect(override).toBeDisabled()
    await userEvent.type(
      within(again).getByLabelText(/Motivo/),
      'referência antiga, conferido na bancada',
    )
    await userEvent.click(override)
    await waitFor(() =>
      expect(bodies.at(-1)).toEqual({ override_reason: 'referência antiga, conferido na bancada' }),
    )
  })

  it('compares two versions', async () => {
    server.use(
      http.get(`*/api/jobs/${JOB}/versions/2/diff`, ({ request }) =>
        HttpResponse.json({
          id: JOB,
          version: 2,
          against: Number(new URL(request.url).searchParams.get('against')),
          diff: '--- v1\n+++ v2\n-  name: A\n+  name: B\n',
        }),
      ),
    )
    as('supervisor')
    renderApp(`/jobs/${JOB}`)
    await userEvent.click(
      within(await firstVersion()).getByRole('button', { name: 'Comparar com…' }),
    )
    const diff = await screen.findByLabelText('Diferenças')
    expect(diff).toHaveTextContent('+ name: B') // toHaveTextContent collapses spaces
    expect(within(diff).getByText('+ name: B')).toHaveClass('text-ok-text')
  })

  it('a maintainer duplicates a version and lands on the new job', async () => {
    server.use(
      http.post(`*/api/jobs/${JOB}/duplicate`, () =>
        HttpResponse.json({ id: 'new-id', version: 1 }, { status: 201 }),
      ),
      http.get('*/api/jobs/new-id', () =>
        HttpResponse.json({
          ...jobDetail,
          id: 'new-id',
          name: 'Tampa azul (cópia)',
          versions: [jobDetail.versions[1]],
        }),
      ),
    )
    as('maintainer')
    const { router } = renderApp(`/jobs/${JOB}`)
    await userEvent.click(within(await firstVersion()).getByRole('button', { name: 'Duplicar' }))
    const dialog = screen.getByRole('dialog', { name: 'Duplicar job' })
    expect(within(dialog).getByLabelText(/Nome do job novo/)).toHaveValue('Tampa azul (cópia)')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Duplicar' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/jobs/new-id'))
  })
})
