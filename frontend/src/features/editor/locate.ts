import { useEffect, useRef, useState } from 'react'
import { describeError } from '@/api/mutations'
import { editorApi, type LocateOut } from '@/api/queries/editor'
import { toRequest, type Draft } from './draft'
import { imageSignature } from './sequence'

/** The pause before the locating step is run again after the last change: dragging a handle is one run. */
export const LOCATE_DELAY_MS = 400

export interface Locating {
  /** where the fixtures of the draft are on its reference and samples, as the server found them */
  out: LocateOut | null
  /** what the draft looked like then differs from now: the numbers are old and are being measured again */
  stale: boolean
  loading: boolean
  error: string
}

/** What the locating step depends on: the pictures and the fixtures, not the tools or the limits. */
export function locateSignature(draft: Draft): string {
  const files = Object.entries(draft.addFiles)
    .filter(([path]) => path.startsWith('locator/'))
    .map(([path, data]) => [path, data.length, data.slice(0, 32), data.slice(-32)])
  return JSON.stringify([imageSignature(draft), draft.job.geometry?.fixtures ?? [], files])
}

/**
 * The draft's fixtures on its reference and samples (docs/frontend.md §7.3, step 3), kept as long as it describes the
 * draft and measured again after a change to the fixtures or the pictures. Only the newest answer is kept.
 */
export function useLocate(draft: Draft, active: boolean): Locating {
  const signature = locateSignature(draft)
  const [kept, setKept] = useState<{ out: LocateOut; signature: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const latest = useRef(signature)
  const draftRef = useRef(draft)
  useEffect(() => {
    latest.current = signature
    draftRef.current = draft
  })
  const measurable =
    (draft.job.geometry?.fixtures ?? []).length > 0 &&
    (draft.expected?.cases.length ?? 0) +
      Object.keys(draft.addFiles).length +
      draft.baseFiles.length >
      0

  useEffect(() => {
    if (!active || !measurable || kept?.signature === signature) return
    const timer = setTimeout(() => {
      setLoading(true)
      editorApi.locate(toRequest(draftRef.current)).then(
        (out) => {
          if (latest.current !== signature) return
          setError(out.ok ? '' : (out.message ?? ''))
          setKept(out.ok ? { out, signature } : null)
          setLoading(false)
        },
        (e: unknown) => {
          if (latest.current !== signature) return
          setError(describeError(e))
          setLoading(false)
        },
      )
    }, LOCATE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [active, measurable, signature, kept?.signature])

  return {
    out: measurable ? (kept?.out ?? null) : null,
    stale: kept !== null && kept.signature !== signature,
    loading,
    error,
  }
}
