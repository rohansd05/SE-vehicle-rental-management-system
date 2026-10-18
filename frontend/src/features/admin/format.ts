import type { AdminVehicle } from '@/api/admin'
import { formatDate } from '@/lib/dates'

/** SA-3: a statutory document missing, expired or expiring soon, in words. */
export function documentAlertText(alert: AdminVehicle['document_alerts'][number]): string {
  if (alert.state === 'Missing') return `${alert.document_type} not on record`
  const verb = alert.state === 'Expired' ? 'expired' : 'expires'
  return `${alert.document_type} ${verb} ${formatDate(alert.expiry_date)}`
}

/** BR-12 needs the tank, gas or battery capacity; the unit follows the fuel. */
export function capacityLabel(fuel: string): string {
  if (fuel === 'Electric') return 'Battery capacity (kWh)'
  if (fuel === 'CNG') return 'CNG capacity (kg)'
  return 'Tank capacity (litres)'
}
