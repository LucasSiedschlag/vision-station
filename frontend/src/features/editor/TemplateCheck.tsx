import { useEffect, useEffectEvent, useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { editorApi } from '@/api/queries/editor'
import { text } from '@/texts'
import type { Rect } from './geometry'
import { cropPng, type EditorImage } from './image'

const t = text.editor.template

export interface ModelCheck {
  usable: boolean
  flat: boolean
  points: number | null
}

interface Props {
  image: EditorImage | null
  crop: Rect | null
  shape: boolean
  onResult: (result: ModelCheck | null) => void
}

interface Preview {
  image: EditorImage
  crop: Rect
  shape: boolean
  png: string
  answer: Awaited<ReturnType<typeof editorApi.inspectModel>>
}

/** A template at 1:1 and the model it would give (VIA-0076, docs/frontend.md §19.5). */
export function TemplateCheck({ image, crop, shape, onResult }: Props) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const report = useEffectEvent(onResult)

  useEffect(() => {
    report(null)
    if (!image || !crop) return
    let cancelled = false
    const timer = setTimeout(() => {
      const inspect = async () => {
        try {
          const png = await cropPng(image, crop)
          if (cancelled) return
          const answer = await editorApi.inspectModel(png)
          if (cancelled) return
          if (!answer.ok) {
            setPreview(null)
            report(null)
            toast.error(answer.message ?? text.ui.noServer)
            return
          }
          setPreview({ image, crop, shape, png, answer })
          report({
            usable: answer.ok && !answer.flat && (!shape || answer.points !== null),
            flat: answer.flat,
            points: answer.points,
          })
        } catch (error) {
          if (cancelled) return
          setPreview(null)
          report(null)
          toast.error(describeError(error))
        }
      }
      void inspect()
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [image, crop, shape])

  // An earlier crop's preview must disappear before the next request starts.
  if (!preview || preview.image !== image || preview.crop !== crop || preview.shape !== shape)
    return null
  const { png, answer } = preview
  const usable = answer.ok && !answer.flat && (!shape || answer.points !== null)

  return (
    <div className="flex flex-col gap-2 rounded-control border border-line p-3">
      <div
        // A scrolling region must be reached by keyboard (WCAG 2.1.1, axe scrollable-region-focusable).
        // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
        role="group"
        aria-label={t.preview}
        className="max-h-48 overflow-auto"
      >
        <img
          src={`data:image/png;base64,${png}`}
          alt={t.preview}
          className="max-w-none"
          style={{ imageRendering: 'pixelated' }}
        />
      </div>
      <p className="text-sm">{`${answer.width} × ${answer.height} px`}</p>
      {shape && answer.points !== null ? (
        <p className="text-sm">{t.points(answer.points)}</p>
      ) : null}
      {!usable ? (
        <p role="alert" className="text-sm text-fail-text">
          {answer.reason ?? t.flat}
        </p>
      ) : null}
    </div>
  )
}
