import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'

import type { AvailableVehicle } from './api'

function billedFor(unit: 'day' | 'hour', count: number): string {
  return `${count} ${unit}${count === 1 ? '' : 's'}`
}

/** Search.Price: the estimate for the searched period, marked as one; the deposit apart (Pay.Deposit). */
export function Estimate({ vehicle }: { vehicle: AvailableVehicle }) {
  const { currency } = useAgency()
  const estimate = vehicle.estimate
  if (!estimate) {
    return <p className="text-sm text-muted-foreground">No price is published for this category yet.</p>
  }
  return (
    <div className="grid gap-1">
      <p className="text-sm">
        <span className="text-muted-foreground">Estimated price </span>
        <span className="num-strong text-foreground">
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
