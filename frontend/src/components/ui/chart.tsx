import type { CSSProperties, ReactElement } from 'react'
import { ResponsiveContainer, Tooltip, type TooltipContentProps } from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'
import { cn } from '@/lib/cn'
import { Table, TBody, TD, TH, THead, TR } from './table'

// Low-frequency charts (Recharts 3, TD-29): result trends, the Pareto of reason codes, margin
// trends (document 05 §7.13). Series take a token colour; axes and grid use the line and muted
// tokens, never Recharts' own greys.

/** One entry per series: its name and a token colour, e.g. `{ fail: { label: 'Reprovadas', color: 'var(--fail)' } }`. */
export type ChartConfig = Record<string, { label: string; color: string }>

/** Props for XAxis/YAxis so they draw in the theme. */
export const chartAxis = {
  stroke: 'var(--border-strong)',
  tick: { fill: 'var(--fg-muted)', fontSize: 12 },
  tickLine: false,
} as const

/** Props for CartesianGrid. */
export const chartGrid = {
  stroke: 'var(--border)',
  strokeDasharray: '3 3',
  vertical: false,
} as const

/**
 * A chart with a name and a summary in words (read instead of the drawing). Each series colour is
 * set as `--series-<key>` (not `--color-*`, which are Tailwind's), so a bar takes `fill="var(--series-fail)"`.
 */
export function ChartContainer({
  config,
  title,
  summary,
  table,
  className,
  children,
}: {
  config: ChartConfig
  title: string
  /** What the chart shows, in a sentence: the text alternative. */
  summary: string
  /** The same data as a table, under "Ver como tabela" (design system: a chart always has one). */
  table: { columns: string[]; rows: (string | number)[][] }
  className?: string
  children: ReactElement
}) {
  const vars = Object.fromEntries(
    Object.entries(config).map(([key, { color }]) => [`--series-${key}`, color]),
  ) as CSSProperties
  return (
    <figure className={cn('flex flex-col gap-2', className)} style={vars}>
      <figcaption className="flex flex-col">
        <span className="text-sm font-medium">{title}</span>
        <span className="text-xs text-fg-muted">{summary}</span>
      </figcaption>
      <div aria-hidden className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-fg-muted hover:text-fg">Ver como tabela</summary>
        <Table className="mt-2">
          <THead>
            <TR>
              {table.columns.map((c) => (
                <TH key={c}>{c}</TH>
              ))}
            </TR>
          </THead>
          <TBody>
            {table.rows.map((row, i) => (
              <TR key={i}>
                {row.map((cell, j) => (
                  <TD key={j} numeric={typeof cell === 'number'}>
                    {typeof cell === 'number' ? cell.toLocaleString('pt-BR') : cell}
                  </TD>
                ))}
              </TR>
            ))}
          </TBody>
        </Table>
      </details>
    </figure>
  )
}

/** The tooltip, drawn with the tokens. Use as `<ChartTooltip config={config} />` inside a chart. */
export function ChartTooltip({ config }: { config: ChartConfig }) {
  return (
    <Tooltip
      cursor={{ fill: 'var(--bg-3)' }}
      content={(props: TooltipContentProps<ValueType, NameType>) => (
        <TooltipBody {...props} config={config} />
      )}
    />
  )
}

function TooltipBody({
  active,
  payload,
  label,
  config,
}: TooltipContentProps<ValueType, NameType> & { config: ChartConfig }) {
  if (!active || !payload?.length) return null
  return (
    <div className="flex flex-col gap-1 rounded-control border border-line bg-surface-1 px-3 py-2 text-xs shadow-overlay">
      <p className="font-medium">{label}</p>
      {payload.map((p) => {
        const key = String(p.dataKey)
        return (
          <p key={key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2 rounded-pill"
              style={{ background: config[key]?.color }}
            />
            <span className="text-fg-muted">{config[key]?.label ?? key}</span>
            <span className="ml-auto font-mono tabular-nums">
              {typeof p.value === 'number' ? p.value.toLocaleString('pt-BR') : p.value}
            </span>
          </p>
        )
      })}
    </div>
  )
}
