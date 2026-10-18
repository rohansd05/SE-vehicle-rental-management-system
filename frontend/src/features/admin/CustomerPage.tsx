import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  type AdminCustomerDetail,
  cancelCustomerBooking,
  cancellationQuote,
  type CancellationQuote,
  getCustomer,
  type OpenBooking,
  setBlacklisted,
} from '@/api/admin'
import { StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { StickyRail } from '@/components/sticky-rail'
import { TONE_PILL } from '@/components/status-tone'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PasswordDialog } from '@/features/payment/PasswordDialog'
import { formatINR } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { DETAILS_LIST, RAIL_LAYOUT } from '@/lib/layout'

import { CUSTOMERS_KEY, customerKey } from './keys'
import { ReasonDialog } from './ReasonDialog'
import { BlacklistBadge } from './UsersPage'

/** R2's BR-8 refund for cancelling now, loaded when the dialog opens. */
function RefundQuote({ customerId, bookingId, onQuote }: { customerId: number; bookingId: number; onQuote: (quote: CancellationQuote) => void }) {
  const quote = useQuery({
    queryKey: ['admin', 'cancel-quote', bookingId],
    queryFn: () => cancellationQuote(customerId, bookingId),
  })
  useEffect(() => {
    if (quote.data) onQuote(quote.data)
  }, [quote.data, onQuote])
  if (quote.isPending) return <LoadingState label="Working out the refund…" />
  if (quote.isError) return <ErrorState title="We couldn’t work out the refund" error={quote.error} />
  const data = quote.data
  return (
    <p className="text-sm">
      Refund now (BR-8): <span className="num-strong">{formatINR(data.total_refund)}</span>, being{' '}
      {Number(data.refund_percent)}% of the rental ({formatINR(data.rental_refund)}) and the whole deposit (
      {formatINR(data.deposit_refund)}).{data.awaits_approval ? ' Part of it waits for an Administrator’s approval.' : ''}
    </p>
  )
}

function BookingRow({ customer, booking, onCancelled }: { customer: AdminCustomerDetail; booking: OpenBooking; onCancelled: (note: string) => void }) {
  const [quote, setQuote] = useState<CancellationQuote | null>(null)
  return (
    <li className="grid gap-x-8 gap-y-3 border-b py-5 @xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_auto] @xl:items-center">
      <span className="grid min-w-0 gap-1.5">
        <span className="num font-medium whitespace-nowrap">{booking.booking_reference}</span>
        <span>
          {booking.return_pending ? (
            <Badge variant="secondary" className={TONE_PILL.booked}>
              Return pending
            </Badge>
          ) : (
            <Badge variant="secondary" className={TONE_PILL.available}>
              {booking.status}
            </Badge>
          )}
        </span>
      </span>
      <span className="grid min-w-0 gap-1 text-sm">
        <span>
          <span className="num">{booking.registration_no}</span> · {booking.vehicle}, {booking.pickup_branch}
        </span>
        <span className="text-muted-foreground">
          <span className="num whitespace-nowrap">{formatDateTime(booking.pickup_datetime)}</span> to{' '}
          <span className="num whitespace-nowrap">{formatDateTime(booking.return_datetime)}</span>
        </span>
        <Link
          to={`/app/audit?entity_type=bookings.Booking&entity_id=${booking.id}`}
          className="text-sm text-primary underline"
          aria-label={`View the booking's history for ${booking.booking_reference}`}
        >
          View the booking's history
        </Link>
      </span>
      <span>
        {booking.return_pending ? (
          <span className="text-sm text-muted-foreground">The vehicle is out; it is returned as usual.</span>
        ) : customer.is_blacklisted ? (
          <PasswordDialog
            id={`cancel-${booking.id}`}
            trigger="Cancel booking"
            variant="destructive"
            title={`Cancel ${booking.booking_reference}?`}
            description={`The vehicle is released, the refund follows the cancellation policy, and ${customer.name} and the branch are told.`}
            submitLabel="Cancel booking"
            busyLabel="Cancelling…"
            cancelLabel="Keep the booking"
            check={() => (quote ? null : 'Wait for the refund to be worked out.')}
            onConfirm={async (password) => {
              await cancelCustomerBooking(customer.customer_id, booking.id, {
                expected_refund: quote?.total_refund ?? '0.00',
                password,
              })
              onCancelled(`${booking.booking_reference} cancelled. The refund has been started.`)
            }}
          >
            <RefundQuote customerId={customer.customer_id} bookingId={booking.id} onQuote={setQuote} />
          </PasswordDialog>
        ) : null}
      </span>
    </li>
  )
}

