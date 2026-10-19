import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { editorApi, type BatchOut, type LimitProposal, type TypeInfo } from '@/api/queries/editor'
import { ToolToleranceGauge, type GaugeLimit } from '@/components/vision/ToolToleranceGauge'
import type { Dot, Side } from '@/components/vision/gauge-model'
import type { Level } from '@/app/levels'
import { text } from '@/texts'
import { toRequest, useDraft, type Draft, type JobJson } from './draft'
import type { Schema } from './SchemaForm'

const g = text.editor.gauge

/** The numbers of a parameter's schema a gauge needs: its default, whether it may be empty, what it accepts. */
function paramInfo(schema: Schema | undefined): {
  default: number | null
  optional: boolean
  bounds: readonly [number | null, number | null]
} {
  const options: Schema[] = schema ? [schema, ...(schema.anyOf ?? [])] : []
  const number = options.find((o) => o.type === 'number' || o.type === 'integer')
  const integer = number?.type === 'integer'
  const low =
    number?.minimum ??
    (number?.exclusiveMinimum === undefined ? null : number.exclusiveMinimum + (integer ? 1 : 1e-6))
  const high =
    number?.maximum ??
    (number?.exclusiveMaximum === undefined ? null : number.exclusiveMaximum - (integer ? 1 : 1e-6))
  return {
    default: typeof schema?.default === 'number' ? schema.default : null,
    optional: (schema?.anyOf ?? []).some((o: Schema) => o.type === 'null'),
    bounds: [low, high],
  }
}

const sampleName = (path: string) => path.replace('tests/images/', '')

/** What one sample measured for a criterion of a tool, as the dots of the gauge. */
export function dotsOf(batch: BatchOut | null, toolId: string, measure: string): Dot[] {
  return (batch?.samples ?? []).flatMap((s): Dot[] => {
    if (s.kind === 'error') return []
    const found = s.result?.tools.find((t) => t.id === toolId)
    return [
      {
        id: s.image,
        kind: s.kind,
        name: s.kind === 'reference' ? g.reference : sampleName(s.image),
        value: found?.values?.[measure] ?? null,
      },
    ]
  })
}

/**
 * The gauges of one tool: one per criterion its type lists and the level shows (docs/frontend.md §19.2, §19.3). They
 * hold the limits of the criterion, so the form leaves those parameters to them. The dots come from the batch test
 * of the draft; the needle from the last measurement of the tool (a test, or the live session).
 */
export function ToolGauges({
  draft,
  index,
  type,
  batch,
  stale,
  measured,
  selectedSample,
  onShowSample,
  level,
}: {
  draft: Draft
  index: number
  type: TypeInfo
  batch: BatchOut | null
  stale: boolean
  /** the tool's last measurement: its values by name, and whether it passed; null: none */
  measured: { values: Record<string, number>; passed: boolean } | null
  selectedSample: string | null
  onShowSample: (path: string) => void
  level: Level
}) {
  const tool: JobJson = draft.job.tools[index]
  const properties = (type.params_schema.properties ?? {}) as Record<string, Schema>
  // a proposal per criterion, kept until it is applied or discarded
  const [proposals, setProposals] = useState<Record<string, LimitProposal[]>>({})
  const [asking, setAsking] = useState<string | null>(null)

  const setParam = (param: string, value: number | null) =>
    useDraft.getState().edit((d) => {
      const params = (d.job.tools[index].params ??= {})
      if (value === null) delete params[param]
      else params[param] = value
    })

  const specs = type.criteria.filter((c) => c.level <= level)
  if (specs.length === 0) return null

  const propose = async (criterion: string) => {
    setAsking(criterion)
    try {
      const out = await editorApi.suggestLimits(toRequest(draft), tool.id)
      if (!out.ok) {
        toast.error(out.message ?? '')
        return
      }
      setProposals((all) => ({
        ...all,
        [criterion]: out.proposals.filter((p) => p.criterion === criterion),
      }))
    } catch (e) {
      toast.error(describeError(e))
    } finally {
      setAsking(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {specs.map((spec) => {
        const info = {
          min: spec.limits.min ? paramInfo(properties[spec.limits.min]) : null,
          max: spec.limits.max ? paramInfo(properties[spec.limits.max]) : null,
        }
        const value = (side: Side) => {
          const param = spec.limits[side]
          if (!param) return null
          const set = tool.params?.[param]
          return typeof set === 'number' ? set : (info[side]?.default ?? null)
        }
        const limitInfo: Partial<Record<Side, GaugeLimit>> = {}
        for (const side of ['min', 'max'] as const)
          if (info[side])
            limitInfo[side] = { optional: info[side].optional, bounds: info[side].bounds }
        const dots = dotsOf(batch, tool.id, spec.value)
        const goodN = dots.filter((d) => d.kind === 'good' && d.value !== null).length
        const badN = dots.filter((d) => d.kind === 'bad' && d.value !== null).length
        const mine = proposals[spec.value] ?? []
        return (
          <ToolToleranceGauge
            key={spec.value}
            label={spec.label}
            unit={spec.unit}
            range={spec.range}
            limits={{ min: value('min'), max: value('max') }}
            limitInfo={limitInfo}
            current={measured?.values[spec.value] ?? null}
            currentPassed={measured && spec.value in measured.values ? measured.passed : undefined}
            dots={dots}
            selected={selectedSample}
            proposals={mine}
            canPropose={{
              ok: goodN >= 3,
              reason: goodN === 0 && badN === 0 ? g.onlyReference : g.fewGood(3),
            }}
            proposing={asking === spec.value}
            stale={stale}
            onSelect={onShowSample}
            onLimit={(side, v) => {
              const param = spec.limits[side]
              if (param) setParam(param, v)
            }}
            onPropose={() => void propose(spec.value)}
            onApply={(p) => {
              const param = spec.limits[p.side]
              if (param && p.proposed !== null) setParam(param, p.proposed)
              setProposals((all) => ({ ...all, [spec.value]: [] }))
            }}
            onDiscard={() => setProposals((all) => ({ ...all, [spec.value]: [] }))}
          />
        )
      })}
    </div>
  )
}
