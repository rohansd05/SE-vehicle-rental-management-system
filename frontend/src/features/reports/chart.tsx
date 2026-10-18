// A bar chart in the chart tokens (ui-brief.md 3.4; B9, B10). Every chart has a table of
// the same figures beside it, so nothing is told by colour or by the chart alone.

import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from 'recharts'

export interface BarSeries {
  key: string
  label: string
  /** A chart token (ui-brief.md 3.4). */
  color: string
}

const TICK = { fill: 'var(--ink-muted)', fontSize: 15 }

/**
 * Horizontal bars, one row per branch, category, job type or customer; several series
 * stack (each with a 2 px surface gap) and get a legend. `format` writes the exact
 * value for the tooltip, `axis` a short one for the scale.
 */
export function BarFigure({
  title,
  rows,
  series,
  format,
  axis = format,
}: {
  title: string
  rows: { name: string; [key: string]: string | number | null }[]
  series: BarSeries[]
  format: (value: number) => string
  axis?: (value: number) => string
}) {
  const data = rows.map((row) => ({
    name: row.name,
    ...Object.fromEntries(series.map((bar) => [bar.key, Number(row[bar.key] ?? 0)])),
  }))
  return (
    <figure className="grid min-w-0 gap-3">
      <figcaption className="heading text-subsection">{title}</figcaption>
      {data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing to chart for this period.</p>
      ) : (
        <BarChart
          responsive
          layout="vertical"
          data={data}
          style={{ width: '100%', height: Math.max(160, data.length * 48 + (series.length > 1 ? 80 : 48)) }}
          margin={{ top: 4, right: 24, bottom: 4, left: 4 }}
        >
          <CartesianGrid horizontal={false} stroke="var(--hairline)" />
          <XAxis type="number" tickFormatter={axis} tick={TICK} stroke="var(--hairline)" />
          <YAxis type="category" dataKey="name" width={150} tick={TICK} stroke="var(--hairline)" />
          <Tooltip
            formatter={(value) => format(Number(value))}
            cursor={{ fill: 'var(--canvas-sunken)' }}
            contentStyle={{
              background: 'var(--surface)',
              border: '1px solid var(--hairline)',
              borderRadius: 6,
              color: 'var(--ink)',
            }}
          />
          {series.length > 1 ? <Legend wrapperStyle={{ color: 'var(--ink)' }} /> : null}
          {series.map((bar, index) => (
            <Bar
              key={bar.key}
              dataKey={bar.key}
              name={bar.label}
              fill={bar.color}
              stroke="var(--surface)"
              strokeWidth={2}
              stackId={series.length > 1 ? 'stack' : undefined}
              radius={index === series.length - 1 ? [0, 4, 4, 0] : 0}
              maxBarSize={28}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      )}
    </figure>
  )
}
