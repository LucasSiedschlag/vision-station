import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ToolToleranceGauge, type GaugeProposal } from './ToolToleranceGauge'
import { domainOf, marginText, tally, wrongSide, type Dot } from './gauge-model'

const dots: Dot[] = [
  { id: 'reference', kind: 'reference', name: 'Referência', value: 0.95 },
  { id: 'g1', kind: 'good', name: 'boa1.png', value: 0.95 },
  { id: 'g2', kind: 'good', name: 'boa2.png', value: 0.92 },
  { id: 'g3', kind: 'good', name: 'boa3.png', value: 0.97 },
  { id: 'b1', kind: 'bad', name: 'ruim1.png', value: 0.52 },
  { id: 'b2', kind: 'bad', name: 'ruim2.png', value: 0.3 },
]

function Gauge(over: Partial<React.ComponentProps<typeof ToolToleranceGauge>> = {}) {
  const props = {
    label: 'Fração com a cor',
    unit: 'fraction' as const,
    range: [0, 1],
    limits: { min: 0.8, max: null },
    limitInfo: { min: { optional: false, bounds: [0, 1] as const } },
    current: 0.92,
    currentPassed: true,
    dots,
    selected: null,
    proposals: [] as GaugeProposal[],
    canPropose: { ok: true, reason: '' },
    onSelect: vi.fn(),
    onLimit: vi.fn(),
    onPropose: vi.fn(),
    onApply: vi.fn(),
    onDiscard: vi.fn(),
    ...over,
  }
  return { props, ...render(<ToolToleranceGauge {...props} />) }
}

describe('what the gauge computes', () => {
  it('a count has no natural top: the scale follows the data', () => {
    expect(domainOf('fraction', [0, 1], [0.2])).toEqual([0, 1])
    expect(domainOf('count', [0, null], [1, 12])).toEqual([0, 15])
    expect(domainOf('count', [0, null], [])).toEqual([0, 5])
  })

  it('a good sample outside the band, or a bad one inside it, is on the wrong side', () => {
    const limits = { min: 0.8, max: null }
    expect(wrongSide({ id: 'a', kind: 'good', name: 'a', value: 0.7 }, limits)).toBe(true)
    expect(wrongSide({ id: 'a', kind: 'good', name: 'a', value: 0.9 }, limits)).toBe(false)
    expect(wrongSide({ id: 'b', kind: 'bad', name: 'b', value: 0.9 }, limits)).toBe(true)
    expect(wrongSide({ id: 'r', kind: 'reference', name: 'r', value: 0.1 }, limits)).toBe(false)
    expect(wrongSide({ id: 'n', kind: 'good', name: 'n', value: null }, limits)).toBe(false)
  })

  it('counts the samples on each side and says the margin in the unit of the measure', () => {
    const limits = { min: 0.8, max: null }
    expect(tally(dots, limits)).toEqual({ goodN: 3, goodIn: 3, badN: 2, badOut: 2 })
    expect(marginText(dots, limits, 'fraction')).toBe(
      'Margem: a pior boa (92%) está 12 pontos percentuais acima do limite; a ruim mais alta, 28 pontos percentuais abaixo.',
    )
    expect(
      marginText([{ id: 'g', kind: 'good', name: 'g', value: 3 }], { min: null, max: 5 }, 'count'),
    ).toBe('Margem: a pior boa (3) está 2 abaixo do limite.')
    // the worst good sample fails: it is said, and not as a bare number
    expect(
      marginText([{ id: 'g', kind: 'good', name: 'g', value: 0.7 }], limits, 'fraction'),
    ).toContain('10 pontos percentuais abaixo do limite, e reprova')
  })
})

