import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { useLoginDialog } from '@/api/auth'
import { useLive } from '@/api/live'
import { useSession } from '@/api/session'
import { renderApp, server, setLive, stateFixture, mockApi } from '@/test/render'

mockApi()

const problem = (status: number, detail: string, code: string) =>
  HttpResponse.json({ detail, code }, { status })

function signIn(role: 'supervisor' | 'maintainer' = 'supervisor') {
  useSession.getState().signIn('tok', role, 3600)
}

describe('the operator screen, without a login', () => {
  it('says it is connecting before the first status, and shows no verdict', () => {
    renderApp('/')
    expect(screen.getByRole('status', { name: 'Resultado' })).toHaveTextContent('Conectando…')
    expect(screen.getByRole('button', { name: 'Sistema: conectando' })).toBeInTheDocument()
  })

  it('stands alone as a kiosk: job, lock button, the verdict, counters, the strip, and no menu', () => {
    setLive({ counters: { PASS: 2, FAIL: 1, ERROR: 0, total: 3 } })
    renderApp('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Tampa azul — etiqueta de lote',
    )
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Resultado' })).toHaveTextContent('Aguardando peça')
    expect(screen.getByText('Hoje')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Estado do sistema' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(screen.getByRole('main')).toBeInTheDocument()
  })

  it('the trigger is enabled for a ready station and sends the request', async () => {
    let called = 0
    server.use(
      http.post(
        '*/api/trigger',
        () => (called++, HttpResponse.json({ accepted: true }, { status: 202 })),
      ),
    )
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Inspecionar agora' }))
    await waitFor(() => expect(called).toBe(1))
  })

  it('the trigger is disabled while inspecting, and a refusal from the server is shown in words', async () => {
    setLive({ state: 'Inspecting' })
    const { unmount } = renderApp('/')
    expect(screen.getByRole('button', { name: 'Inspecionar agora' })).toBeDisabled()
    unmount()
    server.use(
      http.post('*/api/trigger', () =>
        problem(409, 'A estação não está pronta', 'station_not_ready'),
      ),
    )
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Inspecionar agora' }))
    expect(await screen.findByText('A estação não está pronta')).toBeInTheDocument()
  })

  it('a result is the word, the reason and the time; "wrong result?" appears and sends the right label', async () => {
    let body: unknown
    server.use(
      http.post(
        '*/api/results/:id/incorrect',
        async ({ request, params }) => (
          (body = { id: params.id, ...((await request.json()) as object) }),
          HttpResponse.json({})
        ),
      ),
    )
    setLive({
      state: 'ShowingResult',
      last_result: {
        outcome: 'FAIL',
        reason: 'Tampa fora da cor em 40% da área',
        scores: {},
        duration_ms: 290,
        at: '2026-10-14T14:31:02-03:00',
      },
      last_record_id: 'rec-9',
      counters: { PASS: 0, FAIL: 1, ERROR: 0, total: 1 },
      recent: [
        {
          outcome: 'FAIL',
          reason: 'Tampa fora da cor em 40% da área',
          at: '2026-10-14T14:31:02-03:00',
        },
      ],
    })
    renderApp('/')
    const panel = screen.getByRole('status', { name: 'Resultado' })
    expect(panel).toHaveTextContent('REPROVADO')
    expect(panel).toHaveTextContent('Tampa fora da cor em 40% da área')
    expect(panel).toHaveTextContent('290 ms')
    await userEvent.click(screen.getByRole('button', { name: 'Resultado incorreto?' }))
    const dialog = await screen.findByRole('dialog', { name: 'Este resultado estava errado?' })
    expect(dialog).toHaveTextContent('O sistema disse REPROVADO')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Estava OK' }))
    await waitFor(() => expect(body).toEqual({ id: 'rec-9', correct: 'PASS', by: '' }))
    expect(
      await screen.findByText('Marcado como incorreto. A imagem vai para o treinamento.'),
    ).toBeInTheDocument()
  })

  it('"wrong result?" is not offered for a result that was not recorded', () => {
    setLive({
      state: 'ShowingResult',
      last_result: { outcome: 'PASS', reason: '', scores: {}, duration_ms: 1, at: null },
      last_record_id: null,
    })
    renderApp('/')
    expect(screen.queryByRole('button', { name: 'Resultado incorreto?' })).not.toBeInTheDocument()
  })

  it('the last results strip lists what happened, each with its time and reason for a screen reader', () => {
    setLive({
      recent: [
        { outcome: 'PASS', reason: '', at: '2026-10-14T14:30:00-03:00' },
        { outcome: 'FAIL', reason: 'Tampa ausente', at: '2026-10-14T14:31:00-03:00' },
      ],
    })
    renderApp('/')
    const strip = screen.getByRole('list', { name: 'Últimos resultados' })
    expect(
      within(strip).getByRole('button', { name: /^Aprovado às \d\d:\d\d:\d\d$/ }),
    ).toBeInTheDocument()
    expect(
      within(strip).getByRole('button', { name: /^Reprovado às \d\d:\d\d:\d\d: Tampa ausente$/ }),
    ).toBeInTheDocument()
  })

  it('without a connection nothing is clickable that needs one, and the old verdict is marked as old', () => {
    setLive(
      {
        state: 'ShowingResult',
        last_result: { outcome: 'PASS', reason: '', scores: {}, duration_ms: 1, at: null },
        last_record_id: 'r',
      },
      false,
    )
    renderApp('/')
    expect(screen.getByRole('status', { name: 'Resultado' })).toHaveTextContent('Sem conexão')
    expect(screen.getByRole('button', { name: 'Inspecionar agora' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Resultado incorreto?' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sistema: sem conexão' })).toBeInTheDocument()
  })
})

describe('login', () => {
  it('opens from the lock button; a wrong password says so and clears the field', async () => {
    server.use(
      http.post('*/api/login', () =>
        problem(401, 'Perfil ou senha incorretos', 'wrong_credentials'),
      ),
    )
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    const dialog = await screen.findByRole('dialog', { name: 'Entrar' })
    const password = within(dialog).getByLabelText('Senha')
    await userEvent.type(password, 'errada')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entrar' }))
    expect(await within(dialog).findByText('Perfil ou senha incorretos.')).toBeInTheDocument()
    expect(password).toHaveValue('')
    expect(useSession.getState().role).toBe('operator')
  })

  it('too many wrong passwords says to wait', async () => {
    server.use(
      http.post('*/api/login', () =>
        problem(429, 'Muitas tentativas. Tente de novo em 30 s', 'locked'),
      ),
    )
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    const dialog = await screen.findByRole('dialog', { name: 'Entrar' })
    await userEvent.type(within(dialog).getByLabelText('Senha'), 'qualquer')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entrar' }))
    expect(await within(dialog).findByText(/Muitas tentativas/)).toBeInTheDocument()
  })

  it('a correct password signs in: the menu appears with only what the role may open, and the station stays one click away', async () => {
    server.use(
      http.post('*/api/login', () =>
        HttpResponse.json({ token: 'tok', role: 'supervisor', expires_in_s: 3600 }),
      ),
    )
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))
    const dialog = await screen.findByRole('dialog', { name: 'Entrar' })
    await userEvent.type(within(dialog).getByLabelText('Senha'), 'supervisor-pass')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entrar' }))
    const nav = await screen.findByRole('navigation', { name: 'Menu' })
    expect(
      within(nav)
        .getAllByRole('link')
        .map((l) => l.textContent),
    ).toEqual(['Estação', 'Jobs', 'Resultados', 'Auditoria', 'Acessos', 'Sobre'])
    expect(screen.getByRole('button', { name: 'Conta: Supervisor' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Entrar' })).not.toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Estado do sistema' })).toBeInTheDocument() // the strip is now in the shell footer, once
  })

  it('logging out returns to the station without a menu', async () => {
    server.use(http.post('*/api/logout', () => HttpResponse.json({ ok: true })))
    signIn()
    setLive()
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Conta: Supervisor' }))
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Sair' }))
    await waitFor(() =>
      expect(screen.queryByRole('navigation', { name: 'Menu' })).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })
})

