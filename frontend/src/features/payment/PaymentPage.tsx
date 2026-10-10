import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Field, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { ErrorState, LoadingState } from '@/components/states'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDateTime, now } from '@/lib/dates'
import { describedBy } from '@/lib/form'

import { type BookingDetail, getBooking, holdAgain, newIdempotencyKey, payBooking } from '@/features/booking/api'
import { BookingRefusal } from '@/features/booking/BookingRefusal'
import { BOOKINGS_KEY, bookingKey } from '@/features/booking/keys'
import { PriceSummary } from '@/features/booking/PriceSummary'

/**
 * Sandbox tokens (SI-1, Testability: "a test mode in which the payment ...
 * integrations use sandbox endpoints"). A live gateway's hosted fields would
 * produce the token instead; no card number ever reaches VRMS (CO-2).
 */
const TEST_TOKENS = [
  { value: 'tok_visa', label: 'Test card that is approved' },
  { value: 'tok_decline', label: 'Test card that is declined' },
] as const

/** Seconds until `iso`, ticking once a second (Book.Hold: the 15-minute hold). */
function useSecondsUntil(iso: string | null | undefined) {
  const [current, setCurrent] = useState(() => now())
  useEffect(() => {
    if (!iso) return
    const timer = setInterval(() => setCurrent(now()), 1000)
    return () => clearInterval(timer)
  }, [iso])
  if (!iso) return 0
  return Math.max(0, Math.floor((new Date(iso).getTime() - current) / 1000))
}

function HoldTimer({ booking }: { booking: BookingDetail }) {
  const seconds = useSecondsUntil(booking.hold_expires_at)
  const minutes = Math.floor(seconds / 60)
  const label = `${minutes}:${String(seconds % 60).padStart(2, '0')}`
  return (
    <p className="flex items-center gap-2 text-sm" aria-live={seconds <= 60 ? 'polite' : 'off'}>
      <Clock className="size-4" aria-hidden="true" />
      {seconds > 0 ? (
        <span>
          The vehicle is held for you for <strong>{label}</strong> more.
        </span>
      ) : (
        <span>Your hold has run out. Paying now may ask you to hold the vehicle again.</span>
      )}
    </p>
  )
}

function PaymentForm({ booking, onPaid }: { booking: BookingDetail; onPaid: (confirmed: BookingDetail) => void }) {
  const queryClient = useQueryClient()
  const { currency } = useAgency()
  const [token, setToken] = useState<string>(TEST_TOKENS[0].value)
  const [password, setPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)

  const pay = useMutation({
    // A fresh key per attempt: a repeat of the same request never charges twice (Pay.Idempotent).
    mutationFn: () =>
      payBooking(booking.id, { payment_token: token, idempotency_key: newIdempotencyKey(), password }),
    onSuccess: onPaid,
    onError: (error) => {
      setPassword('')
      const message = error instanceof ApiError ? error.fieldErrors.password?.join(' ') : undefined
      setPasswordError(message ?? null)
    },
  })

  const rehold = useMutation({
    mutationFn: () => holdAgain(booking.id),
    onSuccess: (held) => {
      pay.reset()
      queryClient.setQueryData(bookingKey(held.id), held)
    },
  })

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!password) {
      setPasswordError('Enter your password to confirm the payment.')
      return
    }
    setPasswordError(null)
    pay.mutate()
  }

  const refusal = pay.error instanceof ApiError && pay.error.code ? pay.error : null
  const total = formatCurrency(booking.price.total_payable, currency)
  const deposit = formatCurrency(booking.price.security_deposit, currency)

  return (
    <form onSubmit={onSubmit} noValidate className="grid gap-5" aria-label="Pay for this booking">
      <BookingRefusal error={refusal ?? rehold.error} onHoldAgain={() => rehold.mutate()} holding={rehold.isPending} />
      <fieldset className="grid gap-2">
        <legend className="mb-1 text-sm font-medium">Payment method (sandbox)</legend>
        <p className="text-xs text-muted-foreground">
          This is the test mode: no real money moves and no card details are entered here.
        </p>
        {TEST_TOKENS.map((option) => (
          <label key={option.value} className="flex min-h-10 items-center gap-2 text-sm">
            <input
              type="radio"
              name="payment_token"
              value={option.value}
              className="size-4 accent-[var(--brand)]"
              checked={token === option.value}
              onChange={() => setToken(option.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>
      <Field
        id="pay-password"
        label="Your password"
        hint="For your security we ask for your password before every payment."
        error={passwordError ?? undefined}
      >
        <Input
          id="pay-password"
          type="password"
          autoComplete="current-password"
          value={password}
          aria-invalid={passwordError ? true : undefined}
          aria-describedby={describedBy('pay-password', { hint: true, error: Boolean(passwordError) })}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
      <div>
        <SubmitButton busy={pay.isPending} busyLabel="Authorising payment…">
          Pay {total} and hold {deposit} deposit
        </SubmitButton>
      </div>
    </form>
  )
}

/** Pay.Authorize: pay for a held booking (Exp 4 sequence 1, Payment.authorize()). */
export function PaymentPage() {
  const { id } = useParams()
  const bookingId = Number(id)
  const queryClient = useQueryClient()
  const [justPaid, setJustPaid] = useState(false)
  const booking = useQuery({
    queryKey: bookingKey(bookingId),
    queryFn: () => getBooking(bookingId),
    enabled: Number.isInteger(bookingId),
  })
  const rehold = useMutation({
    mutationFn: () => holdAgain(bookingId),
    onSuccess: (held) => queryClient.setQueryData(bookingKey(held.id), held),
  })

  if (booking.data && booking.data.status !== 'Pending Payment' && booking.data.status !== 'Draft') {
    // Pay.Confirm.OK: right after paying, the confirmation page says so.
    return <Navigate to={`/app/bookings/${bookingId}`} replace state={justPaid ? { confirmed: true } : undefined} />
  }

  return (
    <section className="max-w-2xl">
      <PageHeader title="Pay for your booking" />
      {booking.isPending ? (
        <LoadingState label="Loading your booking…" />
      ) : booking.isError ? (
        <ErrorState title="We couldn’t load this booking" error={booking.error} onRetry={() => void booking.refetch()} />
      ) : (
        <div className="grid gap-6">
          <Card>
            <CardHeader>
              <CardTitle>
                <h2>
                  {booking.data.vehicle.brand} {booking.data.vehicle.model}
                </h2>
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {formatDateTime(booking.data.pickup_datetime)} to {formatDateTime(booking.data.return_datetime)},
                collected at {booking.data.pickup_branch}.
              </p>
            </CardHeader>
            <CardContent>
              <PriceSummary quote={booking.data.price} />
            </CardContent>
          </Card>
          <Card>
            <CardContent className="grid gap-4">
              {booking.data.status === 'Draft' ? (
                <BookingRefusal
                  error={
                    rehold.error ??
                    new ApiError(409, 'The 15-minute hold on this vehicle has expired. Hold it again to pay.', {
                      code: 'hold_expired',
                    })
                  }
                  onHoldAgain={() => rehold.mutate()}
                  holding={rehold.isPending}
                />
              ) : (
                <>
                  <HoldTimer booking={booking.data} />
                  <PaymentForm
                    booking={booking.data}
                    onPaid={(confirmed) => {
                      setJustPaid(true)
                      queryClient.setQueryData(bookingKey(confirmed.id), confirmed)
                      void queryClient.invalidateQueries({ queryKey: BOOKINGS_KEY })
                    }}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </section>
  )
}
