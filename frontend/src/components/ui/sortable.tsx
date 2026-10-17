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
import { text } from '@/texts'

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
  const place = (id: UniqueIdentifier) => text.ui.place(ids.indexOf(id) + 1, ids.length)
  return {
    onDragStart: ({ active }) => text.ui.dragStart(name(active.id), place(active.id)),
    onDragOver: ({ active, over }) =>
      over ? text.ui.dragOver(name(active.id), place(over.id)) : text.ui.dragOut(name(active.id)),
    onDragEnd: ({ active, over }) =>
      over ? text.ui.dragEnd(name(active.id), place(over.id)) : text.ui.dropped(name(active.id)),
    onDragCancel: ({ active }) => text.ui.dragCancel(name(active.id)),
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
          draggable: text.ui.dragHelp,
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
        aria-label={text.ui.move(name)}
        aria-roledescription={text.ui.movable}
        className="flex min-h-control w-8 shrink-0 cursor-grab touch-none items-center justify-center text-fg-muted active:cursor-grabbing"
      >
        <GripVertical aria-hidden className="size-4" />
      </button>
      <div className="min-w-0 flex-1">{children}</div>
    </li>
  )
}
