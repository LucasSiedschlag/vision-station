import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { HueBar } from '@/components/vision/HueBar'
import { Toaster } from '@/components/ui/toaster'
import { mockApi, server } from '@/test/render'
import schemas from '@/test/tool-schemas.json'
import { ImageAidsProvider, type ImageAids } from './image-aids'
import { SchemaForm, hiddenChanged, type Schema } from './SchemaForm'

mockApi()

/* eslint-disable @typescript-eslint/no-explicit-any -- request bodies in the mocks */

const color = schemas.color as Schema
const blob = schemas.blob as Schema

function Form({
  schema = color,
  initial,
  level = 1,
  aids = null,
  onWrite,
}: {
  schema?: Schema
  initial: Record<string, unknown>
  level?: 1 | 2 | 3
  aids?: ImageAids | null
  onWrite?: (value: Record<string, unknown>) => void
}) {
  const [value, setValue] = useState(initial)
  const form = (
    <SchemaForm
      schema={schema}
      level={level}
      value={value}
      onChange={(next) => {
        setValue(next)
        onWrite?.(next)
      }}
    />
  )
  return (
    <>
      <Toaster />
      {aids ? <ImageAidsProvider value={aids}>{form}</ImageAidsProvider> : form}
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  )
}
const valueOf = () => JSON.parse(screen.getByTestId('value').textContent ?? '{}')

const aidsWith = (over: Partial<ImageAids> = {}): ImageAids => ({
  pixels: null,
  region: null,
  sampling: null,
  sample: () => Promise.resolve(null),
  cancelSample: () => {},
  showMask: () => {},
  ...over,
})

describe('the hue bar', () => {
  it('moves a handle with the arrows and wraps through red, writing only that handle', () => {
    const seen: [number, number][] = []
    render(
      <HueBar
        value={[170, 10]}
        saturation={200}
        brightness={200}
        labels={['Matiz inicial', 'Matiz final']}
        onChange={(next) => seen.push(next)}
      />,
    )
    const from = screen.getByRole('slider', { name: 'Matiz inicial' })
    const to = screen.getByRole('slider', { name: 'Matiz final' })
    expect(from).toHaveAttribute('aria-valuenow', '340') // degrees: 2 per hue
    expect(to).toHaveAttribute('aria-valuetext', '20°')
    fireEvent.keyDown(to, { key: 'ArrowLeft' })
    expect(seen.at(-1)).toEqual([170, 9])
    fireEvent.keyDown(from, { key: 'ArrowRight', shiftKey: true })
    expect(seen.at(-1)).toEqual([175, 10])
    // the circle has no end: a handle at 179 goes on to 0, the band stays one band
    seen.length = 0
    render(
      <HueBar
        value={[100, 179]}
        saturation={200}
        brightness={200}
        labels={['de', 'até']}
        onChange={(next) => seen.push(next)}
      />,
    )
    fireEvent.keyDown(screen.getByRole('slider', { name: 'até' }), { key: 'ArrowRight' })
    expect(seen.at(-1)).toEqual([100, 0])
  })
})

