import os from 'node:os'
import { accessibilityProblems, expect, test, watchTheBrowser } from './fixtures'

// The commissioning wizard (docs/frontend.md §7.11) on a clean installation: no passwords, no job, a camera that sends
// images. The station is the second one of playwright.config.ts (--fresh); the tests below use up its clean state, so
// they run in this order.
test.use({ baseURL: 'http://127.0.0.1:8781' })
test.describe.configure({ mode: 'serial' })

test('in English the first step has no accessibility violations and nothing is signed in', async ({
  page,
  request,
}) => {
  await request.post('/__e2e/language/en')
  await page.goto('/setup')
  await expect(page.getByRole('heading', { name: 'Station installation' })).toBeVisible()
  await expect(page.getByRole('heading', { name: "Maintainer's password" })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Create password and continue' })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])
  await request.post('/__e2e/language/pt-BR')
})

test('from a clean installation to the first job, without ever logging in first', async ({
  page,
  request,
}) => {
  const problems = watchTheBrowser(page)
  // the operator screen offers the wizard while it is open
  await page.goto('/')
  await expect(page.getByText('Esta instalação ainda não foi configurada.')).toBeVisible()
  await page.getByRole('link', { name: 'Configurar agora' }).click()

  // 1. the Maintainer's password: created here, and it signs the person in
  await expect(page).toHaveURL(/\/setup$/)
  await expect(page.getByRole('heading', { name: 'Senha do Mantenedor' })).toBeVisible()
  await page.getByLabel('Senha do Mantenedor').fill('curta')
  await page.getByLabel('Repita a senha').fill('curta')
  await page.getByRole('button', { name: 'Criar senha e continuar' }).click()
  await expect(page.getByText('Use pelo menos 8 caracteres.')).toBeVisible()
  await page.getByLabel('Senha do Mantenedor').fill('maintainer-pass')
  await page.getByLabel('Repita a senha').fill('maintainer-pass')
  await page.getByRole('button', { name: 'Criar senha e continuar' }).click()

  // the camera sends images, so the wizard goes on to the Supervisor's password
  await expect(page.getByRole('heading', { name: 'Senha do Supervisor' })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])
  await page.getByLabel('Senha do Supervisor').fill('supervisor-pass')
  await page.getByLabel('Repita a senha').fill('supervisor-pass')
  await page.getByRole('button', { name: 'Definir a senha do Supervisor' }).click()

  // backup: the folder is tested before it can be saved
  await expect(page.getByRole('heading', { name: 'Backup' })).toBeVisible()
  await page.getByLabel('Pasta de backup').fill(os.tmpdir())
  await page.getByRole('button', { name: 'Testar pasta' }).click()
  await page.getByRole('button', { name: 'Salvar a pasta de backup' }).click()

  // the first job, made in the editor; the step comes first, the later phases stay readable and unavailable
  await expect(page.getByRole('heading', { name: 'Primeiro job' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Criar o primeiro job' })).toHaveAttribute(
    'href',
    '/jobs/new/edit',
  )
  await page.getByRole('button', { name: /Máquina/ }).click()
  await expect(page.getByText('Ainda não disponível', { exact: true })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])

  // the editor has its own tests; here the job is saved as it would be, and the wizard sees it
  await request.post('/__e2e/demo-job')
  await page.reload()
  await expect(page.getByText('Instalação pronta. A estação já pode trabalhar.')).toBeVisible()
  await page.getByRole('button', { name: 'Ir para a estação' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText('Esta instalação ainda não foi configurada.')).toBeHidden()
  expect(problems).toEqual([])
})

test('once the Maintainer has a password the first one cannot be created again', async ({
  request,
}) => {
  const again = await request.put('/api/setup/maintainer-password', {
    data: { password: 'outra-senha-1' },
  })
  expect(again.status()).toBe(409)
  expect((await request.get('/api/setup/status')).status()).toBe(401)
})
