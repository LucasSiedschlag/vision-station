import { cva, type VariantProps } from 'class-variance-authority'
import { CheckCircle2, Circle, HelpCircle, Loader2, TriangleAlert, XCircle } from 'lucide-react'
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export type Tone = 'ok' | 'fail' | 'warn' | 'busy' | 'neutral' | 'unknown'

const badge = cva('inline-flex items-center gap-1 rounded-pill border px-2 text-xs font-medium', {
  variants: {
    tone: {
      ok: 'border-ok-text/40 bg-ok-surface text-ok-text',
      fail: 'border-fail-text/40 bg-fail-surface text-fail-text',
      warn: 'border-warn-text/40 bg-warn-surface text-warn-text',
      busy: 'border-busy-text/40 bg-busy-surface text-busy-text',
      neutral: 'border-line bg-surface-2 text-fg',
      unknown: 'border-dashed border-line-control bg-transparent text-fg-muted',
    },
  },
  defaultVariants: { tone: 'neutral' },
})

export function Badge({
  tone,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...props} />
}

const icons = {
  ok: CheckCircle2,
  fail: XCircle,
  warn: TriangleAlert,
  busy: Loader2,
  neutral: Circle,
  unknown: HelpCircle,
} as const

/**
 * A status as an icon and a word together, never a colour alone (NFR-USA-2).
 * `unknown` is for what the system does not know: it is never shown as OK.
 */
export function StatusIndicator({
  tone,
  label,
  detail,
  className,
}: {
  tone: Tone
  label: string
  detail?: string
  className?: string
}) {
  const Icon = icons[tone]
  const colour = {
    ok: 'text-ok-text',
    fail: 'text-fail-text',
    warn: 'text-warn-text',
    busy: 'text-busy-text',
    neutral: 'text-fg-muted',
    unknown: 'text-fg-muted',
  }[tone]
  return (
    <span className={cn('inline-flex items-center gap-2 text-sm', className)}>
      <Icon
        aria-hidden
        className={cn('size-4 shrink-0', colour, tone === 'busy' && 'animate-spin')}
      />
      <span className="font-medium">{label}</span>
      {detail ? <span className="text-fg-muted">{detail}</span> : null}
    </span>
  )
}
