import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Stepper } from '@/components/ui/stepper'
import { mockApi } from '@/test/render'
import type { Draft } from './draft'
import { Filmstrip } from './Filmstrip'
import { ResultBar } from './ResultBar'
import { AnchorNotFound, CameraLost } from './StateBanners'

mockApi()

const draft = (over: Partial<Draft> = {}): Draft => ({
  key: 'j',
  base: { id: 'j1', version: 2 },
  job: { tools: [] },
  profile: {},
  baseFiles: [{ path: 'reference/reference.png', size: 1, sha256: 'x' }],
  addFiles: {},
  removeFiles: [],
  expected: {
    cases: [
      { image: 'tests/images/boa-1.png', outcome: 'PASS' },
      { image: 'tests/images/ruim-1.png', outcome: 'FAIL' },
    ],
  } as Draft['expected'],
  baseExpected: 'null',
  notes: '',
  ...over,
})
const strip = (over: Partial<Parameters<typeof Filmstrip>[0]> = {}) => {
  const calls = { show: vi.fn(), live: vi.fn(), capture: vi.fn(), toggle: vi.fn() }
  render(
    <Filmstrip
      draft={draft()}
      batch={
        {
          ok: true,
          samples: [
            {
              image: 'tests/images/boa-1.png',
              kind: 'good',
              expected: 'PASS',
              ok: true,
              message: '',
              result: null,
            },
            {
              image: 'tests/images/ruim-1.png',
              kind: 'bad',
              expected: 'FAIL',
              ok: false,
              message: '',
              result: null,
            },
          ],
          tools: [],
        } as never
      }
      shown={null}
      live
      onShow={calls.show}
      onLive={calls.live}
      onCapture={calls.capture}
      capturing={null}
      canCapture
      open
      onToggle={calls.toggle}
      {...over}
    />,
  )
  return calls
}

describe('the strip of samples (docs/frontend.md §10.1)', () => {
  it('has the reference, each sample with whether the job agrees with its label, and the live image', async () => {
    server()
    const calls = strip()
    const bar = screen.getByRole('toolbar', { name: 'Amostras' })
    expect(within(bar).getByRole('button', { name: 'Referência' })).toBeInTheDocument()
    expect(
      within(bar).getByRole('button', { name: 'boa-1: Boa, o job concorda' }),
    ).toBeInTheDocument()
    expect(
      within(bar).getByRole('button', { name: 'ruim-1: Ruim, o job discorda' }),
    ).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: 'Ao vivo' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await userEvent.click(within(bar).getByRole('button', { name: 'ruim-1: Ruim, o job discorda' }))
    expect(calls.show).toHaveBeenCalledWith('tests/images/ruim-1.png')
    await userEvent.click(within(bar).getByRole('button', { name: 'Referência' }))
    expect(calls.show).toHaveBeenCalledWith('reference/reference.png')
    await userEvent.click(within(bar).getByRole('button', { name: 'Ao vivo' }))
    expect(calls.live).toHaveBeenCalled()
  })

  it('moves between the pictures with the arrows, and says what a sample not measured yet is', async () => {
    server()
    strip({ batch: null })
    const first = screen.getByRole('button', { name: 'Referência' })
    first.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('button', { name: 'boa-1: Boa, ainda não medida' })).toHaveFocus()
    await userEvent.keyboard('{End}')
    expect(screen.getByRole('button', { name: 'Ao vivo' })).toHaveFocus()
    await userEvent.keyboard('{Home}')
    expect(first).toHaveFocus()
  })

  it('takes a sample from the camera as a Boa or a Ruim, and cannot when the camera is lost', async () => {
    server()
    const calls = strip()
    await userEvent.click(screen.getByRole('button', { name: 'Capturar como Boa' }))
    expect(calls.capture).toHaveBeenCalledWith('good')
    await userEvent.click(screen.getByRole('button', { name: 'Capturar como Ruim' }))
    expect(calls.capture).toHaveBeenCalledWith('bad')
  })

  it('says what is needed when there are no samples, and collapses', async () => {
    server()
    const calls = strip({ draft: draft({ expected: null }) })
    expect(
      screen.getByText(/Nenhuma amostra ainda\. Para propor limites: 3 Boas e 1 Ruim/),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar as amostras' }))
    expect(calls.toggle).toHaveBeenCalled()
  })
})

