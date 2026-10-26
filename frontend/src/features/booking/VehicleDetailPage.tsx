import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Star } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { representativeImage } from '@/assets/vehicles/registry'
import { Field, FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { StickyRail } from '@/components/sticky-rail'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/features/auth/auth-context'
import { useCatalogueBase } from '@/features/search/paths'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDate, formatDateTime } from '@/lib/dates'
import { RAIL_LAYOUT } from '@/lib/layout'
import { cn } from '@/lib/utils'

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

const BOOKING_FIELDS = [
  'terms_accepted',
  'safety_notice_acknowledged',
  'add_ons',
  'discount_code',
  'delivery_address',
  'delivery_pincode',
]

/** Book.Addons: the doorstep delivery add-on, known by its name (BR-7, Book.Deliver.Location). */
const isDelivery = (addOn: AddOn) => addOn.name.trim().toLowerCase() === 'doorstep delivery'


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
  // B12: the representative model (or category) photo leads, labelled as such;
  // the vehicle's own photographs follow as a smaller gallery. Without a
  // representative photo, the own photographs lead as before.
  const representative = representativeImage(vehicle)
  const gallery = (
    <ul aria-label="Photographs" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {vehicle.photos.map((url, index) => {
        const lead = index === 0 && !representative
        return (
          <li key={url} className={cn(lead && 'col-span-full')}>
            <img
              src={url}
              alt={`${vehicle.brand} ${vehicle.model}, photo ${index + 1} of ${vehicle.photos.length}`}
              className={cn('w-full object-cover', lead ? 'aspect-[3/2] rounded-xl' : 'aspect-[4/3] rounded-md')}
            />
          </li>
        )
      })}
    </ul>
  )
  return (
    <div className="grid gap-5">
      {representative ? (
        <div className="grid gap-2">
          <Photo
            id={representative.id}
            alt={representative.alt}
            sizes="(min-width: 1280px) 50vw, (min-width: 768px) 60vw, 100vw"
            aspect="native"
            className="rounded-xl"
          />
          <p className="text-small text-muted-foreground">Representative image</p>
          {vehicle.photos.length ? null : (
            <p className="text-small text-muted-foreground">No photographs have been added yet.</p>
          )}
        </div>
      ) : null}
      {representative && vehicle.photos.length ? (
        <section aria-labelledby="vehicle-photos-heading" className="grid gap-2">
          <h2 id="vehicle-photos-heading" className="text-small font-medium">
            Vehicle photos
          </h2>
          {gallery}
        </section>
      ) : representative ? null : vehicle.photos.length ? (
        gallery
      ) : (
        <p className="flex aspect-[3/1] items-center justify-center rounded-md bg-muted text-sm text-muted-foreground sm:aspect-[5/1]">
          No photographs have been added yet.
        </p>
      )}
      <p className="text-small text-muted-foreground">
        <span className="font-medium text-foreground">{vehicle.category}</span>
        {' · '}
        <span>{vehicle.vehicle_type}</span>
      </p>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[9rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Specification</dt>
        <dd>{spec.join(' · ')}</dd>
        <dt className="text-muted-foreground">Pickup branch</dt>
        <dd>{vehicle.home_branch}</dd>
        <dt className="text-muted-foreground">Rating</dt>
        <dd className="flex items-center gap-1">
          {vehicle.average_rating ? (
            <>
              <Star className="size-3.5 fill-current text-signal" aria-hidden="true" />
              {Number(vehicle.average_rating).toFixed(1)} out of 5
              <span className="text-muted-foreground">
                ({vehicle.rating_count === 1 ? '1 rating' : `${vehicle.rating_count} ratings`})
              </span>
            </>
          ) : (
            'No ratings yet'
          )}
        </dd>
        <dt className="text-muted-foreground">Last serviced</dt>
        <dd className="num">{vehicle.last_service_date ? formatDate(vehicle.last_service_date) : 'Not recorded'}</dd>
        {vehicle.tariff ? (
          <>
            <dt className="text-muted-foreground">Free distance</dt>
            <dd>
              {vehicle.tariff.free_km_allowance_per_day} km per day, then{' '}
              {formatCurrency(vehicle.tariff.excess_km_rate, currency)} per km
            </dd>
          </>
        ) : null}
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
    </div>
  )
}

