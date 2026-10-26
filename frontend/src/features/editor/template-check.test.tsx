import { act, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Toaster } from '@/components/ui/toaster'
import { mockApi, server } from '@/test/render'
import { text } from '@/texts'
import { TemplateCheck, type ModelCheck } from './TemplateCheck'
import { cropPng, type EditorImage } from './image'
import type * as ImageModule from './image'

vi.mock('./image', async (orig) => ({
  ...(await orig<typeof ImageModule>()),
  cropPng: vi.fn(async () => 'AAAA'),
}))

mockApi()
beforeEach(() => vi.mocked(cropPng).mockReset().mockResolvedValue('AAAA'))

const image: EditorImage = {
  url: 'blob:x',
  width: 1000,
  height: 500,
  source: 'reference',
}
const answer = (body: Record<string, unknown>) =>
  server.use(
    http.post('*/api/editor/inspect/model', () =>
      HttpResponse.json({
        ok: true,
        message: null,
        width: 90,
        height: 60,
        flat: false,
        points: null,
        reason: null,
        ...body,
      }),
    ),
  )

describe('the template check', () => {
  it('sends the crop and shows its size, contour points and full-size keyboard-accessible preview', async () => {
    const bodies: unknown[] = []
    server.use(
      http.post('*/api/editor/inspect/model', async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json({
          ok: true,
          width: 90,
          height: 60,
          flat: false,
          points: 412,
          reason: null,
          message: null,
        })
      }),
    )
    const seen: (ModelCheck | null)[] = []
    render(
      <TemplateCheck
        image={image}
        crop={[0.1, 0.1, 0.3, 0.4]}
        shape
        onResult={(r) => seen.push(r)}
      />,
    )
    expect(await screen.findByText('412 pontos de contorno')).toBeInTheDocument()
    expect(screen.getByText('90 × 60 px')).toBeInTheDocument()
    expect(bodies).toEqual([{ image: 'AAAA' }])
    expect(cropPng).toHaveBeenCalledWith(image, [0.1, 0.1, 0.3, 0.4])
    const preview = screen.getByRole('img', { name: 'Recorte em tamanho real' })
    expect(preview).toHaveAttribute('src', 'data:image/png;base64,AAAA')
    expect(preview).toHaveStyle({ imageRendering: 'pixelated' })
    expect(preview).toHaveClass('max-w-none')
    const scroll = screen.getByRole('group', { name: 'Recorte em tamanho real' })
    expect(scroll).toHaveAttribute('tabindex', '0')
    expect(scroll).toHaveClass('max-h-48', 'overflow-auto')
    await waitFor(() => expect(seen.at(-1)).toEqual({ usable: true, flat: false, points: 412 }))
  })

  it('says why a shape model is refused and reports it as unusable', async () => {
    answer({ reason: 'O recorte tem menos de 12 pixels de lado' })
    const onResult = vi.fn()
    render(<TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape onResult={onResult} />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'O recorte tem menos de 12 pixels de lado',
    )
    expect(onResult).toHaveBeenLastCalledWith({ usable: false, flat: false, points: null })
  })

  it('without a shape model accepts a non-flat crop even if it has no contour model', async () => {
    answer({ reason: 'sem bordas' })
    const onResult = vi.fn()
    render(
      <TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape={false} onResult={onResult} />,
    )
    expect(await screen.findByText('90 × 60 px')).toBeInTheDocument()
    expect(screen.queryByText(/pontos de contorno/)).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(onResult).toHaveBeenLastCalledWith({ usable: true, flat: false, points: null })
  })

  it.each([true, false])('refuses a flat crop with the fallback text (shape=%s)', async (shape) => {
    answer({ flat: true })
    const onResult = vi.fn()
    render(
      <TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape={shape} onResult={onResult} />,
    )
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'O recorte é plano: não há o que casar.',
    )
    expect(onResult).toHaveBeenLastCalledWith({ usable: false, flat: true, points: null })
  })

  it('reports nothing and does not crop when there is no crop or image', () => {
    const onResult = vi.fn()
    const { rerender } = render(
      <TemplateCheck image={image} crop={null} shape onResult={onResult} />,
    )
    expect(screen.queryByRole('img')).toBeNull()
    expect(onResult).toHaveBeenLastCalledWith(null)
    rerender(<TemplateCheck image={null} crop={[0.1, 0.1, 0.3, 0.4]} shape onResult={onResult} />)
    expect(onResult).toHaveBeenLastCalledWith(null)
    expect(cropPng).not.toHaveBeenCalled()
  })

  it('clears the previous result while a new crop is checked, and when the crop is removed', async () => {
    answer({ points: 412 })
    const onResult = vi.fn()
    const { rerender } = render(
      <TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape onResult={onResult} />,
    )
    await screen.findByText('412 pontos de contorno')
    answer({ points: 87 })
    rerender(<TemplateCheck image={image} crop={[0.2, 0.2, 0.4, 0.5]} shape onResult={onResult} />)
    expect(onResult).toHaveBeenLastCalledWith(null)
    expect(screen.queryByRole('img')).toBeNull()
    await screen.findByText('87 pontos de contorno')
    rerender(<TemplateCheck image={image} crop={null} shape onResult={onResult} />)
    expect(onResult).toHaveBeenLastCalledWith(null)
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('ignores an old response after the crop changes', async () => {
    let finish!: (response: Response) => void
    const oldResponse = new Promise<Response>((resolve) => {
      finish = resolve
    })
    let requests = 0
    server.use(
      http.post('*/api/editor/inspect/model', () => {
        requests += 1
        if (requests === 1) return oldResponse
        return HttpResponse.json({ ok: true, width: 30, height: 20, flat: false, points: 87 })
      }),
    )
    const onResult = vi.fn()
    const { rerender } = render(
      <TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape onResult={onResult} />,
    )
    await waitFor(() => expect(requests).toBe(1))
    rerender(<TemplateCheck image={image} crop={[0.2, 0.2, 0.4, 0.5]} shape onResult={onResult} />)
    await screen.findByText('87 pontos de contorno')
    const calls = onResult.mock.calls.length
    const received = new Promise<void>((resolve) => {
      const done = () => {
        server.events.removeListener('request:end', done)
        resolve()
      }
      server.events.on('request:end', done)
    })
    await act(async () => {
      finish(HttpResponse.json({ ok: true, width: 90, height: 60, flat: false, points: 412 }))
      await received
    })
    expect(onResult).toHaveBeenCalledTimes(calls)
    expect(screen.queryByText('412 pontos de contorno')).toBeNull()
    expect(screen.getByText('30 × 20 px')).toBeInTheDocument()
  })

  it.each(['http', 'image', 'crop'] as const)(
    'reports no result and shows a toast on a %s failure',
    async (failure) => {
      if (failure === 'http') {
        server.use(
          http.post('*/api/editor/inspect/model', () =>
            HttpResponse.json({ detail: 'Falha ao inspecionar' }, { status: 500 }),
          ),
        )
      } else if (failure === 'image') {
        answer({ ok: false, message: 'Imagem inválida' })
      } else {
        vi.mocked(cropPng).mockRejectedValueOnce(new Error('crop failed'))
      }
      const onResult = vi.fn()
      render(
        <>
          <Toaster />
          <TemplateCheck image={image} crop={[0.1, 0.1, 0.3, 0.4]} shape onResult={onResult} />
        </>,
      )
      const message =
        failure === 'http'
          ? 'Falha ao inspecionar'
          : failure === 'image'
            ? 'Imagem inválida'
            : text.ui.noServer
      expect(await screen.findByText(message)).toBeInTheDocument()
      expect(onResult).toHaveBeenLastCalledWith(null)
      expect(onResult.mock.calls.every(([r]) => r === null)).toBe(true)
      expect(screen.queryByRole('img')).toBeNull()
    },
  )
})
