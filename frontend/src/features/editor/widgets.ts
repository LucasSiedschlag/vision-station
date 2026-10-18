import type { ComponentType } from 'react'

/** What a graphical control gets for the parameter that names it in `x-widget` (docs/frontend.md §19.2). */
export interface WidgetProps {
  name: string
  /** The parameter's own schema, with the `x-*` tags. */
  schema: Record<string, unknown>
  value: unknown
  /** `remove`: the value is left out of the job again. */
  onChange: (value: unknown, remove?: boolean) => void
  label: string
  hint?: string
  error?: string
}

/**
 * The graphical controls, by the name a parameter gives in `x-widget`. A parameter whose widget is not here is
 * drawn by its type (a number, a switch, a list), so the server can name a widget before the screen has it.
 * Each control is added where it is built (the HSV range picker, the template cropper...), not in SchemaForm.
 */
export const widgets: Record<string, ComponentType<WidgetProps>> = {}
