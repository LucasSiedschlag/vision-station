import { expect, signInAs, test } from './fixtures'

test('a wrong password says so; the right one opens the menu of the role; logout goes back to the station', async ({
  page,
  station,
}) => {
  void station
  await page.goto('/')
  await page.getByRole('button', { name: 'Entrar' }).click()
  const dialog = page.getByRole('dialog', { name: 'Entrar' })
  await dialog.getByLabel('Senha').fill('errada-errada')
  await dialog.getByRole('button', { name: 'Entrar' }).click()
  await expect(dialog.getByText('Perfil ou senha incorretos.')).toBeVisible()
  await dialog.getByLabel('Senha').fill('supervisor-pass')
  await dialog.getByRole('button', { name: 'Entrar' }).click()
  const nav = page.getByRole('navigation', { name: 'Menu' })
  await expect(nav.getByRole('link')).toHaveText([
    'Estação',
    'Jobs',
    'Resultados',
    'Auditoria',
    'Acessos',
    'Sobre',
  ])
  await page.getByRole('button', { name: 'Conta: Supervisor' }).click()
  await page.getByRole('menuitem', { name: 'Sair' }).click()
  await expect(nav).toBeHidden()
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
})

test('a screen for supervisors asks for the login first and opens after it', async ({
  page,
  station,
}) => {
  void station
  await page.goto('/about')
  const dialog = page.getByRole('dialog', { name: 'Entrar' })
  await expect(dialog).toBeVisible()
  await expect(page).toHaveURL('/')
  await dialog.getByLabel('Senha').fill('supervisor-pass')
  await dialog.getByRole('button', { name: 'Entrar' }).click()
  await expect(page).toHaveURL('/about')
  await expect(page.getByRole('heading', { name: 'Sobre' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'code', exact: true })).toBeVisible()
})

test('a session that the server ends keeps the screen and asks for the login over it', async ({
  page,
  request,
  station,
}) => {
  void station
  await signInAs(page, request, 'supervisor')
  await page.addInitScript(() =>
    sessionStorage.setItem(
      'vision-station-session',
      JSON.stringify({ token: 'revogado', role: 'supervisor', expires: Date.now() + 3600_000 }),
    ),
  )
  await page.goto('/about')
  await expect(page.getByRole('dialog', { name: 'Entrar' })).toContainText('Sua sessão terminou')
  await expect(page).toHaveURL('/about')
})

test('a person with a login who stops touching the screen is logged out after ten minutes', async ({
  page,
  request,
  station,
}) => {
  void station
  await signInAs(page, request, 'supervisor')
  await page.clock.install()
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Conta: Supervisor' })).toBeVisible()
  await page.clock.fastForward('10:05')
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible()
  await expect(page.getByText('Sessão encerrada por inatividade.')).toBeVisible()
})