describe('the colour picker', () => {
  it('draws the range itself: saturation and value are not a second time in the form, at any level', () => {
    for (const level of [1, 2, 3] as const) {
      const { unmount } = render(
        <Form initial={{ hue: [100, 125], min_fraction: 0.5 }} level={level} />,
      )
      expect(screen.getAllByRole('slider', { name: /^Saturação mínima/ })).toHaveLength(1)
      expect(screen.getAllByRole('slider', { name: /^Brilho máximo/ })).toHaveLength(1)
      expect(
        screen.queryByRole('spinbutton', { name: /^Saturação mínima/ }),
      ).not.toBeInTheDocument()
      unmount()
    }
  })

  it('does not count what it draws among the settings a level hides', () => {
    expect(
      hiddenChanged(color, { hue: [1, 2], s_min: 10, s_max: 200, v_min: 5, v_max: 90 }, 1),
    ).toEqual([])
    expect(hiddenChanged(color, { axis: 'x', line_min: 0.4 }, 1).sort()).toEqual([
      'axis',
      'line_min',
    ])
  })

  it('shows the same range in degrees and percent, or in OpenCV numbers at the Especialista level', () => {
    const range = {
      hue: [100, 125],
      s_min: 128,
      s_max: 255,
      v_min: 64,
      v_max: 255,
      min_fraction: 0.5,
    }
    const { unmount } = render(<Form initial={range} level={1} />)
    expect(screen.getByText('200° – 250°')).toBeInTheDocument()
    expect(screen.getByText('50 % – 100 %')).toBeInTheDocument()
    unmount()
    render(<Form initial={range} level={3} />)
    expect(screen.getByText('200° – 250° (100 – 125)')).toBeInTheDocument()
    expect(screen.getByText('128 – 255')).toBeInTheDocument()
  })

  it('writes a value only when its own handle moves: a level that rounds never rewrites what nobody touched', async () => {
    const writes: Record<string, unknown>[] = []
    // 100 of 255 is 39 %, and 39 % is 99: showing it must not change it
    render(
      <Form
        initial={{
          hue: [100, 125],
          s_min: 100,
          s_max: 255,
          v_min: 70,
          v_max: 255,
          min_fraction: 0.5,
        }}
        onWrite={(v) => writes.push(v)}
      />,
    )
    const to = screen.getByRole('slider', { name: 'Matiz final' })
    fireEvent.keyDown(to, { key: 'ArrowRight' })
    expect(writes.at(-1)).toEqual({
      hue: [100, 126],
      s_min: 100,
      s_max: 255,
      v_min: 70,
      v_max: 255,
      min_fraction: 0.5,
    })
    const smax = screen.getAllByRole('slider', { name: /^Saturação máxima/ })[0]!
    smax.focus()
    await userEvent.keyboard('{ArrowLeft}')
    const last = writes.at(-1)!
    expect(last.s_min).toBe(100) // the other thumb of the pair kept its exact value
    expect(last.s_max).toBe(252) // 99 % of 255 is the nearest level of 255 − one step
    expect(last.v_min).toBe(70)
  })

  it('takes any hue (a gray, black or white) as no hue at all, and back to a band', async () => {
    render(<Form initial={{ hue: [100, 125], min_fraction: 0.5 }} />)
    await userEvent.click(screen.getByRole('switch', { name: 'Qualquer matiz' }))
    expect('hue' in valueOf()).toBe(false)
    expect(screen.queryByRole('slider', { name: 'Matiz inicial' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('switch', { name: 'Qualquer matiz' }))
    expect(valueOf().hue).toEqual([0, 179])
  })

  it('Folga widens and narrows from the range last set by hand, and a change from outside is the new base', async () => {
    render(
      <Form
        initial={{
          hue: [100, 120],
          s_min: 100,
          s_max: 200,
          v_min: 60,
          v_max: 220,
          min_fraction: 0.5,
        }}
      />,
    )
    const margin = screen.getByRole('slider', { name: /Folga/ })
    margin.focus()
    await userEvent.keyboard('{ArrowRight}{ArrowRight}{ArrowRight}') // three steps of 2°
    expect(valueOf().hue).toEqual([97, 123])
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}{ArrowLeft}') // and back: no drift
    expect(valueOf()).toMatchObject({
      hue: [100, 120],
      s_min: 100,
      s_max: 200,
      v_min: 60,
      v_max: 220,
    })
    // widened, then a handle of the hue moved by hand: that is the new base and Folga starts at zero
    await userEvent.keyboard('{ArrowRight}{ArrowRight}')
    fireEvent.keyDown(screen.getByRole('slider', { name: 'Matiz final' }), { key: 'ArrowRight' })
    expect(screen.getByRole('slider', { name: /Folga/ })).toHaveValue('0')
  })

  it('works inside a locator, where the colour range is an object of its own', async () => {
    render(<Form schema={blob} initial={{ mode: 'color', color: { hue: [100, 125] } }} />)
    expect(screen.getByRole('slider', { name: 'Matiz inicial' })).toBeInTheDocument()
    expect(screen.getAllByRole('slider', { name: /^Saturação mínima/ })).toHaveLength(1)
  })
})

describe('the eyedropper and the proposal', () => {
  const found = {
    ok: true,
    hue: [104, 118],
    s_min: 110,
    s_max: 255,
    v_min: 80,
    v_max: 255,
    pixels: 900,
    kept: 0.97,
    leak: 0.01,
  }

  it('samples, shows the proposal as a ghost and applies it only when told; excluded samples go with the next request', async () => {
    const bodies: any[] = []
    server.use(
      http.post('*/api/editor/suggest/colour', async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json(found)
      }),
    )
    const crops = ['PNG-CAP', 'PNG-LABEL']
    render(
      <Form
        initial={{ hue: [0, 179], min_fraction: 0.5 }}
        aids={aidsWith({ sample: () => Promise.resolve(crops.shift() ?? null) })}
      />,
    )
    expect(screen.getByRole('button', { name: /Excluir cor/ })).toBeDisabled() // nothing to exclude from yet
    await userEvent.click(screen.getByRole('button', { name: /Incluir cor/ }))
    const status = (await screen.findByText(/Faixa proposta/)).closest('div')!
    expect(within(status).getByText(/Faixa proposta: matiz 208°–236°/)).toBeInTheDocument()
    expect(
      within(status).getByText(/Mantém 97 % da cor amostrada\. Deixa 1 % do que você excluiu/),
    ).toBeInTheDocument()
    expect(bodies[0]).toEqual({ include: ['PNG-CAP'], exclude: [] })
    expect(valueOf().hue).toEqual([0, 179]) // a proposal is not applied
    await userEvent.click(screen.getByRole('button', { name: /Excluir cor/ }))
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[1]).toEqual({ include: ['PNG-CAP'], exclude: ['PNG-LABEL'] })
    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(valueOf()).toMatchObject({ hue: [104, 118], s_min: 110, v_min: 80 })
    expect(screen.queryByRole('button', { name: 'Aplicar' })).not.toBeInTheDocument()
  })

  it('discarding leaves the range as it was, and the samples can be cleared', async () => {
    server.use(http.post('*/api/editor/suggest/colour', () => HttpResponse.json(found)))
    render(
      <Form
        initial={{ hue: [10, 20], min_fraction: 0.5 }}
        aids={aidsWith({ sample: () => Promise.resolve('PNG') })}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /Incluir cor/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Descartar' }))
    expect(valueOf().hue).toEqual([10, 20])
    await userEvent.click(
      screen.getByRole('button', { name: /Limpar amostras \(1 incluídas, 0 excluídas\)/ }),
    )
    expect(screen.queryByRole('button', { name: /Limpar amostras/ })).not.toBeInTheDocument()
  })

  it('says why when the server has no range to propose', async () => {
    server.use(
      http.post('*/api/editor/suggest/colour', () =>
        HttpResponse.json({ ok: false, message: 'Poucos pixels para propor uma cor' }),
      ),
    )
    render(
      <Form
        initial={{ hue: [10, 20], min_fraction: 0.5 }}
        aids={aidsWith({ sample: () => Promise.resolve('PNG') })}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: /Incluir cor/ }))
    expect(await screen.findByText('Poucos pixels para propor uma cor')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aplicar' })).not.toBeInTheDocument()
  })

  it('hatches the mask of the range on the image while the picker is there, and not after', async () => {
    const shown: unknown[] = []
    const aids = aidsWith({ showMask: (r) => shown.push(r) })
    const { unmount } = render(
      <Form initial={{ hue: [100, 125], min_fraction: 0.5 }} aids={aids} />,
    )
    expect(shown.at(-1)).toMatchObject({ hue: [100, 125] })
    await userEvent.click(screen.getByRole('switch', { name: 'Máscara na imagem' }))
    expect(shown.at(-1)).toBeNull()
    await userEvent.click(screen.getByRole('switch', { name: 'Máscara na imagem' }))
    expect(shown.at(-1)).not.toBeNull()
    unmount()
    expect(shown.at(-1)).toBeNull()
  })

  it('has no eyedropper where there is no image beside it', () => {
    render(<Form initial={{ hue: [100, 125], min_fraction: 0.5 }} />)
    expect(screen.queryByRole('button', { name: /Incluir cor/ })).not.toBeInTheDocument()
    act(() => {})
  })
})
