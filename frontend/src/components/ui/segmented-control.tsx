import { ToggleGroup } from 'radix-ui'
import { cn } from '@/lib/cn'
import type { Option } from './select'

/** One choice out of a few, all visible. A choice cannot be unselected, so there is always a value. */
export function SegmentedControl({
  value,
  onValueChange,
  options,
  label,
}: {
  value: string
  onValueChange: (value: string) => void
  options: Option[]
  label: string
}) {
  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onValueChange(v)}
      aria-label={label}
      className="inline-flex rounded-control border border-line-control bg-surface-2 p-0.5"
    >
      {options.map((o) => (
        <ToggleGroup.Item
          key={o.value}
          value={o.value}
          disabled={o.disabled}
          className={cn(
            'h-control min-w-control rounded-control px-3 fs-control font-medium text-fg-muted transition-colors disabled:opacity-50',
            'hover:text-fg data-[state=on]:bg-accent data-[state=on]:text-on-accent',
          )}
        >
          {o.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  )
}
