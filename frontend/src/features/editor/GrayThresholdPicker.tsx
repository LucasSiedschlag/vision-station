import { useMemo } from 'react'
import { GrayThreshold } from '@/components/vision/GrayThreshold'
import { grayHistogram, objectShare, otsu } from '@/components/vision/gray-model'
import { Button } from '@/components/ui/button'
import { NumberField } from '@/components/ui/number-field'
import { formatNumber } from '@/lib/number'
import { text } from '@/texts'
import { useImageAids } from './image-aids'
import type { WidgetProps } from './widgets'

const t = text.editor.threshold

/**
 * The gray level that separates the object from the background, drawn on the histogram of the tool's region
 * (docs/frontend.md §19.5). `threshold` empty means automatic (Otsu): the dashed line then shows the level Otsu finds
 * on the histogram on show. That histogram is of the tool's region when it is drawn on the frame; for a region
 * relative to a fixture, and for a locator's search area, it is of the whole image, so the server's own level on the
 * real area can differ (the text says "da imagem" then). For an object of a colour there is no gray threshold, and
 * the control is left out.
 */
export function GrayThresholdPicker({ value, onChange, label, hint, error, values }: WidgetProps) {
  const aids = useImageAids()
  const mode = values.mode
  const pixels = aids?.pixels
  const region = aids?.region
  const counts = useMemo(
    () => (pixels ? grayHistogram(pixels, region ?? [0, 0, 1, 1]) : null),
    [pixels, region],
  )
  if (mode !== 'dark' && mode !== 'light') return null

  const chosen = typeof value === 'number' ? value : null
  const auto = counts ? otsu(counts) : null
  const level = chosen ?? auto ?? 0
  const share = counts ? objectShare(counts, level, mode) : null

  return (
    <fieldset className="flex flex-col gap-2 rounded-control border border-line p-3">
      <legend className="px-1 text-sm font-medium">{label}</legend>
      {counts ? (
        <GrayThreshold
          counts={counts}
          mode={mode}
          level={level}
          auto={chosen === null}
          label={label}
          autoLabel={chosen === null ? t.auto(String(level)) : undefined}
          onChange={(next) => onChange(next)}
        />
      ) : (
        <p className="text-sm text-fg-muted">{t.noImage}</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <NumberField
          aria-label={label}
          value={chosen}
          min={0}
          max={255}
          step={1}
          placeholder={auto === null ? undefined : String(auto)}
          onChange={(next) => (next === null ? onChange(undefined, true) : onChange(next))}
        />
        <Button
          variant={chosen === null ? 'primary' : 'secondary'}
          aria-pressed={chosen === null}
          disabled={auto === null && chosen === null}
          onClick={() => (chosen === null ? onChange(auto ?? 0) : onChange(undefined, true))}
        >
          {t.automatic}
        </Button>
        {share !== null ? (
          <span className="text-xs tabular-nums text-fg-muted">
            {(region ? t.objectShare : t.objectShareImage)(formatNumber(share * 100, 1))}
          </span>
        ) : null}
      </div>
      <p className="text-xs text-fg-muted">{mode === 'dark' ? t.dark : t.light}</p>
      {hint ? <p className="text-xs text-fg-muted">{hint}</p> : null}
      {error ? (
        <p role="alert" className="text-xs text-fail-text">
          {error}
        </p>
      ) : null}
    </fieldset>
  )
}
