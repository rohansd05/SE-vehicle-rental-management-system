import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { listPendingLicences } from '@/api/licences'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/dates'

import { PENDING_LICENCES_KEY } from './keys'

/** Branch Staff and Administrators: licences waiting for a decision, oldest first. */
export function LicenceQueuePage() {
  const location = useLocation()
  const flash = (location.state as { flash?: string } | null)?.flash ?? null
  const queue = useQuery({ queryKey: PENDING_LICENCES_KEY, queryFn: listPendingLicences })

  return (
    <section>
      <PageHeader
        title="Licence checks"
        description="Licences customers have submitted, oldest first. Check each one against its photos."
        actions={
          <Button variant="outline" size="lg" className="h-10" onClick={() => void queue.refetch()} disabled={queue.isFetching}>
            {queue.isFetching ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
      />
      <div className="mb-4">
        <StatusMessage message={flash} tone="success" />
      </div>
      {queue.isPending ? (
        <LoadingState label="Loading the queue…" />
      ) : queue.isError ? (
        <ErrorState title="We couldn’t load the queue" error={queue.error} onRetry={() => void queue.refetch()} />
      ) : queue.data.results.length === 0 ? (
        <EmptyState
          title="Nothing to check"
          description="No licences are waiting for verification right now."
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            {queue.data.count} {queue.data.count === 1 ? 'licence is' : 'licences are'} waiting.
            {queue.data.next ? ` Showing the oldest ${queue.data.results.length}.` : ''}
          </p>
          <ul className="grid gap-3">
            {queue.data.results.map((licence) => (
              <li key={licence.id}>
                <Link
                  to={`/app/licences/${licence.id}`}
                  state={{ licence }}
                  className="flex items-center gap-3 rounded-lg border p-4 transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{licence.customer.name}</span>
                    <span className="block truncate text-sm text-muted-foreground">
                      {licence.licence_number} · {licence.categories.join(', ')}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      Submitted {formatDateTime(licence.updated_at)}
                    </span>
                  </span>
                  <span className="sr-only">Review</span>
                  <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
