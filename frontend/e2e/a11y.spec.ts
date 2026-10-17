import { accessibilityProblems, expect, signInAs, test } from './fixtures'

const themes = ['dark', 'light'] as const
const outcomes = [
  { outcome: 'PASS', word: 'APROVADO' },
  { outcome: 'FAIL', word: 'REPROVADO' },
  { outcome: 'ERROR', word: 'ERRO' },
] as const

for (const scheme of themes) {
  test.describe(`operator screen, ${scheme}`, () => {
    test.beforeEach(async ({ page }) => page.emulateMedia({ colorScheme: scheme }))

    test('waiting has no accessibility violations', async ({ page, station }) => {
      void station
      await page.goto('/')
      await expect(page.getByRole('status', { name: 'Resultado' })).toContainText('Aguardando peça')
      expect(await accessibilityProblems(page)).toEqual([])
    })

    for (const { outcome, word } of outcomes) {
      test(`${word} has no accessibility violations`, async ({ page, station }) => {
        await page.goto('/')
        await station.outcome(outcome)
        await station.object('on')
        await expect(page.getByRole('status', { name: 'Resultado' })).toContainText(word, {
          timeout: 15_000,
        })
        expect(await accessibilityProblems(page)).toEqual([])
      })
    }

    test('the logged-in shell and the About screen have none', async ({
      page,
      request,
      station,
    }) => {
      void station
      await signInAs(page, request, 'supervisor')
      await page.goto('/about')
      await expect(page.getByRole('heading', { name: 'Sobre' })).toBeVisible()
      await expect(page.getByRole('cell', { name: 'code', exact: true })).toBeVisible()
      expect(await accessibilityProblems(page)).toEqual([])
    })

    test('the shell with the menu collapsed and the Ir para… palette open has none', async ({
      page,
      request,
      station,
    }) => {
      void station
      await signInAs(page, request, 'maintainer')
      await page.goto('/about')
      await page.getByRole('button', { name: 'Recolher menu' }).click()
      await expect(page.getByRole('button', { name: 'Expandir menu' })).toBeVisible()
      expect(await accessibilityProblems(page)).toEqual([])
      await page.keyboard.press('Control+k')
      const palette = page.getByRole('dialog', { name: 'Ir para…' })
      await expect(palette.getByRole('combobox')).toBeFocused()
      expect(await accessibilityProblems(page)).toEqual([])
      await page.keyboard.press('Escape')
      await expect(palette).toBeHidden()
      await page.getByRole('button', { name: 'Expandir menu' }).click()
    })
  })
}
