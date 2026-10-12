import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { type JobStatus, listJobs } from '@/api/maintenance'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'

import { JobList, StatusFilter } from './JobList'
import { JOBS_KEY } from './keys'

function JobsView({
  title,
  description,
  basePath,
  emptyText,
  canReport,
  photo,
}: {
  title: string
  description: string
  basePath: string
  emptyText: string
  canReport: boolean
  photo: string
}) {
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash ?? null
  const [status, setStatus] = useState<JobStatus | ''>('')
  const jobs = useQuery({
    queryKey: [...JOBS_KEY, { status }],
    queryFn: () => listJobs({ status }),
  })

  return (
    <section>
      <PageHeader
        title={title}
        description={description}
        photo={photo}
        variant="compact"
        actions={
          canReport ? (
            <Button asChild>
              <Link to="/app/maintenance/report">
                <Plus aria-hidden="true" />
                Report a fault
              </Link>
            </Button>
          ) : null
        }
      />
      <StatusMessage message={flash} tone="success" />
      {/* One toolbar row (ui-brief.md 6.4.1): the filter, and the count once the jobs load. */}
      <div className="mt-4 mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <StatusFilter value={status} onChange={setStatus} />
        {jobs.data && jobs.data.results.length > 0 ? (
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {jobs.data.count} {jobs.data.count === 1 ? 'job' : 'jobs'}
            {jobs.data.next ? `, showing the latest ${jobs.data.results.length}` : ''}.
          </p>
        ) : null}
      </div>
      {jobs.isPending ? (
        <LoadingState label="Loading jobs…" rows={4} />
      ) : jobs.isError ? (
        <ErrorState title="We couldn’t load the jobs" error={jobs.error} onRetry={() => void jobs.refetch()} />
      ) : jobs.data.results.length === 0 ? (
        <EmptyState
          title={status ? `No ${status.toLowerCase()} jobs` : 'No jobs yet'}
          description={status ? 'Choose another status to see more jobs.' : emptyText}
        />
      ) : (
        <JobList jobs={jobs.data.results} basePath={basePath} />
      )}
    </section>
  )
}

/** Maintenance Technician: the jobs assigned to them (the server shows no others). */
export function MyJobsPage() {
  return (
    <JobsView
      title="Maintenance jobs"
      description="My jobs: the maintenance jobs assigned to you. Open one to start it, record the work and complete it."
      basePath="/app/jobs"
      emptyText="No maintenance jobs are assigned to you."
      canReport={false}
      photo="band-technician-1"
    />
  )
}

/** Branch Staff, Branch Manager and Administrator: their branch's jobs (all for an Administrator). */
export function BranchJobsPage() {
  return (
    <JobsView
      title="Maintenance"
      description="Faults reported on your branch’s vehicles, their technicians and progress."
      basePath="/app/maintenance"
      emptyText="No faults have been reported on your branch’s vehicles."
      canReport
      photo="band-maintenance-1"
    />
  )
}
