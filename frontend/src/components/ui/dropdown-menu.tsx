import { DropdownMenu as RadixMenu } from 'radix-ui'
import { Check } from 'lucide-react'
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

/** An item with a check: a setting that is on or off, which the menu leaves open so several can be changed (WAI-ARIA menuitemcheckbox). */
export function DropdownMenuCheckboxItem({
  className,
  children,
  ...props
}: ComponentProps<typeof RadixMenu.CheckboxItem>) {
  return (
    <RadixMenu.CheckboxItem
      onSelect={(e) => e.preventDefault()}
      className={cn(
        'flex min-h-control cursor-default select-none items-center gap-2 rounded-control px-3 fs-control outline-none data-disabled:opacity-50 data-highlighted:bg-surface-3',
        className,
      )}
      {...props}
    >
      <span aria-hidden className="grid size-4 shrink-0 place-items-center">
        <RadixMenu.ItemIndicator>
          <Check className="size-4" />
        </RadixMenu.ItemIndicator>
      </span>
      {children}
    </RadixMenu.CheckboxItem>
  )
}
