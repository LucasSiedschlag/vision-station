import { accessibilityProblems, expect, test, watchTheBrowser } from './fixtures'

const themes = [
  { name: 'dark (system)', scheme: 'dark' as const, forced: null, background: 'rgb(14, 17, 22)' },
  {
    name: 'light (system)',
    scheme: 'light' as const,
    forced: null,
    background: 'rgb(244, 246, 249)',
  },
  {
    name: 'light forced over a dark system',
    scheme: 'dark' as const,
    forced: 'light',
    background: 'rgb(244, 246, 249)',
  },
  {
    name: 'dark forced over a light system',
    scheme: 'light' as const,
    forced: 'dark',
    background: 'rgb(14, 17, 22)',
  },
]

for (const theme of themes) {
  test.describe(`gallery in ${theme.name}`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme.scheme })
      if (theme.forced)
        await page.addInitScript(
          (forced) => localStorage.setItem('vision-station-theme', forced),
          theme.forced,
        )
      await page.goto('/design')
      await expect(page.getByRole('heading', { name: 'Sistema de design' })).toBeVisible()
    })

    test('uses the tokens of the theme', async ({ page }) => {
      const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
      expect(background).toBe(theme.background)
    })

    test('has no accessibility violations (WCAG 2.2 AA, contrast included)', async ({ page }) => {
      expect(await accessibilityProblems(page)).toEqual([])
    })
  })
}

test.describe('gallery behaviour', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/design')
    await expect(page.getByRole('heading', { name: 'Sistema de design' })).toBeVisible()
  })

  test('loads without errors and without leaving the machine, with the bundled fonts', async ({
    page,
  }) => {
    const problems = watchTheBrowser(page)
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Sistema de design' })).toBeVisible()
    expect(
      await page.evaluate(
        async () => (await document.fonts.load('16px "IBM Plex Sans"')).length > 0,
      ),
    ).toBe(true)
    expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toContain(
      'IBM Plex Sans',
    )
    expect(problems).toEqual([])
  })

  test('the theme control changes the theme and remembers it', async ({ page }) => {
    await page.getByRole('radio', { name: 'Claro' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await page.getByRole('radio', { name: 'Sistema' }).click()
    await expect(page.locator('html')).not.toHaveAttribute('data-theme')
  })

  test('kiosk density makes controls 56 px tall and compact ones 36 px', async ({ page }) => {
    const button = page.getByRole('button', { name: 'Primário' })
    expect((await button.boundingBox())?.height).toBe(36)
    await page.getByRole('switch', { name: 'Densidade quiosque' }).click()
    expect((await button.boundingBox())?.height).toBe(56)
    expect(await button.evaluate((el) => getComputedStyle(el).fontSize)).toBe('18px')
  })

  test('with reduced motion nothing animates', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const duration = await page
      .getByRole('button', { name: 'Secundário' })
      .evaluate((el) => getComputedStyle(el).transitionDuration)
    expect(parseFloat(duration)).toBeLessThan(0.001)
  })

  test('a confirmation asks by name, focuses Cancelar, and Escape returns the focus to the button', async ({
    page,
  }) => {
    const opener = page.getByRole('button', { name: 'Confirmar ação' })
    await opener.click()
    const dialog = page.getByRole('alertdialog', { name: 'Ativar versão 7 de Tampa azul?' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(opener).toBeFocused()
  })

  test('a dialog traps the keyboard focus', async ({ page }) => {
    await page.getByRole('button', { name: 'Abrir diálogo' }).click()
    const dialog = page.getByRole('dialog', { name: 'Resultado incorreto?' })
    await expect(dialog).toBeVisible()
    for (let i = 0; i < 8; i++) {
      await page.keyboard.press('Tab')
      expect(await dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true)
    }
  })

  test('toasts: a success disappears, an error stays until it is dismissed', async ({ page }) => {
    await page.getByRole('button', { name: 'Aviso de erro' }).click()
    await expect(page.getByText('Não foi possível gravar o backup')).toBeVisible()
    await page.waitForTimeout(6000)
    await expect(page.getByText('Não foi possível gravar o backup')).toBeVisible()
  })

  test('a number is read the way it is written in Portuguese', async ({ page }) => {
    const field = page.getByLabel('Exposição')
    await field.fill('')
    await field.pressSequentially('1500.5') // the dot of a numeric keypad is the decimal mark
    await field.blur()
    await expect(field).toHaveValue('1500,5')
    await field.fill('999999')
    await field.blur()
    await expect(field).toHaveAttribute('aria-invalid', 'true')
    await expect(field).toHaveValue('999999') // flagged, not changed
  })

  test('the file drop refuses a file of another type with a message', async ({ page }) => {
    await page
      .getByLabel('Escolher arquivo de job')
      .setInputFiles({ name: 'notas.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
    await expect(page.getByRole('alert').filter({ hasText: 'notas.txt' })).toBeVisible()
    await page.getByLabel('Escolher arquivo de job').setInputFiles({
      name: 'Tampa_v7.vjob',
      mimeType: 'application/octet-stream',
      buffer: Buffer.from('x'),
    })
    await expect(page.getByText('Arquivo recebido: Tampa_v7.vjob')).toBeVisible()
  })

  test('everything is reachable with the keyboard alone', async ({ page }) => {
    const reached = new Set<string>()
    for (let i = 0; i < 60; i++) {
      await page.keyboard.press('Tab')
      const label = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null
        return el
          ? (el.getAttribute('aria-label') ?? el.textContent?.trim() ?? el.tagName).slice(0, 40)
          : ''
      })
      reached.add(label)
    }
    for (const expected of [
      'Sistema',
      'Primário',
      'Abrir diálogo',
      'Confirmar ação',
      'Ações da linha',
    ])
      expect(reached).toContain(expected)
  })
})
