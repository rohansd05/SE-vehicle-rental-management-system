// Modify / Cancel Booking (Exp 2 UC 4), Book.Extend and "rebook" (UC 5
// extension 5a). Every dialog shows the money before the customer confirms
// with their password (SE-9); the server prices and checks everything and
// refuses if the amounts shown have changed (CO-3).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field, FormAlert, StatusMessage } from '@/components/form'
import { LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime, now } from '@/lib/dates'

import {
  type BookingDetail,
  type CancellationQuote,
  type ExtensionQuote,
  type ExtraPayment,
  type ModificationQuote,
  type ModificationRequest,
  cancelBooking,
  extendBooking,
  getCancellationQuote,
  listAddOns,
  modifyBooking,
  newIdempotencyKey,
  quoteExtension,
  quoteModification,
} from '@/features/booking/api'
import { BOOKINGS_KEY, addOnsKey, cancelQuoteKey } from '@/features/booking/keys'
import { AddOnPicker } from '@/features/booking/VehicleDetailPage'
import { MethodPicker } from '@/features/payment/MethodPicker'
import { type MethodChoice, initialChoice, methodRequest } from '@/features/payment/method'
import { PasswordDialog } from '@/features/payment/PasswordDialog'
import { listBranches } from '@/features/search/api'
import { BRANCHES_KEY } from '@/features/search/keys'
import { isoToLocal, localToISO } from '@/features/search/schema'

const ZERO = '0.00'
const percent = (value: string) => `${value.replace(/\.0+$/, '')}%`

/** Itemised amounts (UI-4): label left, mono amount right, never wrapped (B14). */
function Amounts({ rows }: { rows: [label: string, amount: string][] }) {
  const { currency } = useAgency()
  return (
    <dl className="grid grid-cols-[minmax(0,1fr)_max-content] gap-x-6 gap-y-1 border-y py-3 text-sm">
      {rows.map(([label, amount]) => (
        <Fragment key={label}>
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="num-strong text-right whitespace-nowrap">{formatCurrency(amount, currency)}</dd>
        </Fragment>
      ))}
    </dl>
  )
}

/** The fields of an extra charge: card or on-line only (BR-9 keeps cash for collection). */
function extraPayment(choice: MethodChoice, password: string): ExtraPayment {
  const request = methodRequest(choice)
  return { ...request, method: request.method === 'online' ? 'online' : 'card', idempotency_key: newIdempotencyKey(), password }
}

const noPayment = (password: string): ExtraPayment => ({
  method: 'card',
  payment_token: '',
  channel: '',
  upi_id: '',
  idempotency_key: newIdempotencyKey(),
  password,
})

function useRefreshBookings() {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: BOOKINGS_KEY })
}

// ─── Cancel (Book.Cancel, Book.Cancel.Release) ────────────────────────────

function CancelQuoteSummary({ bookingId }: { bookingId: number }) {
  const quote = useQuery({ queryKey: cancelQuoteKey(bookingId), queryFn: () => getCancellationQuote(bookingId) })
  if (quote.isPending) return <LoadingState label="Working out your refund…" />
  if (quote.isError) return <FormAlert message={quote.error.message} />
  const refund = quote.data
  if (refund.deposit_refund === ZERO) {
    return <StatusMessage message="Nothing has been paid for this booking, so there is nothing to refund." />
  }
  return (
    <div className="grid gap-2">
      <Amounts
        rows={[
          [`Rental refund, ${percent(refund.refund_percent)} of the rental`, refund.rental_refund],
          ['Security deposit, refunded in full', refund.deposit_refund],
          ['Total refund', refund.total_refund],
        ]}
      />
      {refund.awaits_approval ? (
        <p className="text-small text-muted-foreground">
          Part of this refund is above our automatic approval limit; it is issued once an administrator approves it.
        </p>
      ) : null}
    </div>
  )
}

