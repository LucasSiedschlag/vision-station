import { useEffect, useState } from 'react'

/** True after `ms` without the mouse moving, so a kiosk screen does not show a stray cursor. Any movement or touch brings it back. */
export function useHideCursor(ms: number, enabled = true) {
  const [idle, setIdle] = useState(false)
  useEffect(() => {
    if (!enabled) return
    let timer = setTimeout(() => setIdle(true), ms)
    const wake = () => {
      setIdle(false)
      clearTimeout(timer)
      timer = setTimeout(() => setIdle(true), ms)
    }
    window.addEventListener('pointermove', wake, { passive: true })
    window.addEventListener('pointerdown', wake, { passive: true })
    return () => {
      clearTimeout(timer)
      window.removeEventListener('pointermove', wake)
      window.removeEventListener('pointerdown', wake)
    }
  }, [ms, enabled])
  return enabled && idle
}
