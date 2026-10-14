import { Check, ChevronDown } from 'lucide-react'
import { Select as RadixSelect } from 'radix-ui'
import { cn } from '@/lib/cn'
import { controlClasses } from './input'

export interface Option {
  value: string
  label: string
  disabled?: boolean
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder,
  disabled,
  id,
  className,
  ...aria
}: {
  value: string | undefined
  onValueChange: (value: string) => void
  options: Option[]
  placeholder?: string
  disabled?: boolean
  id?: string
  className?: string
  'aria-describedby'?: string
  'aria-invalid'?: true
}) {
  return (
    <RadixSelect.Root value={value} onValueChange={onValueChange} disabled={disabled}>
      <RadixSelect.Trigger
        id={id}
        className={cn(
          controlClasses,
          'inline-flex h-control items-center justify-between gap-2 text-left',
          className,
        )}
        {...aria}
      >
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon>
          <ChevronDown aria-hidden className="size-4 text-fg-muted" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className="z-50 min-w-(--radix-select-trigger-width) overflow-hidden rounded-card border border-line bg-surface-1 shadow-overlay"
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((o) => (
              <RadixSelect.Item
                key={o.value}
                value={o.value}
                disabled={o.disabled}
                className="relative flex min-h-control cursor-default select-none items-center rounded-control py-2 pl-8 pr-3 fs-control outline-none data-disabled:opacity-50 data-highlighted:bg-surface-3"
              >
                <RadixSelect.ItemIndicator className="absolute left-2">
                  <Check aria-hidden className="size-4" />
                </RadixSelect.ItemIndicator>
                <RadixSelect.ItemText>{o.label}</RadixSelect.ItemText>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  )
}
