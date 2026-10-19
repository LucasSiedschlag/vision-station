import { RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'

/** The bar turns green within this share of the best value seen (docs/frontend.md §19.5). */
export const NEAR_PEAK = 0.05

/**
 * Sharpness as a bar with a **peak hold**: turn the focus ring and the number rises to its best and stays there, so
 * the person finds the peak by passing it. The value is the one the quality gate uses (variance of the Laplacian),
 * so a number here is a number there.
 */
export function FocusMeter({
  value,
  className,
}: {
  /** The newest measure; null: no picture yet. */
  value: number | null
  className?: string
}) {
  const t = text.editor.camera
  const [held, setHeld] = useState(0)
  // the peak is the best of what was seen, kept while the component stays; a bigger value is the new peak at once
  if (value !== null && value > held) setHeld(value)
  const peak = Math.max(held, value ?? 0)
  const near = value !== null && peak > 0 && value >= peak * (1 - NEAR_PEAK)
  const share = value !== null && peak > 0 ? value / peak : 0
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium">{t.sharpness}</span>
        <span className="font-mono text-sm tabular-nums text-fg-muted">
          {value === null ? t.noValue : formatNumber(value, 0)} · {t.best(formatNumber(peak, 0))}
        </span>
      </div>
      <div
        role="meter"
        aria-label={t.sharpness}
        aria-valuemin={0}
        aria-valuemax={Math.round(peak)}
        aria-valuenow={Math.round(value ?? 0)}
        aria-valuetext={near ? t.atPeak : undefined}
        className="relative h-3 w-full overflow-hidden rounded-pill bg-surface-3"
      >
        <div
          className={cn('h-full rounded-pill', near ? 'bg-ok' : 'bg-accent')}
          style={{ width: `${share * 100}%` }}
        />
      </div>
      <div className="flex items-center gap-2">
        <span className={cn('text-xs', near ? 'text-ok-text' : 'text-fg-muted')}>
          {near ? t.atPeak : t.turnFocus}
        </span>
        <Button variant="ghost" onClick={() => setHeld(0)} className="ml-auto">
          <RotateCcw aria-hidden className="size-4" />
          {t.resetPeak}
        </Button>
      </div>
    </div>
  )
}
