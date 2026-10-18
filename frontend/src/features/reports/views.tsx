// What each report shows (UC 14: utilisation, revenue, maintenance cost, customers): its
// headline figures, its charts and its tables. The tables are also the CSV export.

import type { ReactNode } from 'react'

import { formatCurrency } from '@/lib/currency'

import type { CustomerReport, MaintenanceReport, Reports, ReportType, RevenueReport, UtilisationReport } from './api'
import { type Column, display, type Section } from './csv'
import { BarFigure } from './chart'

export interface ReportView<T> {
  label: string
  figures: (data: T, currency: string) => { label: string; value: ReactNode }[]
  charts: (data: T, currency: string) => ReactNode
  sections: (data: T) => Section[]
}

const percent = (value: number) => `${value}%`
const money = (currency: string) => (value: number) => formatCurrency(value, currency)
const compactMoney = (currency: string) => (value: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency, notation: 'compact', maximumFractionDigits: 1 }).format(
    value,
  )

function section<Row>(title: string, columns: Column<Row>[], rows: Row[]): Section {
  return { title, columns, rows } as Section
}

// ─── Utilisation (Report.Utilisation) ─────────────────────────────────────

type UtilisationVehicle = UtilisationReport['by_vehicle'][number]
type UtilisationGroup = UtilisationReport['by_category'][number]

const groupColumns = (name: string): Column<UtilisationGroup>[] => [
  { label: name, value: (row) => row.name },
  { label: 'Vehicles', value: (row) => row.vehicles, kind: 'number' },
  { label: 'Hours on rent', value: (row) => row.rented_hours, kind: 'number' },
  { label: 'Available hours', value: (row) => row.available_hours, kind: 'number' },
  { label: 'Utilisation', value: (row) => row.utilisation_percent, kind: 'percent' },
]

const VEHICLE_COLUMNS: Column<UtilisationVehicle>[] = [
  { label: 'Registration', value: (row) => row.registration_no },
  { label: 'Vehicle', value: (row) => row.vehicle },
  { label: 'Category', value: (row) => row.category },
  { label: 'Branch', value: (row) => row.branch },
  { label: 'Hours on rent', value: (row) => row.rented_hours, kind: 'number' },
  { label: 'Days under maintenance', value: (row) => row.maintenance_days, kind: 'number' },
  { label: 'Available hours', value: (row) => row.available_hours, kind: 'number' },
  { label: 'Utilisation', value: (row) => row.utilisation_percent, kind: 'percent' },
]

const utilisation: ReportView<UtilisationReport> = {
  label: 'Utilisation',
  figures: (data) => [
    { label: 'Utilisation', value: display(data.totals.utilisation_percent, 'percent', '') },
    { label: 'Hours on rent', value: data.totals.rented_hours },
    { label: 'Available hours', value: data.totals.available_hours },
    { label: 'Vehicles', value: data.totals.vehicles },
  ],
  charts: (data) => (
    <>
      <BarFigure
        title="Utilisation by vehicle category"
        rows={data.by_category}
        series={[{ key: 'utilisation_percent', label: 'Utilisation', color: 'var(--chart-1)' }]}
        format={percent}
      />
      <BarFigure
        title="Utilisation by branch"
        rows={data.by_branch}
        series={[{ key: 'utilisation_percent', label: 'Utilisation', color: 'var(--chart-1)' }]}
        format={percent}
      />
    </>
  ),
  sections: (data) => [
    section('Least utilised vehicles', VEHICLE_COLUMNS, data.least_utilised),
    section('By vehicle', VEHICLE_COLUMNS, data.by_vehicle),
    section('By vehicle category', groupColumns('Category'), data.by_category),
    section('By branch', groupColumns('Branch'), data.by_branch),
  ],
}

// ─── Revenue (Report.Revenue) ─────────────────────────────────────────────

