import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useState } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSession } from '@/api/session'
import { useLevels } from '@/app/levels'
import { activate, chooseLocale } from '@/app/locale'
import { mockApi, renderApp, server } from '@/test/render'
import schemas from '@/test/tool-schemas.json'
import { useDraft } from './draft'
import { SchemaForm, hiddenChanged, type Schema } from './SchemaForm'
import { widgets } from './widgets'

mockApi()

/* eslint-disable @typescript-eslint/no-explicit-any -- request bodies in the mocks */

function Form({ schema, initial = {} }: { schema: Schema; initial?: Record<string, unknown> }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <SchemaForm
        schema={schema}
        value={value}
        onChange={setValue}
        errors={{ min_fraction: 'valor alto demais' }}
      />
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  )
}
const valueOf = () => JSON.parse(screen.getByTestId('value').textContent ?? '{}')

describe('the form drawn from a JSON Schema', () => {
  it('shows the Portuguese titles, the choices with their labels and the server errors on their field', async () => {
    render(<Form schema={schemas.color} initial={{ min_fraction: 0.5 }} />)
    await userEvent.click(screen.getByRole('button', { name: 'Avançado' }))
    expect(screen.getByRole('combobox', { name: 'Medir ao longo de' })).toHaveTextContent(
      'área toda',
    )
    expect(screen.getByLabelText('Saturação mínima')).toHaveAttribute('placeholder', 'padrão: 0')
    expect(screen.getByText('valor alto demais')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Saturação mínima'), '80')
    await userEvent.tab()
    expect(valueOf()).toEqual({ min_fraction: 0.5, s_min: 80 })
  })

  it('an optional value is switched on, then edited; a pair of numbers is two fields', async () => {
    render(<Form schema={schemas.color} initial={{ min_fraction: 0.5 }} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Matiz (de, até)' }))
    expect(valueOf().hue).toEqual([0, 0])
    const second = screen.getByLabelText('Matiz (de, até), 2º valor')
    await userEvent.clear(second)
    await userEvent.type(second, '10')
    await userEvent.tab()
    expect(valueOf().hue).toEqual([0, 10])
    await userEvent.click(screen.getByRole('switch', { name: 'Matiz (de, até)' }))
    expect(valueOf().hue).toBeNull()
  })

  it('lists of words, switches, and nested objects from $defs', async () => {
    const { unmount } = render(<Form schema={schemas.code} />)
    await userEvent.type(screen.getByLabelText('Formatos'), 'QRCode, DataMatrix')
    expect(valueOf().formats).toEqual(['QRCode', 'DataMatrix'])
    await userEvent.click(screen.getByRole('button', { name: 'Avançado' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Tentar invertido' }))
    expect(valueOf().try_invert).toBe(false) // on by default
    unmount()
    render(<Form schema={schemas.blob} initial={{ mode: 'color' }} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Cor do objeto' }))
    expect(screen.getByRole('combobox', { name: 'Modo' })).toHaveTextContent('faixa (HSV)')
  })

  it('anything it does not know becomes a JSON field, never dropped', async () => {
    render(
      <Form
        schema={{
          type: 'object',
          properties: {
            odd: {
              oneOf: [{ type: 'string' }, { type: 'integer' }],
              title: 'Estranho',
              'x-level': 1,
            },
          },
        }}
      />,
    )
    const field = screen.getByLabelText('Estranho')
    await userEvent.clear(field)
    await userEvent.type(field, '[[1, 2]') // [[ types one [
    await userEvent.tab()
    expect(valueOf()).toEqual({ odd: [1, 2] })
  })
})

describe('the settings levels (docs/frontend.md §17)', () => {
  const color = schemas.color as Schema
  const Leveled = ({
    level,
    initial = {},
  }: {
    level: 1 | 2 | 3
    initial?: Record<string, unknown>
  }) => {
    const [value, setValue] = useState(initial)
    return (
      <>
        <SchemaForm schema={color} level={level} value={value} onChange={setValue} />
        <output data-testid="value">{JSON.stringify(value)}</output>
      </>
    )
  }

  it('Essencial shows the main measure and the tolerances in their sections, Avançado adds a collapsed one', async () => {
    const { unmount } = render(<Leveled level={1} />)
    expect(screen.getByRole('heading', { name: 'O que medir' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Critérios' })).toBeInTheDocument()
    expect(screen.getByLabelText('Fração mínima da área')).toBeInTheDocument()
    expect(screen.queryByLabelText('Mínimo por coluna (ou linha)')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Avançado' })).not.toBeInTheDocument()
    unmount()
    render(<Leveled level={2} />)
    const advanced = screen.getByRole('button', { name: 'Avançado' })
    expect(advanced).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(advanced)
    expect(screen.getByLabelText('Mínimo por coluna (ou linha)')).toBeInTheDocument()
  })

  it('a fraction is a percentage on screen and a fraction in the job', async () => {
    render(<Leveled level={1} />)
    const field = screen.getByLabelText('Fração mínima da área')
    await userEvent.type(field, '35')
    await userEvent.tab()
    expect(valueOf()).toEqual({ min_fraction: 0.35 })
    expect(field).toHaveValue('35%')
  })

  it('what a level hides is never invisible: a changed hidden setting shows a badge that opens it', async () => {
    render(<Leveled level={1} initial={{ min_fraction: 0.5, line_min: 0.3, max_gap: 0.2 }} />)
    // line_min is at its default; max_gap is not
    const badge = screen.getByRole('button', { name: /1 ajuste oculto foi alterado/ })
    expect(screen.queryByLabelText('Maior trecho faltando')).not.toBeInTheDocument()
    await userEvent.click(badge)
    expect(screen.getByLabelText('Maior trecho faltando')).toHaveValue('20%')
    expect(screen.queryByLabelText('Mínimo por coluna (ou linha)')).not.toBeInTheDocument()
    await userEvent.click(badge)
    expect(screen.queryByLabelText('Maior trecho faltando')).not.toBeInTheDocument()
  })

  it('a closed section says how many of its settings were changed', async () => {
    render(<Leveled level={2} initial={{ min_fraction: 0.5, max_gap: 0.2, line_min: 0.3 }} />)
    const advanced = screen.getByRole('button', { name: /Avançado/ })
    expect(advanced).toHaveTextContent('1 alterado')
    expect(advanced).toHaveAttribute('aria-expanded', 'false')
  })

  it('counts a hidden value that is present without a default as changed, and never at a level that shows it', () => {
    expect(hiddenChanged(color, { max_gap: 0.2, line_min: 0.3, s_min: 10 }, 1)).toEqual(['max_gap'])
    expect(hiddenChanged(color, { max_gap: 0.2 }, 2)).toEqual([])
    expect(
      hiddenChanged(schemas.pattern as Schema, { max_side: 512, template: 'a.png' }, 2),
    ).toEqual(['max_side'])
  })

  it('a parameter without a level counts as Especialista', async () => {
    const schema = { type: 'object', properties: { odd: { type: 'string', title: 'Esquecido' } } }
    const { unmount } = render(<Form schema={schema} />)
    expect(screen.queryByLabelText('Esquecido')).not.toBeInTheDocument()
    unmount()
    render(<SchemaForm schema={schema} level={3} value={{}} onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: 'Especialista' }))
    expect(screen.getByLabelText('Esquecido')).toBeInTheDocument()
  })

  it('draws a registered widget in place of the plain control, and the plain control while there is none', () => {
    const schema = {
      type: 'object',
      properties: { rect: { type: 'string', title: 'Zona', 'x-level': 1, 'x-widget': 'region' } },
    }
    const { unmount } = render(<Form schema={schema} />)
    expect(screen.getByLabelText('Zona')).toBeInTheDocument()
    unmount()
    widgets.region = ({ label }) => <p>widget {label}</p>
    try {
      render(<Form schema={schema} />)
      expect(screen.getByText('widget Zona')).toBeInTheDocument()
    } finally {
      delete widgets.region
    }
  })

  it('px and ΔE follow the number', () => {
    render(<Leveled level={3} initial={{ mode: 'reference', rgb: [10, 20, 30] }} />)
    expect(screen.getByText('ΔE')).toBeInTheDocument()
  })
})

// --- the editor page -----------------------------------------------------------------------------------

const JOB = 'a1b2c3d4-0000-4000-8000-000000000001'
const version = {
  id: JOB,
  version: 2,
  job: {
    format: 1,
    job: {
      id: JOB,
      name: 'Tampa azul',
      version: 2,
      parent_version: 1,
      author: 'maintainer',
      created_at: '2026-10-15T14:00:00-03:00',
      description: '',
      notes: '',
    },
    camera_profile: 'camera/profile.yaml',
    trigger: { mode: 'manual' },
    quality: { brightness: { min: 15, max: 245 }, sharpness_min_ratio: 0.5 },
    geometry: { rois: { cap: { relative_to: 'frame', rect: [0.3, 0.1, 0.7, 0.3] } } },
    tools: [
      {
        id: 'tampa',
        type: 'color',
        version: 1,
        roi: 'cap',
        params: { hue: [100, 130], s_min: 100, min_fraction: 0.4 },
        reason_fail: 'Tampa ausente',
      },
    ],
    decision: 'all_pass',
    ui: { waiting: 'Aguardando peça' },
  },
  profile: {
    resolution: [1920, 1080],
    exposure: { mode: 'manual', value_us: 8000 },
    gain: { mode: 'manual', value: 0 },
    white_balance: { mode: 'manual', kelvin: 4500 },
    focus: { mode: 'manual', value: 30 },
    power_line_hz: 60,
    low_light_compensation: false,
  },
  files: [{ path: 'reference/reference.png', size: 10, sha256: 'x' }],
  reference: { brightness: 120, sharpness: 300 },
  expected: null,
}
// as the server sends them: the description is the Portuguese one of the parameter schema
const kind = (name: keyof typeof schemas) => ({
  name,
  version: 1,
  description: schemas[name].description,
  params_schema: schemas[name],
})
const types = {
  tools: [kind('color'), kind('code')],
  locators: [kind('fixed')],
  builtin_rois: ['anchor', 'frame'],
}

beforeEach(() => {
  localStorage.clear()
  useLevels.setState({ saved: {} })
  useDraft.getState().clear()
  useSession.getState().signIn('tok', 'maintainer', 3600)
  server.use(
    http.get(`*/api/jobs/${JOB}`, () =>
      HttpResponse.json({
        id: JOB,
        name: 'Tampa azul',
        description: '',
        versions: [
          {
            version: 2,
            created_at: '',
            author: 'maintainer',
            notes: '',
            parent_version: 1,
            active: false,
          },
        ],
      }),
    ),
    http.get(`*/api/jobs/${JOB}/versions/2`, () => HttpResponse.json(version)),
    http.get('*/api/tools', () => HttpResponse.json(types)),
    http.get(
      '*/api/jobs/*/versions/*/files/*',
      () => new HttpResponse(new Uint8Array([1]), { headers: { 'Content-Type': 'image/png' } }),
    ),
    http.get('*/api/snapshot.jpg', () =>
      HttpResponse.json({ detail: 'Sem imagem da câmera', code: 'no_frame' }, { status: 503 }),
    ),
    http.get('*/api/camera/state', () =>
      HttpResponse.json({
        connected: true,
        last_error: null,
        profile: version.profile,
        applied: true,
        settings: {},
        station_paused: false,
      }),
    ),
  )
})

async function openEditor(path = `/jobs/${JOB}/edit`) {
  const app = renderApp(path)
  await screen.findByRole('heading', { level: 1, name: 'Tampa azul' })
  return app
}

describe('the job editor', () => {
  it('the top bar counts the changed settings the level hides', async () => {
    server.use(
      http.get(`*/api/jobs/${JOB}/versions/2`, () =>
        HttpResponse.json({
          ...version,
          job: {
            ...version.job,
            tools: [
              { ...version.job.tools[0], params: { hue: [100, 130], max_gap: 0.2, axis: 'x' } },
            ],
          },
        }),
      ),
    )
    await openEditor()
    expect(await screen.findByText('2 ajustes ocultos foram alterados')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    expect(screen.queryByText(/ajustes? ocultos? foram? alterados?/)).not.toBeInTheDocument()
  })

  it('the level is chosen in the top bar, kept per role, and shows the deeper settings', async () => {
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    expect(screen.queryByRole('button', { name: 'Avançado' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    expect(screen.getByRole('button', { name: 'Avançado' })).toBeInTheDocument()
    expect(screen.queryByText(/ocultos? foi|ocultos? fo/)).not.toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem('vision-station-levels')!)).toEqual({
      maintainer: { editor: 2 },
    })
  })

  it('a job without a reference image shows the live picture, and says so', async () => {
    server.use(
      http.get(`*/api/jobs/${JOB}/versions/2`, () =>
        HttpResponse.json({ ...version, files: [], reference: null }),
      ),
    )
    await openEditor()
    expect(screen.getByRole('radio', { name: 'Ao vivo' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Referência' })).toBeDisabled()
  })

  it('opens the latest version as a draft, on the regions step, with the steps listed', async () => {
    await openEditor()
    expect(screen.getByText('rascunho a partir da v2')).toBeInTheDocument()
    const steps = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    expect(
      steps
        .getAllByRole('button')
        .map((b) => b.textContent?.replace(/,.*$/, '').replace(/^\d/, '')),
    ).toEqual([
      'Câmera',
      'Gatilho',
      'Qualidade',
      'Âncora e regiões',
      'Ferramentas',
      'Referência',
      'Revisar',
    ])
    expect(screen.getByRole('heading', { level: 2, name: 'Âncora e regiões' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'cap' })).toBeInTheDocument()
  })

  it('edits a tool, keeps the draft in the browser, and saves it as the next version', async () => {
    let saved: any = null
    server.use(
      http.post(`*/api/jobs/${JOB}/versions`, async ({ request }) => {
        saved = await request.json()
        return HttpResponse.json({ id: JOB, version: 3 }, { status: 201 })
      }),
    )
    const { router } = await openEditor()
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    const fraction = screen.getByLabelText('Fração mínima da área')
    await userEvent.clear(fraction)
    await userEvent.type(fraction, '60')
    await userEvent.tab()
    expect(screen.getByText('não salvo')).toBeInTheDocument()
    expect(
      JSON.parse(localStorage.getItem(`vision-station-draft:${JOB}`)!).job.tools[0].params
        .min_fraction,
    ).toBe(0.6)

    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar como versão 3' })
    await userEvent.type(within(dialog).getByLabelText('O que mudou'), 'mais cor')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar…' }))
    await waitFor(() => expect(router.state.location.pathname).toBe(`/jobs/${JOB}`))
    expect(saved.base).toEqual({ id: JOB, version: 2 })
    expect(saved.job.tools[0].params.min_fraction).toBe(0.6)
    expect(saved.notes).toBe('mais cor')
    expect(saved.add_files).toEqual({})
    expect(localStorage.getItem(`vision-station-draft:${JOB}`)).toBeNull()
  })

  it('an older version opens as a draft and saves as the next version after the latest', async () => {
    let saved: any = null
    const entry = (v: number) => ({
      version: v,
      created_at: '',
      author: 'maintainer',
      notes: '',
      parent_version: v - 1 || null,
      active: false,
    })
    server.use(
      http.get(`*/api/jobs/${JOB}`, () =>
        HttpResponse.json({
          id: JOB,
          name: 'Tampa azul',
          description: '',
          versions: [entry(2), entry(1)],
        }),
      ),
      http.get(`*/api/jobs/${JOB}/versions/1`, () => HttpResponse.json({ ...version, version: 1 })),
      http.post(`*/api/jobs/${JOB}/versions`, async ({ request }) => {
        saved = await request.json()
        return HttpResponse.json({ id: JOB, version: 3 }, { status: 201 })
      }),
    )
    await openEditor(`/jobs/${JOB}/edit?from=1`)
    expect(screen.getByText('rascunho a partir da v1')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar como versão 3' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar…' }))
    await waitFor(() => expect(saved).not.toBeNull())
    expect(saved.base).toEqual({ id: JOB, version: 1 })
    expect(saved.latest).toBe(2)
  })

  it('a draft survives a change of language (the pages are mounted again, the draft is kept)', async () => {
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    const fraction = screen.getByLabelText('Fração mínima da área')
    await userEvent.clear(fraction)
    await userEvent.type(fraction, '60')
    await userEvent.tab()
    expect(screen.getByText('não salvo')).toBeInTheDocument()
    await act(async () => {
      chooseLocale('en')
      await activate('en')
    })
    expect(await screen.findByText('not saved')).toBeInTheDocument()
    expect(
      JSON.parse(localStorage.getItem(`vision-station-draft:${JOB}`)!).job.tools[0].params
        .min_fraction,
    ).toBe(0.6)
  })

  it('undo and redo', async () => {
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: 'Remover a região cap' }))
    expect(screen.queryByRole('button', { name: 'cap' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Desfazer' }))
    expect(screen.getByRole('button', { name: 'cap' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Refazer' }))
    expect(screen.queryByRole('button', { name: 'cap' })).not.toBeInTheDocument()
  })

  it('tests the draft on the current image and shows the result', async () => {
    let sent: any = null
    server.use(
      http.post('*/api/jobs/test', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({
          result: {
            outcome: 'FAIL',
            reason: 'Tampa ausente',
            scores: { tampa: 0.2 },
            duration_ms: 12,
            at: null,
          },
          regions: [{ tool: 'tampa', roi: 'cap', rect: [576, 108, 1344, 324], passed: false }],
          anchor: null,
          tools: { tampa: { fraction: 0.08 } },
          timings: { total: 0.012 },
          width: 1920,
          height: 1080,
          overlay: '',
        })
      }),
    )
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: 'Testar' }))
    const result = await screen.findByText('Tampa ausente', { selector: 'span' })
    expect(result.closest('[role="status"]')).toHaveTextContent('Reprovado')
    expect(sent.draft.base).toEqual({ id: JOB, version: 2 })
    expect(sent.image).toBeNull()
  })

  it('a refused draft marks the step that has the problem', async () => {
    server.use(
      http.post(`*/api/jobs/${JOB}/versions`, () =>
        HttpResponse.json(
          {
            detail: 'O job tem campos inválidos',
            code: 'invalid_draft',
            fields: { 'job.quality.brightness.min': 'Input should be a valid number' },
          },
          { status: 422 },
        ),
      ),
    )
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Salvar…' }),
    )
    expect(await screen.findByText('O job tem campos inválidos')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Qualidade, com erro/ })).toBeInTheDocument()
  })

  it('a draft kept in the browser comes back, and can be discarded', async () => {
    const kept = {
      key: JOB,
      base: { id: JOB, version: 2 },
      job: { ...version.job, job: { ...version.job.job, name: 'Tampa azul (rascunho)' } },
      profile: version.profile,
      baseFiles: version.files,
      addFiles: {},
      removeFiles: [],
      expected: null,
      baseExpected: 'null',
      notes: '',
    }
    localStorage.setItem(`vision-station-draft:${JOB}`, JSON.stringify(kept))
    const { router } = renderApp(`/jobs/${JOB}/edit`)
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Tampa azul (rascunho)' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Rascunho recuperado deste navegador.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Descartar o rascunho' }))
    await userEvent.click(
      within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Descartar' }),
    )
    await waitFor(() => expect(router.state.location.pathname).toBe(`/jobs/${JOB}`))
    expect(localStorage.getItem(`vision-station-draft:${JOB}`)).toBeNull()
  })

  it('a new job starts from the camera profile and is created on save', async () => {
    let created: any = null
    server.use(
      http.post('*/api/jobs', async ({ request }) => {
        created = await request.json()
        return HttpResponse.json({ id: 'new-id', version: 1 }, { status: 201 })
      }),
      http.get('*/api/jobs/new-id', () =>
        HttpResponse.json({ id: 'new-id', name: 'Novo job', description: '', versions: [] }),
      ),
    )
    const { router } = await openEditor('/jobs/new/edit').catch(async () => {
      await screen.findByRole('heading', { level: 1, name: 'Novo job' })
      return { router: undefined as never }
    })
    void router
    expect(screen.getByRole('heading', { level: 2, name: 'Câmera' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Adicionar ferramenta' }))
    await userEvent.click(screen.getByRole('option', { name: /Código de barras/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Adicionar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Salvar…' }),
    )
    await waitFor(() => expect(created).not.toBeNull())
    expect(created.base).toBeNull()
    expect(created.profile.exposure.value_us).toBe(8000)
    expect(created.job.tools).toEqual([
      { id: 'code1', type: 'code', version: 1, roi: 'frame', params: {}, reason_fail: 'Falhou' },
    ])
  })
})
