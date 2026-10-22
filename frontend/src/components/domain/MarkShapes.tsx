import type { components } from '@/api/schema'

/** A shape a tool measured, as fractions of the frame (docs/frontend.md §18, VIA-0124). */
export type MarkOut = components['schemas']['MarkOut']

/** The marks of one tool and its verdict: `found` marks take the colour of the verdict, `defect` is always a fail. */
export interface ToolMarks {
  id: string
  passed: boolean
  /** False: an informative tool, which never decides, so its failure is a warning and not the part's failure (FR-INS-13). */
  informative?: boolean
  marks: readonly MarkOut[]
}

/** The marks of a result that belong to the shapes (not the text): rect, poly and point. */
const isShape = (m: MarkOut) => m.kind !== 'text'

/**
 * rect, poly and point of a result, in an SVG of `width` × `height` units (the picture's pixels). The colour is never the
 * only signal: a defect is thicker, what was expected is dashed. Each shape has a dark edge so it shows on any picture.
 */
export function MarkShapes({
  tools,
  width,
  height,
}: {
  tools: readonly ToolMarks[]
  width: number
  height: number
}) {
  const arm = Math.max(width, height) * 0.006 // half the size of a point's cross
  const line = { vectorEffect: 'non-scaling-stroke' as const, fill: 'none' }
  return (
    <>
      {tools.flatMap((tool) =>
        tool.marks.filter(isShape).map((m, i) => {
          const pts = m.points.map(([x = 0, y = 0]) => [x * width, y * height] as const)
          const fail = m.role === 'defect' || (m.role === 'found' && !tool.passed)
          const stroke =
            m.role === 'expected'
              ? 'stroke-fg-muted'
              : fail
                ? tool.informative
                  ? 'stroke-warn'
                  : 'stroke-fail'
                : 'stroke-ok'
          const dash = m.role === 'expected' ? '6 4' : undefined
          const w = m.role === 'defect' ? 4 : 2.5
          let d: string
          if (m.kind === 'point') {
            const [x = 0, y = 0] = pts[0] ?? []
            d = `M${x - arm} ${y}H${x + arm}M${x} ${y - arm}V${y + arm}`
          } else if (m.kind === 'rect') {
            const [[ax = 0, ay = 0] = [], [bx = 0, by = 0] = []] = pts
            d = `M${ax} ${ay}H${bx}V${by}H${ax}Z`
          } else {
            d = pts.map(([x, y], j) => `${j ? 'L' : 'M'}${x} ${y}`).join('') + (m.closed ? 'Z' : '')
          }
          return (
            <g key={`${tool.id}:${i}`} data-mark={m.kind} data-role={m.role}>
              <path d={d} className="stroke-surface-0" strokeWidth={w + 3} {...line} />
              <path d={d} className={stroke} strokeWidth={w} strokeDasharray={dash} {...line} />
            </g>
          )
        }),
      )}
    </>
  )
}

/** The text marks, to write over the picture (the canvas of the editor and the operator's each place them their own way). */
export function textMarks(tools: readonly ToolMarks[]) {
  return tools.flatMap((tool) =>
    tool.marks.flatMap((m, i) =>
      m.kind === 'text' && m.points[0]
        ? [
            {
              key: `${tool.id}:${i}`,
              x: m.points[0][0] ?? 0,
              y: m.points[0][1] ?? 0,
              text: m.text,
              fail: m.role === 'defect' || (m.role === 'found' && !tool.passed),
              informative: !!tool.informative,
            },
          ]
        : [],
    ),
  )
}

/** What the tools of a result gave, for a canvas to draw: only the tools that drew something. */
export function toolMarks(
  tools:
    | readonly { id: string; passed: boolean; informative?: boolean; marks?: readonly MarkOut[] }[]
    | undefined,
): ToolMarks[] {
  return (tools ?? []).flatMap((t) => (t.marks?.length ? [{ id: t.id, passed: t.passed, informative: t.informative, marks: t.marks }] : []))
}
