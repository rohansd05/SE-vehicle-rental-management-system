import type { AvailableVehicle } from './api'

/** The specification line a customer chooses by (Search.Filter fields). */
export function specification(vehicle: AvailableVehicle): string {
  const parts = [vehicle.fuel_type, vehicle.colour]
  if (vehicle.transmission) parts.push(vehicle.transmission)
  if (vehicle.seating_capacity) parts.push(`${vehicle.seating_capacity} seats`)
  if (vehicle.engine_cc) parts.push(`${vehicle.engine_cc} cc`)
  return parts.join(' · ')
}
