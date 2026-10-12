import { Bike, Car, Fuel, Gauge, Palette, Settings2, Star, Users, type LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'

import { representativeImage } from '@/assets/vehicles/registry'
import { Photo } from '@/components/photo'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/dates'

import type { AvailableVehicle } from './api'
import { specification } from './spec'
import { Estimate } from './Estimate'

/**
 * Image-led vehicle tile (binding decision B12, imagery-brief.md 3): the car
 * photo leads, then the name, a spec row, rating and service, the estimate
 * and the action. Search results carry no photos, so the representative
 * model photo (or the category photo) is shown with honest alt text.
 */
export function VehicleTile({ vehicle, href }: { vehicle: AvailableVehicle; href: string }) {
  const image = representativeImage(vehicle)
  const TypeIcon = vehicle.vehicle_type === 'Two-Wheeler' ? Bike : Car
  // Only fields the API returns for this vehicle (cars: transmission, seats; two-wheelers: engine).
  const specs: { icon: LucideIcon; text: string }[] = [
    { icon: Fuel, text: vehicle.fuel_type },
    ...(vehicle.transmission ? [{ icon: Settings2, text: vehicle.transmission }] : []),
    ...(vehicle.seating_capacity ? [{ icon: Users, text: `${vehicle.seating_capacity} seats` }] : []),
    ...(vehicle.engine_cc ? [{ icon: Gauge, text: `${vehicle.engine_cc} cc` }] : []),
    { icon: Palette, text: vehicle.colour },
  ]
  return (
    <article className="group/tile flex h-full flex-col overflow-hidden rounded-xl border bg-surface transition-[transform,border-color] duration-200 ease-out hover:-translate-y-0.5 hover:border-line-strong">
      {image ? (
        <Photo id={image.id} alt={image.alt} sizes="(min-width: 1280px) 30vw, (min-width: 640px) 45vw, 100vw" className="aspect-[3/2]" />
      ) : (
        <div className="flex aspect-[3/2] items-center justify-center bg-canvas-sunken" aria-hidden="true">
          <TypeIcon className="size-10 text-ink-subtle" />
        </div>
      )}
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div>
          <h3 className="text-subsection">
            {vehicle.brand} {vehicle.model}{' '}
            <span className="num font-normal text-muted-foreground">({vehicle.year})</span>
          </h3>
          <p className="mt-0.5 text-small text-muted-foreground">
            <span className="font-medium text-foreground">{vehicle.category}</span>
            {' · '}
            <span>{vehicle.vehicle_type}</span>
          </p>
        </div>
        {/* The spec sentence stays whole for assistive technology; the icon row is its visual form. */}
        <p className="sr-only">{specification(vehicle)}</p>
        <ul aria-hidden="true" className="flex flex-wrap gap-x-4 gap-y-1.5 text-small text-muted-foreground">
          {specs.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-1.5">
              <Icon className="size-4 text-ink-subtle" />
              {text}
            </li>
          ))}
        </ul>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-small">
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
        </dl>
        <div className="mt-auto grid gap-4 border-t pt-4">
          <Estimate vehicle={vehicle} />
          <Button asChild className="w-full">
            <Link to={href} aria-label={`View and book the ${vehicle.brand} ${vehicle.model}`}>
              View and book
            </Link>
          </Button>
        </div>
      </div>
    </article>
  )
}
