import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type UniqueIdentifier,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

// A list reordered by dragging a handle, or with the keyboard (dnd-kit 6, TD-29): tools and anchors
// in the editor. The screen-reader texts are Portuguese (dnd-kit's own are English). Inside a Sheet or
// Drawer, pass the live region into the dialog (`accessibility.container`): a modal hides the body.

export interface SortableItem {
  id: UniqueIdentifier
}

function announcements(
  name: (id: UniqueIdentifier) => string,
  ids: UniqueIdentifier[],
): Announcements {
  const place = (id: UniqueIdentifier) => `posição ${ids.indexOf(id) + 1} de ${ids.length}`
  return {
    onDragStart: ({ active }) => `${name(active.id)} pego para mover, na ${place(active.id)}.`,
    onDragOver: ({ active, over }) =>
      over ? `${name(active.id)} na ${place(over.id)}.` : `${name(active.id)} fora da lista.`,
    onDragEnd: ({ active, over }) =>
      over ? `${name(active.id)} solto na ${place(over.id)}.` : `${name(active.id)} solto.`,
    onDragCancel: ({ active }) => `Movimento cancelado. ${name(active.id)} voltou ao lugar.`,
  }
}

export function SortableList<T extends SortableItem>({
  items,
  onReorder,
  itemLabel,
  renderItem,
  label,
  className,
}: {
  items: T[]
  onReorder: (items: T[]) => void
  /** The item's name, for the handle ("Mover tampa") and the announcements. */
  itemLabel: (item: T) => string
  renderItem: (item: T) => ReactNode
  /** The list's name for screen readers. */
  label: string
  className?: string
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )
  const name = (id: UniqueIdentifier) => {
    const item = items.find((i) => i.id === id)
    return item ? itemLabel(item) : String(id)
  }
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return
    const from = items.findIndex((i) => i.id === active.id)
    const to = items.findIndex((i) => i.id === over.id)
    onReorder(arrayMove(items, from, to))
  }
  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={onDragEnd}
      accessibility={{
        announcements: announcements(
          name,
          items.map((i) => i.id),
        ),
        screenReaderInstructions: {
          draggable:
            'Para mover, pressione Espaço ou Enter; use as setas para cima e para baixo; Espaço ou Enter de novo para soltar, Esc para cancelar.',
        },
      }}
    >
      <SortableContext items={items} strategy={verticalListSortingStrategy}>
        <ul aria-label={label} className={cn('flex flex-col gap-1', className)}>
          {items.map((item) => (
            <Row key={item.id} id={item.id} name={itemLabel(item)}>
              {renderItem(item)}
            </Row>
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  )
}

function Row({ id, name, children }: { id: UniqueIdentifier; name: string; children: ReactNode }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'flex items-center gap-2 rounded-control border border-line bg-surface-1 pr-3',
        isDragging && 'relative z-10 border-accent shadow-overlay',
      )}
    >
      <button
        type="button"
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        aria-label={`Mover ${name}`}
        aria-roledescription="item que pode ser movido"
        className="flex min-h-control w-8 shrink-0 cursor-grab touch-none items-center justify-center text-fg-muted active:cursor-grabbing"
      >
        <GripVertical aria-hidden className="size-4" />
      </button>
      <div className="min-w-0 flex-1">{children}</div>
    </li>
  )
}
