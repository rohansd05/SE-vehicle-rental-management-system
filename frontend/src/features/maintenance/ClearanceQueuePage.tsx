import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'

import { listClearances } from '@/api/maintenance'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'

import { JobList } from './JobList'
import { CLEARANCES_KEY } from './keys'

/** Administrator (BR-16): completed work on Unsafe vehicles, oldest request first. */
export function ClearanceQueuePage() {
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash ?? null
  const queue = useQuery({ queryKey: CLEARANCES_KEY, queryFn: listClearances })

  return (
    <section>
      <PageHeader
        title="Unsafe clearances"
        description="Technicians have finished work on these Unsafe vehicles. Review the work, then clear the flag to release the vehicle."
        actions={
          <Button
            variant="outline"
            size="lg"
            className="h-10"
            onClick={() => void queue.refetch()}
            disabled={queue.isFetching}
          >
            {queue.isFetching ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
      />
      <div className="mb-4">
        <StatusMessage message={flash} tone="success" />
      </div>
      {queue.isPending ? (
        <LoadingState label="Loading the clearance queue…" />
      ) : queue.isError ? (
        <ErrorState title="We couldn’t load the queue" error={queue.error} onRetry={() => void queue.refetch()} />
      ) : queue.data.results.length === 0 ? (
        <EmptyState title="Nothing to clear" description="No jobs are waiting for an Administrator’s clearance." />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            {queue.data.count} {queue.data.count === 1 ? 'job is' : 'jobs are'} waiting.
          </p>
          <JobList jobs={queue.data.results} basePath="/app/maintenance" />
        </>
      )}
    </section>
  )
}