function Policies({ vehicle }: { vehicle: VehicleDetail }) {
  if (!vehicle.terms) return null
  return (
    <section aria-labelledby="policies-heading" className="reveal grid gap-3 border-t pt-6">
      <h2 id="policies-heading" className="text-section">
        Policies
      </h2>
      <TermsList terms={vehicle.terms} />
    </section>
  )
}

export function AddOnPicker({
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
    <fieldset className="grid gap-1">
      <legend className="heading mb-2 text-section">Add-ons, charged per day</legend>
      <div className="divide-y border-y">
        {addOns.map((addOn) => {
          const id = `addon-${addOn.id}`
          const quantity = chosen[addOn.id]
          return (
            <div key={addOn.id} className="flex min-h-12 flex-wrap items-center gap-x-6 gap-y-2 py-1">
              <label htmlFor={id} className="flex min-h-12 flex-1 items-center gap-3 text-sm tabular-nums">
                <input
                  id={id}
                  type="checkbox"
                  className="size-4"
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
                <label className="enter flex items-center gap-2 text-sm text-muted-foreground">
                  Quantity
                  <Input
                    type="number"
                    min={1}
                    step={1}
                    value={quantity}
                    className="h-8 w-20"
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
      </div>
    </fieldset>
  )
}

/**
 * Book.Create. One form across both columns: the facts, add-ons, discount
 * code and terms in the main column, the price and the action in the rail.
 */
function BookingForm({ vehicle, period, children }: { vehicle: VehicleDetail; period: Period; children: ReactNode }) {
  const navigate = useNavigate()
  const [chosen, setChosen] = useState<Record<number, number>>({})
  const [codeInput, setCodeInput] = useState('')
  const [appliedCode, setAppliedCode] = useState('')
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [safetyAcknowledged, setSafetyAcknowledged] = useState(false)
  const [deliveryAddress, setDeliveryAddress] = useState('')
  const [deliveryPincode, setDeliveryPincode] = useState('')
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
  const delivery = (addOns.data ?? []).some((addOn) => isDelivery(addOn) && chosen[addOn.id] !== undefined)

  const book = useMutation({
    mutationFn: () =>
      createBooking({
        vehicle: vehicle.id,
        ...period,
        add_ons: choices,
        discount_code: appliedCode,
        terms_accepted: termsAccepted,
        safety_notice_acknowledged: safetyAcknowledged,
        delivery_address: delivery ? deliveryAddress : '',
        delivery_pincode: delivery ? deliveryPincode : '',
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
    if (delivery && !deliveryAddress.trim())
      errors.delivery_address = 'Enter the address we should deliver the vehicle to.'
    if (delivery && !/^[0-9]{6}$/.test(deliveryPincode))
      errors.delivery_pincode = 'Enter the six-digit pincode of the delivery address.'
    setFieldErrors(errors)
    if (Object.keys(errors).length) return
    book.mutate()
  }

  const refusal = book.error instanceof ApiError && book.error.code ? book.error : null

  return (
    <form onSubmit={onSubmit} noValidate className={RAIL_LAYOUT} aria-label="Book this vehicle">
      <div className="grid gap-8">
        <BookingRefusal error={refusal} />
        <FormAlert message={formError} />
        {children}

        <div className="reveal grid gap-2 border-t pt-6">
          {addOns.isError ? (
            <p className="text-sm text-muted-foreground">Add-ons could not be loaded; you can book without them.</p>
          ) : (
            <AddOnPicker addOns={addOns.data ?? []} chosen={chosen} onChange={setChosen} />
          )}
          {fieldErrors.add_ons ? <p className="text-small font-medium text-destructive">{fieldErrors.add_ons}</p> : null}
        </div>

        {delivery ? (
          // Book.Deliver.Location: the server checks the pincode against the branch's areas.
          <fieldset className="enter grid gap-4">
            <legend className="heading mb-1 text-subsection">Delivery address</legend>
            <Field id="delivery-address" label="Address" error={fieldErrors.delivery_address}>
              <Textarea
                id="delivery-address"
                rows={3}
                autoComplete="street-address"
                value={deliveryAddress}
                aria-invalid={fieldErrors.delivery_address ? true : undefined}
                aria-describedby={fieldErrors.delivery_address ? 'delivery-address-error' : undefined}
                onChange={(event) => setDeliveryAddress(event.target.value)}
              />
            </Field>
            <Field
              id="delivery-pincode"
              label="Pincode"
              hint={`We deliver within the areas served by our ${vehicle.home_branch} branch.`}
              error={fieldErrors.delivery_pincode}
            >
              <Input
                id="delivery-pincode"
                inputMode="numeric"
                autoComplete="postal-code"
                maxLength={6}
                className="max-w-40"
                value={deliveryPincode}
                aria-invalid={fieldErrors.delivery_pincode ? true : undefined}
                aria-describedby={
                  fieldErrors.delivery_pincode ? 'delivery-pincode-hint delivery-pincode-error' : 'delivery-pincode-hint'
                }
                onChange={(event) => setDeliveryPincode(event.target.value.trim())}
              />
            </Field>
          </fieldset>
        ) : null}

        <div className="grid gap-1.5">
          <label htmlFor="discount-code" className="text-label font-medium">
            Discount code
          </label>
          <div className="flex flex-wrap gap-2">
            <Input
              id="discount-code"
              value={codeInput}
              autoComplete="off"
              className="num max-w-56"
              aria-invalid={codeError ? true : undefined}
              aria-describedby={codeError ? 'discount-code-error' : undefined}
              onChange={(event) => setCodeInput(event.target.value)}
            />
            <Button type="button" variant="outline" onClick={() => setAppliedCode(codeInput.trim())}>
              Apply
            </Button>
            {appliedCode ? (
              <Button
                type="button"
                variant="ghost"
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
            <p id="discount-code-error" className="text-small font-medium text-destructive">
              {codeError}
            </p>
          ) : null}
        </div>

        {quote.data ? (
          <section aria-labelledby="terms-heading" className="reveal grid gap-3 border-t pt-6">
            <h3 id="terms-heading" className="text-subsection">
              Rental terms
            </h3>
            <TermsList terms={quote.data.terms} />
          </section>
        ) : null}

        <div className="grid gap-1">
          <label htmlFor="accept-terms" className="flex items-start gap-3 text-sm">
            <input
              id="accept-terms"
              type="checkbox"
              className="mt-[3px] size-4"
              checked={termsAccepted}
              aria-invalid={fieldErrors.terms_accepted ? true : undefined}
              aria-describedby={fieldErrors.terms_accepted ? 'accept-terms-error' : undefined}
              onChange={(event) => setTermsAccepted(event.target.checked)}
            />
            I accept the rental terms above.
          </label>
          {fieldErrors.terms_accepted ? (
            <p id="accept-terms-error" className="text-small font-medium text-destructive">
              {fieldErrors.terms_accepted}
            </p>
          ) : null}
        </div>

        {twoWheeler ? (
          <div className="grid gap-2 border-l-2 border-l-status-maintenance pl-4">
            <p className="text-sm font-medium">Safety notice</p>
            <p className="text-sm text-muted-foreground">
              One helmet per rider is included with this two-wheeler. Every rider must wear a helmet while
              riding.
            </p>
            <label htmlFor="accept-safety" className="flex items-start gap-3 text-sm">
              <input
                id="accept-safety"
                type="checkbox"
                className="mt-[3px] size-4"
                checked={safetyAcknowledged}
                aria-invalid={fieldErrors.safety_notice_acknowledged ? true : undefined}
                aria-describedby={fieldErrors.safety_notice_acknowledged ? 'accept-safety-error' : undefined}
                onChange={(event) => setSafetyAcknowledged(event.target.checked)}
              />
              I have read the safety notice.
            </label>
            {fieldErrors.safety_notice_acknowledged ? (
              <p id="accept-safety-error" className="text-small font-medium text-destructive">
                {fieldErrors.safety_notice_acknowledged}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>

      <StickyRail>
        <div className="grid gap-5 lg:pt-1">
          <div>
            <h2 className="text-section">Book this vehicle</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              <span className="num">{formatDateTime(period.pickup_datetime)}</span> to{' '}
              <span className="num">{formatDateTime(period.return_datetime)}</span>
              {delivery ? `, delivered from ${vehicle.home_branch}.` : `, collected at ${vehicle.home_branch}.`}
            </p>
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

          <div className="border-t pt-5">
            <SubmitButton
              busy={book.isPending}
              busyLabel="Holding the vehicle…"
              disabled={!quote.data || Boolean(codeError)}
              className="sm:w-full"
            >
              Hold this vehicle and pay
            </SubmitButton>
            <p className="mt-2 text-small text-muted-foreground">
              We hold the vehicle for you for 15 minutes while you pay.
            </p>
          </div>
        </div>
      </StickyRail>
    </form>
  )
}

/**
 * Search.Browse: a guest sees the vehicle and its price but books only after
 * signing in or registering, which brings them back to this vehicle and these
 * dates inside the app. A signed-in customer on the public page goes there too.
 */
function SignInToBook({ vehicleId, period }: { vehicleId: number; period: Period }) {
  const { status, user } = useAuth()
  const target = { pathname: `/app/vehicles/${vehicleId}`, search: `?${new URLSearchParams({ ...period })}` }
  if (status === 'signed-in' && user?.role === 'CUSTOMER') {
    return (
      <EmptyState
        title="Book this vehicle"
        description="Hold it for 15 minutes and pay to confirm."
        action={
          <Button asChild>
            <Link to={`${target.pathname}${target.search}`}>Book this vehicle</Link>
          </Button>
        }
      />
    )
  }
  if (status === 'signed-in') {
    return <EmptyState title="Booking is for customers" description="Sign in with a customer account to book." />
  }
  return (
    <EmptyState
      title="Sign in to book"
      description="Sign in or register to hold this vehicle for these dates; we bring you back here."
      action={
        <div className="flex flex-wrap gap-3">
          <Button asChild>
            <Link to="/login" state={{ from: target }}>
              Sign in to book
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/register" state={{ from: target }}>
              Register to book
            </Link>
          </Button>
        </div>
      }
    />
  )
}

/** Search.Detail, then Book.Create for the period chosen in the search. */
export function VehicleDetailPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const period = readPeriod(params)
  const base = useCatalogueBase()
  const vehicleId = Number(id)
  const vehicle = useQuery({
    queryKey: vehicleKey(vehicleId),
    queryFn: () => getVehicle(vehicleId),
    enabled: Number.isInteger(vehicleId),
  })
  const title = vehicle.data ? `${vehicle.data.brand} ${vehicle.data.model} (${vehicle.data.year})` : 'Vehicle'

  return (
    <section className="stage">
      <Button asChild variant="ghost" size="sm" className="mb-3 -ml-3">
        <Link to={period ? `${base}/search?${new URLSearchParams({ ...period, branch: String(vehicle.data?.home_branch_id ?? '') })}` : `${base}/search`}>
          <ArrowLeft aria-hidden="true" />
          Back to search
        </Link>
      </Button>
      <PageHeader title={title} />
      {vehicle.isPending ? (
        <LoadingState label="Loading the vehicle…" />
      ) : vehicle.isError ? (
        <ErrorState title="We couldn’t load this vehicle" error={vehicle.error} onRetry={() => void vehicle.refetch()} />
      ) : vehicle.data.tariff && period && base && !vehicle.data.service_overdue ? (
        <BookingForm vehicle={vehicle.data} period={period}>
          <VehicleFacts vehicle={vehicle.data} />
          <Policies vehicle={vehicle.data} />
        </BookingForm>
      ) : (
        <div className={RAIL_LAYOUT}>
          <div className="grid gap-8">
            <VehicleFacts vehicle={vehicle.data} />
            <Policies vehicle={vehicle.data} />
          </div>
          <StickyRail>
            {vehicle.data.service_overdue ? (
              // SA-2: never booked while overdue for its preventive service (BR-15).
              <EmptyState
                title="Not bookable: service overdue"
                description="This vehicle is due for its safety service. Please choose another vehicle."
              />
            ) : !vehicle.data.tariff ? (
              <EmptyState title="Not bookable yet" description="No price has been published for this category." />
            ) : period ? (
              <SignInToBook vehicleId={vehicle.data.id} period={period} />
            ) : (
              <EmptyState
                title="Choose your dates first"
                description="Search with a pickup branch and a period to book this vehicle."
                action={
                  <Button asChild>
                    <Link to={`${base}/search`}>Search vehicles</Link>
                  </Button>
                }
              />
            )}
          </StickyRail>
        </div>
      )}
    </section>
  )
}
