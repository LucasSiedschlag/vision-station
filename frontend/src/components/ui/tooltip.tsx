import { Tooltip as RadixTooltip } from 'radix-ui'
import type { ReactNode } from 'react'

/** A short hint on hover and keyboard focus. Never the only place an essential fact appears. */
export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <RadixTooltip.Provider delayDuration={300}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            sideOffset={6}
            className="z-50 max-w-xs rounded-control border border-line bg-surface-3 px-3 py-1.5 text-xs text-fg shadow-overlay"
          >
            {content}
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  )
}
