import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'

import { BOOKING_STATUSES, type BookingStatus, listBookings } from '@/features/booking/api'
import { bookingsKey } from '@/features/booking/keys'

import { BookingStatusBadge } from './BookingStatusBadge'

/** History.View: the customer's own bookings of every status, most recent first (History.Privacy). */
export function BookingHistoryPage() {
  const { currency } = useAgency()
  const [status, setStatus] = useState<BookingStatus | ''>('')
  const [page, setPage] = useState(1)
  const bookings = useQuery({
    queryKey: bookingsKey(status, page),
    queryFn: () => listBookings({ status, page }),
  })

  return (
    <section>
      <PageHeader
        title="My bookings"
        description="Every booking you have made, the most recent pickup first."
        actions={
          <Button asChild className="h-10">
            <Link to="/app/search">Book a vehicle</Link>
          </Button>
        }
      />
      <div className="mb-4 flex items-center gap-2">
        <label htmlFor="booking-status-filter" className="text-sm font-medium">
          Status
        </label>
        <select
          id="booking-status-filter"
          className="h-10 rounded-lg border border-input bg-background px-3 text-sm"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value as BookingStatus | '')
            setPage(1)
          }}
        >
          <option value="">All statuses</option>
          {BOOKING_STATUSES.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>
      {bookings.isPending ? (
        <LoadingState label="Loading your bookings…" />
      ) : bookings.isError ? (
        <ErrorState title="We couldn’t load your bookings" error={bookings.error} onRetry={() => void bookings.refetch()} />
      ) : bookings.data.count === 0 ? (
        <EmptyState
          title={status ? `No ${status} bookings` : 'No bookings yet'}
          description="Find a vehicle that is free for your dates and book it."
        />
      ) : (
        <div className="grid gap-4">
          <ul aria-label="Bookings" className="grid gap-3">
            {bookings.data.results.map((booking) => (
              <li key={booking.id}>
                <Card>
                  <CardContent className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <Link to={`/app/bookings/${booking.id}`} className="font-semibold underline-offset-4 hover:underline">
                        {booking.vehicle.brand} {booking.vehicle.model}
                        {booking.booking_reference ? ` · ${booking.booking_reference}` : ''}
                      </Link>
                      <p className="text-sm text-muted-foreground">
                        {formatDateTime(booking.pickup_datetime)} to {formatDateTime(booking.return_datetime)} ·{' '}
                        {booking.pickup_branch}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm tabular-nums">{formatCurrency(booking.total_amount, currency)}</span>
                      <BookingStatusBadge status={booking.status} />
                    </div>
                  </CardContent>
                </Card>
              </li>
            ))}
          </ul>
          {bookings.data.next || bookings.data.previous ? (
            <nav aria-label="Booking pages" className="flex gap-2">
              <Button variant="outline" disabled={!bookings.data.previous} onClick={() => setPage(page - 1)}>
                Previous page
              </Button>
              <Button variant="outline" disabled={!bookings.data.next} onClick={() => setPage(page + 1)}>
                Next page
              </Button>
            </nav>
          ) : null}
        </div>
      )}
    </section>
  )
}
