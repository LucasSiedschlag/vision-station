import { ChevronDown } from 'lucide-react'
import { Accordion as RadixAccordion } from 'radix-ui'
import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/cn'

// Sections that open and close (Radix Accordion): the inspector's Região / O que medir / Critério /
// Resultado (document 05 §7.3). Each header is a button inside a heading.

export const Accordion = RadixAccordion.Root

export function AccordionItem({ className, ...props }: ComponentProps<typeof RadixAccordion.Item>) {
  return <RadixAccordion.Item className={cn('border-b border-line', className)} {...props} />
}

export function AccordionTrigger({
  children,
  hint,
  className,
  ...props
}: ComponentProps<typeof RadixAccordion.Trigger> & { hint?: ReactNode }) {
  return (
    <RadixAccordion.Header className="flex">
      <RadixAccordion.Trigger
        className={cn(
          'group flex min-h-control flex-1 items-center justify-between gap-4 py-2 text-left text-sm font-medium hover:text-accent-text',
          className,
        )}
        {...props}
      >
        <span>{children}</span>
        <span className="flex items-center gap-2">
          {hint ? <span className="text-xs font-normal text-fg-muted">{hint}</span> : null}
          <ChevronDown
            aria-hidden
            className="size-4 shrink-0 text-fg-muted transition-transform group-data-[state=open]:rotate-180"
          />
        </span>
      </RadixAccordion.Trigger>
    </RadixAccordion.Header>
  )
}

export function AccordionContent({
  children,
  className,
  ...props
}: ComponentProps<typeof RadixAccordion.Content>) {
  return (
    <RadixAccordion.Content className="overflow-hidden text-sm" {...props}>
      <div className={cn('flex flex-col gap-3 pb-4', className)}>{children}</div>
    </RadixAccordion.Content>
  )
}
