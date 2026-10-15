import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './button'

/** "101–200 de 340" with previous and next. Pages are server-side; `offset` is the first row shown. */
export function Pagination({
  offset,
  page,
  total,
  onOffset,
}: {
  offset: number
  page: number
  total: number
  onOffset: (offset: number) => void
}) {
  if (total <= page && offset === 0) return null
  const last = Math.min(total, offset + page)
  return (
    <nav aria-label="Páginas" className="flex items-center justify-end gap-2 text-sm">
      <span className="tabular-nums text-fg-muted">
        {total === 0 ? '0' : `${offset + 1}–${last} de ${total}`}
      </span>
      <Button
        variant="ghost"
        aria-label="Página anterior"
        disabled={offset === 0}
        onClick={() => onOffset(Math.max(0, offset - page))}
      >
        <ChevronLeft aria-hidden className="size-4" />
      </Button>
      <Button
        variant="ghost"
        aria-label="Próxima página"
        disabled={last >= total}
        onClick={() => onOffset(offset + page)}
      >
        <ChevronRight aria-hidden className="size-4" />
      </Button>
    </nav>
  )
}
