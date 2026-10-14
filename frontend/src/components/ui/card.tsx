import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('rounded-card border border-line bg-surface-1', className)} {...props} />
  )
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex flex-col gap-1 border-b border-line p-4', className)} {...props} />
  )
}

export function CardTitle({ className, children, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn('text-lg font-semibold', className)} {...props}>
      {children}
    </h3>
  )
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-4', className)} {...props} />
}
