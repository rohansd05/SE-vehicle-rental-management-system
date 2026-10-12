import { Button } from '@/components/ui/button'
import { stagger } from '@/lib/motion'

import type { AvailableVehicle } from './api'
import { VehicleTile } from './VehicleTile'

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
    <div className="@container grid gap-6">
      {/* Image-led tiles (B12, imagery-brief.md 3), in a list so each vehicle stays one list item. */}
      {/* Columns follow the content width, not the screen (B14): one below
          576 px of content, two from 576, three from 896, four from 1280. */}
      <ul aria-label="Available vehicles" className="grid gap-5 @xl:grid-cols-2 @4xl:grid-cols-3 @7xl:grid-cols-4">
        {vehicles.map((vehicle, index) => (
          <li key={vehicle.id} className="enter" style={stagger(index % 8)}>
            <VehicleTile vehicle={vehicle} href={hrefFor(vehicle)} />
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
