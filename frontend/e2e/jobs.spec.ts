import { accessibilityProblems, expect, signInAs, test } from './fixtures'

const JOB = 'Tampa azul — etiqueta de lote (demo)'

for (const scheme of ['dark', 'light'] as const) {
  test.describe(`jobs, ${scheme}`, () => {
    test.beforeEach(async ({ page }) => page.emulateMedia({ colorScheme: scheme }))

    test('the list, a job and its dialogs have no accessibility violations', async ({
      page,
      request,
      station,
    }) => {
      void station
      await signInAs(page, request, 'maintainer')
      await page.goto('/jobs')
      const row = page.getByRole('row').filter({ hasText: JOB })
      await expect(row).toContainText('ativo: v1')
      expect(await accessibilityProblems(page)).toEqual([])

      await page.getByRole('button', { name: 'Importar arquivo' }).click()
      await expect(page.getByRole('dialog', { name: 'Importar arquivo' })).toBeVisible()
      expect(await accessibilityProblems(page)).toEqual([])
      await page.keyboard.press('Escape')

      await row.getByRole('link', { name: JOB }).click()
      await expect(page.getByRole('heading', { level: 1, name: JOB })).toBeVisible()
      await expect(
        page.getByRole('list', { name: 'Versões' }).getByRole('button', { name: 'Ativar' }),
      ).toBeDisabled()
      expect(await accessibilityProblems(page)).toEqual([])
    })
  })
}

test('a backup is made and listed, and a job exported downloads a .vjob', async ({
  page,
  request,
  station,
}) => {
  void station
  await signInAs(page, request, 'supervisor')
  await page.goto('/jobs')
  await page.getByRole('button', { name: 'Fazer backup' }).click()
  await expect(page.getByText(/^Backup backup_.*\.vbak \(.+\) gravado\.$/)).toBeVisible()
  await page.getByRole('button', { name: 'Backups…' }).click()
  await expect(
    page.getByRole('dialog', { name: 'Backups' }).getByRole('button', { name: /^Baixar backup_/ }),
  ).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: `Ações de ${JOB}` }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('menuitem', { name: 'Exportar .vjob' }).click()
  expect((await download).suggestedFilename()).toMatch(/_v1\.vjob$/)
})
