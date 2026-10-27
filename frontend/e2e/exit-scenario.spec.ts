import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, signInAs, test, watchTheBrowser } from './fixtures'

// The exit scenario of phase 1 (VIA-0094; docs/project-scope.md §7) for the part that needs no second PC: a job made on the
// screen is exported, imported into a clean installation, activated there (rule 4: it is verified first), and the station
// gives PASS and FAIL. The first station is the shared one of playwright.config.ts, the clean one is the third (--fresh).
// The inspection is the simulated station's, which the test controls: this checks the path, not the vision, which has its
// own tests. What needs the real bench (backup on another PC, a shift, a restart) is the checklist of docs/guias/.
const CLEAN = 'http://127.0.0.1:8782'
// unique on every run: the first station may be one left running, with the job of an earlier run in it
const NAME = `Cenário de saída ${Date.now().toString(36)}`

test('a job made on the screen is exported, imported into a clean installation, activated, and gives PASS and FAIL', async ({
  page,
  request,
  station,
  browser,
}) => {
  void station
  test.setTimeout(120_000) // a whole commissioning in one test
  const problems = watchTheBrowser(page)
  const file = join(mkdtempSync(join(tmpdir(), 'vs-exit-')), 'cenario.vjob')

  await test.step('make the job in the editor: reference, a tool, a good sample, validated, saved', async () => {
    await signInAs(page, request, 'maintainer')
    await page.goto('/jobs/new/edit')
    const steps = page.getByRole('navigation', { name: 'Passos do job' })
    const step = (name: RegExp) => steps.getByRole('button', { name })
    // the trigger of the bench: an object that comes into the area and stays still
    await page.getByRole('combobox', { name: 'Modo de disparo' }).click()
    await page.getByRole('option', { name: /Objeto parado na área/ }).click()
    await step(/^Amostras/).click()
    await page.getByRole('button', { name: 'Capturar a imagem de referência' }).click()
    await expect(page.getByText(/^Imagem de referência capturada/).first()).toBeVisible()

    await step(/^Ferramentas/).click()
    await page.getByRole('combobox', { name: 'Adicionar ferramenta' }).click()
    await page.getByRole('option', { name: /\(brightness\)/ }).click()
    await page.getByRole('button', { name: 'Adicionar', exact: true }).last().click()

    await step(/^Amostras/).click()
    await page.getByLabel('Nome da amostra').fill('boa-1')
    await page.getByRole('button', { name: 'Capturar amostra' }).click()
    await expect(page.getByRole('cell', { name: 'boa-1.png', exact: true })).toBeVisible()

    await step(/^Validar/).click()
    await page.getByRole('button', { name: 'Validar tudo' }).click()
    await expect(page.getByText(/como esperado/).first()).toBeVisible()

    await step(/^Salvar/).click()
    await page.getByLabel('Nome do job').fill(NAME)
    await page.getByRole('button', { name: 'Salvar…' }).last().click()
    const dialog = page.getByRole('dialog', { name: 'Salvar o job novo' })
    await dialog.getByLabel('O que mudou').fill('cenário de saída da fase 1')
    await dialog.getByRole('button', { name: 'Salvar…' }).click()
    await expect(page.getByRole('heading', { level: 1, name: NAME })).toBeVisible()
    await page.goto('/jobs') // leaving the editor ends its session and the station goes back to production
    await expect(page.getByRole('row').filter({ hasText: NAME })).toBeVisible()
  })

  await test.step('export it as a .vjob', async () => {
    await page.getByRole('button', { name: `Ações de ${NAME}` }).click()
    const download = page.waitForEvent('download')
    await page.getByRole('menuitem', { name: 'Exportar .vjob' }).click()
    const saved = await download
    expect(saved.suggestedFilename()).toMatch(/_v1\.vjob$/)
    await saved.saveAs(file)
  })

  // the other PC: an installation with an empty data folder, where nothing has ever been set up
  const other = await browser.newContext({ baseURL: CLEAN, locale: 'pt-BR', timezoneId: 'America/Sao_Paulo' })
  try {
    const clean = await other.newPage()
    const cleanProblems = watchTheBrowser(clean)

    await test.step('on the clean installation: the Maintainer exists, there is no job and none is active', async () => {
      const made = await other.request.put('/api/setup/maintainer-password', { data: { password: 'maintainer-pass' } })
      expect(made.ok()).toBe(true)
      await signInAs(clean, other.request, 'maintainer')
      await clean.goto('/jobs')
      // an installation that is not set up offers the wizard once; the person goes to Jobs, where the file is imported
      await expect(clean.getByRole('heading', { level: 1, name: 'Instalação da estação' })).toBeVisible()
      await clean.getByRole('navigation', { name: 'Menu' }).getByRole('link', { name: 'Jobs' }).click()
      await expect(clean.getByRole('heading', { level: 1, name: 'Jobs' })).toBeVisible()
      await expect(clean.getByRole('row').filter({ hasText: NAME })).toHaveCount(0)
    })

    await test.step('import the file: the version is kept and not active yet', async () => {
      await clean.getByRole('button', { name: 'Importar arquivo' }).click()
      const dialog = clean.getByRole('dialog', { name: 'Importar arquivo' })
      await dialog.getByLabel('Solte o arquivo aqui ou escolha um').setInputFiles(file)
      await expect(dialog.getByText('Arquivo importado')).toBeVisible()
      await clean.keyboard.press('Escape')
      const row = clean.getByRole('row').filter({ hasText: NAME })
      await expect(row).toBeVisible()
      await expect(row).not.toContainText('ativo: v1')
    })

    await test.step('activate it: it is verified first, with its reference image and its reference set', async () => {
      await clean.getByRole('row').filter({ hasText: NAME }).getByRole('link', { name: NAME }).click()
      await expect(clean.getByRole('heading', { level: 1, name: NAME })).toBeVisible()
      await clean.getByRole('list', { name: 'Versões' }).getByRole('listitem').first().getByRole('button', { name: 'Ativar' }).click()
      const confirm = clean.getByRole('alertdialog', { name: `Ativar versão 1 de ${NAME}?` })
      await confirm.getByRole('button', { name: 'Verificar e ativar' }).click()
      await expect(clean.getByText(`Versão 1 de ${NAME} ativada.`)).toBeVisible()
    })

    await test.step('the station of the clean installation gives PASS and FAIL for the job it brought', async () => {
      const verdict = clean.getByRole('status', { name: 'Resultado' })
      await clean.goto('/')
      await expect(clean.getByRole('banner')).toContainText(NAME)
      await expect(verdict).toContainText('Aguardando objeto', { timeout: 20_000 })

      await other.request.post('/__e2e/object/on')
      await expect(verdict).toContainText('APROVADO', { timeout: 15_000 })
      await other.request.post('/__e2e/object/off')
      await expect(verdict).toContainText('Aguardando objeto', { timeout: 15_000 })

      await other.request.post('/__e2e/outcome/FAIL')
      await other.request.post('/__e2e/object/on')
      await expect(verdict).toContainText('REPROVADO', { timeout: 15_000 })
      await other.request.post('/__e2e/object/off')
      await expect(verdict).toContainText('Aguardando objeto', { timeout: 15_000 })
      const state = await (await other.request.get('/api/state')).json()
      expect(state.counters).toMatchObject({ PASS: 1, FAIL: 1, ERROR: 0, total: 2 }) // each object inspected once
    })
    expect(cleanProblems).toEqual([])
  } finally {
    await other.close()
  }
  expect(problems).toEqual([])
})
