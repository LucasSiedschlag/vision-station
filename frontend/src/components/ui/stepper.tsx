import { Check, Lock, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import { text } from '@/texts'

export interface Step {
  id: string
  label: string
  /** done; todo; attention (something to look at, `reason` says what); blocked (needs another step first) */
  status: 'done' | 'todo' | 'attention' | 'blocked'
  current?: boolean
  /** Why a step is blocked or needs attention: written under it, so it never needs a hover. */
  reason?: string
}

/**
 * The steps of a longer task (the job editor). A step's state is an icon and a word for screen readers, not colour
 * alone, and the reason for a state is plain text under the step. A blocked step can still be opened to read.
 */
export function Stepper({ steps, onSelect }: { steps: Step[]; onSelect?: (id: string) => void }) {
  const words = {
    done: text.ui.stepDone,
    todo: text.ui.stepTodo,
    attention: text.ui.stepAttention,
    blocked: text.ui.stepBlocked,
  }
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((step, index) => (
        <li key={step.id}>
          <button
            type="button"
            aria-current={step.current ? 'step' : undefined}
            onClick={() => onSelect?.(step.id)}
            className={cn(
              'flex min-h-control w-full items-center gap-3 rounded-control px-3 py-1 text-left fs-control hover:bg-surface-3',
              step.current && 'bg-surface-3 font-medium',
              step.status === 'blocked' && 'text-fg-muted',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'grid size-6 shrink-0 place-items-center rounded-pill border text-xs',
                step.status === 'done' && 'border-ok bg-ok text-on-ok',
                step.status === 'attention' && 'border-warn bg-warn text-on-warn',
                step.status === 'todo' && 'border-line-control text-fg-muted',
                step.status === 'blocked' && 'border-line text-fg-muted',
                step.current && step.status === 'todo' && 'border-accent bg-accent text-on-accent',
              )}
            >
              {step.status === 'done' ? (
                <Check className="size-3.5" />
              ) : step.status === 'attention' ? (
                <TriangleAlert className="size-3.5" />
              ) : step.status === 'blocked' ? (
                <Lock className="size-3.5" />
              ) : (
                index + 1
              )}
            </span>
            <span className="flex min-w-0 flex-col">
              <span>{step.label}</span>
              {step.reason ? (
                <span className="text-xs font-normal text-fg-muted">{step.reason}</span>
              ) : null}
            </span>
            <span className="sr-only">
              , {step.current ? `${text.ui.stepCurrent}, ` : ''}
              {words[step.status]}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
