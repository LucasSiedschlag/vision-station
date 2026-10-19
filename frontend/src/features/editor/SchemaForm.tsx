import { useState, type ReactNode } from 'react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { formatNumber, formatPercent } from '@/lib/number'
import { text as texts } from '@/texts'
import type { Level } from '@/app/levels'
import { ownedBy, widgets } from './widgets'

/**
 * A form drawn from a tool's or locator's JSON Schema (docs/frontend.md §7.3), so a new tool type needs no
 * screen code (FR-PLT-2). It covers what our Pydantic models produce; anything else becomes a JSON text field,
 * never silently dropped. Titles, descriptions and the labels of choices come from the schema, in the language of the
 * request.
 *
 * Version 2 (docs/frontend.md §17, §19.2) reads the tags the server puts on each parameter: `x-group` (what to measure,
 * or the criteria), `x-level` (Essencial, Avançado, Especialista), `x-unit` (a fraction is written as a percentage, px
 * and ΔE follow the number) and `x-widget` (a graphical control from `widgets`, the plain control while it has none).
 * A parameter without a level counts as Especialista, so a forgotten tag hides a field rather than cluttering the form.
 */

/* eslint-disable @typescript-eslint/no-explicit-any -- JSON Schema and parameter values are open by nature */
export type Schema = Record<string, any>
type Values = Record<string, any>

function resolve(schema: Schema, root: Schema): Schema {
  if (typeof schema.$ref === 'string') {
    const name = schema.$ref.split('/').pop() as string
    return { ...(root.$defs?.[name] ?? {}), ...schema, $ref: undefined }
  }
  return schema
}

/** `anyOf: [X, {type: null}]`: X, and whether the value may be left out. */
function unwrapNullable(schema: Schema, root: Schema): { inner: Schema; nullable: boolean } {
  const options: Schema[] | undefined = schema.anyOf
  if (options && options.length === 2 && options.some((o) => o.type === 'null')) {
    const inner = options.find((o) => o.type !== 'null')!
    return {
      inner: {
        ...resolve(inner, root),
        title: schema.title,
        description: schema.description,
        default: schema.default,
      },
      nullable: true,
    }
  }
  return { inner: resolve(schema, root), nullable: false }
}

const range = (s: Schema) => ({
  min: s.minimum ?? s.exclusiveMinimum,
  max: s.maximum ?? s.exclusiveMaximum,
})

function defaultOf(schema: Schema, root: Schema): any {
  if (schema.default !== undefined && schema.default !== null)
    return structuredClone(schema.default)
  const s = resolve(schema, root)
  if (s.type === 'boolean') return false
  if (s.type === 'integer' || s.type === 'number') return s.minimum ?? 0
  if (s.type === 'string') return s.enum?.[0] ?? ''
  if (s.type === 'array')
    return s.prefixItems ? s.prefixItems.map((p: Schema) => defaultOf(p, root)) : []
  if (s.type === 'object') return {}
  return null
}

/** A list of words typed as "a, b, c": the text is kept as typed, the list follows it. */
function WordList({
  label,
  hint,
  error,
  value,
  onChange,
}: {
  label: string
  hint?: string
  error?: string
  value: unknown
  onChange: (v: string[] | null, remove?: boolean) => void
}) {
  const [text, setText] = useState(Array.isArray(value) ? value.join(', ') : '')
  return (
    <Field
      label={label}
      hint={hint ? texts.ui.commaSeparatedHint(hint) : texts.ui.commaSeparated}
      error={error}
    >
      {(props) => (
        <Input
          {...props}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            const list = e.target.value
              .split(',')
              .map((w) => w.trim())
              .filter(Boolean)
            onChange(list.length ? list : null, list.length === 0)
          }}
        />
      )}
    </Field>
  )
}

function JsonField({
  label,
  hint,
  error,
  value,
  onChange,
}: {
  label: string
  hint?: string
  error?: string
  value: unknown
  onChange: (v: unknown) => void
}) {
  const [text, setText] = useState(JSON.stringify(value ?? null))
  const [bad, setBad] = useState(false)
  return (
    <Field
      label={label}
      hint={hint ?? 'JSON'}
      error={error ?? (bad ? texts.ui.invalidJson : undefined)}
    >
      {(props) => (
        <Textarea
          {...props}
          rows={3}
          className="font-mono"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            try {
              onChange(JSON.parse(text))
              setBad(false)
            } catch {
              setBad(true)
            }
          }}
        />
      )}
    </Field>
  )
}

