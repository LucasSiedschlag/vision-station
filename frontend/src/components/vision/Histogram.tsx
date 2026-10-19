import { cn } from '@/lib/cn'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'

/** Above this share of clipped pixels (percent) the histogram says so in a warning colour (docs/frontend.md §7.3). */
export const CLIP_WARN = 1

/**
 * The gray histogram of the live image with the share of pixels crushed to black and saturated at its ends
 * (docs/frontend.md §19.5). The bars are on a square-root scale, so the thin tails that matter for exposure stay
 * visible next to a tall peak.
 */
export function Histogram({
  counts,
  clippedLow,
  clippedHigh,
  className,
}: {
  counts: number[]
  clippedLow: number
  clippedHigh: number
  className?: string
}) {
  const t = text.editor.camera
  const peak = Math.sqrt(Math.max(1, ...counts))
  return (
    <figure className={cn('flex flex-col gap-1', className)}>
      <svg
        role="img"
        aria-label={t.histogramLabel}
        viewBox="0 0 256 40"
        preserveAspectRatio="none"
        className="h-16 w-full rounded-control border border-line bg-surface-2 text-fg-muted"
      >
        {counts.map((n, i) =>
          n > 0 ? (
            <rect
              key={i}
              x={i}
              y={40 - (Math.sqrt(n) / peak) * 40}
              width={1}
              height={(Math.sqrt(n) / peak) * 40}
              fill="currentColor"
            />
          ) : null,
        )}
      </svg>
      <figcaption className="flex justify-between gap-4 text-xs tabular-nums">
        <span className={clippedLow > CLIP_WARN ? 'text-warn-text' : 'text-fg-muted'}>
          {t.clippedLow(formatNumber(clippedLow, 1))}
        </span>
        <span className={clippedHigh > CLIP_WARN ? 'text-warn-text' : 'text-fg-muted'}>
          {t.clippedHigh(formatNumber(clippedHigh, 1))}
        </span>
      </figcaption>
    </figure>
  )
}
