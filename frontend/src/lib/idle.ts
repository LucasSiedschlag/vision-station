import { useEffect, useRef } from 'react'

const EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart'] as const

/** Calls `onIdle` once after `ms` without any pointer, keyboard or touch activity. Does nothing when `enabled` is false. */
export function useIdle(ms: number, onIdle: () => void, enabled = true) {
  const callback = useRef(onIdle)
  useEffect(() => {
    callback.current = onIdle
  }, [onIdle])

  useEffect(() => {
    if (!enabled) return
    let timer = setTimeout(() => callback.current(), ms)
    const reset = () => {
      clearTimeout(timer)
      timer = setTimeout(() => callback.current(), ms)
    }
    for (const event of EVENTS) window.addEventListener(event, reset, { passive: true })
    return () => {
      clearTimeout(timer)
      for (const event of EVENTS) window.removeEventListener(event, reset)
    }
  }, [ms, enabled])
}
