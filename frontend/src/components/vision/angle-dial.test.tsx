import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AngleRangeDial } from './AngleRangeDial'

const labels: [string, string] = ['Giro mínimo', 'Giro máximo']
const dial = (
  value: [number, number],
  onChange: (v: [number, number]) => void,
  found?: number | null,
) => render(<AngleRangeDial value={value} found={found} onChange={onChange} labels={labels} />)

describe('the dial of the allowed turn', () => {
  it('has a slider for each end, with the angle as its value and in words', () => {
    dial([-15, 15], () => {})
    const least = screen.getByRole('slider', { name: 'Giro mínimo' })
    expect(least).toHaveAttribute('aria-valuenow', '-15')
    expect(least).toHaveAttribute('aria-valuetext', '-15°')
    expect(screen.getByRole('slider', { name: 'Giro máximo' })).toHaveAttribute(
      'aria-valuenow',
      '15',
    )
  })

  it('moves an end with the arrows (a positive turn is to the left), by 5° with Shift, and never past the other end', () => {
    const seen: [number, number][] = []
    dial([-15, 15], (v) => seen.push(v))
    const most = screen.getByRole('slider', { name: 'Giro máximo' })
    fireEvent.keyDown(most, { key: 'ArrowLeft' })
    expect(seen.at(-1)).toEqual([-15, 16])
    fireEvent.keyDown(most, { key: 'ArrowRight', shiftKey: true })
    expect(seen.at(-1)).toEqual([-15, 10])
    const least = screen.getByRole('slider', { name: 'Giro mínimo' })
    fireEvent.keyDown(least, { key: 'ArrowLeft', shiftKey: true })
    expect(seen.at(-1)).toEqual([-10, 15])
    seen.length = 0
    const tight = render(
      <AngleRangeDial value={[5, 5]} onChange={(v) => seen.push(v)} labels={['a', 'b']} />,
    )
    fireEvent.keyDown(tight.getAllByRole('slider', { name: 'b' })[0]!, {
      key: 'ArrowRight',
      shiftKey: true,
    })
    expect(seen.at(-1)).toEqual([5, 5]) // the most turn is never below the least
  })

  it('stays between -90° and 90°', () => {
    const seen: [number, number][] = []
    dial([-90, 90], (v) => seen.push(v))
    fireEvent.keyDown(screen.getByRole('slider', { name: 'Giro máximo' }), { key: 'ArrowLeft' })
    expect(seen.at(-1)).toEqual([-90, 90])
  })

  it('shows the turn found now as a needle, green inside the range and red outside it', () => {
    const { container, rerender } = dial([-15, 15], () => {}, 8)
    expect(container.querySelector('line.stroke-ok-text')).not.toBeNull()
    rerender(<AngleRangeDial value={[-15, 15]} found={28} onChange={() => {}} labels={labels} />)
    expect(container.querySelector('line.stroke-fail-text')).not.toBeNull()
    rerender(<AngleRangeDial value={[-15, 15]} found={null} onChange={() => {}} labels={labels} />)
    expect(container.querySelector('line.stroke-ok-text, line.stroke-fail-text')).toBeNull()
  })
})
