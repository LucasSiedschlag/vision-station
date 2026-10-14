import { Check, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface Step {
  id: string
  label: string
  status: 'done' | 'current' | 'todo' | 'error'
}

/** The steps of a longer task (the job editor). A step's state is an icon and a word for screen readers, not colour alone. */
export function Stepper({ steps, onSelect }: { steps: Step[]; onSelect?: (id: string) => void }) {
  const words = { done: 'concluído', current: 'passo atual', todo: 'pendente', error: 'com erro' }
  return (
    <ol className="flex flex-col gap-1">
      {steps.map((step, index) => (
        <li key={step.id}>
          <button
            type="button"
            aria-current={step.status === 'current' ? 'step' : undefined}
            onClick={() => onSelect?.(step.id)}
            className={cn(
              'flex min-h-control w-full items-center gap-3 rounded-control px-3 text-left fs-control hover:bg-surface-3',
              step.status === 'current' && 'bg-surface-3 font-medium',
            )}
          >
            <span
              aria-hidden
              className={cn(
                'grid size-6 shrink-0 place-items-center rounded-pill border text-xs',
                step.status === 'done' && 'border-ok bg-ok text-on-ok',
                step.status === 'current' && 'border-accent bg-accent text-on-accent',
                step.status === 'error' && 'border-warn bg-warn text-on-warn',
                step.status === 'todo' && 'border-line-control text-fg-muted',
              )}
            >
              {step.status === 'done' ? (
                <Check className="size-3.5" />
              ) : step.status === 'error' ? (
                <TriangleAlert className="size-3.5" />
              ) : (
                index + 1
              )}
            </span>
            <span>{step.label}</span>
            <span className="sr-only">, {words[step.status]}</span>
          </button>
        </li>
      ))}
    </ol>
  )
}
