import { Bike, Car, Star } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'
import { formatDate } from '@/lib/dates'

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
    return <p className="text-sm text-muted-foreground">No price is published for this category yet.</p>
  }
  return (
    <div className="rounded-md bg-muted/60 px-3 py-2">
      <p className="text-sm">
        <span className="text-muted-foreground">Estimated price </span>
        <span className="text-base font-semibold">{formatCurrency(estimate.total_payable, currency)}</span>
        <span className="text-muted-foreground">
          {' '}
          for {billedFor(estimate.billing_unit, estimate.billing_count)}
        </span>
      </p>
      <p className="text-xs text-muted-foreground">
        Includes tax. Add-ons, discounts and usage-based charges are not included.
      </p>
      <p className="text-xs text-muted-foreground">
        Refundable security deposit {formatCurrency(estimate.security_deposit, currency)}, held
        separately.
      </p>
    </div>
  )
}

export function VehicleCard({ vehicle }: { vehicle: AvailableVehicle }) {
  const Icon = vehicle.vehicle_type === 'Two-Wheeler' ? Bike : Car
  return (
    <Card className="h-full">
      <CardContent className="grid gap-3">
        <div className="flex items-start gap-3">
          <span className="rounded-md bg-muted p-2">
            <Icon className="size-5 text-muted-foreground" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <h3 className="font-semibold">
              {vehicle.brand} {vehicle.model}{' '}
              <span className="font-normal text-muted-foreground">({vehicle.year})</span>
            </h3>
            <p className="text-sm text-muted-foreground">{specification(vehicle)}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{vehicle.category}</Badge>
          <Badge variant="outline">{vehicle.vehicle_type}</Badge>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
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
        </dl>
        <Estimate vehicle={vehicle} />
      </CardContent>
    </Card>
  )
}

export function VehicleResults({
  vehicles,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  vehicles: AvailableVehicle[]
  hasPrevious: boolean
  hasNext: boolean
  onPrevious: () => void
  onNext: () => void
}) {
  return (
    <div className="grid gap-4">
      <ul aria-label="Available vehicles" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {vehicles.map((vehicle) => (
          <li key={vehicle.id}>
            <VehicleCard vehicle={vehicle} />
          </li>
        ))}
      </ul>
      {hasPrevious || hasNext ? (
        <nav aria-label="Result pages" className="flex gap-2">
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
