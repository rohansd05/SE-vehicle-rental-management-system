import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import type { VehicleStatus } from '@/api/maintenance'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { useAgency } from '@/hooks/page'
import { stagger } from '@/lib/motion'

import { type Dashboard, DASHBOARD_KEY, getDashboard } from './api'
import type { Section } from './csv'
import { Figures, ReportTable } from './parts'

const PERIOD_LABELS: Record<string, string> = { today: 'Today', week: 'This week', month: 'This month' }

const FIGURES_SECTION = (data: Dashboard): Section<Dashboard['periods'][number]> => ({
  title: 'Bookings and revenue',
  columns: [
    { label: 'Period', value: (row) => PERIOD_LABELS[row.period] ?? row.period },
    { label: 'Bookings', value: (row) => row.bookings, kind: 'number' },
    { label: 'Revenue', value: (row) => row.revenue, kind: 'money' },
  ],
  rows: data.periods,
})

/**
 * Report.Dashboard on the Administrator's and the Branch Manager's home page: vehicles in
 * each status, today's collections and returns, bookings and revenue for the day, week and
 * month, overdue returns and open maintenance jobs (a Branch Manager's branch only).
 */
export function DashboardSummary() {
  const { currency } = useAgency()
  const summary = useQuery({ queryKey: DASHBOARD_KEY, queryFn: getDashboard })
  if (summary.isPending) return <LoadingState label="Loading today’s figures…" />
  if (summary.isError) {
    return (
      <div className="mb-10">
        <ErrorState title="We couldn’t load today’s figures" error={summary.error} onRetry={() => void summary.refetch()} />
      </div>
    )
  }
  const data = summary.data
  return (
    <section aria-labelledby="summary-title" className="enter mb-10 grid gap-6" style={stagger(1)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <h2 id="summary-title" className="heading text-section">
            Today at a glance
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {data.scope === 'All branches' ? 'All branches.' : `${data.scope} branch only.`}
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/app/reports">Open reports</Link>
        </Button>
      </div>
      <Figures
        items={[
          { label: 'Collections due today', value: data.collections_today },
          { label: 'Returns due today', value: data.returns_today },
          { label: 'Overdue returns', value: data.overdue_returns },
          { label: 'Open maintenance jobs', value: data.open_maintenance_jobs },
        ]}
      />
      <div className="grid gap-8 lg:grid-cols-2">
        <ReportTable section={FIGURES_SECTION(data)} currency={currency} />
        <div className="grid content-start gap-3">
          <h3 className="heading text-subsection">Vehicles by status</h3>
          <ul className="border-t">
            {data.vehicles_by_status.map((row) => (
              <li key={row.status} className="flex items-center justify-between gap-4 border-b py-2.5">
                <VehicleStatusBadge status={row.status as VehicleStatus} />
                <span className="num">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
