import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Star } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDate, formatDateTime } from '@/lib/dates'

import {
  type AddOn,
  type AddOnChoice,
  createBooking,
  getQuote,
  getVehicle,
  listAddOns,
  type Period,
  type VehicleDetail,
} from './api'
import { BookingRefusal } from './BookingRefusal'
import { addOnsKey, quoteKey, vehicleKey } from './keys'
import { PriceSummary, TermsList } from './PriceSummary'

const BOOKING_FIELDS = ['terms_accepted', 'safety_notice_acknowledged', 'add_ons', 'discount_code']

function readPeriod(params: URLSearchParams): Period | null {
  const pickup = params.get('pickup_datetime')
  const ret = params.get('return_datetime')
  return pickup && ret ? { pickup_datetime: pickup, return_datetime: ret } : null
}

/** Search.Detail: photographs, specification, tariff, deposit, policies, rating, last service. */
function VehicleFacts({ vehicle }: { vehicle: VehicleDetail }) {
  const { currency } = useAgency()
  const spec = [
    vehicle.fuel_type,
    vehicle.colour,
    vehicle.transmission,
    vehicle.seating_capacity ? `${vehicle.seating_capacity} seats` : null,
    vehicle.engine_cc ? `${vehicle.engine_cc} cc` : null,
  ].filter(Boolean)
  return (
    <Card>
      <CardContent className="grid gap-4">
        {vehicle.photos.length ? (
          <ul aria-label="Photographs" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {vehicle.photos.map((url, index) => (
              <li key={url}>
                <img
                  src={url}
                  alt={`${vehicle.brand} ${vehicle.model}, photo ${index + 1} of ${vehicle.photos.length}`}
                  className="aspect-[4/3] w-full rounded-md object-cover"
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No photographs have been added yet.</p>
        )}
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{vehicle.category}</Badge>
          <Badge variant="outline">{vehicle.vehicle_type}</Badge>
        </div>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Specification</dt>
          <dd>{spec.join(' · ')}</dd>
          <dt className="text-muted-foreground">Pickup branch</dt>
          <dd>{vehicle.home_branch}</dd>
          <dt className="text-muted-foreground">Rating</dt>
          <dd className="flex items-center gap-1">
            {vehicle.average_rating ? (
              <>
                <Star className="size-3.5 fill-current text-amber-500" aria-hidden="true" />
                {Number(vehicle.average_rating).toFixed(1)} out of 5
              </>
            ) : (
              'No ratings yet'
            )}
          </dd>
          <dt className="text-muted-foreground">Last serviced</dt>
          <dd>{vehicle.last_service_date ? formatDate(vehicle.last_service_date) : 'Not recorded'}</dd>
          {vehicle.tariff ? (
            <>
              <dt className="text-muted-foreground">Tariff</dt>
              <dd>
                {formatCurrency(vehicle.tariff.hourly_rate, currency)} per hour,{' '}
                {formatCurrency(vehicle.tariff.daily_rate, currency)} per day
              </dd>
            </>
          ) : null}
          <dt className="text-muted-foreground">Security deposit</dt>
          <dd>{formatCurrency(vehicle.security_deposit, currency)}, refundable</dd>
        </dl>
      </CardContent>
    </Card>
  )
}

function AddOnPicker({
  addOns,
  chosen,
  onChange,
}: {
  addOns: AddOn[]
  chosen: Record<number, number>
  onChange: (next: Record<number, number>) => void
}) {
  const { currency } = useAgency()
  if (!addOns.length) return null
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-medium">Add-ons, charged per day</legend>
      {addOns.map((addOn) => {
        const id = `addon-${addOn.id}`
        const quantity = chosen[addOn.id]
        return (
          <div key={addOn.id} className="flex flex-wrap items-center gap-3">
            <label htmlFor={id} className="flex min-h-10 items-center gap-2 text-sm">
              <input
                id={id}
                type="checkbox"
                className="size-4 accent-[var(--brand)]"
                checked={quantity !== undefined}
                onChange={(event) => {
                  const next = { ...chosen }
                  if (event.target.checked) next[addOn.id] = 1
                  else delete next[addOn.id]
                  onChange(next)
                }}
              />
              {addOn.name} ({formatCurrency(addOn.daily_rate, currency)} per day)
            </label>
            {quantity !== undefined ? (
              <label className="flex items-center gap-2 text-sm">
                Quantity
                <Input
                  type="number"
                  min={1}
                  step={1}
                  value={quantity}
                  className="h-9 w-20"
                  aria-label={`Quantity of ${addOn.name}`}
                  onChange={(event) => {
                    const value = Number.parseInt(event.target.value, 10)
                    onChange({ ...chosen, [addOn.id]: Number.isInteger(value) && value > 0 ? value : 1 })
                  }}
                />
              </label>
            ) : null}
          </div>
        )
      })}
    </fieldset>
  )
}

function BookingForm({ vehicle, period }: { vehicle: VehicleDetail; period: Period }) {
  const navigate = useNavigate()
  const [chosen, setChosen] = useState<Record<number, number>>({})
  const [codeInput, setCodeInput] = useState('')
  const [appliedCode, setAppliedCode] = useState('')
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const twoWheeler = vehicle.vehicle_type === 'Two-Wheeler'

  const addOns = useQuery({ queryKey: addOnsKey(vehicle.vehicle_type), queryFn: () => listAddOns(vehicle.vehicle_type) })
  const choices: AddOnChoice[] = Object.entries(chosen).map(([id, quantity]) => ({
    add_on: Number(id),
    quantity,
  }))
  const quote = useQuery({
    queryKey: quoteKey(vehicle.id, period, choices, appliedCode),
    queryFn: () => getQuote(vehicle.id, period, choices, appliedCode),
    placeholderData: keepPreviousData,
  })
  const codeError =
    quote.error instanceof ApiError ? quote.error.fieldErrors.discount_code?.join(' ') : undefined

  const book = useMutation({
    mutationFn: () =>
      createBooking({
        vehicle: vehicle.id,
        ...period,
        add_ons: choices,
        discount_code: appliedCode,
        terms_accepted: termsAccepted,
        safety_notice_acknowledged: safetyAcknowledged,
      }),
    onSuccess: (booking) => navigate(`/app/bookings/${booking.id}/pay`),
    onError: (error) => {
      if (error instanceof ApiError && !error.code) {
        const mine = Object.fromEntries(
          Object.entries(error.fieldErrors)
            .filter(([field]) => BOOKING_FIELDS.includes(field))
            .map(([field, messages]) => [field, messages.join(' ')]),
        )
        setFieldErrors(mine)
        const others = Object.entries(error.fieldErrors).filter(([field]) => !BOOKING_FIELDS.includes(field))
        setFormError(others.length ? others.flatMap(([, messages]) => messages).join(' ') : Object.keys(mine).length ? null : error.message)
      }
    },
  })

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    setFormError(null)
    // Usability checks only; the server checks both again (CO-3).
    const errors: Record<string, string> = {}
    if (!termsAccepted) errors.terms_accepted = 'Accept the rental terms to continue.'
    if (twoWheeler && !safetyAcknowledged)
      errors.safety_notice_acknowledged = 'Read and acknowledge the safety notice.'
    setFieldErrors(errors)
    if (Object.keys(errors).length) return
    book.mutate()
  }

  const refusal = book.error instanceof ApiError && book.error.code ? book.error : null

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Book this vehicle</h2>
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {formatDateTime(period.pickup_datetime)} to {formatDateTime(period.return_datetime)}, collected at{' '}
          {vehicle.home_branch}.
        </p>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="grid gap-5" aria-label="Book this vehicle">
          <BookingRefusal error={refusal} />
          <FormAlert message={formError} />

          {addOns.isError ? (
            <p className="text-sm text-muted-foreground">Add-ons could not be loaded; you can book without them.</p>
          ) : (
            <AddOnPicker addOns={addOns.data ?? []} chosen={chosen} onChange={setChosen} />
          )}
          {fieldErrors.add_ons ? <p className="text-sm text-destructive">{fieldErrors.add_ons}</p> : null}

          <div className="grid gap-1.5">
            <label htmlFor="discount-code" className="text-sm font-medium">
              Discount code
            </label>
            <div className="flex gap-2">
              <Input
                id="discount-code"
                value={codeInput}
                autoComplete="off"
                className="max-w-56"
                aria-invalid={codeError ? true : undefined}
                aria-describedby={codeError ? 'discount-code-error' : undefined}
                onChange={(event) => setCodeInput(event.target.value)}
              />
              <Button type="button" variant="outline" className="h-10" onClick={() => setAppliedCode(codeInput.trim())}>
                Apply
              </Button>
              {appliedCode ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="h-10"
                  onClick={() => {
                    setAppliedCode('')
                    setCodeInput('')
                  }}
                >
                  Remove
                </Button>
              ) : null}
            </div>
            {codeError ? (
              <p id="discount-code-error" className="text-sm text-destructive">
                {codeError}
              </p>
            ) : null}
          </div>

          <div aria-live="polite" aria-busy={quote.isFetching}>
            {quote.data && !codeError ? (
              <PriceSummary quote={quote.data} />
            ) : quote.isPending ? (
              <LoadingState label="Working out the price…" />
            ) : codeError ? null : (
              <ErrorState title="We couldn’t work out the price" error={quote.error} onRetry={() => void quote.refetch()} />
            )}
          </div>

          {quote.data ? (
            <section aria-labelledby="terms-heading" className="grid gap-2">
              <h3 id="terms-heading" className="text-sm font-semibold">
                Rental terms
              </h3>
              <TermsList terms={quote.data.terms} />
            </section>
          ) : null}

          <div className="grid gap-1">
            <label htmlFor="accept-terms" className="flex items-start gap-2 text-sm">
              <input
                id="accept-terms"
                type="checkbox"
                className="mt-0.5 size-4 accent-[var(--brand)]"
                checked={termsAccepted}
                aria-invalid={fieldErrors.terms_accepted ? true : undefined}
                aria-describedby={fieldErrors.terms_accepted ? 'accept-terms-error' : undefined}
                onChange={(event) => setTermsAccepted(event.target.checked)}
              />
              I accept the rental terms above.
            </label>
            {fieldErrors.terms_accepted ? (
              <p id="accept-terms-error" className="text-sm text-destructive">
                {fieldErrors.terms_accepted}
              </p>
            ) : null}
          </div>

          {twoWheeler ? (
            <div className="grid gap-2 rounded-md border p-3">
              <p className="text-sm font-medium">Safety notice</p>
              <p className="text-sm text-muted-foreground">
                One helmet per rider is included with this two-wheeler. Every rider must wear a helmet while
                riding.
              </p>
              <label htmlFor="accept-safety" className="flex items-start gap-2 text-sm">
                <input
                  id="accept-safety"
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--brand)]"
                  checked={safetyAcknowledged}
                  aria-invalid={fieldErrors.safety_notice_acknowledged ? true : undefined}
                  aria-describedby={fieldErrors.safety_notice_acknowledged ? 'accept-safety-error' : undefined}
                  onChange={(event) => setSafetyAcknowledged(event.target.checked)}
                />
                I have read the safety notice.
              </label>
              {fieldErrors.safety_notice_acknowledged ? (
                <p id="accept-safety-error" className="text-sm text-destructive">
                  {fieldErrors.safety_notice_acknowledged}
                </p>
              ) : null}
            </div>
          ) : null}

          <div>
            <SubmitButton busy={book.isPending} busyLabel="Holding the vehicle…" disabled={!quote.data || Boolean(codeError)}>
              Hold this vehicle and pay
            </SubmitButton>
            <p className="mt-2 text-xs text-muted-foreground">
              We hold the vehicle for you for 15 minutes while you pay.
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

