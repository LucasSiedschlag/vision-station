import type { ComponentType } from 'react'
import { GrayThresholdPicker } from './GrayThresholdPicker'
import { HsvRangePicker } from './HsvRangePicker'

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
  /** Every parameter of the object this one belongs to, for a control that edits several together. */
  values: Record<string, unknown>
  /** Several parameters at once, in one step of the undo history: a key set to `undefined` is left out of the job. */
  patch: (changes: Record<string, unknown>) => void
  /** The settings level of the form (1 Essencial, 2 Avançado, 3 Especialista). */
  level: number
}

/**
 * The graphical controls, by the name a parameter gives in `x-widget`. A parameter whose widget is not here is
 * drawn by its type (a number, a switch, a list), so the server can name a widget before the screen has it.
 * Each control is added where it is built (the HSV range picker, the template cropper...), not in SchemaForm.
 */
export const widgets: Record<string, ComponentType<WidgetProps>> = {
  'hsv-range': HsvRangePicker,
  'gray-threshold': GrayThresholdPicker,
}

/**
 * The other parameters a control draws itself, by widget: the form leaves them out, whatever their level, because
 * the control shows them at every level (as the picker does with the saturation and value of its range).
 */
export const widgetOwns: Record<string, readonly string[]> = {
  'hsv-range': ['s_min', 's_max', 'v_min', 'v_max'],
}

/** The parameters of a schema that a widget in it draws. */
export function ownedBy(properties: Record<string, Record<string, unknown>>): string[] {
  return Object.values(properties).flatMap((p) => {
    const w = typeof p['x-widget'] === 'string' ? p['x-widget'] : ''
    return w in widgets ? [...(widgetOwns[w] ?? [])] : []
  })
}