/** BR-4, UC 12 step 2 and extension 2a: blacklist a customer and decide on their bookings. */
export function CustomerPage() {
  const { id } = useParams()
  const customerId = Number(id)
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const customer = useQuery({ queryKey: customerKey(customerId), queryFn: () => getCustomer(customerId) })

  const changed = (next: AdminCustomerDetail | null, note: string) => {
    if (next) queryClient.setQueryData(customerKey(customerId), next)
    else void queryClient.invalidateQueries({ queryKey: customerKey(customerId) })
    void queryClient.invalidateQueries({ queryKey: CUSTOMERS_KEY })
    setMessage(note)
  }

  const back = (
    <Button asChild variant="ghost" className="mb-2 -ml-2 h-10">
      <Link to="/app/users">
        <ArrowLeft aria-hidden="true" />
        Back to users
      </Link>
    </Button>
  )
  if (customer.isPending || customer.isError) {
    return (
      <section>
        {back}
        <PageHeader title="Customer" />
        {customer.isPending ? (
          <LoadingState label="Loading the customer…" />
        ) : (
          <ErrorState title="We couldn’t load this customer" error={customer.error} onRetry={() => void customer.refetch()} />
        )}
      </section>
    )
  }
  const data = customer.data
  return (
    <section>
      {back}
      <PageHeader
        title={data.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            {data.is_blacklisted ? <BlacklistBadge /> : null}
            {data.email}, <span className="num">{data.mobile_no}</span>
          </span>
        }
      />
      <div className="mb-6">
        <StatusMessage message={message} tone="success" />
      </div>
      <div className={RAIL_LAYOUT}>
        <div className="grid min-w-0 content-start gap-8">
          {data.is_blacklisted ? (
            <div className="@container">
              <dl className={DETAILS_LIST}>
                <dt className="text-muted-foreground">Reason</dt>
                <dd className="font-medium">{data.blacklist_reason ?? '—'}</dd>
                <dt className="text-muted-foreground">Blacklisted</dt>
                <dd className="font-medium">
                  {data.blacklisted_by ?? '—'}, {formatDateTime(data.blacklisted_at)}
                </dd>
                <dt className="text-muted-foreground">Outstanding due</dt>
                <dd className="num font-medium">{formatINR(data.outstanding_due)}</dd>
              </dl>
            </div>
          ) : null}
          <section aria-labelledby="customer-bookings" className="grid gap-4">
            <h2 id="customer-bookings">Confirmed and active bookings</h2>
            {data.open_bookings.length === 0 ? (
              <EmptyState title="No open bookings" description="This customer has no Confirmed or Active booking." />
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {data.is_blacklisted
                    ? 'Decide on each Confirmed booking (UC 12 extension 2a). An Active rental is returned as usual.'
                    : 'Blacklisting does not cancel these; you then decide on each Confirmed booking.'}
                </p>
                <ul aria-label="Open bookings" className="@container border-t">
                  {data.open_bookings.map((booking) => (
                    <BookingRow key={booking.id} customer={data} booking={booking} onCancelled={(note) => changed(null, note)} />
                  ))}
                </ul>
              </>
            )}
          </section>
        </div>
        <StickyRail>
          <div className="grid gap-4 lg:pt-1">
            {data.is_blacklisted ? (
              <ReasonDialog
                id="lift"
                trigger="Take off the blacklist"
                title={`Take ${data.name} off the blacklist?`}
                description="They can make bookings again (BR-4)."
                submitLabel="Take off the blacklist"
                busyLabel="Saving…"
                cancelLabel="Keep blacklisted"
                onConfirm={async (reason) => changed(await setBlacklisted(data.customer_id, false, reason), `${data.name} can book again.`)}
              />
            ) : (
              <ReasonDialog
                id="blacklist"
                trigger="Blacklist customer"
                variant="destructive"
                title={`Blacklist ${data.name}?`}
                description="They can no longer make bookings (BR-4). Their Confirmed bookings are then listed for you to decide on."
                submitLabel="Blacklist customer"
                busyLabel="Blacklisting…"
                cancelLabel="Keep as is"
                onConfirm={async (reason) =>
                  changed(await setBlacklisted(data.customer_id, true, reason), `${data.name} is blacklisted.`)
                }
              />
            )}
          </div>
        </StickyRail>
      </div>
    </section>
  )
}
