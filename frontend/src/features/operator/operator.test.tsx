import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useLive } from '@/api/live'
import { renderApp, server, setLive, mockApi } from '@/test/render'

mockApi()

/* eslint-disable @typescript-eslint/no-explicit-any -- the open shape of a result in the fixtures */

const tool = (id: string, passed: boolean, over: Record<string, unknown> = {}) => ({
  id,
  type: 'color',
  version: 1,
  passed,
  score: passed ? 1 : 0.2,
  margin: null,
  values: { fraction: 0.12 },
  units: { fraction: 'fraction' },
  criteria: [
    { code: 'min_fraction', kind: 'min', measure: 'fraction', value: 0.12, passed, score: 1 },
  ],
  affects_result: true,
  error: '',
  error_code: 0,
  region: [0.1, 0.1, 0.3, 0.3],
  ...over,
})

const AT = '2026-10-14T14:31:02-03:00'
const result = (outcome: 'PASS' | 'FAIL', tools: unknown[]) => ({
  outcome,
  reason: outcome === 'FAIL' ? 'Tampa ausente' : '',
  scores: {},
  duration_ms: 290,
  at: AT,
  tools,
})

/** A result on screen, with its picture, as if the socket had delivered them. */
function showing(outcome: 'PASS' | 'FAIL', tools: unknown[], over: Record<string, unknown> = {}) {
  const last = result(outcome, tools)
  setLive({
    state: 'ShowingResult',
    last_result: last,
    last_record_id: 'rec-1',
    recent: [{ outcome, reason: last.reason, at: AT, record_id: 'rec-1' }],
    ...over,
  })
  useLive.setState({
    frame: new Blob(['x'], { type: 'image/jpeg' }),
    results: { 'rec-1': last as any },
  })
}

beforeEach(() => {
  // jsdom has no image decoding: a picture of 640 × 480 is enough for the markings to know their frame
  globalThis.createImageBitmap = (() =>
    Promise.resolve({ width: 640, height: 480, close() {} })) as unknown as typeof createImageBitmap
})
afterEach(() => {
  vi.useRealTimers()
})

describe('the lines under the verdict', () => {
  it('lists the deciding tools, the failing one first in word and icon, with its value', () => {
    showing('FAIL', [
      tool('lote', true),
      tool('tampa', false),
      tool('logo', true, { affects_result: false }),
    ])
    renderApp('/')
    const lines = screen.getByRole('list', { name: 'Ferramentas' })
    const items = Array.from(lines.querySelectorAll('li')).map((li) => li.textContent)
    expect(items).toEqual(['Reprovadotampa12%', 'Aprovadolote12%'])
  })

  it('counts the lines past the sixth', () => {
    showing(
      'FAIL',
      Array.from({ length: 9 }, (_, i) => tool(`t${i}`, i % 2 === 0)),
    )
    renderApp('/')
    expect(screen.getByText('+ 3 outras')).toBeInTheDocument()
  })

  it('shows none while the station is not showing a result', () => {
    setLive()
    renderApp('/')
    expect(screen.queryByRole('list', { name: 'Ferramentas' })).not.toBeInTheDocument()
  })
})

describe('the markings', () => {
  const marks = () => screen.queryAllByLabelText(/^Região de /)

  it('a failure is drawn by default, with the failing region said in words', async () => {
    showing('FAIL', [tool('lote', true), tool('tampa', false)])
    renderApp('/')
    expect(await screen.findByLabelText('Região de tampa: reprovou')).toBeInTheDocument()
    expect(screen.getByLabelText('Região de lote: passou')).toBeInTheDocument()
  })

  it('a pass is not, until the operator turns the markings on; the verdict stays whatever they choose', async () => {
    showing('PASS', [tool('lote', true)])
    renderApp('/')
    const button = screen.getByRole('button', { name: 'Marcações' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(marks()).toHaveLength(0)
    await userEvent.click(button)
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByLabelText('Região de lote: passou')).toBeInTheDocument()
    await userEvent.click(button)
    expect(marks()).toHaveLength(0)
    expect(screen.getByRole('status', { name: 'Resultado' })).toHaveTextContent('APROVADO')
  })

  it('turning them off hides no failing tool: it is still named in the lines', async () => {
    showing('FAIL', [tool('tampa', false)])
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: 'Marcações' }))
    expect(marks()).toHaveLength(0)
    expect(screen.getByRole('list', { name: 'Ferramentas' })).toHaveTextContent('tampa')
  })

  it('the station can take the choice away from the operator, and then the default rules', async () => {
    showing('FAIL', [tool('tampa', false)], { operator_markings: false, markings: 'never' })
    renderApp('/')
    expect(screen.queryByRole('button', { name: 'Marcações' })).not.toBeInTheDocument()
    expect(marks()).toHaveLength(0)
  })
})

describe('the last results as pictures', () => {
  beforeEach(() => {
    server.use(
      http.get('*/api/results/rec-1/thumb', () =>
        HttpResponse.arrayBuffer(new Uint8Array([0xff, 0xd8]).buffer, {
          headers: { 'Content-Type': 'image/jpeg' },
        }),
      ),
    )
  })

  it('each is a picture with its outcome in words; touching one freezes that result for a while', async () => {
    showing('FAIL', [tool('tampa', false)], {
      state: 'Ready',
      showing_result: false,
      message: 'Aguardando peça',
    })
    const { container } = renderApp('/')
    expect(container.querySelector('img')).toHaveAttribute('src', '/api/results/rec-1/thumb')
    const thumb = screen.getByRole('button', { name: /Reprovado às .*: Tampa ausente/ })
    await userEvent.click(thumb)
    const banner = await screen.findByText(/^Resultado das /)
    expect(banner).toBeInTheDocument()
    expect(thumb).toHaveAttribute('aria-pressed', 'true')
    // its markings come with it, though the station is only waiting now
    expect(await screen.findByLabelText('Região de tampa: reprovou')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar ao vivo' }))
    expect(screen.queryByText(/^Resultado das /)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/^Região de /)).not.toBeInTheDocument()
  })

  it('goes back to the live image by itself after ten seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    showing('FAIL', [tool('tampa', false)], { state: 'Ready' })
    renderApp('/')
    await user.click(screen.getByRole('button', { name: /Reprovado às / }))
    expect(await screen.findByText(/^Resultado das /)).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_100)
    })
    expect(screen.queryByText(/^Resultado das /)).not.toBeInTheDocument()
  })

  it('a new result ends it: an old picture is never taken for the present', async () => {
    showing('FAIL', [tool('tampa', false)], { state: 'Ready' })
    renderApp('/')
    await userEvent.click(screen.getByRole('button', { name: /Reprovado às / }))
    expect(await screen.findByText(/^Resultado das /)).toBeInTheDocument()
    act(() =>
      useLive.getState().apply({
        type: 'result',
        ...(result('PASS', []) as any),
        record_id: 'rec-2',
        job: { id: 'j', name: 'x', version: 1, number: null, content_hash: null },
      } as any),
    )
    await waitFor(() => expect(screen.queryByText(/^Resultado das /)).not.toBeInTheDocument())
  })

  it('a result that was not recorded has no picture to open', () => {
    setLive({ recent: [{ outcome: 'PASS', reason: '', at: AT, record_id: null }] })
    renderApp('/')
    expect(screen.getByRole('button', { name: /Aprovado às / })).toBeDisabled()
  })
})
