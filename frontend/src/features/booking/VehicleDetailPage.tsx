import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Star } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { representativeImage } from '@/assets/vehicles/registry'
import { FormAlert, SubmitButton } from '@/components/form'
import { PageHeader } from '@/components/page'
import { Photo } from '@/components/photo'
import { StickyRail } from '@/components/sticky-rail'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
  // B12: the vehicle's own photographs first; without them, the representative
  // model (or category) photo, labelled as such, above the existing note.
  const representative = vehicle.photos.length ? null : representativeImage(vehicle)
  return (
    <div className="grid gap-5">
      {vehicle.photos.length ? (
        <ul aria-label="Photographs" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {vehicle.photos.map((url, index) => (
            <li key={url} className="first:col-span-full">
              <img
                src={url}
                alt={`${vehicle.brand} ${vehicle.model}, photo ${index + 1} of ${vehicle.photos.length}`}
                className={cn('w-full object-cover', index === 0 ? 'aspect-[3/2] rounded-xl' : 'aspect-[4/3] rounded-md')}
              />
            </li>
          ))}
        </ul>
      ) : representative ? (
        <div className="grid gap-2">
          <Photo
            id={representative.id}
            alt={representative.alt}
            sizes="(min-width: 1280px) 50vw, (min-width: 768px) 60vw, 100vw"
            aspect="native"
            className="rounded-xl"
          />
          <p className="text-small text-muted-foreground">No photographs have been added yet.</p>
        </div>
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
            </>
          ) : (
            'No ratings yet'
          )}
        </dd>
        <dt className="text-muted-foreground">Last serviced</dt>
        <dd className="num">{vehicle.last_service_date ? formatDate(vehicle.last_service_date) : 'Not recorded'}</dd>
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
              <span className="num">{formatDateTime(period.return_datetime)}</span>, collected at{' '}
              {vehicle.home_branch}.
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
    <section className="stage">
      <Button asChild variant="ghost" size="sm" className="mb-3 -ml-3">
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
      ) : vehicle.data.tariff && period ? (
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
            {!vehicle.data.tariff ? (
              <EmptyState title="Not bookable yet" description="No price has been published for this category." />
            ) : (
              <EmptyState
                title="Choose your dates first"
                description="Search with a pickup branch and a period to book this vehicle."
                action={
                  <Button asChild>
                    <Link to="/app/search">Search vehicles</Link>
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
