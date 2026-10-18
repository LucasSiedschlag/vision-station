import { Badge } from '@/components/ui/badge'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { text } from '@/texts'
import { LEVELS, useLevel, type Family } from '../levels'

/** Essencial / Avançado / Especialista for a family of screens (docs/frontend.md §17, FR-UI-10). */
export function LevelSwitch({ family, hidden = 0 }: { family: Family; hidden?: number }) {
  const [level, setLevel] = useLevel(family)
  return (
    <span className="inline-flex items-center gap-2">
      {hidden > 0 ? <Badge tone="warn">{text.ui.hiddenChanged(hidden)}</Badge> : null}
      <SegmentedControl
        label={text.ui.levelLabel}
        value={String(level)}
        onValueChange={(v) => setLevel(Number(v) as 1 | 2 | 3)}
        options={LEVELS.map((l) => ({ value: String(l), label: text.ui.levels[l] }))}
      />
    </span>
  )
}
