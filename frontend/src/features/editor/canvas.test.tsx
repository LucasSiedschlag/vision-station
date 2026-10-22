import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { mockApi } from '@/test/render'
import { LayerMenu } from './LayerMenu'
import { DEFAULT_LAYERS, drawn, useLayers } from './layers'
import type { ToolMarks } from '@/components/domain/MarkShapes'
import { RegionCanvas, layerOf, type Shape } from './RegionCanvas'

mockApi()

const image = { url: 'blob:x', width: 1920, height: 1080, source: 'reference' as const }
const shapes: Shape[] = [
  { id: 'roi:tampa', label: 'tampa', rect: [0.1, 0.1, 0.4, 0.4], kind: 'roi', editable: true },
  { id: 'anchor', label: 'âncora', rect: [0.5, 0.5, 0.9, 0.9], kind: 'anchor' },
  { id: 'presence', label: 'presença', rect: [0.2, 0.2, 0.8, 0.8], kind: 'presence' },
  { id: 'crop', label: 'recorte', rect: [0.3, 0.3, 0.4, 0.4], kind: 'presence', layer: null },
]

const measured: ToolMarks[] = [
  {
    id: 'tampa',
    passed: false,
    marks: [
      { kind: 'poly', role: 'defect', points: [[0.1, 0.1], [0.3, 0.1], [0.2, 0.3]], closed: true, text: '' },
      { kind: 'rect', role: 'expected', points: [[0.1, 0.1], [0.4, 0.4]], closed: true, text: '' },
      { kind: 'text', role: 'found', points: [[0.1, 0.1]], closed: true, text: 'LOTE-1' },
    ],
  },
]

const canvas = (layers = drawn({ master: true, on: DEFAULT_LAYERS })) =>
  render(
    <RegionCanvas
      image={image}
      shapes={shapes}
      selected={null}
      onSelect={() => {}}
      onChange={() => {}}
      drawing={null}
      emptyText="sem imagem"
      layers={layers}
      marks={measured}
      caption="Ao vivo"
    />,
  )
const drawnShapes = (root: HTMLElement) =>
  [...root.querySelectorAll('[data-shape]')].map((e) => e.getAttribute('data-shape'))

beforeEach(() => useLayers.setState({ master: true, on: DEFAULT_LAYERS }))

describe('the layers of the image (docs/frontend.md §18)', () => {
  it('a shape is in the layer of its kind, and a working aid is in none, so no switch hides it', () => {
    expect(shapes.map(layerOf)).toEqual(['regions', 'anchors', 'presence', null])
  })

  it('draws only the layers that are on, keeps the aids, and the master switch turns all off', () => {
    const all = canvas()
    expect(drawnShapes(all.container)).toEqual(['roi:tampa', 'anchor', 'presence', 'crop'])
    all.unmount()
    const some = canvas(
      drawn({ master: true, on: { ...DEFAULT_LAYERS, regions: false, anchors: false } }),
    )
    expect(drawnShapes(some.container)).toEqual(['presence', 'crop']) // the crop being drawn is never hidden
    some.unmount()
    const none = canvas(drawn({ master: false, on: DEFAULT_LAYERS }))
    expect(drawnShapes(none.container)).toEqual(['crop'])
  })

  it('says what the image is over its corner', () => {
    canvas()
    expect(screen.getByText('Ao vivo')).toBeInTheDocument()
  })
})

describe('Medições: what the tools measured (VIA-0124)', () => {
  const shapesOf = (root: HTMLElement) =>
    [...root.querySelectorAll('[data-mark]')].map((e) => `${e.getAttribute('data-mark')}:${e.getAttribute('data-role')}`)

  it('draws a shape per mark, the text apart, and a defect is never in the colour of a pass', () => {
    const { container } = canvas()
    expect(shapesOf(container)).toEqual(['poly:defect', 'rect:expected'])
    expect(screen.getByText('LOTE-1')).toBeInTheDocument()
    expect(container.querySelector('[data-role="defect"] path.stroke-fail')).not.toBeNull()
    expect(container.querySelector('[data-role="expected"] path.stroke-fg-muted')).not.toBeNull()
  })

  it('what an informative tool found is a warning, not the failure of the part (FR-INS-13)', () => {
    const informative = measured.map((t) => ({ ...t, informative: true }))
    const { container } = render(
      <RegionCanvas
        image={image}
        shapes={[]}
        selected={null}
        onSelect={() => {}}
        onChange={() => {}}
        drawing={null}
        emptyText="sem imagem"
        marks={informative}
      />,
    )
    expect(container.querySelector('[data-role="defect"] path.stroke-warn')).not.toBeNull()
    expect(container.querySelector('path.stroke-fail')).toBeNull()
    expect(screen.getByText('LOTE-1')).toHaveClass('text-warn-text')
  })

  it('is its own layer: off hides the marks and keeps the regions, and the master switch hides it too', () => {
    const off = canvas(drawn({ master: true, on: { ...DEFAULT_LAYERS, measures: false } }))
    expect(shapesOf(off.container)).toEqual([])
    expect(screen.queryByText('LOTE-1')).toBeNull()
    expect(drawnShapes(off.container)).toContain('roi:tampa')
    off.unmount()
    const none = canvas(drawn({ master: false, on: DEFAULT_LAYERS }))
    expect(shapesOf(none.container)).toEqual([])
  })

  it('a choice saved before the layer existed gets it on', async () => {
    const { measures, ...before } = DEFAULT_LAYERS
    void measures
    localStorage.setItem(
      'vision-station-layers',
      JSON.stringify({ state: { master: true, on: { ...before, grid: true } }, version: 1 }),
    )
    await useLayers.persist.rehydrate()
    expect(useLayers.getState().on).toEqual({ ...DEFAULT_LAYERS, grid: true })
  })
})

