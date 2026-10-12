import { JOB_STATUSES, type JobStatus, type MaintenanceJob } from '@/api/maintenance'
import { RowLink, RowList } from '@/components/row-list'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { VehicleStatusBadge } from '@/components/VehicleStatusBadge'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

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
  // One aligned row with the queue's count (ui-brief.md 6.4.1): label beside the select.
  return (
    <div className="flex items-center gap-3">
      <Label htmlFor="job-status-filter">Status</Label>
      <NativeSelect
        id="job-status-filter"
        className="w-56"
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

/**
 * Jobs as queue rows (ui-brief.md 6.4.1); `basePath` is where a job's detail
 * page lives. Columns once the list is 36 rem wide: the job and its vehicle, the problem, then
 * the people and the date.
 */
export function JobList({ jobs, basePath }: { jobs: MaintenanceJob[]; basePath: string }) {
  return (
    <RowList>
      {jobs.map((job, index) => (
        <RowLink
          key={job.job_id}
          to={`${basePath}/${job.job_id}`}
          srLabel="Open job"
          columns="@xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_minmax(0,1fr)]"
          style={stagger(index)}
        >
          <span className="grid min-w-0 gap-1.5">
            <span className="font-medium">
              Job {job.job_id} · <span className="num whitespace-nowrap">{job.vehicle.registration_no}</span>
            </span>
            <span className="flex flex-wrap items-center gap-2">
              <JobStatusBadge job={job} />
              <VehicleStatusBadge status={job.vehicle.status} />
            </span>
          </span>
          <span className="line-clamp-2 min-w-0 text-sm text-muted-foreground">
            {job.job_type}: {job.reported_problem}
          </span>
          <span className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 text-small text-muted-foreground @xl:flex-col @xl:items-end @xl:text-right">
            <SeverityBadge severity={job.severity} />
            <span>{job.vehicle.brand} {job.vehicle.model}</span>
            {job.technician ? <span>Technician: {job.technician.name}</span> : <span>Not assigned</span>}
            {job.scheduled_from ? (
              <span>
                From <span className="num whitespace-nowrap">{formatDateTime(job.scheduled_from)}</span>
              </span>
            ) : null}
          </span>
        </RowLink>
      ))}
    </RowList>
  )
}
