import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Plain styled table parts. Sorting and paging come with TanStack Table where a screen needs them. */
export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-auto rounded-card border border-line">
      <table className={cn('w-full border-collapse text-left text-sm', className)} {...props} />
    </div>
  )
}

export const THead = (props: HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className="sticky top-0 bg-surface-2 text-xs text-fg-muted" {...props} />
)
export const TBody = (props: HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody className="[&>tr:nth-child(even)]:bg-surface-2/50" {...props} />
)

export function TR({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn(
        'border-t border-line hover:bg-surface-3 aria-selected:bg-surface-3',
        className,
      )}
      {...props}
    />
  )
}

export function TH({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return <th scope="col" className={cn('px-4 py-2 font-medium', className)} {...props} />
}

/** `numeric` right-aligns and uses tabular figures. */
export function TD({
  className,
  numeric,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <td
      className={cn(
        'px-4 py-2 align-middle',
        numeric && 'text-right font-mono tabular-nums',
        className,
      )}
      {...props}
    />
  )
}
