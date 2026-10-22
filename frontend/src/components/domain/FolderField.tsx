import { FolderOpen } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { systemChecks, useSystem } from '@/api/queries/admin'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { text } from '@/texts'

/**
 * A folder of the station PC: the path in a text field, and *Escolher pasta…* beside it, which opens the PC's own
 * folder chooser (the browser cannot give a path, so the program asks Windows, VIA-0122). The button is there only
 * where the PC can open one; elsewhere the path is typed. Every folder on the screens uses this one component.
 */
export function FolderField({
  label,
  hint,
  value,
  onChange,
  error,
}: {
  label: string
  hint?: string
  value: string
  onChange: (path: string) => void
  error?: string
}) {
  const system = useSystem()
  const [choosing, setChoosing] = useState(false)

  const choose = async () => {
    setChoosing(true)
    try {
      const out = await systemChecks.pickFolder(value || null)
      if (out.path) onChange(out.path)
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setChoosing(false)
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <Field label={label} hint={hint} error={error}>
        {(p) => (
          <div className="flex flex-wrap items-center gap-2">
            <Input {...p} value={value} onChange={(e) => onChange(e.target.value)} />
            {system.data?.can_pick_folder ? (
              <Button loading={choosing} onClick={() => void choose()}>
                <FolderOpen aria-hidden className="size-4" />
                {text.settings.chooseFolder}
              </Button>
            ) : null}
          </div>
        )}
      </Field>
      {choosing ? (
        <p role="status" className="text-xs text-fg-muted">
          {text.settings.chooseFolderOpen}
        </p>
      ) : null}
    </div>
  )
}
