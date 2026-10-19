import { CheckCircle2, Minus, XCircle } from 'lucide-react'
import type { DraftTestOut } from '@/api/queries/editor'
import { Badge } from '@/components/ui/badge'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import type { JobJson } from './draft'

const t = text.editor
const tone = { PASS: 'ok', FAIL: 'fail', ERROR: 'warn' } as const

/**
 * The bar under the workbench (docs/frontend.md §10.1): the verdict of the last measurement of the draft, a chip for
 * each tool (✓, ✕, or – when it did not run) **without values**, which live in the gauges, the time it took and the
 * rate of the live measurement. It is a group, not a live region: it changes several times a second.
 */
export function ResultBar({
  test,
  tools,
  rate,
  note,
}: {
  test: DraftTestOut | null
  tools: JobJson[]
  /** measurements per second of the live session; null: not live */
  rate: number | null
  /** where the measurement comes from, in a few words */
  note: string
}) {
  const b = t.bar
  return (
    <div
      role="group"
      aria-label={t.resultBarLabel}
      className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 border-t border-line bg-surface-1 px-4 py-1"
    >
      {test ? (
        <>
          <Badge tone={tone[test.result.outcome]}>{t.outcome[test.result.outcome]}</Badge>
          <span className="min-w-0 max-w-md truncate text-sm">{test.result.reason}</span>
          <ul className="flex flex-wrap items-center gap-2">
            {tools.map((tool) => {
              const found = test.result.tools?.find((x) => x.id === tool.id)
              const state = found ? (found.passed ? b.passed : b.failed) : b.notRun
              return (
                <li
                  key={tool.id}
                  aria-label={b.toolChip(tool.id, state)}
                  className="inline-flex items-center gap-1 text-sm"
                >
                  {found ? (
                    found.passed ? (
                      <CheckCircle2 aria-hidden className="size-4 text-ok-text" />
                    ) : (
                      <XCircle aria-hidden className="size-4 text-fail-text" />
                    )
                  ) : (
                    <Minus aria-hidden className="size-4 text-fg-muted" />
                  )}
                  {tool.id}
                </li>
              )
            })}
          </ul>
          <span className="font-mono text-xs tabular-nums text-fg-muted">
            {test.result.duration_ms} ms
          </span>
        </>
      ) : (
        <span className="text-sm text-fg-muted">{b.none}</span>
      )}
      <span className="ml-auto flex items-center gap-3 text-xs text-fg-muted">
        {rate === null ? null : (
          <span className="tabular-nums">● {b.rate(formatNumber(rate, 1))}</span>
        )}
        <span>{note}</span>
      </span>
    </div>
  )
}
