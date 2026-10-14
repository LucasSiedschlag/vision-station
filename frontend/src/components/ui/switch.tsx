import { Switch as RadixSwitch } from 'radix-ui'
import { useId } from 'react'
import { cn } from '@/lib/cn'

export function Switch({
  checked,
  onCheckedChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label: string
  hint?: string
  disabled?: boolean
}) {
  const id = useId()
  return (
    <div className="flex items-start gap-3">
      <RadixSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={cn(
          'mt-0.5 h-6 w-11 shrink-0 rounded-pill border border-line-control bg-surface-2 transition-colors data-[state=checked]:border-transparent data-[state=checked]:bg-accent disabled:cursor-not-allowed disabled:opacity-50',
        )}
      >
        <RadixSwitch.Thumb className="block size-4 translate-x-1 rounded-pill bg-fg transition-transform data-[state=checked]:translate-x-6 data-[state=checked]:bg-on-accent" />
      </RadixSwitch.Root>
      <div className="flex flex-col">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint ? (
          <span id={`${id}-hint`} className="text-xs text-fg-muted">
            {hint}
          </span>
        ) : null}
      </div>
    </div>
  )
}
