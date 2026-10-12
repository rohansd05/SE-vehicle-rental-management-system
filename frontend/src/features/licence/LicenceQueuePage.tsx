import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'react-router-dom'

import { listPendingLicences } from '@/api/licences'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { RowLink, RowList } from '@/components/row-list'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

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
        photo="band-licence-checks-1"
        variant="compact"
        description="Licences customers have submitted, oldest first. Check each one against its photos."
        actions={
          <Button variant="outline" onClick={() => void queue.refetch()} disabled={queue.isFetching}>
            {queue.isFetching ? 'Refreshing…' : 'Refresh'}
          </Button>
        }
      />
      <div className="mb-4">
        <StatusMessage message={flash} tone="success" />
      </div>
      {queue.isPending ? (
        <LoadingState label="Loading the queue…" rows={3} />
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
          {/* Queue rows (ui-brief.md 6.4.1): customer, licence and categories, submitted. */}
          <RowList>
            {queue.data.results.map((licence, index) => (
              <RowLink
                key={licence.id}
                to={`/app/licences/${licence.id}`}
                state={{ licence }}
                srLabel="Review"
                columns="@xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_auto]"
                style={stagger(index)}
              >
                <span className="min-w-0 font-medium">{licence.customer.name}</span>
                <span className="min-w-0 text-sm text-muted-foreground">
                  <span className="num whitespace-nowrap">{licence.licence_number}</span> · {licence.categories.join(', ')}
                </span>
                <span className="text-small text-muted-foreground @xl:text-right">
                  Submitted <span className="num whitespace-nowrap">{formatDateTime(licence.updated_at)}</span>
                </span>
              </RowLink>
            ))}
          </RowList>
        </>
      )}
    </section>
  )
}
