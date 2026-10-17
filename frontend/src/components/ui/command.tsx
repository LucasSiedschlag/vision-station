import {
  CommandEmpty as CmdkEmpty,
  CommandGroup as CmdkGroup,
  CommandInput as CmdkInput,
  CommandItem as CmdkItem,
  CommandList as CmdkList,
  CommandRoot,
  CommandSeparator as CmdkSeparator,
} from 'cmdk'
import { Search } from 'lucide-react'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/cn'

// A filtered list to pick from with the keyboard (cmdk, TD-29): the Ctrl+K palette. Shown inside our
// own Dialog (title, focus trap, focus return), never in cmdk's dialog.

export function Command({ className, ...props }: ComponentProps<typeof CommandRoot>) {
  return <CommandRoot className={cn('flex flex-col gap-2', className)} {...props} />
}

export function CommandInput({ className, ...props }: ComponentProps<typeof CmdkInput>) {
  return (
    <div className="relative">
      <Search
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-3 my-auto size-4 text-fg-muted"
      />
      <CmdkInput
        className={cn(
          'h-control w-full rounded-control border border-line-control bg-surface-2 pl-9 pr-3 fs-control text-fg placeholder:text-fg-muted',
          className,
        )}
        {...props}
      />
    </div>
  )
}

export function CommandList({ className, ...props }: ComponentProps<typeof CmdkList>) {
  return <CmdkList className={cn('max-h-80 overflow-y-auto', className)} {...props} />
}

export function CommandEmpty({ className, ...props }: ComponentProps<typeof CmdkEmpty>) {
  return (
    <CmdkEmpty className={cn('py-6 text-center text-sm text-fg-muted', className)} {...props} />
  )
}

export function CommandGroup({ className, ...props }: ComponentProps<typeof CmdkGroup>) {
  return (
    <CmdkGroup
      className={cn(
        'py-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-fg-muted',
        className,
      )}
      {...props}
    />
  )
}

export function CommandItem({ className, ...props }: ComponentProps<typeof CmdkItem>) {
  return (
    <CmdkItem
      className={cn(
        'flex min-h-control cursor-pointer items-center gap-3 rounded-control px-3 text-control data-[selected=true]:bg-surface-3 data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

export function CommandSeparator({ className, ...props }: ComponentProps<typeof CmdkSeparator>) {
  return <CmdkSeparator className={cn('my-1 h-px bg-line', className)} {...props} />
}
