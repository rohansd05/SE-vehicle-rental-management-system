import { Bike, Car, Star } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDate } from '@/lib/dates'
import { stagger } from '@/lib/motion'

import type { AvailableVehicle } from './api'

/** The specification line a customer chooses by (Search.Filter fields). */
function specification(vehicle: AvailableVehicle): string {
  const parts = [vehicle.fuel_type, vehicle.colour]
  if (vehicle.transmission) parts.push(vehicle.transmission)
  if (vehicle.seating_capacity) parts.push(`${vehicle.seating_capacity} seats`)
  if (vehicle.engine_cc) parts.push(`${vehicle.engine_cc} cc`)
  return parts.join(' · ')
}

function billedFor(unit: 'day' | 'hour', count: number): string {
  return `${count} ${unit}${count === 1 ? '' : 's'}`
}

/** Search.Price: the estimate for the searched period, marked as one; the deposit apart (Pay.Deposit). */
function Estimate({ vehicle }: { vehicle: AvailableVehicle }) {
  const { currency } = useAgency()
  const estimate = vehicle.estimate
  if (!estimate) {
    return <p className="text-sm text-muted-foreground lg:text-right">No price is published for this category yet.</p>
  }
  return (
    <div className="grid gap-1 lg:text-right">
      <p className="text-sm">
        <span className="text-muted-foreground">Estimated price </span>
        <span className="num text-lead font-medium text-foreground">
          {formatCurrency(estimate.total_payable, currency)}
        </span>
        <span className="text-muted-foreground">
          {' '}
          for {billedFor(estimate.billing_unit, estimate.billing_count)}
        </span>
      </p>
      <p className="text-small text-muted-foreground">
        Includes tax. Add-ons, discounts and usage-based charges are not included.
      </p>
      <p className="text-small text-muted-foreground">
        Refundable security deposit {formatCurrency(estimate.security_deposit, currency)}, held
        separately.
      </p>
    </div>
  )
}

/** One result row (docs/design/ui-brief.md, 6.4): vehicle, rating and service, price, action. */
export function VehicleCard({ vehicle, href }: { vehicle: AvailableVehicle; href: string }) {
  const Icon = vehicle.vehicle_type === 'Two-Wheeler' ? Bike : Car
  return (
    <div className="grid gap-x-8 gap-y-4 py-5 lg:grid-cols-[2.5rem_minmax(0,1fr)_12rem_17rem_auto] lg:items-start">
      <span className="hidden size-10 items-center justify-center rounded-md bg-muted lg:flex" aria-hidden="true">
        <Icon className="size-5 text-ink-muted" />
      </span>
      <div className="min-w-0">
        <h3 className="text-section font-semibold">
          {vehicle.brand} {vehicle.model}{' '}
          <span className="num text-sm font-normal text-muted-foreground">({vehicle.year})</span>
        </h3>
        <p className="mt-0.5 text-sm text-muted-foreground">{specification(vehicle)}</p>
        <p className="mt-1.5 text-small text-muted-foreground">
          <span className="font-medium text-foreground">{vehicle.category}</span>
          {' · '}
          <span>{vehicle.vehicle_type}</span>
        </p>
      </div>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm lg:grid-cols-1 lg:gap-y-0.5">
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
        <dt className="text-muted-foreground lg:mt-2">Last serviced</dt>
        <dd className="num">{vehicle.last_service_date ? formatDate(vehicle.last_service_date) : 'Not recorded'}</dd>
      </dl>
      <Estimate vehicle={vehicle} />
      <Button asChild className="lg:justify-self-end">
        <Link to={href} aria-label={`View and book the ${vehicle.brand} ${vehicle.model}`}>
          View and book
        </Link>
      </Button>
    </div>
  )
}

export function VehicleResults({
  vehicles,
  hrefFor,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  vehicles: AvailableVehicle[]
  hrefFor: (vehicle: AvailableVehicle) => string
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
}) {
  return (
    <div className="grid gap-6">
      <ul aria-label="Available vehicles" className="border-t">
        {vehicles.map((vehicle, index) => (
          <li key={vehicle.id} className="enter border-b" style={stagger(index, 45)}>
            <VehicleCard vehicle={vehicle} href={hrefFor(vehicle)} />
          </li>
        ))}
      </ul>
      {hasPrevious || hasNext ? (
        <nav aria-label="Result pages" className="flex justify-end gap-2">
          <Button variant="outline" disabled={!hasPrevious} onClick={onPrevious}>
            Previous page
          </Button>
          <Button variant="outline" disabled={!hasNext} onClick={onNext}>
            Next page
          </Button>
        </nav>
      ) : null}
    </div>
  )
}
