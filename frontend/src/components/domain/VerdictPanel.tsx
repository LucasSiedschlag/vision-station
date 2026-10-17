import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  TriangleAlert,
  Video,
  WifiOff,
  Wrench,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import type { Tone, Verdict } from '@/features/operator/view'
import { text } from '@/texts'

const icons = {
  check: CheckCircle2,
  cross: XCircle,
  alert: TriangleAlert,
  busy: Loader2,
  wait: CircleDashed,
  offline: WifiOff,
  camera: Video,
  wrench: Wrench,
} as const

// the status surface, a solid edge in the status colour, and the text in the status text colour (all AA, see tokens.test.ts)
const tones: Record<Tone, string> = {
  ok: 'border-ok bg-ok-surface text-ok-text',
  fail: 'border-fail bg-fail-surface text-fail-text',
  warn: 'border-warn bg-warn-surface text-warn-text',
  busy: 'border-busy-text bg-busy-surface text-busy-text',
  neutral: 'border-line bg-surface-1 text-fg',
}

/**
 * The verdict, as the figure of the operator screen: an icon, the word, the reason. Colour and word always come
 * together. It is a live region, so a screen reader announces each new result at once.
 */
export function VerdictPanel({ verdict }: { verdict: Verdict }) {
  const Icon = icons[verdict.icon]
  return (
    <section
      role="status"
      aria-live="assertive"
      aria-label={text.live.verdictLabel}
      className={cn(
        'flex size-full min-h-0 flex-col items-center justify-center gap-4 rounded-card border-2 p-6 text-center',
        tones[verdict.tone],
      )}
    >
      <Icon
        aria-hidden
        className={cn('size-20 shrink-0', verdict.icon === 'busy' && 'animate-spin')}
      />
      <p
        className={cn(
          'font-bold break-words',
          verdict.size === 'display' ? 'text-display' : 'text-3xl',
        )}
      >
        {verdict.headline}
      </p>
      {verdict.reason ? (
        <p className="text-3xl font-medium text-fg break-words">{verdict.reason}</p>
      ) : null}
      {verdict.meta ? (
        <p className="font-mono text-base text-fg tabular-nums">{verdict.meta}</p>
      ) : null}
      {verdict.stale ? <p className="text-base text-fg">{verdict.stale}</p> : null}
    </section>
  )
}
