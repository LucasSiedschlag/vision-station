import { Tabs as RadixTabs } from 'radix-ui'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

export const Tabs = RadixTabs.Root

export function TabsList({ className, ...props }: ComponentProps<typeof RadixTabs.List>) {
  return <RadixTabs.List className={cn('flex gap-1 border-b border-line', className)} {...props} />
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof RadixTabs.Trigger>) {
  return (
    <RadixTabs.Trigger
      className={cn(
        '-mb-px h-control border-b-2 border-transparent px-4 fs-control font-medium text-fg-muted hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  )
}

export function TabsContent({ className, ...props }: ComponentProps<typeof RadixTabs.Content>) {
  return <RadixTabs.Content className={cn('pt-4', className)} {...props} />
}
