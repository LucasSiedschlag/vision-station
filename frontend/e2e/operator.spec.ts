import { expect, test, watchTheBrowser } from './fixtures'

// The operator screen is still the skeleton of VIA-0031; these tests check the live path end to end
// (camera -> controller -> API -> socket -> screen) and are rewritten for the designed screen in VIA-0033.

test('shows the job, the connection and what the station is waiting for', async ({
  page,
  station,
}) => {
  void station
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Conectado')
  await expect(page.getByText('Caixa M — fita vermelha (demo)')).toBeVisible()
  await expect(page.getByText('Aguardando caixa')).toBeVisible()
})

test('a box that passes is shown as a pass, once, and the screen waits again when it is taken away', async ({
  page,
  station,
}) => {
  await page.goto('/')
  const before = (await station.state()).counters
  await station.box('on')
  await expect(page.getByText('PASS', { exact: true })).toBeVisible({ timeout: 15_000 })
  await station.box('off')
  await expect(page.getByText('Aguardando caixa')).toBeVisible({ timeout: 15_000 })
  const after = (await station.state()).counters
  expect(after.PASS).toBe(before.PASS + 1) // inspected once, not once per frame
  expect(after.total).toBe(before.total + 1)
})

test('a failure shows its reason', async ({ page, station }) => {
  await page.goto('/')
  await station.outcome('FAIL')
  await station.box('on')
  await expect(page.getByText('FAIL: Fita ausente em 40% da emenda')).toBeVisible({
    timeout: 15_000,
  })
})

test('an error is never shown as a pass', async ({ page, station }) => {
  await page.goto('/')
  await station.outcome('ERROR')
  await station.box('on')
  await expect(page.getByText('ERROR: Imagem fora do padrão')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('PASS', { exact: true })).toHaveCount(0)
})

test('the counters follow the results', async ({ page, station }) => {
  await page.goto('/')
  const before = (await station.state()).counters
  await station.outcome('FAIL')
  await station.box('on')
  await expect(page.getByText('FAIL:', { exact: false })).toBeVisible({ timeout: 15_000 })
  const expected = `${before.total + 1} · ${before.PASS} · ${before.FAIL + 1} · ${before.ERROR}`
  await expect(page.getByText(expected)).toBeVisible()
})

test('a client route opens on reload, and a wrong one says so', async ({ page }) => {
  await page.goto('/jobs/abc')
  await expect(page.getByRole('heading', { name: 'Página não encontrada' })).toBeVisible()
  await page.getByRole('link', { name: 'Vision Station' }).click()
  await expect(page).toHaveURL('/')
})

test('a page load is clean: no console error, no request that leaves this machine', async ({
  page,
}) => {
  const problems = watchTheBrowser(page)
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Conectado')
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