function Property({
  name,
  schema,
  root,
  value,
  present,
  required,
  onChange,
  errors,
  path,
  values,
  patch,
  level,
}: {
  name: string
  schema: Schema
  root: Schema
  value: any
  present: boolean
  required: boolean
  onChange: (v: any, remove?: boolean) => void
  errors: Record<string, string>
  path: string
  values: Values
  patch: (changes: Values) => void
  level: Level
}) {
  const { inner: s, nullable } = unwrapNullable(schema, root)
  const label = s.title ?? name
  const hint = s.description as string | undefined
  const error = errors[path]
  const unset = !present || value === null || value === undefined
  const unit = schema['x-unit'] as string | undefined
  const Widget = typeof schema['x-widget'] === 'string' ? widgets[schema['x-widget']] : undefined
  if (Widget)
    return (
      <Widget
        name={name}
        schema={schema}
        value={unset ? undefined : value}
        onChange={onChange}
        label={label}
        hint={hint}
        error={error}
        values={values}
        patch={patch}
        level={level}
      />
    )
  const optional = nullable || (!required && s.type !== 'boolean')

  // an optional value: a switch to use it, then the control
  // a switch only for the optional values that have no natural "empty" (a pair of numbers, a group);
  // an optional text, number or list is just left empty
  const grouped = (s.type === 'array' && Array.isArray(s.prefixItems)) || s.type === 'object'
  if (optional && grouped) {
    const on = !unset
    return (
      <fieldset className="flex flex-col gap-2 rounded-control border border-line p-3">
        <Switch
          checked={on}
          onCheckedChange={(checked) =>
            checked
              ? onChange(defaultOf({ ...s, default: s.default ?? undefined }, root))
              : onChange(null, !nullable)
          }
          label={label}
          hint={on ? undefined : hint ? texts.ui.notUsedHint(hint) : texts.ui.notUsed}
        />
        {on ? (
          <Control
            name={name}
            s={{ ...s, title: undefined }}
            root={root}
            value={value}
            onChange={onChange}
            errors={errors}
            path={path}
            label={label}
            hint={hint}
            error={error}
            unit={unit}
            level={level}
          />
        ) : null}
      </fieldset>
    )
  }
  return (
    <Control
      name={name}
      s={s}
      root={root}
      value={unset ? undefined : value}
      onChange={onChange}
      errors={errors}
      path={path}
      label={label}
      hint={hint}
      error={error}
      unit={unit}
      placeholderDefault={!required ? s.default : undefined}
      level={level}
    />
  )
}

