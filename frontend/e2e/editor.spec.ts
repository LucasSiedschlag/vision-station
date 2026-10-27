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

  // the job has a reference image (rule 4 asks for one to be active): the editor opens on it, and the live view is a click away
  const canvas = page.getByRole('group', { name: 'Regiões sobre a imagem' })
  await expect(canvas).toBeVisible()
  await expect(page.getByText(/imagem de referência/).first()).toBeVisible()
  await page.getByRole('radiogroup', { name: 'Imagem mostrada' }).getByRole('radio', { name: 'Ao vivo' }).click()
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

test('the workbench: zoom and pan the image, the markings menu, the strip of samples and the result bar', async ({
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

  // the three panels, with a handle to resize each side, and the bar under them
  await expect(page.getByRole('separator', { name: 'Largura da lista de passos' })).toBeVisible()
  await expect(page.getByRole('separator', { name: 'Largura do inspetor' })).toBeVisible()
  await expect(page.getByRole('group', { name: 'Resultado do rascunho' })).toBeVisible()
  await expect(
    page
      .getByRole('toolbar', { name: 'Amostras' })
      .or(page.getByRole('region', { name: 'Amostras' })),
  ).toBeVisible()

  // the wheel zooms around the pointer; the buttons fit and go to 100 %
  const canvas = page.getByRole('group', { name: 'Regiões sobre a imagem' })
  const zoom = page.getByText(/^\d+ %$/)
  const fitted = await zoom.textContent()
  const box = (await canvas.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.wheel(0, -600)
  await expect(zoom).not.toHaveText(fitted!)
  await page.getByRole('button', { name: 'Ajustar à janela' }).click()
  await expect(zoom).toHaveText(fitted!)
  await page.getByRole('button', { name: 'Tamanho real (100 %)' }).click()
  await expect(zoom).toHaveText('100 %')
  await expect(page.getByRole('button', { name: /^Mapa da imagem/ })).toHaveCount(0) // above 200 % only
  await page.keyboard.press('Control+0')
  await expect(zoom).toHaveText(fitted!)

  // the markings: the menu has a check per layer and the key M turns them all off
  await page.getByRole('button', { name: 'Escolher as marcações' }).click()
  await expect(page.getByRole('menuitemcheckbox', { name: /Grade de pixels/ })).not.toBeChecked()
  await page.keyboard.press('Escape')
  const markings = page.getByRole('button', { name: /^Marcações · \d\/7$/ })
  await expect(markings).toHaveAttribute('aria-pressed', 'true')
  await page.keyboard.press('m')
  await expect(page.getByRole('button', { name: 'Marcações · 0/7' })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  await page.keyboard.press('m')
  await expect(markings).toHaveAttribute('aria-pressed', 'true')
  expect(await accessibilityProblems(page)).toEqual([])
  await page.goto('/')
})

test('the anchor step: kinds as cards, the allowed turn on a dial, the result on each picture, and the page stays accessible', async ({
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

  // the anchor needs the reference picture: the job has one (rule 4), and it is taken again from the camera
  await page.getByRole('button', { name: /^Amostras/ }).click()
  await page.getByRole('button', { name: /^Capturar de novo/ }).click()
  await expect(page.getByText(/^Imagem de referência capturada/).first()).toBeVisible()
  await expect(page.getByRole('button', { name: /^Capturar de novo/ })).toBeVisible() // it was taken
  await page.getByRole('button', { name: /^Âncora/ }).click()

  const kinds = page.getByRole('radiogroup', { name: 'O que acha o objeto' })
  await expect(kinds.getByRole('radio', { name: /^Sem âncora/ })).toHaveAttribute(
    'aria-checked',
    'true',
  )
  await kinds.getByRole('radio', { name: /^Mancha de cor/ }).click()
  // the dial has a handle for each end, and the numbers beside it say the same
  const least = page.getByRole('slider', { name: 'Giro mínimo' })
  await expect(least).toHaveAttribute('aria-valuenow', '-15')
  await least.focus()
  await page.keyboard.press('Shift+ArrowRight') // to the right is a smaller angle: -15° becomes -20°
  await expect(least).toHaveAttribute('aria-valuenow', '-20')
  await expect(page.getByRole('textbox', { name: 'Giro mínimo' })).toHaveValue(/-20/)
  // the result on each picture comes from the server: the reference at least
  await expect(page.getByRole('region', { name: 'Resultado em cada amostra' })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Referência:/ })).toBeVisible()
  expect(await accessibilityProblems(page)).toEqual([])
  await page.goto('/')
})

test('the gray threshold: a histogram of the image, the level Otsu finds, a line moved with the keys, and Automático takes it out (VIA-0076)', async ({
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
  await page.getByRole('option', { name: /\(blob\)/ }).click()
  await page.getByRole('button', { name: 'Adicionar', exact: true }).last().click()

  // the tool looks at the whole picture: its histogram has the bench and the darker band (a flat patch has one level, and Otsu finds none)
  await page.getByRole('combobox', { name: 'Região', exact: true }).click()
  await page.getByRole('option', { name: 'all' }).click()

  // the threshold is an Avançado setting, in the section that opens with that name
  await expect(page.getByRole('slider', { name: 'Limiar de cinza' })).toHaveCount(0)
  await page.getByRole('radio', { name: 'Avançado' }).click()
  await page.getByRole('button', { name: 'Avançado', exact: true }).click()
  const line = page.getByRole('slider', { name: 'Limiar de cinza' })
  await expect(line).toBeVisible()
  await expect(page.getByText(/^automático: \d+$/)).toBeVisible() // empty means Otsu: the dashed line says where it is
  const otsu = Number(await line.getAttribute('aria-valuenow'))
  expect(otsu).toBeGreaterThan(0)
  expect(await accessibilityProblems(page)).toEqual([])

  // moving the line makes it a chosen level, written in the number field beside it
  await line.focus()
  await page.keyboard.press('ArrowRight')
  await expect(line).toHaveAttribute('aria-valuenow', String(otsu + 1))
  await expect(page.getByText(/^automático: /)).toBeHidden()
  await expect(page.getByRole('textbox', { name: 'Limiar de cinza' })).toHaveValue(String(otsu + 1))
  await expect(page.getByText(/% da imagem é objeto|% da região é objeto/)).toBeVisible()

  // Automático gives the choice back to Otsu
  await page.getByRole('button', { name: 'Automático' }).click()
  await expect(page.getByText(`automático: ${otsu}`)).toBeVisible()
  await page.goto('/') // leaving the editor ends its session
})

test('the template check: the crop at full size, its size and the contour points of the model, and a flat crop cannot become the template (VIA-0076)', async ({
  page,
  request,
  station,
}) => {
  void station
  await page.setViewportSize({ width: 1600, height: 1100 }) // the whole picture in view, so a crop can be dragged anywhere on it
  await signInAs(page, request, 'maintainer')
  await page.goto('/jobs')
  await page.getByRole('button', { name: `Ações de ${JOB}` }).click()
  await page.getByRole('menuitem', { name: 'Editar' }).click()
  await expect(page.getByRole('heading', { level: 1, name: JOB })).toBeVisible()
  await page.getByRole('button', { name: /Ferramentas/ }).click()
  await page.getByRole('combobox', { name: 'Adicionar ferramenta' }).click()
  await page.getByRole('option', { name: /\(pattern\)/ }).last().click() // pattern v2: matches by the shape of the edges
  await page.getByRole('button', { name: 'Adicionar', exact: true }).last().click()
  await page.getByRole('radiogroup', { name: 'Imagem mostrada' }).getByRole('radio', { name: 'Referência' }).click()

  const canvas = page.getByRole('group', { name: 'Regiões sobre a imagem' })
  const drag = async (from: [number, number], to: [number, number]) => {
    const box = (await canvas.boundingBox())!
    await page.mouse.move(box.x + box.width * from[0], box.y + box.height * from[1])
    await page.mouse.down()
    await page.mouse.move(box.x + box.width * to[0], box.y + box.height * to[1], { steps: 5 })
    await page.mouse.up()
  }
  const use = page.getByRole('button', { name: 'Usar como padrão de pattern1' })
  await expect(use).toBeDisabled() // no crop yet
  await page.getByRole('button', { name: 'Desenhar recorte' }).click()

  // the title written on the bench has edges: the model has contour points, and the crop can be used
  // (the drag starts well inside the picture: near its border it would take the handles of the region)
  await drag([0.12, 0.055], [0.45, 0.13])
  await expect(page.getByText(/^\d+ pontos de contorno$/)).toBeVisible()
  await expect(page.getByText(/^\d+ × \d+ px$/)).toBeVisible()
  await expect(page.getByRole('img', { name: 'Recorte em tamanho real' })).toBeVisible()
  await expect(use).toBeEnabled()
  expect(await accessibilityProblems(page)).toEqual([])

  // a patch of the empty bench has nothing to match by: the reason shows and the button stays off
  // (the drawing stays on after a crop: a new drag replaces it)
  await drag([0.6, 0.25], [0.9, 0.5])
  await expect(page.getByRole('alert').filter({ hasText: /plano|poucas bordas/ })).toBeVisible()
  await expect(use).toBeDisabled()

  // back to the good crop: the template is kept in the job
  await drag([0.12, 0.055], [0.45, 0.13])
  await expect(use).toBeEnabled()
  await use.click()
  await expect(page.getByText('Gabarito guardado no job.')).toBeVisible()
  await page.goto('/')
})
