// UC 14 step 3: "The actor optionally exports the report to a file." CSV (RFC 4180) built
// from the figures the server sent: money stays the exact decimal string (CO-6), and the
// text columns are guarded against spreadsheet formula injection (names are user data).

import { formatCurrency } from '@/lib/currency'

/** A report table column; the same definition draws the table and writes the CSV. */
export interface Column<Row> {
  label: string
  // Method syntax, so a section of any row type can join one export.
  value(row: Row): string | number | null | undefined
  kind?: 'text' | 'money' | 'number' | 'percent'
}

/** One block of the exported file: a titled table. */
export interface Section<Row = unknown> {
  title: string
  columns: Column<Row>[]
  rows: Row[]
}

/** A cell as shown on screen: money in the agency's currency, a percentage, or a dash. */
export function display(value: string | number | null | undefined, kind: Column<never>['kind'], currency: string) {
  if (value == null || value === '') return '—'
  if (kind === 'money') return formatCurrency(value, currency)
  if (kind === 'percent') return `${value}%`
  return String(value)
}

const FORMULA = /^[=+\-@\t\r]/

function cell(value: string | number | null | undefined, kind: Column<never>['kind']): string {
  let text = value == null ? '' : String(value)
  if (kind === 'text' || kind === undefined) {
    if (FORMULA.test(text)) text = `'${text}`
  }
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/** Each section as its title, a header row and its rows, with a blank line between. */
export function toCsv(sections: Section<unknown>[]): string {
  return sections
    .map(({ title, columns, rows }) =>
      [
        cell(title, 'text'),
        columns.map((column) => cell(column.label, 'text')).join(','),
        ...rows.map((row) => columns.map((column) => cell(column.value(row), column.kind)).join(',')),
      ].join('\r\n'),
    )
    .join('\r\n\r\n')
}

/** Save `csv` as `filename` (with a BOM, so spreadsheets read it as UTF-8). */
export function downloadCsv(filename: string, csv: string): void {
  const url = URL.createObjectURL(new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
