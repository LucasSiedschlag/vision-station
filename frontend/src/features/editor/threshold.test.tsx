import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '@/test/render'
import schemas from '@/test/tool-schemas.json'
import { ImageAidsProvider, type ImageAids } from './image-aids'
import { SchemaForm, type Schema } from './SchemaForm'

mockApi()

const blob = schemas.blob as Schema

function Form({
  initial,
  aids = null,
}: {
  initial: Record<string, unknown>
  aids?: ImageAids | null
}) {
  const [value, setValue] = useState(initial)
  const form = <SchemaForm schema={blob} level={1} value={value} onChange={setValue} />
  return (
    <>
      {aids ? <ImageAidsProvider value={aids}>{form}</ImageAidsProvider> : form}
      <output data-testid="value">{JSON.stringify(value)}</output>
    </>
  )
}
const valueOf = () => JSON.parse(screen.getByTestId('value').textContent ?? '{}')

/** 20 x 1 pixels: the left half black, the right half white. */
const twoLevels = (): ImageData =>
  ({
    width: 20,
    height: 1,
    data: Uint8ClampedArray.from(
      Array.from({ length: 20 }, (_, i) => (i < 10 ? [0, 0, 0, 255] : [255, 255, 255, 255])).flat(),
    ),
  }) as ImageData

const aidsWith = (over: Partial<ImageAids> = {}): ImageAids => ({
  pixels: twoLevels(),
  region: null,
  sampling: null,
  sample: () => Promise.resolve(null),
  cancelSample: () => {},
  showMask: () => {},
  ...over,
})

describe('the gray threshold control', () => {
  it('is left out when the object is of a colour', () => {
    render(<Form initial={{ mode: 'color' }} aids={aidsWith()} />)
    expect(screen.queryByRole('slider', { name: /Limiar de cinza/ })).toBeNull()
  })

  it('shows Otsu as the automatic level and writes nothing', () => {
    render(<Form initial={{ mode: 'dark' }} aids={aidsWith()} />)
    expect(screen.getByRole('slider', { name: /Limiar de cinza/ })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
    expect(screen.getByText(/automático: 0/)).toBeInTheDocument()
    expect(valueOf()).toEqual({ mode: 'dark' })
  })

  it('writes the level when the line moves and takes it out with Automático', async () => {
    render(<Form initial={{ mode: 'light', threshold: 100 }} aids={aidsWith()} />)
    const line = screen.getByRole('slider', { name: /Limiar de cinza/ })
    expect(line).toHaveAttribute('aria-valuenow', '100')
    fireEvent.keyDown(line, { key: 'ArrowRight' })
    expect(valueOf().threshold).toBe(101)
    await userEvent.click(screen.getByRole('button', { name: 'Automático' }))
    expect(valueOf()).toEqual({ mode: 'light' })
  })

  it('starts a chosen level from the automatic one', async () => {
    render(<Form initial={{ mode: 'dark' }} aids={aidsWith()} />)
    await userEvent.click(screen.getByRole('button', { name: 'Automático' }))
    expect(valueOf().threshold).toBe(0)
  })

  it('still has the number field when there is no image', () => {
    render(<Form initial={{ mode: 'dark', threshold: 80 }} />)
    expect(screen.getByText('Sem imagem para mostrar o histograma.')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /Limiar de cinza/ })).toHaveValue('80')
  })

  it('does not break on a region with a single level', () => {
    const flat = { width: 4, height: 1, data: new Uint8ClampedArray(16).fill(90) } as ImageData
    render(<Form initial={{ mode: 'light' }} aids={aidsWith({ pixels: flat })} />)
    expect(screen.getByRole('slider', { name: /Limiar de cinza/ })).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
  })

  it('says whose pixels the share is of: the tool\'s region when it is known, else the whole image', () => {
    const { unmount } = render(<Form initial={{ mode: 'dark', threshold: 100 }} aids={aidsWith()} />)
    expect(screen.getByText(/% da imagem é objeto/)).toBeInTheDocument()
    unmount()
    render(
      <Form
        initial={{ mode: 'dark', threshold: 100 }}
        aids={aidsWith({ region: [0, 0, 0.5, 1] })}
      />,
    )
    expect(screen.getByText(/% da região é objeto/)).toBeInTheDocument()
  })
})