/** Search.Detail, then Book.Create for the period chosen in the search. */
export function VehicleDetailPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const period = readPeriod(params)
  const vehicleId = Number(id)
  const vehicle = useQuery({
    queryKey: vehicleKey(vehicleId),
    queryFn: () => getVehicle(vehicleId),
    enabled: Number.isInteger(vehicleId),
  })
  const title = vehicle.data ? `${vehicle.data.brand} ${vehicle.data.model} (${vehicle.data.year})` : 'Vehicle'

  return (
    <section className="max-w-3xl">
      <Button asChild variant="ghost" size="lg" className="mb-2 -ml-2 h-10">
        <Link to={period ? `/app/search?${new URLSearchParams({ ...period, branch: String(vehicle.data?.home_branch_id ?? '') })}` : '/app/search'}>
          <ArrowLeft aria-hidden="true" />
          Back to search
        </Link>
      </Button>
      <PageHeader title={title} />
      {vehicle.isPending ? (
        <LoadingState label="Loading the vehicle…" />
      ) : vehicle.isError ? (
        <ErrorState title="We couldn’t load this vehicle" error={vehicle.error} onRetry={() => void vehicle.refetch()} />
      ) : (
        <div className="grid gap-6">
          <VehicleFacts vehicle={vehicle.data} />
          {vehicle.data.terms ? (
            <section aria-labelledby="policies-heading" className="grid gap-2">
              <h2 id="policies-heading" className="text-lg font-semibold">
                Policies
              </h2>
              <TermsList terms={vehicle.data.terms} />
            </section>
          ) : null}
          {!vehicle.data.tariff ? (
            <EmptyState title="Not bookable yet" description="No price has been published for this category." />
          ) : period ? (
            <BookingForm vehicle={vehicle.data} period={period} />
          ) : (
            <EmptyState
              title="Choose your dates first"
              description="Search with a pickup branch and a period to book this vehicle."
              action={
                <Button asChild className="h-10">
                  <Link to="/app/search">Search vehicles</Link>
                </Button>
              }
            />
          )}
        </div>
      )}
    </section>
  )
}
