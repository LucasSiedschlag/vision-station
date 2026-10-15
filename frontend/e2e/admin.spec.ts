import { accessibilityProblems, expect, signInAs, test } from './fixtures'

const screens = [
  { path: '/results', heading: 'Resultados' },
  { path: '/dataset', heading: 'Dataset e coleta' },
  { path: '/audit', heading: 'Auditoria' },
  { path: '/access', heading: 'Acessos' },
  { path: '/settings', heading: 'Configurações' },
]

for (const scheme of ['dark', 'light'] as const) {
  test(`results, dataset, audit, access and settings have no accessibility violations, ${scheme}`, async ({
    page,
    request,
    station,
  }) => {
    await page.emulateMedia({ colorScheme: scheme })
    // one inspection, so the results table and its detail have something to show
    await station.outcome('FAIL')
    await station.object('on')
    await expect
      .poll(async () => (await station.state()).counters.total, { timeout: 15_000 })
      .toBeGreaterThan(0)

    await signInAs(page, request, 'maintainer')
    for (const { path, heading } of screens) {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible()
      await expect(page.locator('[aria-busy="true"]')).toHaveCount(0)
      expect(await accessibilityProblems(page), path).toEqual([])
    }

    await page.goto('/results?period=all')
    await page
      .getByRole('button', { name: /^Abrir o resultado de/ })
      .first()
      .click()
    await expect(page.getByRole('dialog', { name: 'Resultado' })).toBeVisible()
    await expect(page.getByRole('dialog', { name: 'Resultado' }).getByRole('img')).toBeVisible()
    expect(await accessibilityProblems(page), 'result detail').toEqual([])
  })
}
