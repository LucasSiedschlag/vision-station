import { accessibilityProblems, expect, signInAs, test } from './fixtures'

const JOB = 'Tampa azul — etiqueta de lote (demo)'

test('the editor: live image, draw a region, test the draft and save it as the next version', async ({
  page,
  request,
  station,
}) => {
  void station
  await signInAs(page, request, 'maintainer')
  await page.goto('/jobs')
  await page.getByRole('button', { name: `Ações de ${JOB}` }).click()
  await page.getByRole('menuitem', { name: 'Editar' }).click()
  await expect(page.getByRole('heading', { level: 1, name: JOB })).toBeVisible()

  // the job has no reference yet: the live view is shown
  const canvas = page.getByRole('group', { name: 'Regiões sobre a imagem' })
  await expect(canvas).toBeVisible()
  await expect(page.getByText(/imagem ao vivo \(reduzida\)/)).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])

  // add a region and draw it by dragging over the image
  await page.getByLabel('Nova região').fill('etiqueta')
  await page.getByRole('button', { name: 'Adicionar', exact: true }).click()
  const box = (await canvas.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.3)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.6, { steps: 5 })
  await page.mouse.up()
  const region = page.getByRole('button', { name: /^etiqueta: x \d+, y \d+, \d+ × \d+ px$/ })
  await expect(region).toBeVisible()
  await expect(page.getByText('não salvo')).toBeVisible()

  // keyboard: nudge it right by 10 px
  const before = await region.getAttribute('aria-label')
  await region.focus()
  await page.keyboard.press('Shift+ArrowRight')
  await expect(region).not.toHaveAttribute('aria-label', before!)

  // the tool looks at the new region; test the whole draft on the current image
  await page.getByRole('button', { name: /Ferramentas/ }).click()
  await page.getByRole('combobox', { name: 'Região' }).click()
  await page.getByRole('option', { name: 'etiqueta' }).click()
  await page.getByRole('button', { name: 'Testar' }).click()
  await expect(page.getByText('Testado na imagem mais nova da câmera')).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])

  // save as version 2
  await page.getByRole('button', { name: 'Salvar…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Salvar como versão 2' })
  await dialog.getByLabel('O que mudou').fill('região da etiqueta')
  await dialog.getByRole('button', { name: 'Salvar…' }).click()
  await expect(page.getByRole('heading', { level: 1, name: JOB })).toBeVisible()
  const versions = page.getByRole('list', { name: 'Versões' })
  await expect(versions.getByRole('listitem').first()).toContainText('região da etiqueta')
})
