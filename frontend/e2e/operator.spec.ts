import type { Page } from '@playwright/test'
import { expect, test, watchTheBrowser } from './fixtures'

// Camera -> controller -> API -> socket -> screen, as the operator sees it.

const verdict = (page: Page) => page.getByRole('status', { name: 'Resultado' })

test('shows the job, the connection and what the station is waiting for', async ({
  page,
  station,
}) => {
  void station
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText(
    'Tampa azul — etiqueta de lote (demo)',
  )
  await expect(page.getByRole('button', { name: 'Sistema: conectado' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Câmera: ok' })).toBeVisible()
  await expect(verdict(page)).toContainText('Aguardando peça')
})

test('an object that passes is APROVADO, counted once, and the screen waits again when it is taken away', async ({
  page,
  station,
}) => {
  await page.goto('/')
  const before = (await station.state()).counters
  await station.object('on')
  await expect(verdict(page)).toContainText('APROVADO', { timeout: 15_000 })
  await expect(
    page
      .getByRole('list', { name: 'Últimos resultados' })
      .getByRole('button', { name: /^Aprovado/ })
      .last(),
  ).toBeVisible()
  await station.object('off')
  await expect(verdict(page)).toContainText('Aguardando peça', { timeout: 15_000 })
  const after = (await station.state()).counters
  expect(after.PASS).toBe(before.PASS + 1) // inspected once, not once per frame
  expect(after.total).toBe(before.total + 1)
})

test('a failure is REPROVADO with its reason', async ({ page, station }) => {
  await page.goto('/')
  await station.outcome('FAIL')
  await station.object('on')
  await expect(verdict(page)).toContainText('REPROVADO', { timeout: 15_000 })
  await expect(verdict(page)).toContainText('Tampa fora da cor em 40% da área')
})

test('an error is ERRO and never shown as a pass', async ({ page, station }) => {
  await page.goto('/')
  await station.outcome('ERROR')
  await station.object('on')
  await expect(verdict(page)).toContainText('ERRO', { timeout: 15_000 })
  await expect(verdict(page)).toContainText('Imagem fora do padrão')
  await expect(verdict(page)).not.toContainText('APROVADO')
})

test('a result can be marked as wrong from the screen, with no login', async ({
  page,
  station,
}) => {
  await page.goto('/')
  await station.outcome('FAIL')
  await station.object('on')
  await expect(verdict(page)).toContainText('REPROVADO', { timeout: 15_000 })
  await page.getByRole('button', { name: 'Resultado incorreto?' }).click()
  const dialog = page.getByRole('dialog', { name: 'Este resultado estava errado?' })
  await expect(dialog).toContainText('O sistema disse REPROVADO')
  await dialog.getByRole('button', { name: 'Estava OK' }).click()
  await expect(
    page.getByText('Marcado como incorreto. A imagem vai para o treinamento.'),
  ).toBeVisible()
})

test('without a connection the screen says so instead of showing an old verdict', async ({
  page,
}) => {
  await page.routeWebSocket('**/api/live', (ws) => ws.close())
  await page.goto('/')
  await expect(verdict(page)).toContainText('Sem conexão')
  await expect(page.getByRole('button', { name: 'Inspecionar agora' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Câmera: desconhecido' })).toBeVisible()
})

test('a wrong address says so and offers the way back', async ({ page }) => {
  await page.goto('/jobs/abc')
  await expect(page.getByRole('heading', { name: 'Página não encontrada' })).toBeVisible()
  await page.getByRole('link', { name: 'Voltar para a estação' }).click()
  await expect(page).toHaveURL('/')
})

test('a page load is clean: no console error, no request that leaves this machine', async ({
  page,
}) => {
  const problems = watchTheBrowser(page)
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Sistema: conectado' })).toBeVisible()
  expect(problems).toEqual([])
})

test('the page is served with a strict content policy and the API refuses another origin', async ({
  page,
  request,
}) => {
  const response = await page.goto('/')
  const csp = response?.headers()['content-security-policy'] ?? ''
  expect(csp).toContain("script-src 'self'")
  expect(csp).not.toContain('unsafe-eval')
  expect(csp).toContain("frame-ancestors 'none'")
  const foreign = await request.get('/api/state', {
    headers: { Origin: 'http://evil.example.com' },
  })
  expect(foreign.status()).toBe(403)
  expect((await foreign.json()).code).toBe('origin_not_allowed')
})
