import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GrayThreshold } from './GrayThreshold'

const counts = Array.from({ length: 256 }, (_, i) => (i < 100 ? 5 : 1))

describe('the gray threshold line', () => {
  it('is a slider read by its level, moved by the arrows (shift: 10), Home and End', () => {
    const seen: number[] = []
    render(<GrayThreshold counts={counts} mode="dark" level={120} auto={false} label="Limiar de cinza" onChange={(n) => seen.push(n)} />)
    const line = screen.getByRole('slider', { name: 'Limiar de cinza' })
    expect(line).toHaveAttribute('aria-valuenow', '120')
    expect(line).toHaveAttribute('aria-valuemax', '255')
    fireEvent.keyDown(line, { key: 'ArrowRight' })
    fireEvent.keyDown(line, { key: 'ArrowLeft', shiftKey: true })
    fireEvent.keyDown(line, { key: 'Home' })
    fireEvent.keyDown(line, { key: 'End' })
    expect(seen).toEqual([121, 110, 0, 255])
  })

  it('never goes past the ends', () => {
    const seen: number[] = []
    render(<GrayThreshold counts={counts} mode="light" level={255} auto={false} label="L" onChange={(n) => seen.push(n)} />)
    fireEvent.keyDown(screen.getByRole('slider', { name: 'L' }), { key: 'ArrowRight' })
    expect(seen).toEqual([255])
  })

  it('moves with the pointer: the level under it', () => {
    const seen: number[] = []
    render(<GrayThreshold counts={counts} mode="dark" level={50} auto={false} label="L" onChange={(n) => seen.push(n)} />)
    const track = screen.getByTestId('gray-track')
    track.getBoundingClientRect = () => ({ left: 0, width: 255, top: 0, height: 64, right: 255, bottom: 64, x: 0, y: 0, toJSON: () => ({}) })
    track.setPointerCapture = () => {}
    fireEvent.pointerDown(track, { clientX: 200, pointerId: 1 })
    fireEvent.pointerMove(track, { clientX: 30, pointerId: 1 })
    expect(seen).toEqual([200, 30])
  })

  it('says the level is automatic, with its value', () => {
    render(<GrayThreshold counts={counts} mode="dark" level={118} auto label="L" autoLabel="automático: 118" onChange={() => {}} />)
    expect(screen.getByText('automático: 118')).toBeInTheDocument()
  })
})