function Control({
  name,
  s,
  root,
  value,
  onChange,
  errors,
  path,
  label,
  hint,
  error,
  unit,
  placeholderDefault,
  level,
}: {
  name: string
  s: Schema
  root: Schema
  level: Level
  value: any
  onChange: (v: any, remove?: boolean) => void
  errors: Record<string, string>
  path: string
  label: string
  hint?: string
  error?: string
  unit?: string
  placeholderDefault?: unknown
}) {
  const percent = unit === 'fraction'
  const placeholder =
    placeholderDefault !== undefined && placeholderDefault !== null
      ? texts.ui.defaultValue(
          typeof placeholderDefault === 'number'
            ? percent
              ? formatPercent(placeholderDefault)
              : formatNumber(placeholderDefault)
            : String(placeholderDefault),
        )
      : undefined

  if (s.type === 'string' && Array.isArray(s.enum)) {
    const labels: Record<string, string> = s['x-enum-labels'] ?? {}
    return (
      <Field label={label} hint={hint} error={error}>
        {(props) => (
          <Select
            {...props}
            value={value ?? s.default ?? undefined}
            onValueChange={(v) => onChange(v)}
            options={s.enum.map((v: string) => ({ value: v, label: labels[v] ?? v }))}
          />
        )}
      </Field>
    )
  }
  if (s.type === 'string') {
    return (
      <Field label={label} hint={hint} error={error}>
        {(props) => (
          <Input
            {...props}
            value={value ?? ''}
            placeholder={placeholder}
            onChange={(e) =>
              onChange(e.target.value === '' ? null : e.target.value, e.target.value === '')
            }
          />
        )}
      </Field>
    )
  }
  if (s.type === 'integer' || s.type === 'number') {
    const { min, max } = range(s)
    return (
      <Field label={label} hint={hint} error={error}>
        {(props) => (
          <NumberField
            {...props}
            value={typeof value === 'number' ? value : null}
            onChange={(v) =>
              onChange(v === null ? null : s.type === 'integer' ? Math.round(v) : v, v === null)
            }
            min={min}
            max={max}
            step={s.type === 'integer' ? 1 : 0.01}
            decimals={s.type === 'integer' ? 0 : 4}
            percent={percent}
            unit={unit === 'px' || unit === 'ΔE' ? unit : undefined}
            placeholder={placeholder}
          />
        )}
      </Field>
    )
  }
  if (s.type === 'boolean') {
    return (
      <Switch
        checked={value ?? s.default ?? false}
        onCheckedChange={(c) => onChange(c)}
        label={label}
        hint={hint}
      />
    )
  }
  if (
    s.type === 'array' &&
    Array.isArray(s.prefixItems) &&
    s.prefixItems.every((p: Schema) => p.type === 'integer' || p.type === 'number')
  ) {
    const items: Schema[] = s.prefixItems
    const current: (number | null)[] = Array.isArray(value) ? value : items.map(() => null)
    return (
      <fieldset className="flex flex-col gap-1">
        <legend className="text-sm font-medium">{label}</legend>
        <div className="flex flex-wrap gap-2">
          {items.map((item, i) => {
            const { min, max } = range(item)
            return (
              <NumberField
                key={i}
                aria-label={`${label}, ${i + 1}º valor`}
                className="w-24"
                value={current[i] ?? null}
                onChange={(v) => {
                  const next = [...current]
                  next[i] = v === null ? null : item.type === 'integer' ? Math.round(v) : v
                  onChange(next)
                }}
                min={min}
                max={max}
                step={item.type === 'integer' ? 1 : 0.01}
                decimals={item.type === 'integer' ? 0 : 4}
              />
            )
          })}
        </div>
        {hint ? <p className="text-xs text-fg-muted">{hint}</p> : null}
        {error ? (
          <p role="alert" className="text-xs text-fail-text">
            {error}
          </p>
        ) : null}
      </fieldset>
    )
  }
  if (s.type === 'array' && resolve(s.items ?? {}, root).type === 'string') {
    return <WordList label={label} hint={hint} error={error} value={value} onChange={onChange} />
  }
  if (s.type === 'object' && s.properties) {
    return (
      <fieldset className="flex flex-col gap-3">
        {label ? <legend className="text-sm font-medium">{label}</legend> : null}
        <SchemaForm
          schema={s}
          root={root}
          value={value ?? {}}
          onChange={(v) => onChange(v)}
          errors={errors}
          path={path}
          level={level}
          nested
        />
      </fieldset>
    )
  }
  return (
    <JsonField label={label ?? name} hint={hint} error={error} value={value} onChange={onChange} />
  )
}

