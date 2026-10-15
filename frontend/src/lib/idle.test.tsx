import { act, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useIdle } from './idle'

function Probe({
  ms,
  onIdle,
  enabled = true,
}: {
  ms: number
  onIdle: () => void
  enabled?: boolean
}) {
  useIdle(ms, onIdle, enabled)
  return null
}

describe('useIdle', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fires once after the time without activity', () => {
    const onIdle = vi.fn()
    render(<Probe ms={1000} onIdle={onIdle} />)
    act(() => void vi.advanceTimersByTime(999))
    expect(onIdle).not.toHaveBeenCalled()
    act(() => void vi.advanceTimersByTime(2))
    expect(onIdle).toHaveBeenCalledOnce()
  })

  it('any activity starts the wait again', () => {
    const onIdle = vi.fn()
    render(<Probe ms={1000} onIdle={onIdle} />)
    for (const event of ['pointermove', 'keydown', 'touchstart']) {
      act(() => void vi.advanceTimersByTime(900))
      act(() => void window.dispatchEvent(new Event(event)))
    }
    expect(onIdle).not.toHaveBeenCalled()
    act(() => void vi.advanceTimersByTime(1001))
    expect(onIdle).toHaveBeenCalledOnce()
  })

  it('does nothing when disabled, and stops when it goes away', () => {
    const onIdle = vi.fn()
    const { rerender, unmount } = render(<Probe ms={1000} onIdle={onIdle} enabled={false} />)
    act(() => void vi.advanceTimersByTime(5000))
    expect(onIdle).not.toHaveBeenCalled()
    rerender(<Probe ms={1000} onIdle={onIdle} />)
    unmount()
    act(() => void vi.advanceTimersByTime(5000))
    expect(onIdle).not.toHaveBeenCalled()
  })
})