type RevenueGroup = RevenueReport['by_branch'][number]
type RevenueMethod = RevenueReport['by_method'][number]
type RevenueLine = { line: string; amount: string; counted: string }

const revenueGroupColumns = (name: string): Column<RevenueGroup>[] => [
  { label: name, value: (row) => row.name },
  { label: 'Rental', value: (row) => row.rental, kind: 'money' },
  { label: 'Add-ons', value: (row) => row.add_ons, kind: 'money' },
  { label: 'Discounts', value: (row) => row.discounts, kind: 'money' },
  { label: 'Tax', value: (row) => row.tax, kind: 'money' },
  { label: 'Debit notes', value: (row) => row.debit_notes, kind: 'money' },
  { label: 'Credit notes', value: (row) => row.credit_notes, kind: 'money' },
  { label: 'Net revenue', value: (row) => row.net_revenue, kind: 'money' },
]

/** Report.Revenue: rental and add-on income apart; refunds awaiting approval never counted. */
function revenueLines(data: RevenueReport): RevenueLine[] {
  const { totals } = data
  const counted = (line: string, amount: string) => ({ line, amount, counted: 'Yes' })
  return [
    counted('Rental income', totals.rental),
    counted('Add-on income', totals.add_ons),
    counted('Discounts', totals.discounts),
    counted('Tax', totals.tax),
    counted('Debit notes (booking changes and return charges)', totals.debit_notes),
    counted('Credit notes (refunds), deducted', totals.credit_notes),
    counted('Net revenue', totals.net_revenue),
    { line: 'Refunds awaiting approval', amount: totals.refunds_awaiting_approval, counted: 'No' },
    { line: 'Outstanding dues', amount: totals.outstanding_dues, counted: 'No' },
  ]
}

const revenue: ReportView<RevenueReport> = {
  label: 'Revenue',
  figures: (data, currency) => [
    { label: 'Net revenue', value: formatCurrency(data.totals.net_revenue, currency) },
    { label: 'Invoices issued', value: data.totals.invoices },
    { label: 'Refunds awaiting approval', value: formatCurrency(data.totals.refunds_awaiting_approval, currency) },
    { label: 'Outstanding dues', value: formatCurrency(data.totals.outstanding_dues, currency) },
  ],
  charts: (data, currency) => (
    <>
      <BarFigure
        title="Net revenue by branch"
        rows={data.by_branch}
        series={[{ key: 'net_revenue', label: 'Net revenue', color: 'var(--chart-1)' }]}
        format={money(currency)}
        axis={compactMoney(currency)}
      />
      <BarFigure
        title="Net revenue by vehicle category"
        rows={data.by_category}
        series={[{ key: 'net_revenue', label: 'Net revenue', color: 'var(--chart-1)' }]}
        format={money(currency)}
        axis={compactMoney(currency)}
      />
    </>
  ),
  sections: (data) => [
    section<RevenueLine>(
      'Revenue',
      [
        { label: 'Line', value: (row) => row.line },
        { label: 'Amount', value: (row) => row.amount, kind: 'money' },
        { label: 'In net revenue', value: (row) => row.counted },
      ],
      revenueLines(data),
    ),
    section('By branch', revenueGroupColumns('Branch'), data.by_branch),
    section('By vehicle category', revenueGroupColumns('Category'), data.by_category),
    section<RevenueMethod>(
      'By payment method',
      [
        { label: 'Method', value: (row) => row.method },
        { label: 'Charges', value: (row) => row.charges, kind: 'money' },
        { label: 'Refunds', value: (row) => row.refunds, kind: 'money' },
        { label: 'Net', value: (row) => row.net, kind: 'money' },
      ],
      data.by_method,
    ),
  ],
}

// ─── Maintenance cost ─────────────────────────────────────────────────────

type CostVehicle = MaintenanceReport['by_vehicle'][number]
type CostJobType = MaintenanceReport['by_job_type'][number]

