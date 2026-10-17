import { GripVertical } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import { cn } from '@/lib/cn'

// Resizable panels (react-resizable-panels 4, TD-29): the workbench of the editor (document 05 §10.1).
// Sizes: a number is pixels, a string without a unit is a percentage ("30").

export function ResizablePanelGroup({ className, ...props }: ComponentProps<typeof Group>) {
  return (
    <Group
      className={cn(
        'flex h-full w-full',
        props.orientation === 'vertical' && 'flex-col',
        className,
      )}
      {...props}
    />
  )
}

export const ResizablePanel = Panel

/** The handle between two panels: drag it, or focus it and use the arrow keys. It is named for screen readers. */
export function ResizableHandle({
  className,
  'aria-label': ariaLabel,
  ...props
}: ComponentProps<typeof Separator> & { 'aria-label': string }) {
  return (
    <Separator
      aria-label={ariaLabel}
      className={cn(
        'group relative flex w-2 shrink-0 items-center justify-center bg-surface-0 hover:bg-surface-3 data-[separator=active]:bg-accent aria-[orientation=horizontal]:h-2 aria-[orientation=horizontal]:w-full',
        className,
      )}
      {...props}
    >
      <span
        aria-hidden
        className="z-10 flex h-6 w-3 items-center justify-center rounded-control border border-line bg-surface-2 group-aria-[orientation=horizontal]:rotate-90"
      >
        <GripVertical className="size-3 text-fg-muted" />
      </span>
    </Separator>
  )
}
