import { TriangleAlert, VideoOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { text } from '@/texts'

const s = text.editor.states

/** "há 42 s" / "há 3 min": how long ago, updated every second. */
function useAge(since: number | null): string {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (since === null) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [since])
  const seconds = Math.max(0, Math.round((now - (since ?? now)) / 1000))
  return seconds < 90 ? s.seconds(seconds) : s.minutes(Math.round(seconds / 60))
}

/**
 * The two states of the image that the editor cannot show as usual (docs/frontend.md §19.1): the anchor was not found,
 * and the camera was lost. Both say what happened in words, and both leave a way out: the samples and the reference
 * still work.
 */
export function AnchorNotFound({
  code,
  reason,
  onOpen,
}: {
  code: string
  reason: string
  onOpen: () => void
}) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center gap-3 rounded-control border border-warn-text/40 bg-warn-surface px-3 py-2 text-sm text-warn-text"
    >
      <TriangleAlert aria-hidden className="size-4 shrink-0" />
      <span className="flex min-w-0 flex-col">
        <strong>{code === 'E202' ? s.anchorOutOfRange(code) : s.anchorNotFound(code)}</strong>
        <span>{reason}</span>
        <span>{code === 'E202' ? s.rangeHint : s.anchorHint}</span>
      </span>
      <Button variant="ghost" className="ml-auto" onClick={onOpen}>
        {s.openAnchor}
      </Button>
    </div>
  )
}

export function CameraLost({
  since,
  onReference,
  canUseReference,
}: {
  since: number | null
  onReference: () => void
  canUseReference: boolean
}) {
  const age = useAge(since)
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-3 rounded-control border border-warn-text/40 bg-warn-surface px-3 py-2 text-sm text-warn-text"
    >
      <VideoOff aria-hidden className="size-4 shrink-0" />
      <span className="flex min-w-0 flex-col">
        <strong>{s.cameraLost}</strong>
        {since === null ? null : <span>{s.lastImage(age)}</span>}
      </span>
      {canUseReference ? (
        <Button variant="ghost" className="ml-auto" onClick={onReference}>
          {s.adjustOnReference}
        </Button>
      ) : null}
    </div>
  )
}
