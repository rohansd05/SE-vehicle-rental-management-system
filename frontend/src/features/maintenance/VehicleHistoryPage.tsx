import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { vehicleHistory } from '@/api/maintenance'
import { PageHeader } from '@/components/page'
import { RowLink, RowList } from '@/components/row-list'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { formatINR } from '@/lib/currency'
import { formatDate } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { JobStatusBadge } from './badges'
import { formatKm } from './format'
import { ServiceOverdueNote } from './JobDetailPage'

/**
 * Maint.History: the complete chronological maintenance history of a vehicle, every
 * job with its date, type, odometer reading, work performed, parts, cost and
 * downtime, for staff, technicians and Administrators. `basePath` is where the
 * jobs open (/app/jobs for a technician, /app/maintenance otherwise).
 */
export function VehicleHistoryPage({ basePath }: { basePath: string }) {
  const { id } = useParams()
  const vehicleId = Number(id)
  const history = useQuery({
    queryKey: ['maintenance', 'history', vehicleId],
    queryFn: () => vehicleHistory(vehicleId),
  })
  const vehicle = history.data?.results[0]?.vehicle

  return (
    <section>
      <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
        <Link to={basePath}>
          <ArrowLeft aria-hidden="true" />
          {basePath === '/app/jobs' ? 'Back to my jobs' : 'Back to maintenance'}
        </Link>
      </Button>
      <PageHeader
        title={vehicle ? `Maintenance history · ${vehicle.registration_no}` : 'Maintenance history'}
        description={
          vehicle ? (
            <span className="flex flex-wrap items-center gap-2">
              {vehicle.brand} {vehicle.model}, {formatKm(vehicle.odometer)}
              <VehicleStatusBadge status={vehicle.status} />
            </span>
          ) : (
            'Every job on this vehicle, newest first.'
          )
        }
      />
      {vehicle?.service_overdue ? (
        <div className="mb-6">
          <ServiceOverdueNote registration={vehicle.registration_no} />
        </div>
      ) : null}
      {history.isPending ? (
        <LoadingState label="Loading the history…" rows={3} />
      ) : history.isError ? (
        <ErrorState title="We couldn’t load the history" error={history.error} onRetry={() => void history.refetch()} />
      ) : history.data.results.length === 0 ? (
        <EmptyState title="No maintenance recorded" description="No job has been reported on this vehicle yet." />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground" aria-live="polite">
            {history.data.count} {history.data.count === 1 ? 'job' : 'jobs'}
            {history.data.next ? `, showing the latest ${history.data.results.length}` : ''}.
          </p>
          <RowList>
            {history.data.results.map((job, index) => (
              <RowLink
                key={job.job_id}
                to={`${basePath}/${job.job_id}`}
                srLabel="Open job"
                columns="@xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)_minmax(0,0.9fr)]"
                style={stagger(index)}
              >
                <span className="grid min-w-0 gap-1.5">
                  <span className="font-medium">
                    Job {job.job_id} · {job.job_type}
                  </span>
                  <span className="flex flex-wrap items-center gap-2">
                    <JobStatusBadge job={job} />
                  </span>
                  <span className="text-sm text-muted-foreground">
                    <span className="num whitespace-nowrap">{formatDate(job.service_date ?? job.created_at)}</span>
                    {job.odometer_at_service !== null ? ` at ${formatKm(job.odometer_at_service)}` : ''}
                  </span>
                </span>
                <span className="grid min-w-0 gap-1 text-sm">
                  <span>{job.work_description || job.reported_problem}</span>
                  <span className="text-muted-foreground">
                    {job.parts.length
                      ? `Parts: ${job.parts.map((part) => `${part.part_name} × ${part.quantity.replace(/\.00$/, '')}`).join(', ')}`
                      : 'No parts recorded'}
                  </span>
                </span>
                <span className="flex min-w-0 flex-wrap gap-x-4 gap-y-1 text-small text-muted-foreground @xl:flex-col @xl:items-end @xl:text-right">
                  <span>
                    Cost <span className="num whitespace-nowrap text-foreground">{formatINR(job.total_cost)}</span>
                  </span>
                  <span>Downtime {job.downtime_hours ? `${job.downtime_hours} hours` : '—'}</span>
                </span>
              </RowLink>
            ))}
          </RowList>
        </>
      )}
    </section>
  )
}
