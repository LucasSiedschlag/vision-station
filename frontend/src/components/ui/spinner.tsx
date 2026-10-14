import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

/** Shown only while something is running (no idle animation); `prefers-reduced-motion` stops the spin. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role={label ? 'status' : undefined} className="inline-flex items-center">
      <Loader2 aria-hidden className={cn('size-4 animate-spin', className)} />
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  )
}
