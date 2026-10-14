import { useLayoutEffect, useRef } from 'react'

/**
 * Radix returns the focus to the button that opened a dialog only when it was opened through its own trigger.
 * A dialog opened from state (open={flag}) loses the focus when it closes. This remembers the element that had the
 * focus when the dialog opened and gives it back: pass the result to `onCloseAutoFocus` of the dialog content.
 * A layout effect runs before the dialog moves the focus into itself.
 */
export function useReturnFocus(open: boolean) {
  const opener = useRef<HTMLElement | null>(null)
  useLayoutEffect(() => {
    if (open)
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
  }, [open])
  return (event: Event) => {
    event.preventDefault()
    opener.current?.focus()
  }
}
