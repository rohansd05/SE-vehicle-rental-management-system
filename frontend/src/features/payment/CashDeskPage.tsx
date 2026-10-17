import { useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useState } from 'react'

import { Field, StatusMessage } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import { newIdempotencyKey } from '@/features/booking/api'
import { BOOKINGS_KEY } from '@/features/booking/keys'

import { type CashDueBooking, listAwaitingCash, listRefunds, payOutCashRefund, recordCash, type Refund } from './api'
import { AWAITING_CASH_KEY, REFUNDS_KEY, refundsKey } from './keys'
import { PasswordDialog } from './PasswordDialog'

const ROW = 'enter grid min-w-0 gap-x-8 gap-y-3 border-b py-5 @xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto] @xl:items-center'

/** BR-9: record the cash a customer pays at collection; the booking is then confirmed (Book.Done). */
function RecordCashDialog({ booking, onDone }: { booking: CashDueBooking; onDone: (message: string) => void }) {
  const { currency } = useAgency()
  const [amount, setAmount] = useState('')
  const id = `cash-${booking.id}`
  return (
    <PasswordDialog
      id={id}
      trigger="Record cash"
      title="Record the cash received"
      description={`${booking.customer_name} pays ${formatCurrency(booking.total_amount, currency)} for the rental and ${formatCurrency(booking.security_deposit, currency)} for the refundable deposit. You are recorded as the staff member who received it.`}
      submitLabel="Record cash and confirm"
      busyLabel="Recording the cash…"
      cancelLabel="Not now"
      check={() => (amount.trim() ? null : 'Enter the cash you received.')}
      onClose={() => setAmount('')}
      onConfirm={async (password) => {
        const confirmed = await recordCash(booking.id, {
          amount_received: amount.trim(),
          idempotency_key: newIdempotencyKey(),
          password,
        })
        onDone(`Cash recorded. Booking ${confirmed.booking_reference} is confirmed.`)
      }}
    >
      <Field id={`${id}-amount`} label="Cash received" hint={`The rental and the deposit together, in ${currency}.`}>
        <Input
          id={`${id}-amount`}
          inputMode="decimal"
          className="num max-w-48"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </Field>
    </PasswordDialog>
  )
}

/** Pay.Refund: an approved cash refund, paid out and acknowledged at the counter. */
function PayOutDialog({ refund, onDone }: { refund: Refund; onDone: (message: string) => void }) {
  const { currency } = useAgency()
  const [acknowledged, setAcknowledged] = useState(false)
  const id = `payout-${refund.id}`
  return (
    <PasswordDialog
      id={id}
      trigger="Pay out"
      title="Pay out the cash refund"
      description={`Hand ${formatCurrency(refund.amount, currency)} to ${refund.customer_name}. You are recorded as the staff member who paid it.`}
      submitLabel="Record the payout"
      busyLabel="Recording the payout…"
      cancelLabel="Not now"
      check={() => (acknowledged ? null : 'The customer must acknowledge the cash first.')}
      onClose={() => setAcknowledged(false)}
      onConfirm={async (password) => {
        await payOutCashRefund(refund.id, password)
        onDone(`Cash refund of ${formatCurrency(refund.amount, currency)} paid out.`)
      }}
    >
      <div className="flex items-start gap-3">
        <input
          id={`${id}-ack`}
          type="checkbox"
          className="mt-1 size-4"
          checked={acknowledged}
          onChange={(event) => setAcknowledged(event.target.checked)}
        />
        <Label htmlFor={`${id}-ack`} className="leading-snug">
          The customer has received the cash and acknowledged it.
        </Label>
      </div>
    </PasswordDialog>
  )
}

function Section({ id, title, count, children }: { id: string; title: string; count?: number; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 id={id}>{title}</h2>
        {count ? <p className="text-sm text-muted-foreground">{count} waiting.</p> : null}
      </div>
      {children}
    </section>
  )
}

