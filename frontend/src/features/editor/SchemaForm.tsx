import { useState } from 'react'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { formatNumber } from '@/lib/number'
import { text as texts } from '@/texts'

/**
 * A form drawn from a tool's or locator's JSON Schema (docs/frontend.md §7.3), so a new tool type needs no
 * screen code (FR-PLT-2). It covers what our Pydantic models produce; anything else becomes a JSON text field,
 * never silently dropped. Titles, descriptions and the labels of choices come from the schema (in Portuguese).
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
}) {
  const { inner: s, nullable } = unwrapNullable(schema, root)
  const label = s.title ?? name
  const hint = s.description as string | undefined
  const error = errors[path]
  const unset = !present || value === null || value === undefined
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
      placeholderDefault={!required ? s.default : undefined}
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
  placeholderDefault,
}: {
  name: string
  s: Schema
  root: Schema
  value: any
  onChange: (v: any, remove?: boolean) => void
  errors: Record<string, string>
  path: string
  label: string
  hint?: string
  error?: string
  placeholderDefault?: unknown
}) {
  const placeholder =
    placeholderDefault !== undefined && placeholderDefault !== null
      ? texts.ui.defaultValue(
          typeof placeholderDefault === 'number'
            ? formatNumber(placeholderDefault)
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
        />
      </fieldset>
    )
  }
  return (
    <JsonField label={label ?? name} hint={hint} error={error} value={value} onChange={onChange} />
  )
}

/** The form for one object schema. `errors` are keyed by dotted path from the server (e.g. "params.min_fraction"). */
export function SchemaForm({
  schema,
  root,
  value,
  onChange,
  errors = {},
  path = '',
}: {
  schema: Schema
  root?: Schema
  value: Values
  onChange: (next: Values) => void
  errors?: Record<string, string>
  path?: string
}) {
  const base = root ?? schema
  const properties: Record<string, Schema> = schema.properties ?? {}
  const required: string[] = schema.required ?? []
  return (
    <div className="flex flex-col gap-3">
      {Object.entries(properties).map(([name, prop]) => (
        <Property
          key={name}
          name={name}
          schema={prop}
          root={base}
          value={value[name]}
          present={name in value}
          required={required.includes(name)}
          errors={errors}
          path={path ? `${path}.${name}` : name}
          onChange={(v, remove) => {
            const next = { ...value }
            if (remove || v === undefined) delete next[name]
            else next[name] = v
            onChange(next)
          }}
        />
      ))}
    </div>
  )
}
