import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { PageHeader } from '@/components/page'
import { RowLink, RowList } from '@/components/row-list'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { type BranchBooking, listCollections, listReturns } from './api'
import { COLLECTIONS_KEY, RETURNS_KEY } from './keys'

/**
 * Collections (or returns) as queue rows (ui-brief.md 6.4.1); each opens the
 * booking's handover (or its return, Exp 2 use case 8).
 */
function CollectionList({
  bookings,
  label,
  returns = false,
}: {
  bookings: BranchBooking[]
  label: string
  returns?: boolean
}) {
  return (
    <RowList>
      {bookings.map((booking, index) => (
        <RowLink
          key={booking.id}
          to={returns ? `/app/returns/${booking.id}` : `/app/handover/${booking.id}`}
          srLabel={`Open the ${returns ? 'return' : 'handover'} of ${booking.booking_reference} (${label})`}
          columns="@xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,auto)]"
          style={stagger(index)}
        >
          <span className="grid min-w-0 gap-1.5">
            <span className="font-medium">
              {booking.vehicle.brand} {booking.vehicle.model} ·{' '}
              <span className="num whitespace-nowrap">{booking.vehicle.registration_no}</span>
            </span>
            <span className="num text-sm whitespace-nowrap text-muted-foreground">{booking.booking_reference}</span>
          </span>
          <span className="grid min-w-0 gap-1.5 text-sm">
            <span>{booking.customer_name}</span>
            <span className="num whitespace-nowrap text-muted-foreground">{booking.customer_mobile}</span>
            {/* Book.Deliver.Location (R4): staff take a delivered booking to this address. */}
            {booking.delivery_address ? (
              <span className="text-muted-foreground">
                Doorstep delivery: <span className="text-foreground">{booking.delivery_address}</span>
              </span>
            ) : null}
          </span>
          {returns ? (
            <span className="text-sm text-muted-foreground @xl:text-right">
              Return due <span className="num whitespace-nowrap text-foreground">{formatDateTime(booking.return_datetime)}</span>
            </span>
          ) : (
            <span className="text-sm text-muted-foreground @xl:text-right">
              Pickup <span className="num whitespace-nowrap text-foreground">{formatDateTime(booking.pickup_datetime)}</span>
            </span>
          )}
        </RowLink>
      ))}
    </RowList>
  )
}

function CollectionSection({
  title,
  when,
  emptyTitle,
  emptyText,
}: {
  title: string
  when: 'today' | 'upcoming'
  emptyTitle: string
  emptyText: string
}) {
  const bookings = useQuery({ queryKey: [...COLLECTIONS_KEY, { when }], queryFn: () => listCollections({ when }) })
  return (
    <section aria-labelledby={`collections-${when}`} className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id={`collections-${when}`}>{title}</h2>
        {bookings.data && bookings.data.count > 0 ? (
          <p className="text-sm text-muted-foreground">
            {bookings.data.count} {bookings.data.count === 1 ? 'booking' : 'bookings'}.
          </p>
        ) : null}
      </div>
      {bookings.isPending ? (
        <LoadingState label="Loading collections…" rows={3} />
      ) : bookings.isError ? (
        <ErrorState title="We couldn’t load the collections" error={bookings.error} onRetry={() => void bookings.refetch()} />
      ) : bookings.data.results.length === 0 ? (
        <EmptyState title={emptyTitle} description={emptyText} />
      ) : (
        <CollectionList bookings={bookings.data.results} label={title} />
      )}
    </section>
  )
}

/** UC 8 step 1: rentals in progress due back today or overdue. */
function ReturnSection() {
  const returns = useQuery({ queryKey: [...RETURNS_KEY, {}], queryFn: () => listReturns() })
  return (
    <section aria-labelledby="returns-today" className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id="returns-today">Returns due today</h2>
        {returns.data && returns.data.count > 0 ? (
          <p className="text-sm text-muted-foreground">
            {returns.data.count} {returns.data.count === 1 ? 'rental' : 'rentals'}.
          </p>
        ) : null}
      </div>
      {returns.isPending ? (
        <LoadingState label="Loading returns…" rows={2} />
      ) : returns.isError ? (
        <ErrorState title="We couldn’t load the returns" error={returns.error} onRetry={() => void returns.refetch()} />
      ) : returns.data.results.length === 0 ? (
        <EmptyState
          title="No returns due today"
          description="No rentals in progress at your branch are due back today or overdue."
        />
      ) : (
        <CollectionList bookings={returns.data.results} label="Returns due today" returns />
      )}
    </section>
  )
}