function server() {
  // the thumbnails are asked for when they come near the screen: here there is no IntersectionObserver, so at once
  vi.stubGlobal(
    'URL',
    Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() }),
  )
}

describe('the result bar', () => {
  const test = {
    result: {
      outcome: 'FAIL',
      reason: 'Largura fora do limite',
      scores: {},
      duration_ms: 182,
      tools: [
        { id: 'largura', passed: false },
        { id: 'tampa', passed: true },
      ],
    },
  } as never

  it('has the verdict, a chip for each tool (✓, ✕, or – when it did not run) with no value, the time and the rate', () => {
    render(
      <ResultBar
        test={test}
        tools={[{ id: 'largura' }, { id: 'tampa' }, { id: 'lote' }]}
        rate={3.8}
        note="Medido agora."
      />,
    )
    const bar = screen.getByRole('group', { name: 'Resultado do rascunho' })
    expect(bar).toHaveTextContent('Reprovado')
    expect(bar).toHaveTextContent('Largura fora do limite')
    expect(within(bar).getByLabelText('largura: reprovou')).toBeInTheDocument()
    expect(within(bar).getByLabelText('tampa: passou')).toBeInTheDocument()
    expect(within(bar).getByLabelText('lote: não rodou')).toBeInTheDocument()
    expect(bar).toHaveTextContent('182 ms')
    expect(bar).toHaveTextContent('Captura 3,8/s')
  })

  it('says there is no result yet, and shows no rate when it is not live', () => {
    render(<ResultBar test={null} tools={[]} rate={null} note="" />)
    expect(screen.getByText(/Sem resultado ainda/)).toBeInTheDocument()
    expect(screen.queryByText(/Captura/)).not.toBeInTheDocument()
  })
})

describe('the states of the image', () => {
  it('names the anchor that was not found, says the tools did not run, and offers the Anchor step', async () => {
    const open = vi.fn()
    render(<AnchorNotFound code="E201" reason="A âncora não foi achada na imagem" onOpen={open} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Âncora não encontrada (E201)')
    expect(screen.getByRole('alert')).toHaveTextContent('As ferramentas não rodaram')
    await userEvent.click(screen.getByRole('button', { name: 'Abrir o passo Âncora' }))
    expect(open).toHaveBeenCalled()
  })

  it('says the camera was lost and how long ago the last image came, with the reference as the way out', async () => {
    const back = vi.fn()
    render(<CameraLost since={Date.now() - 42_000} canUseReference onReference={back} />)
    expect(screen.getByText('Câmera desconectada')).toBeInTheDocument()
    expect(screen.getByText(/Última imagem há 4\d s/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ajustar na referência' }))
    expect(back).toHaveBeenCalled()
  })
})

describe('the step rail', () => {
  const steps = [
    { id: 'a', label: 'Imagem e disparo', status: 'done' as const },
    {
      id: 'b',
      label: 'Amostras',
      status: 'todo' as const,
      current: true,
      reason: 'Capture a referência',
    },
  ]
  it('collapses to numbered icons with the names in a tooltip and for screen readers', () => {
    render(<Stepper steps={steps} compact />)
    const second = screen.getByRole('button', { name: /Amostras/ })
    expect(second).toHaveAttribute('title', 'Amostras: Capture a referência')
    expect(screen.getByText('Amostras').parentElement).toHaveClass('sr-only') // read, not shown
    expect(second).toHaveTextContent('2')
  })
})