/** A parameter's settings level; one without a tag is Especialista (docs/frontend.md §17). */
export function levelOf(prop: Schema): Level {
  const level = prop['x-level']
  return level === 1 || level === 2 || level === 3 ? level : 3
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** Of these parameters, the ones that differ from their defaults: a value present without a default counts as changed. */
function changedAmong(schema: Schema, value: Values, names: string[]): string[] {
  const properties = (schema.properties ?? {}) as Record<string, Schema>
  return names.filter((name) => {
    if (!(name in value) || value[name] === undefined) return false
    const { inner } = unwrapNullable(properties[name]!, schema)
    return !same(value[name], inner.default ?? null)
  })
}

/** The parameters a level hides that differ from their defaults. */
export function hiddenChanged(schema: Schema, value: Values, level: Level): string[] {
  const properties = (schema.properties ?? {}) as Record<string, Schema>
  const owned = ownedBy(properties) // a control that draws them shows them at every level
  return changedAmong(
    schema,
    value,
    Object.keys(properties).filter(
      (name) => levelOf(properties[name]!) > level && !owned.includes(name),
    ),
  )
}

/**
 * The form for one object schema. `errors` are keyed by dotted path from the server (e.g. "params.min_fraction").
 *
 * At the top it is drawn in sections (docs/frontend.md §19.2): what to measure, the criteria, then the Avançado and
 * Especialista parameters in collapsed sections, each only once `level` reaches it. What a level hides is never
 * invisible: a badge counts the hidden parameters that were changed and shows just those. A nested object (a color
 * range inside a locator) is drawn whole, whatever the level.
 */
export function SchemaForm({
  schema,
  root,
  value,
  onChange,
  errors = {},
  path = '',
  level = 3,
  nested = false,
  hide = [],
  criteriaExtra,
}: {
  schema: Schema
  root?: Schema
  value: Values
  onChange: (next: Values) => void
  errors?: Record<string, string>
  path?: string
  /** The settings level to show (1 Essencial, 2 Avançado, 3 Especialista); every parameter by default. */
  level?: Level
  nested?: boolean
  /** Parameters drawn elsewhere (the limits that a gauge holds). A changed one hidden by the level is still counted. */
  hide?: readonly string[]
  /** What goes at the top of the *Critérios* section: the tolerance gauges. */
  criteriaExtra?: ReactNode
}) {
  const base = root ?? schema
  const properties: Record<string, Schema> = schema.properties ?? {}
  const required: string[] = schema.required ?? []
  const [revealed, setRevealed] = useState(false)

  const field = (name: string) => (
    <Property
      key={name}
      name={name}
      schema={properties[name]!}
      root={base}
      value={value[name]}
      present={name in value}
      required={required.includes(name)}
      errors={errors}
      path={path ? `${path}.${name}` : name}
      values={value}
      level={level}
      patch={(changes) => {
        const next = { ...value }
        for (const [key, v] of Object.entries(changes))
          if (v === undefined) delete next[key]
          else next[key] = v
        onChange(next)
      }}
      onChange={(v, remove) => {
        const next = { ...value }
        if (remove || v === undefined) delete next[name]
        else next[name] = v
        onChange(next)
      }}
    />
  )
  const owned = ownedBy(properties)
  if (nested)
    return (
      <div className="flex flex-col gap-3">
        {Object.keys(properties)
          .filter((n) => !owned.includes(n))
          .map(field)}
      </div>
    )

  const names = Object.keys(properties).filter((n) => !hide.includes(n) && !owned.includes(n))
  const at = (wanted: Level, group?: string) =>
    names.filter(
      (n) =>
        levelOf(properties[n]!) === wanted &&
        (group === undefined ||
          (properties[n]!['x-group'] === 'criteria') === (group === 'criteria')),
    )
  const sections: { title: string; names: string[] }[] = [
    { title: texts.ui.groupMeasure, names: at(1, 'measure') },
    { title: texts.ui.groupCriteria, names: at(1, 'criteria') },
  ].filter(
    (section) =>
      section.names.length > 0 || (!!criteriaExtra && section.title === texts.ui.groupCriteria),
  )
  const deeper = ([2, 3] as const).filter((l) => l <= level && at(l).length > 0)
  const changed = hiddenChanged(schema, value, level)
  // a closed section says how many of its settings were changed
  const changedHint = (l: 2 | 3) => {
    const n = changedAmong(schema, value, at(l)).length
    return n > 0 ? <Badge tone="warn">{texts.ui.sectionChanged(n)}</Badge> : undefined
  }

  return (
    <div className="flex flex-col gap-3">
      {sections.map((section) => (
        <section key={section.title} className="flex flex-col gap-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-fg-muted">
            {section.title}
          </h4>
          {section.title === texts.ui.groupCriteria ? criteriaExtra : null}
          {section.names.map(field)}
        </section>
      ))}
      {deeper.length > 0 ? (
        <Accordion type="multiple">
          {deeper.map((l) => (
            <AccordionItem key={l} value={String(l)}>
              <AccordionTrigger hint={changedHint(l)}>{texts.ui.levels[l]}</AccordionTrigger>
              <AccordionContent>{at(l).map(field)}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      ) : null}
      {changed.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-control border border-warn-text/40 p-3">
          <button
            type="button"
            aria-expanded={revealed}
            title={texts.ui.hiddenChangedHint}
            onClick={() => setRevealed((r) => !r)}
            className="flex min-h-control items-center gap-2 text-left text-sm"
          >
            <Badge tone="warn">{texts.ui.hiddenChanged(changed.length)}</Badge>
            {revealed ? <span className="text-fg-muted">{texts.ui.hiddenChangedHide}</span> : null}
          </button>
          {revealed ? changed.map(field) : null}
        </div>
      ) : null}
    </div>
  )
}