describe('screens by role', () => {
  it('a supervisor opens the screen straight away; a loading skeleton, then the data', async () => {
    server.use(
      http.get('*/api/about', () =>
        HttpResponse.json({ version: '9.9.9', job_format: 1, tools: [] }),
      ),
    )
    signIn()
    setLive()
    renderApp('/about')
    expect(await screen.findByText('9.9.9')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sobre' })).toHaveAttribute('aria-current', 'page')
  })

  it('a failed load shows what went wrong and a retry that works', async () => {
    let fail = true
    server.use(
      http.get('*/api/about', () =>
        fail
          ? problem(503, 'Falha ao ler', 'unavailable')
          : HttpResponse.json({ version: '1.2.3', job_format: 1, tools: [] }),
      ),
    )
    signIn()
    setLive()
    renderApp('/about')
    expect(
      await screen.findByText('Não foi possível ler as informações do programa.'),
    ).toBeInTheDocument()
    fail = false
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(await screen.findByText('1.2.3')).toBeInTheDocument()
  })

  it('a session that ends on a screen keeps the screen and opens the login over it', async () => {
    server.use(http.get('*/api/about', () => problem(401, 'É preciso entrar', 'login_required')))
    signIn()
    setLive()
    const { router } = renderApp('/about')
    expect(await screen.findByRole('dialog', { name: 'Entrar' })).toHaveAccessibleDescription(
      'Sua sessão terminou. Entre de novo para continuar.',
    )
    expect(router.state.location.pathname).toBe('/about')
    expect(screen.getByText('Sua sessão terminou')).toBeInTheDocument()
  })

  it('an address that does not exist says so and offers the way back', async () => {
    setLive()
    renderApp('/nope')
    expect(
      await screen.findByRole('heading', { name: /Página não encontrada/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar para a estação' })).toHaveAttribute('href', '/')
  })

  it('a screen that fails while it is built shows the plain message, a retry and the detail folded', async () => {
    useLive.setState({ status: stateFixture() as never, connected: true, connecting: false })
    server.use(
      http.get('*/api/about', () =>
        HttpResponse.json({ version: '1', job_format: 1, tools: null }),
      ),
    )
    signIn()
    renderApp('/about')
    expect(await screen.findByText('Esta tela falhou')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tentar de novo' })).toBeInTheDocument()
    expect(screen.queryByText(/TypeError/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Detalhes' }))
    expect(screen.getByText(/TypeError/)).toBeInTheDocument()
  })

  // last in the group: it ends with the login dialog just closed, and a Radix modal leaves the next test's page marked inert
  it('a screen for supervisors sends a visitor back to the station with the login open, and goes there after the login', async () => {
    server.use(
      http.post('*/api/login', () =>
        HttpResponse.json({ token: 'tok', role: 'supervisor', expires_in_s: 3600 }),
      ),
      http.get('*/api/about', () =>
        HttpResponse.json({
          version: '0.1.0',
          job_format: 1,
          tools: [{ name: 'code', version: 1 }],
        }),
      ),
    )
    setLive()
    const { router } = renderApp('/about')
    const dialog = await screen.findByRole('dialog', { name: 'Entrar' })
    expect(router.state.location.pathname).toBe('/')
    expect(useLoginDialog.getState().next).toBe('/about')
    await userEvent.type(within(dialog).getByLabelText('Senha'), 'supervisor-pass')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Entrar' }))
    expect(await screen.findByRole('heading', { name: 'Sobre' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/about')
    expect(await screen.findByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'code' })).toBeInTheDocument()
  })
})

describe('the shell', () => {
  it('shows the offline banner to a logged-in person, and the job and version in the top bar', () => {
    signIn()
    setLive({}, false)
    renderApp('/')
    expect(screen.getByRole('alert')).toHaveTextContent('Sem conexão com o programa da estação')
    expect(screen.getByText('Tampa azul — etiqueta de lote')).toBeInTheDocument()
    expect(screen.getByText('v7')).toBeInTheDocument()
  })

  it('has a skip link to the content', () => {
    setLive()
    renderApp('/')
    expect(screen.getByRole('link', { name: 'Pular para o conteúdo' })).toHaveAttribute(
      'href',
      '#content',
    )
  })
})