/** A search also finds a rental in progress, to take it back early or late. */
function ReturnResults({ query }: { query: string }) {
  const found = useQuery({ queryKey: [...RETURNS_KEY, { q: query }], queryFn: () => listReturns({ q: query }) })
  if (!found.data?.results.length) return null
  return (
    <section aria-labelledby="returns-search" className="grid gap-4">
      <h2 id="returns-search">Rentals in progress</h2>
      <CollectionList bookings={found.data.results} label="Rentals in progress" returns />
    </section>
  )
}

function SearchResults({ query, onClear }: { query: string; onClear: () => void }) {
  const found = useQuery({ queryKey: [...COLLECTIONS_KEY, { q: query }], queryFn: () => listCollections({ q: query }) })
  return (
    <section aria-labelledby="collections-search" className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id="collections-search">Search results</h2>
        <Button variant="outline" onClick={onClear}>
          Clear search
        </Button>
      </div>
      {found.isPending ? (
        <LoadingState label="Finding the booking…" rows={1} />
      ) : found.isError ? (
        <ErrorState title="We couldn’t search the bookings" error={found.error} onRetry={() => void found.refetch()} />
      ) : found.data.results.length === 0 ? (
        <EmptyState
          title="No booking found"
          description="Check the booking reference, pickup code or mobile number. Only Confirmed bookings collected at your branch are found."
        />
      ) : (
        <CollectionList bookings={found.data.results} label="Search results" />
      )}
    </section>
  )
}

/**
 * UC 7 step 1: the branch's collections and the booking lookup by reference,
 * pickup code or customer mobile. /app/handover shows today's collections;
 * /app/branch-bookings adds the upcoming ones.
 */
export function CollectionsPage({
  title,
  description,
  photo,
  showUpcoming,
}: {
  title: string
  description: string
  photo: string
  showUpcoming: boolean
}) {
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setQuery(draft.trim())
  }

  return (
    <section>
      <PageHeader title={title} description={description} photo={photo} variant="compact" />
      <form role="search" onSubmit={submit} className="mb-8 flex flex-wrap items-end gap-3">
        <div className="grid min-w-0 flex-1 gap-1.5 sm:max-w-md">
          <Label htmlFor="booking-search">Booking reference, pickup code or mobile number</Label>
          <Input
            id="booking-search"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            autoComplete="off"
            className="num"
          />
        </div>
        <Button type="submit" size="lg">
          <Search aria-hidden="true" />
          Find booking
        </Button>
      </form>
      {query ? (
        <div className="grid gap-10">
          <SearchResults
            query={query}
            onClear={() => {
              setDraft('')
              setQuery('')
            }}
          />
          <ReturnResults query={query} />
        </div>
      ) : (
        <div className="grid gap-10">
          <CollectionSection
            title="Today’s collections"
            when="today"
            emptyTitle="No collections today"
            emptyText="No Confirmed bookings are due for collection at your branch today."
          />
          <ReturnSection />
          {showUpcoming ? (
            <CollectionSection
              title="Upcoming collections"
              when="upcoming"
              emptyTitle="No upcoming collections"
              emptyText="No Confirmed bookings are due for collection at your branch after today."
            />
          ) : null}
        </div>
      )}
    </section>
  )
}

/** Branch Staff: the handover desk (today's collections and the lookup). */
export function HandoverDeskPage() {
  return (
    <CollectionsPage
      title="Handover and return"
      description="Hand vehicles over to customers and record their return."
      photo="step-collect-1"
      showUpcoming={false}
    />
  )
}

/** Branch Staff and Branch Managers: today's and upcoming collections at their branch. */
export function BranchBookingsPage() {
  return (
    <CollectionsPage
      title="Branch bookings"
      description="Today's collections and returns at your branch."
      photo="band-bookings-1"
      showUpcoming
    />
  )
}
