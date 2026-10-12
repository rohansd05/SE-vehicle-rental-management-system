import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

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
    <section className="stage">
      <PageHeader
        title="My bookings"
        photo="band-bookings-1"
        description="Every booking you have made, the most recent pickup first."
        actions={
          <Button asChild>
            <Link to="/app/search">Book a vehicle</Link>
          </Button>
        }
      />
      <div className="mb-5 flex items-center gap-3">
        <label htmlFor="booking-status-filter" className="text-label font-medium">
          Status
        </label>
        <NativeSelect
          id="booking-status-filter"
          className="w-auto"
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
        </NativeSelect>
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
        <div className="grid gap-6">
          {/* Rows, not boxes (docs/design/ui-brief.md, 6.4): vehicle, period, branch, amount, status. */}
          <ul aria-label="Bookings" className="border-t">
            {bookings.data.results.map((booking, index) => (
              <li
                key={booking.id}
                className="enter grid gap-x-10 gap-y-2 border-b py-5 xl:grid-cols-[minmax(0,1fr)_max-content_minmax(6rem,0.5fr)_max-content_minmax(10rem,max-content)] xl:items-center"
                style={stagger(index)}
              >
                <div className="min-w-0">
                  <Link to={`/app/bookings/${booking.id}`} className="font-medium underline-offset-4 hover:text-primary hover:underline">
                    {booking.vehicle.brand} {booking.vehicle.model}
                    {/* B14: the reference never breaks inside itself. */}
                    {booking.booking_reference ? (
                      <>
                        {' · '}
                        <span className="num whitespace-nowrap">{booking.booking_reference}</span>
                      </>
                    ) : null}
                  </Link>
                </div>
                {/* B14: pickup and return on their own lines, each kept whole. */}
                <p className="num text-muted-foreground">
                  <span className="block whitespace-nowrap">{formatDateTime(booking.pickup_datetime)}</span>{' '}
                  <span className="block whitespace-nowrap">to {formatDateTime(booking.return_datetime)}</span>
                </p>
                <p className="text-sm text-muted-foreground">{booking.pickup_branch}</p>
                <p className="num-strong xl:text-right">{formatCurrency(booking.total_amount, currency)}</p>
                <div className="xl:justify-self-end">
                  <BookingStatusBadge status={booking.status} />
                </div>
              </li>
            ))}
          </ul>
          {bookings.data.next || bookings.data.previous ? (
            <nav aria-label="Booking pages" className="flex justify-end gap-2">
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
