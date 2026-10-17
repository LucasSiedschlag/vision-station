import { X } from 'lucide-react'
import { AlertDialog, Dialog as RadixDialog } from 'radix-ui'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Button } from './button'
import { useReturnFocus } from './use-return-focus'
import { text } from '@/texts'

const overlay = 'fixed inset-0 z-40 bg-surface-0/80 backdrop-blur-sm'

export const Dialog = RadixDialog.Root
export const DialogTrigger = RadixDialog.Trigger
export const DialogClose = RadixDialog.Close

/** A dialog always has a title (read by screen readers); the focus is trapped inside and returns to the opener. */
export function DialogContent({
  title,
  description,
  children,
  className,
  onOpenAutoFocus,
  onCloseAutoFocus,
  id,
}: {
  id?: string
  title: string
  description?: string
  children: ReactNode
  className?: string
  /** Where the focus goes on open; by default the first control (often Fechar). */
  onOpenAutoFocus?: (event: Event) => void
  /** Where the focus goes on close; by default the trigger, when there is one. */
  onCloseAutoFocus?: (event: Event) => void
}) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className={overlay} />
      <RadixDialog.Content
        {...(description ? {} : { 'aria-describedby': undefined })}
        onOpenAutoFocus={onOpenAutoFocus}
        onCloseAutoFocus={onCloseAutoFocus}
        id={id}
        className={cn(
          'fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-dialog -translate-x-1/2 -translate-y-1/2 flex-col gap-4 overflow-auto rounded-card border border-line bg-surface-1 p-6 shadow-overlay',
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <RadixDialog.Title className="text-lg font-semibold">{title}</RadixDialog.Title>
            {description ? (
              <RadixDialog.Description className="text-sm text-fg-muted">
                {description}
              </RadixDialog.Description>
            ) : null}
          </div>
          <RadixDialog.Close asChild>
            <Button variant="ghost" aria-label={text.ui.close} className="-mr-2 -mt-2 px-0">
              <X aria-hidden className="size-4" />
            </Button>
          </RadixDialog.Close>
        </div>
        {children}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  )
}

export function DialogFooter({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap justify-end gap-2">{children}</div>
}

/**
 * For actions that matter (activate a job, override a verification, change a password): says exactly what
 * will happen and asks for it by name. Cancel is the default focus, so Enter never confirms by accident.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  tone = 'primary',
  loading = false,
  onConfirm,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  tone?: 'primary' | 'danger'
  loading?: boolean
  onConfirm: () => void
  children?: ReactNode
}) {
  const returnFocus = useReturnFocus(open)
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className={overlay} />
        <AlertDialog.Content
          onCloseAutoFocus={returnFocus}
          className="fixed left-1/2 top-1/2 z-50 flex w-confirm -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-card border border-line bg-surface-1 p-6 shadow-overlay"
        >
          <div className="flex flex-col gap-2">
            <AlertDialog.Title className="text-lg font-semibold">{title}</AlertDialog.Title>
            <AlertDialog.Description className="text-sm text-fg-muted">
              {description}
            </AlertDialog.Description>
          </div>
          {children}
          <DialogFooter>
            <AlertDialog.Cancel asChild>
              <Button>{cancelLabel ?? text.ui.cancel}</Button>
            </AlertDialog.Cancel>
            <Button
              variant={tone === 'danger' ? 'danger' : 'primary'}
              loading={loading}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
          </DialogFooter>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  )
}

/** A panel that slides in from the right, for the detail of a row without leaving the list. */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  side = 'right',
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  /** `bottom` is the drawer: the filmstrip and the inspector at 1366×768 (document 05 §10). */
  side?: 'right' | 'bottom'
  children: ReactNode
}) {
  const returnFocus = useReturnFocus(open)
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={overlay} />
        <RadixDialog.Content
          onCloseAutoFocus={returnFocus}
          {...(description ? {} : { 'aria-describedby': undefined })}
          className={cn(
            'fixed z-50 flex flex-col gap-4 overflow-auto bg-surface-1 p-6 shadow-overlay',
            side === 'right'
              ? 'inset-y-0 right-0 w-sheet border-l border-line'
              : 'inset-x-0 bottom-0 max-h-[70vh] rounded-t-card border-t border-line',
          )}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-1">
              <RadixDialog.Title className="text-xl font-semibold">{title}</RadixDialog.Title>
              {description ? (
                <RadixDialog.Description className="text-sm text-fg-muted">
                  {description}
                </RadixDialog.Description>
              ) : null}
            </div>
            <RadixDialog.Close asChild>
              <Button variant="ghost" aria-label={text.ui.close} className="-mr-2 -mt-2 px-0">
                <X aria-hidden className="size-4" />
              </Button>
            </RadixDialog.Close>
          </div>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

/** A sheet that comes up from the bottom (TD-29 `Drawer`, built on the same dialog as `Sheet`, without vaul). */
export function Drawer(props: Omit<Parameters<typeof Sheet>[0], 'side'>) {
  return <Sheet {...props} side="bottom" />
}
