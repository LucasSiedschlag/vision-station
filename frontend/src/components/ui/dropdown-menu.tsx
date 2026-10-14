import { DropdownMenu as RadixMenu } from 'radix-ui'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

export const DropdownMenu = RadixMenu.Root
export const DropdownMenuTrigger = RadixMenu.Trigger

export function DropdownMenuContent({
  className,
  ...props
}: ComponentProps<typeof RadixMenu.Content>) {
  return (
    <RadixMenu.Portal>
      <RadixMenu.Content
        sideOffset={4}
        align="end"
        className={cn(
          'z-50 min-w-48 rounded-card border border-line bg-surface-1 p-1 shadow-overlay',
          className,
        )}
        {...props}
      />
    </RadixMenu.Portal>
  )
}

export function DropdownMenuItem({
  className,
  danger,
  ...props
}: ComponentProps<typeof RadixMenu.Item> & { danger?: boolean }) {
  return (
    <RadixMenu.Item
      className={cn(
        'flex min-h-control cursor-default select-none items-center gap-2 rounded-control px-3 fs-control outline-none data-disabled:opacity-50 data-highlighted:bg-surface-3',
        danger && 'text-fail-text',
        className,
      )}
      {...props}
    />
  )
}

export const DropdownMenuSeparator = (props: ComponentProps<typeof RadixMenu.Separator>) => (
  <RadixMenu.Separator className="my-1 h-px bg-line" {...props} />
)
