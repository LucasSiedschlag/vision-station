import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { FocusMeter } from './FocusMeter'
import { Histogram } from './Histogram'

const counts = (hot: number, dark = 0) => {
  const c = new Array<number>(256).fill(0)
  c[128] = 1000
  c[255] = hot
  c[0] = dark
  return c
}

describe('the histogram', () => {
  it('says how much of the image is black and how much is saturated, and turns amber above 1 %', () => {
    const { rerender } = render(<Histogram counts={counts(0)} clippedLow={0.2} clippedHigh={0.4} />)
    expect(screen.getByRole('img', { name: /Histograma/ })).toBeInTheDocument()
    expect(screen.getByText('0,4 % da imagem saturada')).toHaveClass('text-fg-muted')
    rerender(<Histogram counts={counts(50)} clippedLow={0.2} clippedHigh={2.4} />)
    expect(screen.getByText('2,4 % da imagem saturada')).toHaveClass('text-warn-text')
    expect(screen.getByText('0,2 % da imagem preta')).toHaveClass('text-fg-muted')
  })
})

describe('the focus meter', () => {
  it('holds the best value seen, turns green within 5 % of it, and starts over on request', () => {
    const { rerender } = render(<FocusMeter value={120} />)
    expect(screen.getByText(/120 · melhor: 120/)).toBeInTheDocument()
    rerender(<FocusMeter value={412} />)
    rerender(<FocusMeter value={300} />)
    expect(screen.getByText(/300 · melhor: 412/)).toBeInTheDocument()
    expect(screen.getByRole('meter')).not.toHaveAttribute('aria-valuetext')
    expect(screen.getByText('Gire o foco até a barra ficar verde')).toBeInTheDocument()
    rerender(<FocusMeter value={395} />) // 96 % of the best
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuetext', 'No ponto mais nítido')
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '395')
  })

  it('says there is no picture instead of showing zero', () => {
    render(<FocusMeter value={null} />)
    expect(screen.getByText(/sem imagem/)).toBeInTheDocument()
  })
})