describe('the gauge', () => {
  it('shows the current value with its verdict, the dots on two rows and the margin in words', () => {
    Gauge()
    const section = screen.getByRole('region', { name: 'Fração com a cor' })
    expect(within(section).getByText('92%')).toBeInTheDocument()
    expect(within(section).getByRole('group', { name: 'Boas' })).toBeInTheDocument()
    expect(within(section).getByRole('group', { name: 'Ruins' })).toBeInTheDocument()
    expect(within(section).getAllByRole('button', { name: /boa\d\.png/ })).toHaveLength(3)
    expect(within(section).getAllByRole('button', { name: /ruim\d\.png/ })).toHaveLength(2)
    expect(within(section).getByText(/^Margem: a pior boa \(92%\)/)).toBeInTheDocument()
    expect(within(section).getByText('3 de 3 boas dentro · 2 de 2 ruins fora')).toBeInTheDocument()
  })

  it('without a measurement there is no value and no verdict: "não medido"', () => {
    Gauge({ current: null, currentPassed: undefined })
    expect(screen.getByText('não medido')).toBeInTheDocument()
  })

  it('a sample is chosen by its dot, and a dot on the wrong side says so by its ring', async () => {
    const { props } = Gauge({ limits: { min: 0.94, max: null } })
    const wrong = screen.getByRole('button', { name: /boa2\.png/ })
    expect(wrong.className).toContain('ring-fail')
    expect(screen.getByRole('button', { name: /boa1\.png/ }).className).not.toContain('ring-fail')
    await userEvent.click(wrong)
    expect(props.onSelect).toHaveBeenCalledWith('g2')
  })

  it('the limit is moved with the keyboard, or by typing the exact value', async () => {
    const { props } = Gauge()
    screen.getByRole('slider', { name: /Limite mínimo/ }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(props.onLimit).toHaveBeenLastCalledWith('min', 0.81)
    const box = screen.getByRole('textbox', { name: 'Limite mínimo' })
    expect(box).toHaveValue('80%')
    await userEvent.clear(box)
    await userEvent.type(box, '85')
    await userEvent.tab()
    expect(props.onLimit).toHaveBeenLastCalledWith('min', 0.85)
  })

  it('a screen reader hears the limit, the current value and how many good samples are inside', () => {
    Gauge()
    expect(screen.getByRole('slider', { name: /Limite mínimo/ })).toHaveAccessibleDescription(
      'Limite mínimo 80%; valor atual 92%; 3 de 3 boas dentro',
    )
  })

  it('an optional limit is switched on and off, and keeps no thumb while it is off', async () => {
    const { props } = Gauge({
      limits: { min: 0.8, max: null },
      limitInfo: {
        min: { optional: true, bounds: [0, 1] },
        max: { optional: true, bounds: [0, 1] },
      },
    })
    expect(screen.getAllByRole('slider')).toHaveLength(1)
    await userEvent.click(screen.getByRole('switch', { name: 'Usar o limite máximo' }))
    expect(props.onLimit).toHaveBeenLastCalledWith('max', 1)
    await userEvent.click(screen.getByRole('switch', { name: 'Usar o limite mínimo' }))
    expect(props.onLimit).toHaveBeenLastCalledWith('min', null)
  })

  it('with only the reference, it says the limit cannot be checked, and the proposal is off with its reason', async () => {
    const reason = 'Capture ao menos 3 amostras Boas'
    const { props } = Gauge({
      dots: [dots[0]!],
      canPropose: { ok: false, reason },
    })
    expect(screen.getByText(/Só a referência foi medida/)).toBeInTheDocument()
    const button = screen.getByRole('button', { name: 'Ajustar pelas amostras' })
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).toHaveAttribute('title', reason)
    await userEvent.click(button)
    expect(props.onPropose).not.toHaveBeenCalled()
  })

  it('a proposal is shown as a ghost with its margins in words, and applied only on Aplicar', async () => {
    const proposal: GaugeProposal = {
      side: 'min',
      proposed: 0.66,
      reason: '',
      margin_good: 0.26,
      margin_bad: 0.14,
    }
    const { props } = Gauge({ proposals: [proposal] })
    expect(
      screen.getByText(
        'Proposta: limite mínimo 66%, no meio entre as ruins e as boas (26 pontos percentuais abaixo da pior boa, 14 pontos percentuais acima da ruim mais alta).',
      ),
    ).toBeInTheDocument()
    expect(props.onApply).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Aplicar' }))
    expect(props.onApply).toHaveBeenCalledWith(proposal)
    await userEvent.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(props.onDiscard).toHaveBeenCalled()
  })

  it('samples that overlap get no proposal and the gauge says why', async () => {
    const { props } = Gauge({
      proposals: [
        { side: 'min', proposed: null, reason: 'overlap', margin_good: null, margin_bad: null },
      ],
    })
    expect(
      screen.getByText('As amostras se sobrepõem; a medição não separa boas de ruins.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Aplicar' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(props.onDiscard).toHaveBeenCalled()
  })
})
