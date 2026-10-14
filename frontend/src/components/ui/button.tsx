import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import { Spinner } from './spinner'

export const buttonVariants = cva(
  'relative inline-flex items-center justify-center gap-2 rounded-control font-medium h-control min-w-control px-4 fs-control select-none transition-colors disabled:cursor-not-allowed disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-on-accent hover:brightness-95 active:brightness-90',
        secondary: 'border border-line-control bg-surface-2 text-fg hover:bg-surface-3',
        ghost: 'text-fg hover:bg-surface-3',
        danger: 'bg-fail text-on-fail hover:brightness-95 active:brightness-90',
      },
    },
    defaultVariants: { variant: 'secondary' },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  /** Shows a spinner, disables the button, and keeps its width. */
  loading?: boolean
}

export function Button({
  variant,
  loading = false,
  className,
  children,
  disabled,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant }), className)}
      {...props}
    >
      <span className={cn('inline-flex items-center gap-2', loading && 'invisible')}>
        {children}
      </span>
      {loading ? (
        <span className="absolute inset-0 grid place-items-center">
          <Spinner />
        </span>
      ) : null}
    </button>
  )
}
