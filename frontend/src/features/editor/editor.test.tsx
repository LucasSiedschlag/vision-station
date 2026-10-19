import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useLive } from '@/api/live'
import { useSession } from '@/api/session'
import { useLevels } from '@/app/levels'
import { activate, chooseLocale } from '@/app/locale'
import { FakeSocket } from '@/test/fake-socket'
import { mockApi, renderApp, server, stateFixture } from '@/test/render'
import criteria from '@/test/tool-criteria.json'
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
    expect(screen.getByLabelText('Distância máxima (ΔE)')).toHaveAttribute(
      'placeholder',
      'padrão: 20',
    )
    expect(screen.getByText('valor alto demais')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Distância máxima (ΔE)'), '15')
    await userEvent.tab()
    expect(valueOf()).toEqual({ min_fraction: 0.5, max_distance: 15 })
  })

  it('an optional value is switched on, then edited; a pair of numbers is two fields', async () => {
    render(<Form schema={schemas.color} initial={{ min_fraction: 0.5 }} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Cor de referência (R, G, B)' }))
    expect(valueOf().rgb).toEqual([0, 0, 0])
    const third = screen.getByLabelText('Cor de referência (R, G, B), 3º valor')
    await userEvent.clear(third)
    await userEvent.type(third, '10')
    await userEvent.tab()
    expect(valueOf().rgb).toEqual([0, 0, 10])
    await userEvent.click(screen.getByRole('switch', { name: 'Cor de referência (R, G, B)' }))
    expect(valueOf().rgb).toBeNull()
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
  criteria: (criteria as Record<string, unknown[]>)[name] ?? [],
})
const types = {
  tools: [kind('color'), kind('code')],
  locators: [kind('fixed')],
  builtin_rois: ['anchor', 'frame'],
}

afterEach(() => vi.unstubAllGlobals())

beforeEach(() => {
  FakeSocket.all = []
  vi.stubGlobal('WebSocket', FakeSocket) // the live session of the editor: it opens when the test says so
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
    // in the top bar, and in the form of the tool
    expect((await screen.findAllByText('2 ajustes ocultos foram alterados')).length).toBe(2)
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    expect(screen.queryByText(/ajustes? ocultos? foram? alterados?/)).not.toBeInTheDocument()
  })

  it('Validar runs the draft on every sample, says which are off, and the rail follows', async () => {
    let sent: any = null
    server.use(
      http.post('*/api/jobs/verify', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({
          ok: false,
          message: null,
          fields: {},
          max_ms: 42,
          cases: [
            {
              image: 'tests/images/a.png',
              expected: 'PASS',
              outcome: 'PASS',
              ok: true,
              message: 'tests/images/a.png: APROVADO como esperado',
              reason: '',
              duration_ms: 30,
            },
            {
              image: 'tests/images/b.png',
              expected: 'FAIL',
              outcome: 'PASS',
              ok: false,
              message: 'tests/images/b.png: resultado PASS, esperado FAIL',
              reason: '',
              duration_ms: 42,
            },
          ],
        })
      }),
    )
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Validar/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Validar tudo' }))
    expect(
      (await screen.findAllByText('1 de 2 amostras não saíram como esperado')).length,
    ).toBeGreaterThan(0)
    expect(sent.job.tools[0].id).toBe('tampa')
    expect(screen.getByText('Mais lenta: 42 ms')).toBeInTheDocument()
    expect(screen.getByText(/resultado PASS, esperado FAIL/)).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Boa' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Ruim' })).toBeInTheDocument()
    // the rail says it, in words under the step
    expect(
      within(screen.getByRole('navigation', { name: 'Passos do job' })).getByText(
        '1 de 2 amostras não saíram como esperado',
      ),
    ).toBeInTheDocument()
  })

  it('the limits of a criterion are on its gauge, with the samples as dots, and a proposal applied only on Aplicar', async () => {
    const measure = (id: string, kind: string, value: number, expected: string | null) => ({
      image: id,
      kind,
      expected,
      ok: true,
      message: '',
      result: {
        outcome: 'PASS',
        tools: [
          {
            id: 'tampa',
            passed: value >= 0.4,
            values: { fraction: value },
            units: { fraction: 'fraction' },
          },
        ],
      },
    })
    let asked: any = null
    server.use(
      http.post('*/api/editor/batch', () =>
        HttpResponse.json({
          ok: true,
          samples: [
            measure('reference/reference.png', 'reference', 0.9, null),
            measure('tests/images/boa1.png', 'good', 0.95, 'PASS'),
            measure('tests/images/boa2.png', 'good', 0.92, 'PASS'),
            measure('tests/images/boa3.png', 'good', 0.97, 'PASS'),
            measure('tests/images/ruim1.png', 'bad', 0.2, 'FAIL'),
          ],
          tools: [],
        }),
      ),
      http.post('*/api/editor/suggest/limits', async ({ request }) => {
        asked = await request.json()
        return HttpResponse.json({
          ok: true,
          proposals: [
            {
              tool: 'tampa',
              criterion: 'fraction',
              label: 'Fração com a cor',
              param: 'min_fraction',
              side: 'min',
              unit: 'fraction',
              current: 0.4,
              proposed: 0.57,
              reason: '',
              basis: 'gap',
              worst_good: 0.92,
              nearest_bad: 0.2,
              margin_good: 0.35,
              margin_bad: 0.37,
              good_n: 3,
              bad_n: 1,
            },
          ],
        })
      }),
      http.get(`*/api/jobs/${JOB}/versions/2/files/tests/images/boa1.png`, () =>
        HttpResponse.arrayBuffer(new Uint8Array([137, 80, 78, 71]).buffer),
      ),
    )
    await openEditor()
    const gauge = await screen.findByRole('region', { name: 'Fração com a cor' })
    // the limit is on the gauge only: the form does not draw it a second time
    expect(screen.queryByLabelText('Fração mínima da área')).not.toBeInTheDocument()
    expect(within(gauge).getByRole('textbox', { name: 'Limite mínimo' })).toHaveValue('40%')
    // the samples were measured: their dots, the margin in words, how many are on the right side
    expect(await within(gauge).findAllByRole('button', { name: /boa\d\.png/ })).toHaveLength(3)
    expect(within(gauge).getByText('3 de 3 boas dentro · 1 de 1 ruins fora')).toBeInTheDocument()
    expect(within(gauge).getByText(/Margem: a pior boa \(92%\)/)).toBeInTheDocument()
    // a dot shows its sample on the image, with a way back
    await userEvent.click(within(gauge).getByRole('button', { name: /boa1\.png/ }))
    expect(await screen.findByText('Amostra: boa1.png')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar à imagem' }))
    expect(screen.queryByText('Amostra: boa1.png')).not.toBeInTheDocument()
    // the proposal is a ghost until Aplicar
    await userEvent.click(within(gauge).getByRole('button', { name: 'Ajustar pelas amostras' }))
    expect(await within(gauge).findByText(/^Proposta: limite mínimo 57%/)).toBeInTheDocument()
    expect(asked.tool).toBe('tampa')
    expect(useDraft.getState().draft?.job.tools[0].params.min_fraction).toBe(0.4)
    await userEvent.click(within(gauge).getByRole('button', { name: 'Aplicar' }))
    expect(useDraft.getState().draft?.job.tools[0].params.min_fraction).toBe(0.57)
    expect(within(gauge).queryByRole('button', { name: 'Aplicar' })).not.toBeInTheDocument()
  })

  it('a gauge of a deeper level appears with the level, and takes its parameter out of the form', async () => {
    await openEditor()
    await screen.findByRole('region', { name: 'Fração com a cor' })
    expect(screen.queryByRole('region', { name: 'Cobertura da faixa' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    expect(await screen.findByRole('region', { name: 'Cobertura da faixa' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Avançado/ }))
    expect(screen.queryByLabelText('Cobertura mínima')).not.toBeInTheDocument() // it is on the gauge
    expect(screen.getByLabelText('Medir ao longo de')).toBeInTheDocument() // what is not a limit stays
  })

  it('the live session measures the draft on every new frame: the picture, the needle of the gauge and the state', async () => {
    useSession.getState().signIn('tok', 'maintainer', 3600)
    await openEditor()
    const socket = FakeSocket.all.at(-1)!
    expect(socket.url).toContain('/api/editor/live')
    socket.open()
    expect(socket.sent[0]).toEqual({ type: 'hello', token: 'tok' })
    expect(await screen.findByText('Conectando à câmera…')).toBeInTheDocument()
    // the files go once, with the first draft
    socket.say({ type: 'ready', fps: 4, paused_by_session: true })
    expect(socket.sent[1]).toMatchObject({ type: 'draft', job: expect.anything() })
    // the picture on screen is the camera's: the reference is not
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(screen.getByRole('radio', { name: 'Ao vivo' }))
    act(() => {
      socket.say({
        type: 'result',
        frame_id: 1,
        width: 640,
        height: 480,
        result: {
          outcome: 'PASS',
          reason: '',
          scores: { tampa: 1 },
          duration_ms: 35,
          tools: [
            {
              id: 'tampa',
              passed: true,
              values: { fraction: 0.83 },
              units: { fraction: 'fraction' },
            },
          ],
        },
        regions: [],
        anchor: null,
        tools: {},
        timings: {},
      })
      socket.picture()
    })
    expect(await screen.findByText(/^Ao vivo ● /)).toBeInTheDocument()
    const gauge = await screen.findByRole('region', { name: 'Fração com a cor' })
    expect(within(gauge).getByText('83%')).toBeInTheDocument() // the needle's value: the gauge is the one place for it
    expect(
      screen.getByText('Medido agora, na imagem ao vivo, com a estação pausada.'),
    ).toBeInTheDocument()
    // a draft the server refuses is a banner, and its fields mark the steps
    act(() =>
      socket.say({
        type: 'draft_error',
        message: 'O job tem campos inválidos',
        fields: { 'job.quality.sharpness_min_ratio': 'x' },
      }),
    )
    expect(
      await screen.findByText(/O rascunho não pôde ser medido: O job tem campos inválidos/),
    ).toBeInTheDocument()
    expect(rail.getByRole('button', { name: /Qualidade.*precisa de atenção/ })).toBeInTheDocument()
    // a lost camera leaves the reference and the samples to work with
    act(() => socket.say({ type: 'camera', connected: false, message: 'Câmera desconectada' }))
    expect(
      await screen.findByText(/Câmera desconectada: dá para seguir ajustando na referência/),
    ).toBeInTheDocument()
  })

  it("the pause of the session is the session's: the banner says so and offers no way to resume under it", async () => {
    useSession.getState().signIn('tok', 'maintainer', 3600)
    useLive.setState({
      status: stateFixture({ state: 'Paused' }),
      connected: true,
      connecting: false,
    })
    await openEditor()
    const socket = FakeSocket.all.at(-1)!
    socket.open()
    expect(screen.getByRole('button', { name: 'Retomar a estação' })).toBeInTheDocument() // Aplicar's pause
    act(() => socket.say({ type: 'ready', fps: 4, paused_by_session: true }))
    expect(await screen.findByText(/pausada enquanto o editor mede ao vivo/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retomar a estação' })).not.toBeInTheDocument()
  })

  it('dragging a limit does not measure the samples again, but changing what is measured does', async () => {
    let calls = 0
    server.use(
      http.post('*/api/editor/batch', () => {
        calls++
        return HttpResponse.json({ ok: true, samples: [], tools: [] })
      }),
    )
    await openEditor()
    const box = await screen.findByRole('textbox', { name: 'Limite mínimo' })
    await waitFor(() => expect(calls).toBe(1), { timeout: 3000 })
    await userEvent.clear(box)
    await userEvent.type(box, '55')
    await userEvent.tab()
    expect(useDraft.getState().draft?.job.tools[0].params.min_fraction).toBe(0.55)
    await new Promise((resolve) => setTimeout(resolve, 900)) // longer than the pause before a new measurement
    expect(calls).toBe(1)
    await userEvent.click(screen.getByRole('switch', { name: 'Qualquer matiz' })) // a band of hues: what is measured changed
    await waitFor(() => expect(calls).toBe(2), { timeout: 3000 })
  })

  it('a second editor is told the camera is taken, and the first one is not disturbed', async () => {
    useSession.getState().signIn('tok', 'maintainer', 3600)
    await openEditor()
    const socket = FakeSocket.all.at(-1)!
    socket.open()
    act(() => socket.say({ type: 'error', code: 'session_busy' }))
    expect(await screen.findByText('Outro editor está usando a câmera')).toBeInTheDocument()
    // the editor still works on the reference and the samples
    expect(screen.getByRole('heading', { level: 2, name: 'Ferramentas' })).toBeInTheDocument()
  })

  it('Auto uma vez measures the exposure on the camera and writes it as a fixed value, keeping its parameters', async () => {
    let sent: any = null
    server.use(
      http.post('*/api/camera/auto-exposure', async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({
          value_us: 4000.4,
          saturated_percent: 9.6,
          target_percent: 10,
          reached: true,
          limit: '',
          steps: [{ exposure_us: 4000.4, saturated_percent: 9.6 }],
        })
      }),
    )
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Imagem e disparo/ }))
    // Avançado shows the parameters of the measurement
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    const target = screen.getByLabelText('Brilho-alvo do Auto uma vez')
    expect(target).toHaveAttribute('placeholder', 'padrão: 10')
    await userEvent.type(target, '5')
    await userEvent.tab()
    expect(useDraft.getState().draft?.profile.exposure.auto_once).toEqual({ target_brightness: 5 })
    await userEvent.click(screen.getByRole('button', { name: 'Auto uma vez' }))
    expect(
      await screen.findByText('Exposição ajustada para 4000 µs (9,6 % de pixels saturados).'),
    ).toBeInTheDocument()
    expect(sent.exposure.auto_once).toEqual({ target_brightness: 5 })
    expect(useDraft.getState().draft?.profile.exposure).toEqual({
      mode: 'manual',
      value_us: 4000,
      auto_once: { target_brightness: 5 },
    })
    // typing another value, or going back to automatic, does not lose the parameters
    const value = screen.getByLabelText('Tempo de exposição')
    await userEvent.clear(value)
    await userEvent.type(value, '6000')
    await userEvent.tab()
    expect(useDraft.getState().draft?.profile.exposure.auto_once).toEqual({ target_brightness: 5 })
    expect(useDraft.getState().draft?.profile.exposure.value_us).toBe(6000)
  })

  it('the camera step shows the histogram and the focus meter of the live frame, and a log slider for a fixed exposure', async () => {
    useSession.getState().signIn('tok', 'maintainer', 3600)
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Imagem e disparo/ }))
    expect(screen.getByText(/Sem imagem ao vivo/)).toBeInTheDocument()
    const socket = FakeSocket.all.at(-1)!
    socket.open()
    act(() => socket.say({ type: 'ready', fps: 4, paused_by_session: true }))
    act(() =>
      socket.say({
        type: 'metrics',
        frame_id: 1,
        sharpness: 412,
        histogram: new Array(256).fill(1),
        clipped_low: 0,
        clipped_high: 2.4,
      }),
    )
    expect(await screen.findByText('2,4 % da imagem saturada')).toHaveClass('text-warn-text')
    expect(screen.getByRole('meter', { name: 'Nitidez' })).toHaveAttribute('aria-valuenow', '412')
    // a fixed exposure gets a slider on a log scale, written in µs, and it moves the value in the draft
    act(() =>
      useDraft.getState().edit((d) => (d.profile.exposure = { mode: 'manual', value_us: 8000 })),
    )
    const slider = await screen.findByRole('slider', { name: /Exposição \(escala logarítmica\)/ })
    slider.focus()
    const before = useDraft.getState().draft?.profile.exposure.value_us as number
    await userEvent.keyboard('{ArrowRight}')
    const after = useDraft.getState().draft?.profile.exposure.value_us as number
    expect(after).toBeGreaterThan(before)
    expect(after / before).toBeLessThan(1.03) // one position of 1000 over four decades
  })

  it('the measuring region of Auto uma vez is optional and drawn on the image', async () => {
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Imagem e disparo/ }))
    expect(screen.queryByLabelText('Brilho-alvo do Auto uma vez')).not.toBeInTheDocument() // Essencial
    await userEvent.click(screen.getByRole('radio', { name: 'Avançado' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Medir só numa região' }))
    expect(useDraft.getState().draft?.profile.exposure.auto_once.region).toEqual([
      0.25, 0.25, 0.75, 0.75,
    ])
    expect(screen.getByRole('button', { name: 'Desenhar a região de medição' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('switch', { name: 'Medir só numa região' }))
    expect(useDraft.getState().draft?.profile.exposure).not.toHaveProperty('auto_once')
  })

  it('the orientation of the image is chosen with the camera, kept out of the profile when normal, and told in the summary', async () => {
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Imagem e disparo/ }))
    const select = screen.getByRole('combobox', { name: 'Orientação da imagem' })
    expect(select).toHaveTextContent('Normal')
    await userEvent.click(select)
    await userEvent.click(screen.getByRole('option', { name: 'Espelhada' }))
    expect(useDraft.getState().draft?.profile.orientation).toBe('mirror')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar como versão 3' })
    expect(within(dialog).getByText('Câmera, orientação: Normal → Espelhada')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Orientação da imagem' }))
    await userEvent.click(screen.getByRole('option', { name: 'Normal' }))
    expect(useDraft.getState().draft?.profile).not.toHaveProperty('orientation')
  })

  it('the trigger is set with the image, in the first step, and the quality gates are a step of their own (TD-32)', async () => {
    await openEditor()
    const rail = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    await userEvent.click(rail.getByRole('button', { name: /^Imagem e disparo/ }))
    expect(screen.getByRole('heading', { level: 2, name: 'Imagem e disparo' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 3, name: 'Disparo' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Modo de disparo' })).toBeInTheDocument()
    await userEvent.click(rail.getByRole('button', { name: /^Qualidade/ }))
    expect(screen.getByRole('heading', { level: 2, name: 'Qualidade' })).toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Modo de disparo' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Brilho mínimo')).toBeInTheDocument()
  })

  it('the trigger is chosen in the top bar or in its step, and both are the same value', async () => {
    await openEditor()
    const bar = screen.getByRole('combobox', { name: 'Disparo' })
    await userEvent.click(bar)
    await userEvent.click(screen.getByRole('option', { name: 'Contínuo' }))
    expect(useDraft.getState().draft?.job.trigger.mode).toBe('continuous')
    await userEvent.click(
      within(screen.getByRole('navigation', { name: 'Passos do job' })).getByRole('button', {
        name: /^Imagem e disparo/,
      }),
    )
    expect(screen.getByRole('combobox', { name: 'Modo de disparo' })).toHaveTextContent('Contínuo')
    // continuous waits at least this long between inspections (FR-TRG-7)
    const interval = screen.getByLabelText('Intervalo mínimo entre inspeções')
    expect(interval).toHaveAttribute('placeholder', 'padrão: 500')
    await userEvent.type(interval, '1000')
    await userEvent.tab()
    expect(useDraft.getState().draft?.job.trigger.interval_ms).toBe(1000)
  })

  it('the save dialog lists what changed in words, and the last step offers the way on', async () => {
    await openEditor()
    const fraction = await screen.findByRole('textbox', { name: 'Limite mínimo' })
    await userEvent.clear(fraction)
    await userEvent.type(fraction, '60')
    await userEvent.tab()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar como versão 3' })
    expect(within(dialog).getByText('tampa: Fração mínima da área, 40% → 60%')).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    // "Próximo passo" leads forward, one step at a time
    await userEvent.click(screen.getByRole('button', { name: /Próximo passo: Qualidade/ }))
    expect(screen.getByRole('heading', { level: 2, name: 'Qualidade' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Próximo passo: Resultado e saídas/ }),
    ).toBeInTheDocument()
  })

  it('Resultado e saídas turns a tool into one that only informs', async () => {
    await openEditor()
    await userEvent.click(screen.getByRole('button', { name: /Resultado e saídas/ }))
    await userEvent.click(screen.getByRole('switch', { name: /Decide o resultado: tampa/ }))
    expect(useDraft.getState().draft?.job.tools[0].affects_result).toBe(false)
    await userEvent.click(screen.getByRole('switch', { name: /Decide o resultado: tampa/ }))
    expect(useDraft.getState().draft?.job.tools[0]).not.toHaveProperty('affects_result')
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

  it('opens the latest version as a draft, on the tools step, with the eight steps listed', async () => {
    await openEditor()
    expect(screen.getByText('rascunho a partir da v2')).toBeInTheDocument()
    const steps = within(screen.getByRole('navigation', { name: 'Passos do job' }))
    const labels = [
      'Imagem e disparo',
      'Amostras',
      'Âncora',
      'Ferramentas',
      'Qualidade',
      'Resultado e saídas',
      'Validar',
      'Salvar',
    ]
    const buttons = steps.getAllByRole('button')
    expect(buttons).toHaveLength(8)
    labels.forEach((label, i) =>
      expect(buttons[i]!.textContent?.replace(/^\d/, '').startsWith(label)).toBe(true),
    )
    // an existing job opens where most edits happen
    expect(screen.getByRole('heading', { level: 2, name: 'Ferramentas' })).toBeInTheDocument()
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
    const fraction = await screen.findByRole('textbox', { name: 'Limite mínimo' })
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
    const fraction = await screen.findByRole('textbox', { name: 'Limite mínimo' })
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
    expect(
      screen.getByRole('button', { name: /Qualidade.*precisa de atenção/ }),
    ).toBeInTheDocument()
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
    expect(screen.getByRole('heading', { level: 2, name: 'Imagem e disparo' })).toBeInTheDocument()
    // a new job learns from its reference image first: the tools can be read, not edited
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    expect(screen.getByText(/Este passo está bloqueado/)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Adicionar ferramenta' })).toBeDisabled()
    server.use(
      http.post('*/api/reference/capture', () =>
        HttpResponse.json({
          files: { 'reference/reference.png': 'AAAA' },
          width: 1920,
          height: 1080,
          brightness: 120,
          sharpness: 300,
        }),
      ),
    )
    await userEvent.click(screen.getByRole('button', { name: /Amostras/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Capturar a imagem de referência' }))
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Adicionar ferramenta' }))
    await userEvent.click(screen.getByRole('option', { name: /Código de barras/ }))
    await userEvent.click(screen.getAllByRole('button', { name: 'Adicionar' }).at(-1)!)
    await userEvent.click(screen.getByRole('button', { name: 'Salvar…' }))
    await userEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Salvar…' }),
    )
    await waitFor(() => expect(created).not.toBeNull())
    expect(created.base).toBeNull()
    expect(created.profile.exposure.value_us).toBe(8000)
    expect(created.add_files['reference/reference.png']).toBe('AAAA')
    expect(created.job.tools).toEqual([
      { id: 'code1', type: 'code', version: 1, roi: 'frame', params: {}, reason_fail: 'Falhou' },
    ])
  })
})

describe('the fine-tune of tolerances (docs/frontend.md §7.12)', () => {
  const openTune = async () => {
    useSession.getState().signIn('tok', 'supervisor', 3600)
    const app = renderApp(`/jobs/${JOB}/tune`)
    await screen.findByRole('heading', { level: 1, name: 'Ajuste fino — Tampa azul v2' })
    return app
  }

  it('shows the gauges of the tools that decide and nothing of regions, camera or tools', async () => {
    await openTune()
    expect(await screen.findByRole('textbox', { name: 'Limite mínimo' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Ferramentas|Imagem e disparo/ }),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Região' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Nova região')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar como v3…' })).toBeDisabled() // nothing changed yet
    expect(screen.getByRole('button', { name: 'Capturar como Boa' })).toBeInTheDocument()
  })

  it('a moved limit is saved with a required note, as the next version, then activated when verified', async () => {
    let sent: any = null
    let activated = 0
    server.use(
      http.post(`*/api/jobs/${JOB}/tune`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json(
          { id: JOB, version: 3, verified: true, problems: [], changes: [] },
          { status: 201 },
        )
      }),
      http.post(`*/api/jobs/${JOB}/versions/3/activate`, () => {
        activated++
        return HttpResponse.json({ activated: true, verified: true, warnings: [], override: false })
      }),
    )
    await openTune()
    const box = await screen.findByRole('textbox', { name: 'Limite mínimo' })
    await userEvent.clear(box)
    await userEvent.type(box, '55')
    await userEvent.tab()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar como v3…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar o ajuste como versão 3' })
    expect(within(dialog).getByRole('button', { name: 'Salvar…' })).toBeDisabled() // a note is required
    await userEvent.type(within(dialog).getByLabelText('O que você ajustou e por quê'), 'lote novo')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar…' }))
    expect(sent.notes).toBe('lote novo')
    expect(sent.base).toEqual({ id: JOB, version: 2 })
    expect(sent.job.tools[0].params.min_fraction).toBe(0.55)
    expect(sent.job.geometry).toEqual(version.job.geometry) // nothing else moved
    const done = await screen.findByRole('dialog', { name: 'Salvar o ajuste como versão 3' })
    expect(
      within(done).getByText('Versão 3 salva e verificada: pode ser ativada.'),
    ).toBeInTheDocument()
    await userEvent.click(within(done).getByRole('button', { name: 'Ativar a versão 3' }))
    await waitFor(() => expect(activated).toBe(1))
  })

  it('a version that did not pass verification says why and cannot be activated here', async () => {
    server.use(
      http.post(`*/api/jobs/${JOB}/tune`, () =>
        HttpResponse.json(
          {
            id: JOB,
            version: 3,
            verified: false,
            problems: ['ok1.png: esperado PASS'],
            changes: [],
          },
          { status: 201 },
        ),
      ),
    )
    await openTune()
    const box = await screen.findByRole('textbox', { name: 'Limite mínimo' })
    await userEvent.clear(box)
    await userEvent.type(box, '90')
    await userEvent.tab()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar como v3…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar o ajuste como versão 3' })
    await userEvent.type(within(dialog).getByLabelText('O que você ajustou e por quê'), 'teste')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar…' }))
    expect(await screen.findByText('ok1.png: esperado PASS')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ativar a versão 3' })).not.toBeInTheDocument()
  })

  it('a refusal of the server is shown with the fields it names', async () => {
    server.use(
      http.post(`*/api/jobs/${JOB}/tune`, () =>
        HttpResponse.json(
          {
            detail: 'No ajuste fino só mudam os limites de tolerância e as amostras',
            code: 'not_tunable',
            fields: {
              'tools.0.params.hue': 'Só os limites de tolerância podem mudar no ajuste fino',
            },
          },
          { status: 422 },
        ),
      ),
    )
    await openTune()
    const box = await screen.findByRole('textbox', { name: 'Limite mínimo' })
    await userEvent.clear(box)
    await userEvent.type(box, '60')
    await userEvent.tab()
    await userEvent.click(screen.getByRole('button', { name: 'Salvar como v3…' }))
    const dialog = screen.getByRole('dialog', { name: 'Salvar o ajuste como versão 3' })
    await userEvent.type(within(dialog).getByLabelText('O que você ajustou e por quê'), 'x')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Salvar…' }))
    expect(await screen.findByText(/Só os limites de tolerância podem mudar/)).toBeInTheDocument()
  })
})
