import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState, type ReactNode } from 'react'
import { I18nProvider, parseColor, type Color } from 'react-aria-components'
import { describe, expect, it } from 'vitest'
import { LocaleProvider } from '@/app/locale'
import { ColorArea, ColorField, ColorSlider } from './color'
import { Field } from './field'
import { NumberField } from './number-field'
import { Slider } from './slider'

// The React Aria controls (TD-29): numbers, ranges and colours, formatted in the interface language.

const pt = {
  wrapper: ({ children }: { children: ReactNode }) => <LocaleProvider>{children}</LocaleProvider>,
}

function Exposure({ start = 8000 }: { start?: number | null }) {
  const [value, setValue] = useState<number | null>(start)
  return (
    <>
      <NumberField
        aria-label="Exposição"
        value={value}
        onChange={setValue}
        unit="µs"
        min={100}
        max={33000}
        step={100}
      />
      <output data-testid="value">{value === null ? 'vazio' : value}</output>
    </>
  )
}

describe('NumberField', () => {
  it('reads numbers with a comma and shows the unit', async () => {
    render(<Exposure start={null} />, pt)
    const input = screen.getByLabelText('Exposição')
    await userEvent.type(input, '1500,5')
    await userEvent.tab()
    expect(screen.getByTestId('value')).toHaveTextContent('1500.5')
    expect(input).toHaveValue('1500,5')
    expect(screen.getByText('µs')).toBeInTheDocument()
  })

  it('flags a value out of range without changing it', async () => {
    render(<Exposure />, pt)
    const input = screen.getByLabelText('Exposição')
    await userEvent.clear(input)
    await userEvent.type(input, '50')
    await userEvent.tab()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveValue('50')
    expect(screen.getByTestId('value')).toHaveTextContent('50') // kept as typed
  })

  it('does not take letters', async () => {
    render(<Exposure start={null} />, pt)
    const input = screen.getByLabelText('Exposição')
    await userEvent.type(input, 'abc')
    expect(input).toHaveValue('')
    expect(screen.getByTestId('value')).toHaveTextContent('vazio')
  })

  it('a dot or a comma typed is the decimal mark of the language, never dropped (0.8 is not 8)', async () => {
    function Host({ locale }: { locale: string }) {
      const [value, setValue] = useState<number | null>(null)
      return (
        <I18nProvider locale={locale}>
          <NumberField aria-label={locale} value={value} onChange={setValue} decimals={2} />
          <output data-testid={`${locale}-value`}>{value}</output>
        </I18nProvider>
      )
    }
    render(
      <>
        <Host locale="pt-BR" />
        <Host locale="en-US" />
      </>,
    )
    await userEvent.type(screen.getByLabelText('pt-BR'), '0.8')
    await userEvent.type(screen.getByLabelText('en-US'), '0,8')
    await userEvent.tab()
    expect(screen.getByLabelText('pt-BR')).toHaveValue('0,8')
    expect(screen.getByTestId('pt-BR-value')).toHaveTextContent('0.8')
    expect(screen.getByLabelText('en-US')).toHaveValue('0.8')
    expect(screen.getByTestId('en-US-value')).toHaveTextContent('0.8')
  })

  it('a value off the step is kept: the step is only for the arrows', async () => {
    render(<Exposure />, pt)
    const input = screen.getByLabelText('Exposição')
    await userEvent.clear(input)
    await userEvent.type(input, '8150')
    await userEvent.tab()
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(screen.getByTestId('value')).toHaveTextContent('8150')
  })

  it('steps with the arrows inside the range', async () => {
    render(<Exposure start={32950} />, pt)
    const input = screen.getByLabelText('Exposição')
    input.focus()
    await userEvent.keyboard('{ArrowUp}')
    expect(screen.getByTestId('value')).toHaveTextContent('33000')
    await userEvent.keyboard('{ArrowUp}')
    expect(screen.getByTestId('value')).toHaveTextContent('33000') // stays at the maximum
    await userEvent.keyboard('{ArrowDown}')
    expect(screen.getByTestId('value')).toHaveTextContent('32900')
  })

  it('emptied, it gives null', async () => {
    render(<Exposure />, pt)
    await userEvent.clear(screen.getByLabelText('Exposição'))
    await userEvent.tab()
    expect(screen.getByTestId('value')).toHaveTextContent('vazio')
  })

  it('writes the number in the interface language', () => {
    const field = (locale: string) =>
      render(
        <I18nProvider locale={locale}>
          <NumberField aria-label={locale} value={0.8} onChange={() => {}} decimals={2} />
        </I18nProvider>,
      )
    field('pt-BR')
    field('en-US')
    expect(screen.getByLabelText('pt-BR')).toHaveValue('0,8')
    expect(screen.getByLabelText('en-US')).toHaveValue('0.8')
  })

  it('inside a Field it takes the label, the hint and the error, and still flags a value out of range', async () => {
    function Host({ error }: { error?: string }) {
      const [value, setValue] = useState<number | null>(8000)
      return (
        <Field label="Exposição" hint="Em microssegundos" error={error}>
          {(p) => <NumberField {...p} value={value} onChange={setValue} min={100} max={33000} />}
        </Field>
      )
    }
    const { rerender } = render(<Host />, pt)
    const input = screen.getByLabelText('Exposição')
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(document.getElementById(input.getAttribute('aria-describedby')!)).toHaveTextContent(
      'Em microssegundos',
    )
    await userEvent.clear(input)
    await userEvent.type(input, '999999')
    await userEvent.tab()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    rerender(<Host error="Fora da faixa" />)
    expect(screen.getByLabelText('Exposição')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('Slider', () => {
  it('one thumb: moves by the step and says the value in the interface language', async () => {
    function Host() {
      const [value, setValue] = useState([0.8])
      return (
        <Slider
          label="Cobertura mínima"
          value={value}
          onChange={setValue}
          min={0}
          max={1}
          step={0.05}
          decimals={2}
        />
      )
    }
    render(<Host />, pt)
    const thumb = screen.getByRole('slider', { name: 'Cobertura mínima' })
    expect(thumb).toHaveAttribute('aria-valuetext', '0,8')
    thumb.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(thumb).toHaveAttribute('aria-valuetext', '0,85')
  })

  it('two thumbs: each has its own name and they never cross', async () => {
    function Host() {
      const [value, setValue] = useState([100, 120])
      return (
        <>
          <Slider
            label="Matiz"
            thumbLabels={['Início', 'Fim']}
            value={value}
            onChange={setValue}
            min={0}
            max={179}
            step={10}
            unit="°"
          />
          <output>{value.join('–')}</output>
        </>
      )
    }
    render(<Host />, pt)
    const start = screen.getByRole('slider', { name: /Início/ })
    screen.getByRole('slider', { name: /Fim/ })
    start.focus()
    await userEvent.keyboard('{ArrowRight}{ArrowRight}{ArrowRight}')
    expect(screen.getByText('120–120')).toBeInTheDocument()
  })

  it('with fields: a number box beside each thumb for the exact value', async () => {
    function Host() {
      const [value, setValue] = useState([100, 120])
      return (
        <>
          <Slider
            label="Matiz"
            thumbLabels={['Início', 'Fim']}
            value={value}
            onChange={setValue}
            min={0}
            max={179}
            fields
          />
          <output>{value.join('–')}</output>
        </>
      )
    }
    render(<Host />, pt)
    const end = screen.getByLabelText('Fim (valor exato)')
    await userEvent.clear(end)
    await userEvent.type(end, '130')
    await userEvent.tab()
    expect(screen.getByText('100–130')).toBeInTheDocument()
    expect(screen.getByRole('slider', { name: /Fim/ })).toHaveValue('130')
  })

  it('a box out of range is flagged and leaves the slider where it was', async () => {
    function Host() {
      const [value, setValue] = useState([0.5])
      return (
        <Slider
          label="Limite"
          value={value}
          onChange={setValue}
          min={0}
          max={1}
          step={0.01}
          decimals={2}
          fields
        />
      )
    }
    render(<Host />, pt)
    const box = screen.getByLabelText('Limite (valor exato)')
    await userEvent.clear(box)
    await userEvent.type(box, '3')
    await userEvent.tab()
    expect(box).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('slider', { name: 'Limite' })).toHaveValue('0.5')
  })

  it('disabled, it does not move', () => {
    render(
      <Slider label="Limite" value={[0.5]} onChange={() => {}} min={0} max={1} isDisabled />,
      pt,
    )
    expect(screen.getByRole('slider', { name: 'Limite' })).toBeDisabled()
  })
})

describe('colour controls (HSB)', () => {
  function Host({ children }: { children: (color: Color, set: (c: Color) => void) => ReactNode }) {
    const [color, setColor] = useState(parseColor('hsb(210, 80%, 70%)'))
    return (
      <>
        {children(color, setColor)}
        <output>{color.toString('hsb')}</output>
      </>
    )
  }

  it('ColorSlider: a hue slider with its label and value', async () => {
    render(
      <Host>
        {(c, set) => <ColorSlider label="Matiz" channel="hue" value={c} onChange={set} />}
      </Host>,
      pt,
    )
    const thumb = screen.getByRole('slider', { name: 'Matiz' })
    thumb.focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByText('hsb(211, 80%, 70%)')).toBeInTheDocument()
    expect(screen.getByText('211 °')).toBeInTheDocument() // the value beside the label
  })

  it('ColorArea: saturation across, brightness up, both by keyboard', async () => {
    render(
      <Host>
        {(c, set) => <ColorArea aria-label="Cor de referência" value={c} onChange={set} />}
      </Host>,
      pt,
    )
    // one stop for the keyboard; the second channel's input is hidden from it
    const area = screen.getByRole('slider', { name: /Cor de referência/ })
    area.focus()
    await userEvent.keyboard('{ArrowRight}')
    await userEvent.keyboard('{ArrowUp}')
    expect(screen.getByText('hsb(210, 81%, 71%)')).toBeInTheDocument()
  })

  it('ColorField: types a hex colour', async () => {
    render(
      <Host>{(c, set) => <ColorField label="Cor" value={c} onChange={(v) => v && set(v)} />}</Host>,
      pt,
    )
    const input = screen.getByLabelText('Cor')
    await userEvent.clear(input)
    await userEvent.type(input, '#FF0000')
    await userEvent.tab()
    expect(screen.getByText('hsb(0, 100%, 100%)')).toBeInTheDocument()
  })
})
