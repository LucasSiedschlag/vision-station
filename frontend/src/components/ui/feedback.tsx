import { AlertOctagon, Inbox } from 'lucide-react'
import { useState, type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Button } from './button'

/** A placeholder with the shape of what is loading. Motion is only the soft pulse, and it stops with reduced motion. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn('animate-pulse rounded-control bg-surface-3', className)}
      {...props}
    />
  )
}

/** An empty list or panel says what it is for and offers the first action. */
export function EmptyState({
  title,
  description,
  action,
  icon,
  heading,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
  heading?: 'h1' | 'h2'
}) {
  const Title = heading ?? 'p'
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <span className="text-fg-muted">{icon ?? <Inbox aria-hidden className="size-8" />}</span>
      <Title className="text-base font-medium">{title}</Title>
      {description ? <p className="max-w-md text-sm text-fg-muted">{description}</p> : null}
      {action}
    </div>
  )
}

/** What went wrong in plain words, a retry, and the technical detail folded away. */
export function ErrorState({
  title = 'Algo deu errado',
  message,
  detail,
  onRetry,
}: {
  title?: string
  message?: string
  detail?: string
  onRetry?: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <AlertOctagon aria-hidden className="size-8 text-fail-text" />
      <p className="text-base font-medium">{title}</p>
      {message ? <p className="max-w-md text-sm text-fg-muted">{message}</p> : null}
      {onRetry ? <Button onClick={onRetry}>Tentar de novo</Button> : null}
      {detail ? (
        <div className="max-w-md text-left text-xs">
          <button
            type="button"
            className="text-accent-text underline"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? 'Ocultar detalhes' : 'Detalhes'}
          </button>
          {open ? (
            <pre className="mt-2 overflow-auto rounded-control bg-surface-2 p-3 font-mono whitespace-pre-wrap">
              {detail}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