function CancelBooking({ booking }: { booking: BookingDetail }) {
  const queryClient = useQueryClient()
  const refresh = useRefreshBookings()
  const key = cancelQuoteKey(booking.id)
  return (
    <PasswordDialog
      id="cancel-booking"
      trigger="Cancel booking"
      variant="outline"
      title="Cancel this booking?"
      description={
        <>
          {booking.vehicle.brand} {booking.vehicle.model}, collected at {booking.pickup_branch} on{' '}
          <span className="num whitespace-nowrap">{formatDateTime(booking.pickup_datetime)}</span>. The vehicle is
          released at once and the refund follows the cancellation policy in your booking terms.
        </>
      }
      submitLabel="Cancel booking"
      busyLabel="Cancelling…"
      cancelLabel="Keep booking"
      check={() => (queryClient.getQueryData(key) ? null : 'Wait until the refund is shown.')}
      onConfirm={async (password) => {
        const quote = queryClient.getQueryData<CancellationQuote>(key)
        if (!quote) throw new Error('Wait until the refund is shown.')
        try {
          await cancelBooking(booking.id, { expected_refund: quote.total_refund, password })
        } catch (error) {
          void queryClient.invalidateQueries({ queryKey: key }) // refund_changed: show the new amount
          throw error
        }
        refresh()
      }}
    >
      <CancelQuoteSummary bookingId={booking.id} />
    </PasswordDialog>
  )
}

// ─── Modify (Book.Modify, Book.Modify.Price; UC 4 extension 3a) ───────────

function ModificationSummary({
  quote,
  choice,
  onChoice,
}: {
  quote: ModificationQuote
  choice: MethodChoice
  onChoice: (next: MethodChoice) => void
}) {
  const rows: [string, string][] = [
    ['Current total', quote.previous_total],
    ['New total', quote.new_total],
  ]
  if (quote.extra_charge !== ZERO) rows.push(['To pay now', quote.extra_charge])
  if (quote.refund_amount !== ZERO) {
    rows.push([`Refund, ${percent(quote.refund_percent)} of the difference`, quote.refund_amount])
  }
  return (
    <div className="grid gap-4">
      <Amounts rows={rows} />
      {quote.extra_charge === ZERO && quote.refund_amount === ZERO ? (
        <p className="text-small text-muted-foreground">The price does not change.</p>
      ) : null}
      {quote.extra_charge !== ZERO ? <MethodPicker value={choice} onChange={onChoice} allowCash={false} /> : null}
    </div>
  )
}

