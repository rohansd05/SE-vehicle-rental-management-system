import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { FormAlert, StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/lib/dates'

import { type BookingDetail, downloadInvoice, getBooking } from '@/features/booking/api'
import { bookingKey } from '@/features/booking/keys'
import { PriceSummary } from '@/features/booking/PriceSummary'
import { RAIL_LAYOUT } from '@/lib/layout'

import { BookingStatusBadge } from './BookingStatusBadge'

function Confirmation({ booking }: { booking: BookingDetail }) {
  return (
    <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[10rem_minmax(0,1fr)]">
      <dt className="text-muted-foreground">Booking reference</dt>
      <dd className="num font-medium">{booking.booking_reference}</dd>
      {booking.pickup_code ? (
        <>
          <dt className="text-muted-foreground sm:pt-1">Pickup code</dt>
          <dd>
            <span className="num-lg block tracking-[0.25em] text-foreground">
              {booking.pickup_code}
            </span>
            <span className="block text-small text-muted-foreground">Show this code at the branch to collect the vehicle.</span>
          </dd>
        </>
      ) : null}
      {booking.transaction_id ? (
        <>
          <dt className="text-muted-foreground">Transaction</dt>
          <dd className="num break-all">{booking.transaction_id}</dd>
        </>
      ) : null}
      {booking.invoice_number ? (
        <>
          <dt className="text-muted-foreground">Invoice</dt>
          <dd className="num">{booking.invoice_number}</dd>
        </>
      ) : null}
    </dl>
  )
}

/** One booking: Pay.Confirm.OK after payment, the itemised price, and the invoice (History.Download). */
export function BookingDetailPage() {
  const { id } = useParams()
  const bookingId = Number(id)
  const location = useLocation()
  const justConfirmed = Boolean((location.state as { confirmed?: boolean } | null)?.confirmed)
  const booking = useQuery({
    queryKey: bookingKey(bookingId),
    queryFn: () => getBooking(bookingId),
    enabled: Number.isInteger(bookingId),
  })
  const download = useMutation({
    mutationFn: (detail: BookingDetail) => downloadInvoice(detail.id, detail.invoice_number ?? 'invoice'),
  })

  return (
    <section className="stage">
      <Button asChild variant="ghost" size="sm" className="mb-3 -ml-3">
        <Link to="/app/bookings">
          <ArrowLeft aria-hidden="true" />
          My bookings
        </Link>
      </Button>
      <PageHeader
        title={booking.data?.booking_reference ? `Booking ${booking.data.booking_reference}` : 'Booking'}
        photo="band-bookings-1"
      />
      {booking.isPending ? (
        <LoadingState label="Loading the booking…" />
      ) : booking.isError ? (
        <ErrorState title="We couldn’t load this booking" error={booking.error} onRetry={() => void booking.refetch()} />
      ) : (
        <div className={RAIL_LAYOUT}>
          <div className="grid gap-8">
            {justConfirmed && booking.data.status === 'Confirmed' ? (
              <StatusMessage
                tone="success"
                message="Your booking is confirmed. Keep the pickup code safe; you will need it at the branch."
              />
            ) : null}
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-section">
                  {booking.data.vehicle.brand} {booking.data.vehicle.model}
                </h2>
                <BookingStatusBadge status={booking.data.status} />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                <span className="num">{formatDateTime(booking.data.pickup_datetime)}</span> to{' '}
                <span className="num">{formatDateTime(booking.data.return_datetime)}</span>, collected at{' '}
                {booking.data.pickup_branch}.
              </p>
            </div>
            {booking.data.booking_reference ? (
              <div className="reveal border-t pt-6">
                <Confirmation booking={booking.data} />
              </div>
            ) : null}
            {booking.data.status === 'Pending Payment' || booking.data.status === 'Draft' ? (
              <div className="border-t pt-6">
                <Button asChild>
                  <Link to={`/app/bookings/${booking.data.id}/pay`}>
                    {booking.data.status === 'Draft' ? 'Hold again and pay' : 'Continue to payment'}
                  </Link>
                </Button>
              </div>
            ) : null}
            {booking.data.invoice_number ? (
              <div className="reveal grid gap-3 border-t pt-6">
                <FormAlert message={download.error instanceof Error ? download.error.message : null} />
                <div>
                  <Button
                    variant="outline"
                    disabled={download.isPending}
                    onClick={() => download.mutate(booking.data)}
                  >
                    <Download aria-hidden="true" />
                    {download.isPending ? 'Preparing the invoice…' : `Download invoice ${booking.data.invoice_number}`}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
          <StickyRail>
            <div className="lg:pt-1">
              <PriceSummary quote={booking.data.price} caption="Price" />
            </div>
          </StickyRail>
        </div>
      )}
    </section>
  )
}
