import { useEffect, useRef, useState } from 'react'
import { describeError } from '@/api/mutations'
import { editorApi, type BatchOut } from '@/api/queries/editor'
import { toRequest, type Draft, type JobJson } from './draft'
import { fullSignature } from './sequence'

/** The pause before the samples are measured again after the last change: a drag of a limit is one measurement. */
export const BATCH_DELAY_MS = 500

export interface Batch {
  /** the draft on its reference and samples, as the server measured it */
  out: BatchOut | null
  /** what the draft looked like then; different from now: the numbers are old and are being measured again */
  stale: boolean
  loading: boolean
  error: string
}

/**
 * What the dots of the gauges depend on: the draft without the limits of the criteria. The values the tools measure on
 * the samples do not change when a limit moves, so dragging one never asks for the samples to be measured again (the
 * numbers that decide pass or fail are read against the limit on the screen). A parameter that is not a limit, `hue` or
 * `min_score` for instance, changes what is measured, and does.
 */
export function batchSignature(draft: Draft, limits: Record<string, readonly string[]>): string {
  const tools = ((draft.job.tools ?? []) as JobJson[]).map((tool) => {
    const skip = limits[tool.type] ?? []
    const params = Object.fromEntries(
      Object.entries(tool.params ?? {}).filter(([k]) => !skip.includes(k)),
    )
    return { ...tool, params }
  })
  return fullSignature({ ...draft, job: { ...draft.job, tools } })
}

/**
 * The draft on all its samples (docs/frontend.md §9.4), kept as long as it describes the draft. It is measured when the
 * screen needs it and again after every change that affects a result, so the dots of the gauges follow the limits.
 * Only the newest answer is kept: a slow one that comes after a newer request is dropped.
 */
export function useBatch(
  draft: Draft,
  active: boolean,
  limits: Record<string, readonly string[]> = {},
): Batch {
  const signature = batchSignature(draft, limits)
  const [kept, setKept] = useState<{ out: BatchOut; signature: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const latest = useRef(signature)
  const draftRef = useRef(draft)
  // what the answer of a request and the next request read: set after the render, before the effects below
  useEffect(() => {
    latest.current = signature
    draftRef.current = draft
  })

  const measurable =
    (draft.job.tools ?? []).length > 0 &&
    (draft.expected?.cases.length ?? 0) +
      Object.keys(draft.addFiles).length +
      draft.baseFiles.length >
      0

  useEffect(() => {
    if (!active || !measurable || kept?.signature === signature) return
    const timer = setTimeout(() => {
      setLoading(true)
      editorApi.batch(toRequest(draftRef.current)).then(
        (out) => {
          if (latest.current !== signature) return // a newer draft is on its way
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
    }, BATCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [active, measurable, signature, kept?.signature])

  return {
    out: kept?.out ?? null,
    stale: kept !== null && kept.signature !== signature,
    loading,
    error,
  }
}