function Alternatives({
  quote,
  busy,
  onTake,
}: {
  quote: ModificationQuote
  busy: boolean
  onTake: (vehicleId: number) => void
}) {
  return (
    <div className="grid gap-3">
      <StatusMessage
        message={`The ${quote.vehicle.brand} ${quote.vehicle.model} is not free for these dates at this branch.`}
      />
      {quote.alternatives.length ? (
        <ul aria-label="Other vehicles at the same price" className="divide-y border-y">
          {quote.alternatives.map((vehicle) => (
            <li key={vehicle.id} className="flex flex-wrap items-center justify-between gap-3 py-2">
              <span className="text-sm">
                {vehicle.brand} {vehicle.model} <span className="num whitespace-nowrap">{vehicle.registration_no}</span>
              </span>
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onTake(vehicle.id)}>
                Take this {vehicle.category}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-small text-muted-foreground">
          No other {quote.vehicle.category} is free then at this branch. Try other dates.
        </p>
      )}
    </div>
  )
}

interface ModifyForm {
  pickup: string
  ret: string
  branch: string
  addOns: Record<number, number>
}

const formOf = (booking: BookingDetail): ModifyForm => ({
  pickup: isoToLocal(booking.pickup_datetime),
  ret: isoToLocal(booking.return_datetime),
  branch: String(booking.pickup_branch_id),
  addOns: Object.fromEntries(booking.add_ons.map((line) => [line.add_on_id, line.quantity])),
})

function ModifyBooking({ booking }: { booking: BookingDetail }) {
  const refresh = useRefreshBookings()
  const [form, setForm] = useState<ModifyForm>(() => formOf(booking))
  const [vehicle, setVehicle] = useState<number | null>(null)
  const [quote, setQuote] = useState<ModificationQuote | null>(null)
  const [choice, setChoice] = useState<MethodChoice>(() => initialChoice())
  const [fieldError, setFieldError] = useState<string | null>(null)
  const branches = useQuery({ queryKey: BRANCHES_KEY, queryFn: listBranches })
  const vehicleType = booking.vehicle.vehicle_type
  const addOns = useQuery({ queryKey: addOnsKey(vehicleType), queryFn: () => listAddOns(vehicleType) })

  const request = (pick: number | null): ModificationRequest => ({
    pickup_datetime: localToISO(form.pickup),
    return_datetime: localToISO(form.ret),
    pickup_branch: Number(form.branch),
    add_ons: Object.entries(form.addOns).map(([id, quantity]) => ({ add_on: Number(id), quantity })),
    vehicle: pick,
  })
  const price = useMutation({
    mutationFn: (pick: number | null) => quoteModification(booking.id, request(pick)),
    onSuccess: (data, pick) => {
      setVehicle(pick)
      setQuote(data)
    },
  })
  const edit = (patch: Partial<ModifyForm>) => {
    setForm((current) => ({ ...current, ...patch }))
    setQuote(null)
    setVehicle(null)
    price.reset()
  }
  const check = () => {
    if (!form.pickup || !form.ret) {
      setFieldError('Choose the pickup and return times.')
      return
    }
    setFieldError(null)
    price.mutate(vehicle)
  }

  return (
    <PasswordDialog
      id="modify-booking"
      trigger="Modify booking"
      variant="outline"
      title="Modify this booking"
      description="Change the period, the pickup branch or the add-ons. We check the vehicle is free and work out the new price before anything changes."
      submitLabel="Confirm the change"
      busyLabel="Saving the change…"
      cancelLabel="Keep the booking as it is"
      check={() =>
        !quote
          ? 'Check the new price first.'
          : !quote.vehicle_free
            ? 'Choose a vehicle that is free, or other dates.'
            : null
      }
      onClose={() => {
        setForm(formOf(booking))
        setQuote(null)
        setVehicle(null)
        price.reset()
      }}
      onConfirm={async (password) => {
        if (!quote) throw new Error('Check the new price first.')
        const payment = quote.extra_charge === ZERO ? noPayment(password) : extraPayment(choice, password)
        try {
          await modifyBooking(booking.id, {
            ...request(vehicle),
            ...payment,
            expected_charge: quote.extra_charge,
            expected_refund: quote.refund_amount,
          })
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) setQuote(null) // check the price again
          throw error
        }
        refresh()
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="modify-pickup" label="Pickup" error={fieldError ?? undefined}>
          <Input
            id="modify-pickup"
            type="datetime-local"
            className="num"
            value={form.pickup}
            onChange={(event) => edit({ pickup: event.target.value })}
          />
        </Field>
        <Field id="modify-return" label="Return">
          <Input
            id="modify-return"
            type="datetime-local"
            className="num"
            value={form.ret}
            onChange={(event) => edit({ ret: event.target.value })}
          />
        </Field>
      </div>
      <Field id="modify-branch" label="Pickup branch">
        <NativeSelect id="modify-branch" value={form.branch} onChange={(event) => edit({ branch: event.target.value })}>
          {(branches.data ?? [{ branch_id: booking.pickup_branch_id, branch_name: booking.pickup_branch }]).map(
            (branch) => (
              <option key={branch.branch_id} value={branch.branch_id}>
                {branch.branch_name}
              </option>
            ),
          )}
        </NativeSelect>
      </Field>
      {addOns.data ? <AddOnPicker addOns={addOns.data} chosen={form.addOns} onChange={(next) => edit({ addOns: next })} /> : null}
      <div>
        <Button type="button" variant="outline" disabled={price.isPending} onClick={check}>
          {price.isPending ? 'Checking…' : 'Check the new price'}
        </Button>
      </div>
      <FormAlert message={price.error instanceof Error ? price.error.message : null} />
      {quote && quote.vehicle_free ? <ModificationSummary quote={quote} choice={choice} onChoice={setChoice} /> : null}
      {quote && !quote.vehicle_free ? (
        <Alternatives quote={quote} busy={price.isPending} onTake={(id) => price.mutate(id)} />
      ) : null}
    </PasswordDialog>
  )
}

// ─── Extend (Book.Extend) ─────────────────────────────────────────────────

function ExtendBooking({ booking }: { booking: BookingDetail }) {
  const refresh = useRefreshBookings()
  const [ret, setRet] = useState(() => isoToLocal(booking.return_datetime))
  const [quote, setQuote] = useState<ExtensionQuote | null>(null)
  const [choice, setChoice] = useState<MethodChoice>(() => initialChoice())
  const price = useMutation({
    mutationFn: () => quoteExtension(booking.id, localToISO(ret)),
    onSuccess: setQuote,
  })
  const reset = () => {
    setQuote(null)
    price.reset()
  }

  return (
    <PasswordDialog
      id="extend-booking"
      trigger="Extend rental"
      variant="outline"
      title="Extend this rental"
      description="Choose a later return time. The extra charge is collected before the extension takes effect."
      submitLabel="Pay and extend"
      busyLabel="Extending…"
      cancelLabel="Keep the current return time"
      check={() => (quote ? null : 'Check the extra charge first.')}
      onClose={() => {
        setRet(isoToLocal(booking.return_datetime))
        reset()
      }}
      onConfirm={async (password) => {
        if (!quote) throw new Error('Check the extra charge first.')
        const payment = quote.extra_charge === ZERO ? noPayment(password) : extraPayment(choice, password)
        try {
          await extendBooking(booking.id, {
            ...payment,
            return_datetime: quote.return_datetime,
            expected_charge: quote.extra_charge,
          })
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) setQuote(null)
          throw error
        }
        refresh()
      }}
    >
      <Field id="extend-return" label="New return time">
        <Input
          id="extend-return"
          type="datetime-local"
          className="num"
          value={ret}
          onChange={(event) => {
            setRet(event.target.value)
            reset()
          }}
        />
      </Field>
      <div>
        <Button type="button" variant="outline" disabled={price.isPending || !ret} onClick={() => price.mutate()}>
          {price.isPending ? 'Checking…' : 'Check the extra charge'}
        </Button>
      </div>
      <FormAlert message={price.error instanceof Error ? price.error.message : null} />
      {quote ? (
        <div className="grid gap-4">
          <Amounts
            rows={[
              ['Current total', quote.previous_total],
              ['New total', quote.price.total_payable],
              ['To pay now', quote.extra_charge],
            ]}
          />
          {quote.extra_charge !== ZERO ? <MethodPicker value={choice} onChange={setChoice} allowCash={false} /> : null}
        </div>
      ) : null}
    </PasswordDialog>
  )
}

// ─── Rebook (Exp 2 UC 5 extension 5a) ─────────────────────────────────────

/** The same length of rental, from tomorrow at the same time of day; the server checks it. */
function rebookPeriod(booking: BookingDetail) {
  const pickup = new Date(booking.pickup_datetime)
  const length = new Date(booking.return_datetime).getTime() - pickup.getTime()
  const start = new Date(now() + 86_400_000)
  start.setHours(pickup.getHours(), pickup.getMinutes(), 0, 0)
  return {
    pickup_datetime: start.toISOString(),
    return_datetime: new Date(start.getTime() + length).toISOString(),
  }
}

function Rebook({ booking }: { booking: BookingDetail }) {
  const navigate = useNavigate()
  return (
    <Button
      variant="outline"
      onClick={() =>
        navigate(`/app/vehicles/${booking.vehicle.id}?${new URLSearchParams(rebookPeriod(booking))}`)
      }
    >
      Book this vehicle again
    </Button>
  )
}

/** UC 4 and Book.Extend actions for the booking's status (Appendix B); the server decides. */
export function BookingActions({ booking }: { booking: BookingDetail }) {
  const unpaidCash = booking.status === 'Pending Payment' && booking.cash_on_collection
  const actions =
    booking.status === 'Confirmed' ? (
      <>
        <ModifyBooking booking={booking} />
        <CancelBooking booking={booking} />
      </>
    ) : unpaidCash ? (
      <CancelBooking booking={booking} />
    ) : booking.status === 'Active' ? (
      <ExtendBooking booking={booking} />
    ) : booking.status === 'Completed' || booking.status === 'Cancelled' || booking.status === 'No-show' ? (
      <Rebook booking={booking} />
    ) : null
  if (!actions) return null
  return (
    <div aria-label="Booking actions" role="group" className="flex flex-wrap gap-3 border-t pt-6">
      {actions}
    </div>
  )
}
