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
  // the regions and the tools share the step now: the first button adds the region
  await page.getByRole('button', { name: 'Adicionar', exact: true }).first().click()
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
  // the session of the editor measures every new frame: *Testar* has nothing more to wait for
  await expect(page.getByText(/^Ao vivo ● /)).toBeVisible()
  await expect(
    page.getByText('Medido agora, na imagem ao vivo, com a estação pausada.'),
  ).toBeVisible()
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

test('the colour picker: drag over the image to sample a colour, see the proposal, apply it, and the page stays accessible', async ({
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
  await page.getByRole('button', { name: /Ferramentas/ }).click()
  await page.getByRole('combobox', { name: 'Adicionar ferramenta' }).click()
  await page.getByRole('option', { name: /\(color\)/ }).click()
  await page.getByRole('button', { name: 'Adicionar', exact: true }).last().click()

  // the colour tool draws its range itself: any hue until a colour is chosen, and the other bars
  await expect(page.getByRole('switch', { name: 'Qualquer matiz' })).toBeChecked()
  await page.getByRole('switch', { name: 'Qualquer matiz' }).click()
  await expect(page.getByRole('slider', { name: 'Matiz inicial' })).toBeVisible()
  await expect(page.getByRole('slider', { name: /^Saturação mínima/ })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])

  const canvas = page.getByRole('group', { name: 'Regiões sobre a imagem' })
  await page.getByRole('button', { name: /Incluir cor/ }).click()
  await expect(page.getByText('Arraste sobre a cor na imagem')).toBeVisible()
  await expect(canvas).toBeInViewport() // the image stays in view while the inspector is used
  const box = (await canvas.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.3)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.6, box.y + box.height * 0.6, { steps: 5 })
  await page.mouse.up()
  // the proposal waits for the person: the range is applied only by *Aplicar*
  await expect(page.getByText(/^Faixa proposta: /)).toBeVisible()
  await expect(page.getByText('Arraste sobre a cor na imagem')).toBeHidden()
  await page.getByRole('button', { name: 'Aplicar', exact: true }).click()
  await expect(page.getByText(/^Faixa proposta: /)).toBeHidden()
  await expect(page.getByRole('slider', { name: 'Matiz final' })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])
  // leaving the editor ends its session, and the station goes back to production
  await page.goto('/')
})

test('the fine-tune: a supervisor opens it from the job, sees only the gauges, and the save asks for a note', async ({
  page,
  request,
  station,
}) => {
  void station
  await signInAs(page, request, 'supervisor')
  await page.goto('/jobs')
  await page.getByRole('row').filter({ hasText: JOB }).getByRole('link', { name: JOB }).click()
  await page.getByRole('button', { name: 'Ajuste fino' }).first().click()
  await expect(page.getByRole('heading', { level: 1, name: /^Ajuste fino — / })).toBeVisible()
  await expect(page.getByRole('slider', { name: /Limite mínimo/ })).toBeVisible()
  await expect(page.getByRole('button', { name: /Ferramentas|Imagem e disparo/ })).toHaveCount(0)
  await expect(page.getByText(/^Ao vivo ● /)).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])

  // a limit moves, and the save needs a note
  const save = page.getByRole('button', { name: /^Salvar como v\d+…$/ })
  await expect(save).toBeDisabled()
  await page.getByRole('slider', { name: /Limite mínimo/ }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(save).toBeEnabled()
  await save.click()
  const dialog = page.getByRole('dialog', { name: /^Salvar o ajuste como versão / })
  await expect(dialog.getByRole('button', { name: 'Salvar…' })).toBeDisabled()
  expect(await accessibilityProblems(page)).toEqual([])
  await page.keyboard.press('Escape')
  // leaving ends the session and the station goes back to production
  await page.goto('/')
})