describe('Marcações: the split button and its menu', () => {
  it('the button turns everything off and on, the menu has a check per layer, and the choice is kept', async () => {
    render(<LayerMenu />)
    const button = screen.getByRole('button', { name: 'Marcações · 6/7' })
    expect(button).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(button)
    expect(useLayers.getState().master).toBe(false)
    expect(screen.getByRole('button', { name: 'Marcações · 0/7' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Marcações · 0/7' }))
    await userEvent.click(screen.getByRole('button', { name: 'Escolher as marcações' }))
    const grid = await screen.findByRole('menuitemcheckbox', { name: /Grade de pixels/ })
    expect(grid).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(grid)
    expect(useLayers.getState().on.grid).toBe(true)
    await userEvent.click(await screen.findByRole('menuitemcheckbox', { name: /Rótulos/ }))
    expect(useLayers.getState().on.labels).toBe(false)
    expect(screen.getByRole('menuitemcheckbox', { name: /Rótulos/ })).toHaveAttribute(
      'aria-checked',
      'false',
    )
    expect(JSON.parse(localStorage.getItem('vision-station-layers') ?? '{}').state.on.labels).toBe(
      false,
    )
  })

  it('the key M turns every marking on or off, except while typing', async () => {
    render(
      <>
        <LayerMenu />
        <input aria-label="nome" />
      </>,
    )
    await userEvent.keyboard('m')
    expect(useLayers.getState().master).toBe(false)
    await userEvent.keyboard('M')
    expect(useLayers.getState().master).toBe(true)
    await userEvent.type(screen.getByLabelText('nome'), 'm')
    expect(useLayers.getState().master).toBe(true)
  })
})

describe('zoom and pan of the image (docs/frontend.md §10.2)', () => {
  const zoomText = () => screen.getByText(/^\d+ %$/).textContent

  it('the buttons zoom in and out, fit and go to 100 %, and the mini-map appears above 200 %', async () => {
    canvas()
    const fit = zoomText() // 800 of 1920 pixels: 42 %
    expect(fit).toBe('42 %')
    expect(screen.queryByRole('button', { name: /^Mapa da imagem/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Tamanho real (100 %)' }))
    expect(zoomText()).toBe('100 %')
    await userEvent.click(screen.getByRole('button', { name: 'Aproximar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Aproximar' }))
    expect(Number.parseInt(zoomText() ?? '0')).toBeGreaterThan(200)
    expect(screen.getByRole('button', { name: /^Mapa da imagem/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ajustar à janela' }))
    expect(zoomText()).toBe(fit)
    await userEvent.click(screen.getByRole('button', { name: 'Afastar' }))
    expect(zoomText()).toBe(fit) // never smaller than fitted
  })

  it('the wheel zooms, and the keys 1 and Ctrl+0 act while the pointer is over the image', () => {
    canvas()
    const frame = screen
      .getByRole('group', { name: 'Regiões sobre a imagem' })
      .closest('div')!.parentElement!
    fireEvent.pointerEnter(frame)
    fireEvent.wheel(frame, { deltaY: -400, clientX: 100, clientY: 100 })
    expect(Number.parseInt(zoomText() ?? '0')).toBeGreaterThan(42)
    fireEvent.keyDown(window, { key: '0', ctrlKey: true })
    expect(zoomText()).toBe('42 %')
    fireEvent.keyDown(window, { key: '1' })
    expect(zoomText()).toBe('100 %')
  })

  it('the keys do nothing while the pointer is elsewhere or something is being typed', () => {
    canvas()
    fireEvent.keyDown(window, { key: '1' })
    expect(zoomText()).toBe('42 %') // pointer not over the image
    const frame = screen
      .getByRole('group', { name: 'Regiões sobre a imagem' })
      .closest('div')!.parentElement!
    fireEvent.pointerEnter(frame)
    const typing = document.body.appendChild(document.createElement('input'))
    act(() => {
      fireEvent.keyDown(typing, { key: '1' })
    })
    expect(zoomText()).toBe('42 %')
  })

  it('a key still works with a button of the image holding the focus, but Space stays the button’s', () => {
    canvas()
    const frame = screen
      .getByRole('group', { name: 'Regiões sobre a imagem' })
      .closest('div')!.parentElement!
    fireEvent.pointerEnter(frame)
    const button = screen.getByRole('button', { name: 'Aproximar' })
    fireEvent.keyDown(button, { key: '1' })
    expect(zoomText()).toBe('100 %')
    fireEvent.keyDown(button, { key: '0', ctrlKey: true })
    expect(zoomText()).toBe('42 %')
    const space = fireEvent.keyDown(button, { code: 'Space', key: ' ' })
    expect(space).toBe(true) // not cancelled: the button is pressed, the image is not grabbed
  })
})
