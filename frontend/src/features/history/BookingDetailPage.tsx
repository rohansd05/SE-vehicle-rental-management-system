import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { FormAlert, StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/dates'

import { type BookingDetail, downloadInvoice, getBooking } from '@/features/booking/api'
import { bookingKey } from '@/features/booking/keys'
import { PriceSummary } from '@/features/booking/PriceSummary'

import { BookingStatusBadge } from './BookingStatusBadge'

function Confirmation({ booking }: { booking: BookingDetail }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
      <dt className="text-muted-foreground">Booking reference</dt>
      <dd className="font-mono font-semibold">{booking.booking_reference}</dd>
      {booking.pickup_code ? (
        <>
          <dt className="text-muted-foreground">Pickup code</dt>
          <dd>
            <span className="font-mono text-lg font-semibold tracking-widest">{booking.pickup_code}</span>
            <span className="block text-xs text-muted-foreground">Show this code at the branch to collect the vehicle.</span>
          </dd>
        </>
      ) : null}
      {booking.transaction_id ? (
        <>
          <dt className="text-muted-foreground">Transaction</dt>
          <dd className="font-mono">{booking.transaction_id}</dd>
        </>
      ) : null}
      {booking.invoice_number ? (
        <>
          <dt className="text-muted-foreground">Invoice</dt>
          <dd className="font-mono">{booking.invoice_number}</dd>
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
    <section className="max-w-2xl">
      <Button asChild variant="ghost" size="lg" className="mb-2 -ml-2 h-10">
        <Link to="/app/bookings">
          <ArrowLeft aria-hidden="true" />
          My bookings
        </Link>
      </Button>
      <PageHeader title={booking.data?.booking_reference ? `Booking ${booking.data.booking_reference}` : 'Booking'} />
      {booking.isPending ? (
        <LoadingState label="Loading the booking…" />
      ) : booking.isError ? (
        <ErrorState title="We couldn’t load this booking" error={booking.error} onRetry={() => void booking.refetch()} />
      ) : (
        <div className="grid gap-6">
          {justConfirmed && booking.data.status === 'Confirmed' ? (
            <StatusMessage
              tone="success"
              message="Your booking is confirmed. Keep the pickup code safe; you will need it at the branch."
            />
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center justify-between gap-2">
                <h2>
                  {booking.data.vehicle.brand} {booking.data.vehicle.model}
                </h2>
                <BookingStatusBadge status={booking.data.status} />
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {formatDateTime(booking.data.pickup_datetime)} to {formatDateTime(booking.data.return_datetime)},
                collected at {booking.data.pickup_branch}.
              </p>
            </CardHeader>
            <CardContent className="grid gap-5">
              {booking.data.booking_reference ? <Confirmation booking={booking.data} /> : null}
              {booking.data.status === 'Pending Payment' || booking.data.status === 'Draft' ? (
                <div>
                  <Button asChild className="h-10">
                    <Link to={`/app/bookings/${booking.data.id}/pay`}>
                      {booking.data.status === 'Draft' ? 'Hold again and pay' : 'Continue to payment'}
                    </Link>
                  </Button>
                </div>
              ) : null}
              <PriceSummary quote={booking.data.price} caption="Price" />
              {booking.data.invoice_number ? (
                <div className="grid gap-2">
                  <FormAlert message={download.error instanceof Error ? download.error.message : null} />
                  <div>
                    <Button
                      variant="outline"
                      className="h-10"
                      disabled={download.isPending}
                      onClick={() => download.mutate(booking.data)}
                    >
                      <Download aria-hidden="true" />
                      {download.isPending ? 'Preparing the invoice…' : `Download invoice ${booking.data.invoice_number}`}
                    </Button>
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  )
}
