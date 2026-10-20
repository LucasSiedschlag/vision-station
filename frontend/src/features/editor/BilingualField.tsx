import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { text } from '@/texts'
import { writtenIn, withText } from './draft'

const b = text.editor.bilingual

/**
 * A text of the job in both languages, side by side (FR-JOB-15, docs/frontend.md §11.1): what is written for the operator
 * of one language is not a translation of the other word by word. An empty one falls back to the other language, and the
 * field says so.
 */
export function BilingualField({
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
  onChange: (next: { 'pt-BR': string; en: string }) => void
}) {
  const pt = writtenIn(value, 'pt-BR')
  const en = writtenIn(value, 'en')
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-medium">{label}</legend>
      {hint ? <p className="text-xs text-fg-muted">{hint}</p> : null}
      <div className="grid grid-cols-2 gap-2">
        <Field label={b.pt} error={error}>
          {(props) => (
            <Input
              {...props}
              value={pt}
              onChange={(e) => onChange(withText(value, 'pt-BR', e.target.value))}
            />
          )}
        </Field>
        <Field label={b.en}>
          {(props) => (
            <Input
              {...props}
              value={en}
              onChange={(e) => onChange(withText(value, 'en', e.target.value))}
            />
          )}
        </Field>
      </div>
      {pt.trim() && !en.trim() ? <p className="text-xs text-warn-text">{b.missing(b.en)}</p> : null}
      {en.trim() && !pt.trim() ? <p className="text-xs text-warn-text">{b.missing(b.pt)}</p> : null}
    </fieldset>
  )
}
