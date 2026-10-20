import { useEffect, useRef, useState } from 'react'
import type { Draft } from './draft'
import { base64ToBlob, fetchBlob } from './image'

/**
 * A small picture of a file of the draft (the reference, a sample), asked for only when the element that shows it comes
 * near the screen. It is a thumbnail of the job's file on the server, or the picture the draft has added and not saved
 * yet. `ref` goes on the element that will hold it; `url` is what to put in an `<img>` (null until it is there).
 */
export function useThumbnail<T extends Element>(draft: Draft, path: string | null, width = 160) {
  const ref = useRef<T>(null)
  const [near, setNear] = useState(typeof IntersectionObserver === 'undefined')
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    const el = ref.current
    if (near || !el) return
    const watcher = new IntersectionObserver(
      (entries) => entries.some((e) => e.isIntersecting) && setNear(true),
      { rootMargin: '200px' },
    )
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [near])
  const added = path ? draft.addFiles[path] : undefined
  const base = draft.base
  useEffect(() => {
    if (!near || !path) return
    let alive = true
    let made: string | null = null
    const get = async () =>
      added
        ? base64ToBlob(added)
        : await fetchBlob(
            `/api/jobs/${base!.id}/versions/${base!.version}/files/${path}?width=${width}`,
          )
    get().then(
      (blob) => {
        if (!alive) return
        made = URL.createObjectURL(blob)
        setUrl(made)
      },
      () => {},
    )
    return () => {
      alive = false
      if (made) URL.revokeObjectURL(made)
    }
  }, [near, path, added, base, width])
  return { ref, url }
}
