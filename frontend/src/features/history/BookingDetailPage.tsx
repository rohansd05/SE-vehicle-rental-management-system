import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router-dom'

import { FormAlert, StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDate, formatDateTime } from '@/lib/dates'

import { type BookingDetail, downloadInvoice, getBooking } from '@/features/booking/api'
import { bookingKey } from '@/features/booking/keys'
import { PriceSummary } from '@/features/booking/PriceSummary'
import { RAIL_LAYOUT } from '@/lib/layout'

import { BookingActions } from './BookingActions'
import { BookingStatusBadge } from './BookingStatusBadge'

type Refund = BookingDetail['refunds'][number]

/** Pay.Refund, UC 13: where each refund stands, in the customer's words. */
function refundState(refund: Refund): string {
  switch (refund.status) {
    case 'Pending Approval':
      return 'Waiting for approval.'
    case 'Approved':
      return 'Approved; collect it in cash at the branch.'
    case 'Issued':
      return refund.refund_due_by
        ? `Issued to your original payment method; it reaches you by ${formatDate(refund.refund_due_by)}.`
        : 'Issued to your original payment method.'
    case 'Rejected':
      return `Not approved: ${refund.rejection_reason}`
    default:
      return 'The payment provider could not complete it; our staff will contact you.'
  }
}

function Refunds({ refunds }: { refunds: Refund[] }) {
  const { currency } = useAgency()
  return (
    <div className="reveal grid gap-3 border-t pt-6">
      <h2 className="text-section">Refunds</h2>
      <ul className="divide-y border-y">
        {refunds.map((refund) => (
          <li key={refund.id} className="grid gap-1 py-3 text-sm">
            <span>
              <span className="num-strong whitespace-nowrap">{formatCurrency(refund.amount, currency)}</span> of the{' '}
              {refund.purpose.toLowerCase()}: {refund.reason}
            </span>
            <span className="text-muted-foreground">{refundState(refund)}</span>
            {refund.refund_transaction_id ? (
              <span className="num whitespace-nowrap text-muted-foreground">{refund.refund_transaction_id}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** BR-9: cash at collection; the booking waits for the branch to record the payment. */
function CashNote({ booking }: { booking: BookingDetail }) {
  const { currency } = useAgency()
  return (
    <StatusMessage
      message={
        <>
          You chose to pay in cash when you collect the vehicle. Bring{' '}
          <span className="num whitespace-nowrap">{formatCurrency(booking.price.total_payable, currency)}</span> for the
          rental and <span className="num whitespace-nowrap">{formatCurrency(booking.price.security_deposit, currency)}</span>{' '}
          for the refundable deposit to {booking.pickup_branch}. The booking is confirmed when the branch records your
          payment; the vehicle is held for you until{' '}
          <span className="num whitespace-nowrap">{formatDateTime(booking.hold_expires_at)}</span>.
        </>
      }
    />
  )
}

function Confirmation({ booking }: { booking: BookingDetail }) {
  return (
    // B14: label above value until the column is 28rem wide; references never wrap.
    <div className="@container">
    <dl className="grid gap-x-6 gap-y-1 text-sm @md:grid-cols-[10rem_minmax(0,1fr)] @md:gap-y-3">
      <dt className="text-muted-foreground">Booking reference</dt>
      <dd className="num font-medium whitespace-nowrap">{booking.booking_reference}</dd>
      {booking.pickup_code ? (
        <>
          <dt className="mt-2 text-muted-foreground @md:mt-0 @md:pt-1">Pickup code</dt>
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
          <dt className="mt-2 text-muted-foreground @md:mt-0">Transaction</dt>
          <dd className="num whitespace-nowrap">{booking.transaction_id}</dd>
        </>
      ) : null}
      {booking.invoice_number ? (
        <>
          <dt className="mt-2 text-muted-foreground @md:mt-0">Invoice</dt>
          <dd className="num whitespace-nowrap">{booking.invoice_number}</dd>
        </>
      ) : null}
    </dl>
    </div>
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
      <PageHeader title={booking.data?.booking_reference ? `Booking ${booking.data.booking_reference}` : 'Booking'} />
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
            {booking.data.status === 'Pending Payment' && booking.data.cash_on_collection ? (
              <CashNote booking={booking.data} />
            ) : null}
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
            <BookingActions booking={booking.data} />
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
            {booking.data.refunds.length ? <Refunds refunds={booking.data.refunds} /> : null}
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