/** BR-9 and Pay.Refund at the branch counter (Branch Staff only; the API scopes both lists). */
export function CashDeskPage() {
  const queryClient = useQueryClient()
  const { currency } = useAgency()
  const [flash, setFlash] = useState<string | null>(null)
  const collections = useQuery({ queryKey: AWAITING_CASH_KEY, queryFn: listAwaitingCash })
  const payouts = useQuery({ queryKey: refundsKey('Approved'), queryFn: () => listRefunds('Approved') })

  const done = (message: string) => {
    setFlash(message)
    void queryClient.invalidateQueries({ queryKey: AWAITING_CASH_KEY })
    void queryClient.invalidateQueries({ queryKey: REFUNDS_KEY })
    void queryClient.invalidateQueries({ queryKey: BOOKINGS_KEY })
  }

  return (
    <section>
      <PageHeader
        title="Cash desk"
        description="Record the cash customers pay when they collect, and pay out approved cash refunds."
        photo="step-collect-1"
        variant="compact"
      />
      <div className="mb-4">
        <StatusMessage message={flash} tone="success" />
      </div>
      <div className="grid gap-10">
        <Section id="cash-collections" title="Waiting for cash" count={collections.data?.count}>
          {collections.isPending ? (
            <LoadingState label="Loading the collections…" rows={2} />
          ) : collections.isError ? (
            <ErrorState title="We couldn’t load the collections" error={collections.error} onRetry={() => void collections.refetch()} />
          ) : collections.data.results.length === 0 ? (
            <EmptyState title="No cash to collect" description="No customer of your branch is waiting to pay in cash." />
          ) : (
            <ul className="@container border-t">
              {collections.data.results.map((booking, index) => (
                <li key={booking.id} className={ROW} style={stagger(index)}>
                  <span className="grid min-w-0 gap-1.5">
                    <span className="font-medium">{booking.customer_name}</span>
                    <span className="num text-sm whitespace-nowrap text-muted-foreground">{booking.customer_mobile}</span>
                  </span>
                  <span className="grid min-w-0 gap-1.5 text-sm">
                    <span>
                      {booking.vehicle.brand} {booking.vehicle.model} ·{' '}
                      <span className="num whitespace-nowrap">{booking.vehicle.registration_no}</span>
                    </span>
                    <span className="text-muted-foreground">
                      Pickup <span className="num whitespace-nowrap text-foreground">{formatDateTime(booking.pickup_datetime)}</span>
                      {' · '}
                      <span className="num whitespace-nowrap text-foreground">{formatCurrency(booking.total_amount, currency)}</span> rental,{' '}
                      <span className="num whitespace-nowrap text-foreground">{formatCurrency(booking.security_deposit, currency)}</span> deposit
                    </span>
                  </span>
                  <span>
                    <RecordCashDialog booking={booking} onDone={done} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section id="cash-refunds" title="Cash refunds to pay out" count={payouts.data?.count}>
          {payouts.isPending ? (
            <LoadingState label="Loading the refunds…" rows={1} />
          ) : payouts.isError ? (
            <ErrorState title="We couldn’t load the refunds" error={payouts.error} onRetry={() => void payouts.refetch()} />
          ) : payouts.data.results.length === 0 ? (
            <EmptyState title="No cash refunds to pay" description="Approved cash refunds for your branch appear here." />
          ) : (
            <ul className="@container border-t">
              {payouts.data.results.map((refund, index) => (
                <li key={refund.id} className={ROW} style={stagger(index)}>
                  <span className="grid min-w-0 gap-1.5">
                    <span className="font-medium">{refund.customer_name}</span>
                    <span className="num text-sm whitespace-nowrap text-muted-foreground">{refund.booking_reference}</span>
                  </span>
                  <span className="grid min-w-0 gap-1.5 text-sm">
                    <span className="num-strong whitespace-nowrap">{formatCurrency(refund.amount, currency)}</span>
                    <span className="text-muted-foreground">{refund.reason}</span>
                  </span>
                  <span>
                    <PayOutDialog refund={refund} onDone={done} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </section>
  )
}
