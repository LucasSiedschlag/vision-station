import { Toaster as Sonner } from 'sonner'

/** Toasts: success disappears after a few seconds, errors stay until dismissed (docs/frontend.md §6.4). */
export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      closeButton
      duration={5000}
      toastOptions={{
        unstyled: true,
        duration: 5000,
        classNames: {
          toast:
            'flex w-toast items-start gap-3 rounded-card border border-line border-l-4 bg-surface-1 p-4 text-sm text-fg shadow-overlay',
          success: 'border-l-ok',
          error: 'border-l-fail',
          warning: 'border-l-warn',
          info: 'border-l-accent',
          title: 'font-medium',
          description: 'text-fg-muted',
          closeButton: 'rounded-control border border-line bg-surface-2',
        },
      }}
    />
  )
}
