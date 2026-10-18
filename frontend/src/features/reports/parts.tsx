// The building blocks of every report: headline figures and a ruled table (ui-brief.md 7,
// "Table"). The charts are in chart.tsx, so Recharts loads only with the Reports page.

import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

import { display, type Section } from './csv'

const NUMERIC = new Set(['money', 'number', 'percent'])

/** Headline figures of a report (UI-4: each money figure is itemised in the tables below). */
export function Figures({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="grid gap-x-8 gap-y-5 border-y py-5 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="grid min-w-0 content-start gap-1">
          <dt className="text-sm text-muted-foreground">{item.label}</dt>
          <dd className="num-lg whitespace-nowrap">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function ReportTable<Row>({ section, currency }: { section: Section<Row>; currency: string }) {
  const { title, columns, rows } = section
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="heading pb-3 text-left text-subsection">{title}</caption>
        <thead>
          <tr className="border-b text-left text-label text-muted-foreground">
            {columns.map((column) => (
              <th
                key={column.label}
                scope="col"
                className={cn('py-2.5 pr-3 font-normal', NUMERIC.has(column.kind ?? 'text') && 'text-right')}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((row, index) => (
              <tr key={index} className="border-b">
                {columns.map((column) => (
                  <td
                    key={column.label}
                    className={cn(
                      'py-2.5 pr-3',
                      NUMERIC.has(column.kind ?? 'text') && 'num text-right whitespace-nowrap',
                    )}
                  >
                    {display(column.value(row), column.kind, currency)}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr className="border-b">
              <td colSpan={columns.length} className="py-4 text-muted-foreground">
                Nothing in this period.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
