import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { JOB_STATUSES, type JobStatus, type MaintenanceJob } from '@/api/maintenance'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { formatDateTime } from '@/lib/dates'

import { JobStatusBadge, SeverityBadge } from './badges'

// The shared native select; re-exported because the maintenance forms import it from here.
export { NativeSelect }

export function StatusFilter({
  value,
  onChange,
}: {
  value: JobStatus | ''
  onChange: (value: JobStatus | '') => void
}) {
  return (
    <div className="grid gap-1.5 sm:w-56">
      <Label htmlFor="job-status-filter">Status</Label>
      <NativeSelect
        id="job-status-filter"
        value={value}
        onChange={(event) => onChange(event.target.value as JobStatus | '')}
      >
        <option value="">All statuses</option>
        {JOB_STATUSES.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </NativeSelect>
    </div>
  )
}

/** Jobs as tappable cards; `basePath` is where a job's detail page lives. */
export function JobList({ jobs, basePath }: { jobs: MaintenanceJob[]; basePath: string }) {
  return (
    <ul className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {jobs.map((job) => (
        <li key={job.job_id} className="min-w-0">
          <Link
            to={`${basePath}/${job.job_id}`}
            className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  Job {job.job_id} · {job.vehicle.registration_no}
                </span>
                <JobStatusBadge job={job} />
                <VehicleStatusBadge status={job.vehicle.status} />
              </span>
              <span className="mt-1 block truncate text-sm text-muted-foreground">
                {job.job_type}: {job.reported_problem}
              </span>
              <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <SeverityBadge severity={job.severity} />
                <span>{job.vehicle.brand} {job.vehicle.model}</span>
                {job.technician ? <span>Technician: {job.technician.name}</span> : <span>Not assigned</span>}
                {job.scheduled_from ? <span>From {formatDateTime(job.scheduled_from)}</span> : null}
              </span>
            </span>
            <span className="sr-only">Open job</span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          </Link>
        </li>
      ))}
    </ul>
  )
}
