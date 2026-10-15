import { Popover as RadixPopover } from 'radix-ui'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

export const Popover = RadixPopover.Root
export const PopoverTrigger = RadixPopover.Trigger

export function PopoverContent({
  className,
  ...props
}: ComponentProps<typeof RadixPopover.Content>) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        sideOffset={6}
        className={cn(
          'z-50 w-72 rounded-card border border-line bg-surface-1 p-4 text-sm shadow-overlay',
          className,
        )}
        {...props}
      />
    </RadixPopover.Portal>
  )
}
