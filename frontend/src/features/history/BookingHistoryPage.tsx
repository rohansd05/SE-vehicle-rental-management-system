import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { BOOKING_STATUSES, type BookingStatus, type HistoryFilters, listBookings } from '@/features/booking/api'
import { bookingsKey } from '@/features/booking/keys'

import { BookingStatusBadge } from './BookingStatusBadge'

// D18: the licence categories are the vehicle types.
const VEHICLE_TYPES = ['Car', 'Two-Wheeler'] as const

/** A labelled filter control in the toolbar (ui-brief 6.4: label beside the control). */
function Filter({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <label htmlFor={id} className="text-label font-medium whitespace-nowrap">
        {label}
      </label>
      {children}
    </div>
  )
}

/**
 * History.View: the customer's own bookings of every status, most recent first
 * (History.Privacy), filtered by pickup date range, status and vehicle type, or
 * searched by booking reference.
 */
export function BookingHistoryPage() {
  const { currency } = useAgency()
  const [filters, setFilters] = useState<Omit<HistoryFilters, 'page'>>({})
  const [page, setPage] = useState(1)
  const status = filters.status ?? ''
  const narrowed = Boolean(filters.vehicle_type || filters.pickup_from || filters.pickup_to || filters.reference?.trim())
  const bookings = useQuery({
    queryKey: bookingsKey({ ...filters, page }),
    queryFn: () => listBookings({ ...filters, page }),
  })
  const filter = (patch: Omit<HistoryFilters, 'page'>) => {
    setFilters((current) => ({ ...current, ...patch }))
    setPage(1)
  }

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
      <div role="search" aria-label="Filter bookings" className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-3">
        <Filter id="booking-status-filter" label="Status">
          <NativeSelect
            id="booking-status-filter"
            className="w-auto"
            value={status}
            onChange={(event) => filter({ status: event.target.value as BookingStatus | '' })}
          >
            <option value="">All statuses</option>
            {BOOKING_STATUSES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </NativeSelect>
        </Filter>
        <Filter id="booking-type-filter" label="Vehicle type">
          <NativeSelect
            id="booking-type-filter"
            className="w-auto"
            value={filters.vehicle_type ?? ''}
            onChange={(event) => filter({ vehicle_type: event.target.value })}
          >
            <option value="">All vehicles</option>
            {VEHICLE_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </NativeSelect>
        </Filter>
        <Filter id="booking-from-filter" label="Pickup from">
          <Input
            id="booking-from-filter"
            type="date"
            className="num w-auto"
            value={filters.pickup_from ?? ''}
            onChange={(event) => filter({ pickup_from: event.target.value })}
          />
        </Filter>
        <Filter id="booking-to-filter" label="Pickup to">
          <Input
            id="booking-to-filter"
            type="date"
            className="num w-auto"
            value={filters.pickup_to ?? ''}
            min={filters.pickup_from || undefined}
            onChange={(event) => filter({ pickup_to: event.target.value })}
          />
        </Filter>
        <Filter id="booking-reference-filter" label="Reference">
          <Input
            id="booking-reference-filter"
            type="search"
            className="num w-56"
            placeholder="VRMS-20261020-0001"
            autoComplete="off"
            value={filters.reference ?? ''}
            onChange={(event) => filter({ reference: event.target.value })}
          />
        </Filter>
      </div>
      {bookings.isPending ? (
        <LoadingState label="Loading your bookings…" />
      ) : bookings.isError ? (
        <ErrorState title="We couldn’t load your bookings" error={bookings.error} onRetry={() => void bookings.refetch()} />
      ) : bookings.data.count === 0 ? (
        narrowed ? (
          <EmptyState
            title="No bookings match these filters"
            description="Change the dates, vehicle type or reference, or clear them to see every booking."
          />
        ) : (
          <EmptyState
            title={status ? `No ${status} bookings` : 'No bookings yet'}
            description="Find a vehicle that is free for your dates and book it."
          />
        )
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