const maintenance: ReportView<MaintenanceReport> = {
  label: 'Maintenance cost',
  figures: (data, currency) => [
    { label: 'Total cost', value: formatCurrency(data.totals.total, currency) },
    { label: 'Jobs', value: data.totals.jobs },
    { label: 'Labour', value: formatCurrency(data.totals.labour, currency) },
    { label: 'Parts', value: formatCurrency(data.totals.parts, currency) },
  ],
  charts: (data, currency) => (
    <BarFigure
      title="Cost by job type"
      rows={data.by_job_type.filter((row) => row.jobs > 0).map((row) => ({ name: row.job_type, ...row }))}
      series={[
        { key: 'labour', label: 'Labour', color: 'var(--chart-1)' },
        { key: 'parts', label: 'Parts', color: 'var(--chart-4)' },
      ]}
      format={money(currency)}
      axis={compactMoney(currency)}
    />
  ),
  sections: (data) => [
    section<CostJobType>(
      'By job type',
      [
        { label: 'Job type', value: (row) => row.job_type },
        { label: 'Jobs', value: (row) => row.jobs, kind: 'number' },
        { label: 'Raised by the system', value: (row) => row.automatic, kind: 'number' },
        { label: 'Labour', value: (row) => row.labour, kind: 'money' },
        { label: 'Parts', value: (row) => row.parts, kind: 'money' },
        { label: 'Total', value: (row) => row.total, kind: 'money' },
      ],
      data.by_job_type,
    ),
    section<CostVehicle>(
      'By vehicle',
      [
        { label: 'Registration', value: (row) => row.registration_no },
        { label: 'Vehicle', value: (row) => row.vehicle },
        { label: 'Branch', value: (row) => row.branch },
        { label: 'Jobs', value: (row) => row.jobs, kind: 'number' },
        { label: 'Labour', value: (row) => row.labour, kind: 'money' },
        { label: 'Parts', value: (row) => row.parts, kind: 'money' },
        { label: 'Total', value: (row) => row.total, kind: 'money' },
      ],
      data.by_vehicle,
    ),
  ],
}

// ─── Customers ────────────────────────────────────────────────────────────

type TopCustomer = CustomerReport['top'][number]
type CustomerDue = CustomerReport['with_dues'][number]

const customers: ReportView<CustomerReport> = {
  label: 'Customers',
  figures: (data, currency) => [
    { label: 'New customers', value: data.totals.new },
    { label: 'Active customers', value: data.totals.active },
    { label: 'No-shows', value: data.totals.no_shows },
    { label: 'Outstanding dues', value: formatCurrency(data.totals.dues_total, currency) },
  ],
  charts: (data, currency) => (
    <BarFigure
      title="Top customers by net revenue"
      rows={data.top}
      series={[{ key: 'net_revenue', label: 'Net revenue', color: 'var(--chart-1)' }]}
      format={money(currency)}
      axis={compactMoney(currency)}
    />
  ),
  sections: (data) => [
    section<TopCustomer>(
      'Top customers',
      [
        { label: 'Customer', value: (row) => row.name },
        { label: 'E-mail', value: (row) => row.email },
        { label: 'Bookings', value: (row) => row.bookings, kind: 'number' },
        { label: 'No-shows', value: (row) => row.no_shows, kind: 'number' },
        { label: 'Net revenue', value: (row) => row.net_revenue, kind: 'money' },
      ],
      data.top,
    ),
    section<CustomerDue>(
      'Customers with dues',
      [
        { label: 'Customer', value: (row) => row.name },
        { label: 'E-mail', value: (row) => row.email },
        { label: 'Outstanding due', value: (row) => row.outstanding_due, kind: 'money' },
      ],
      data.with_dues,
    ),
  ],
}

export const REPORT_VIEWS: { [T in ReportType]: ReportView<Reports[T]> } = {
  utilisation,
  revenue,
  maintenance,
  customers,
}
