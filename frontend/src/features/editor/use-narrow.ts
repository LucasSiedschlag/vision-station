import { useEffect, useState } from 'react'

/** True while the window is narrower than `px`: the workbench starts with the step rail collapsed (docs/frontend.md §10.1). */
export function useNarrow(px: number): boolean {
  const query = `(max-width: ${px - 1}px)`
  const [narrow, setNarrow] = useState(() =>
    typeof matchMedia === 'function' ? matchMedia(query).matches : false,
  )
  useEffect(() => {
    if (typeof matchMedia !== 'function') return
    const list = matchMedia(query)
    const change = () => setNarrow(list.matches)
    list.addEventListener('change', change)
    return () => list.removeEventListener('change', change)
  }, [query])
  return narrow
}
