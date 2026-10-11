// Book.Quote.Display: base charge, each add-on, the discount, the taxes and
// the total, with the refundable deposit shown apart (Pay.Deposit, UI-4).
// Book.Quote.Terms: the figures the customer accepts before paying.
// Amounts arrive as decimal strings and are only formatted here (CO-6).

import { useEffect, useRef, useState } from 'react'

import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'

import type { Quote, QuoteTerms } from './api'

function plural(count: number, unit: string) {
  return `${count} ${unit}${count === 1 ? '' : 's'}`
}

/**
 * Counts how many times the total has changed since mount, so the total can
 * be highlighted briefly when a quote is recalculated. The figure itself is
 * always the exact formatted value; only a tint behind it fades.
 */
function useChangeCount(value: string): number {
  const previous = useRef(value)
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (previous.current !== value) {
      previous.current = value
      setCount((current) => current + 1)
    }
  }, [value])
  return count
}

export function PriceSummary({ quote, caption = 'Price summary' }: { quote: Quote; caption?: string }) {
  const { currency } = useAgency()
  const money = (amount: string) => formatCurrency(amount, currency)
  const hasDiscount = Number(quote.discount_amount) > 0
  const changes = useChangeCount(quote.total_payable)
  return (
    <div className="grid gap-3">
      <table className="w-full text-sm">
        <caption className="mb-2 text-left font-heading text-section font-[650] [font-stretch:118%] [letter-spacing:-0.015em] text-foreground">
          {caption}
        </caption>
        <tbody className="[&_td]:py-2 [&_td:last-child]:num [&_td:last-child]:pl-4 [&_td:last-child]:text-right [&_td:last-child]:whitespace-nowrap [&_tr]:border-b [&_tr]:border-hairline">
          <tr>
            <td>
              Rental, {plural(quote.billing_count, quote.billing_unit)} at {money(quote.unit_rate)}
            </td>
            <td>{money(quote.base_charge)}</td>
          </tr>
          {quote.add_ons.map((line) => (
            <tr key={line.add_on_id}>
              <td>
                {line.name} × {line.quantity}, {plural(line.days, 'day')} at {money(line.daily_rate)}
              </td>
              <td>{money(line.amount)}</td>
            </tr>
          ))}
          {hasDiscount ? (
            <tr>
              <td>Discount {quote.discount_code}</td>
              <td>−{money(quote.discount_amount)}</td>
            </tr>
          ) : null}
          <tr>
            <td>Tax at {Number(quote.tax_rate_percent)}%</td>
            <td>{money(quote.tax_amount)}</td>
          </tr>
          <tr className="border-b-0! font-semibold [&_td]:pt-3 [&_td]:pb-1 [&_td:last-child]:num-lg!">
            <td className="align-baseline">Total payable</td>
            <td>
              <span key={changes} className={changes > 0 ? 'flash' : undefined}>
                {money(quote.total_payable)}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p className="border-t pt-3 text-sm text-muted-foreground">
        Refundable security deposit <strong className="num-strong text-foreground">{money(quote.security_deposit)}</strong>, held separately
        and not part of the total.
      </p>
      {quote.free_helmets_per_rider > 0 ? (
        <p className="text-sm text-muted-foreground">
          One helmet per rider is included free of charge.
        </p>
      ) : null}
    </div>
  )
}

export function TermsList({ terms }: { terms: QuoteTerms }) {
  const { currency } = useAgency()
  const money = (amount: string) => formatCurrency(amount, currency)
  const [full, partial, late] = terms.cancellation_refunds
  return (
    <ul className="grid list-disc gap-1.5 pl-5 text-sm marker:text-ink-subtle">
      <li>
        {terms.free_km_allowance_per_day} km free per rental day; beyond that{' '}
        {money(terms.excess_km_rate)} per km.
      </li>
      <li>Return the vehicle with the fuel or charge level it had at pickup; a shortfall is charged at the
        prevailing price plus {Number(terms.fuel_shortfall_service_charge_percent)}%.</li>
      <li>
        Late return: {terms.late_return_grace_minutes} minutes’ grace, then {money(terms.late_return_hourly_rate)}{' '}
        per hour, at most {money(terms.late_return_daily_cap)} per 24 hours; a delay over{' '}
        {terms.late_return_full_day_after_hours} hours is a full extra day.
      </li>
      {full && partial && late ? (
        <li>
          Cancellation: {Number(full.refund_percent)}% refunded at least {full.notice_hours_at_least} hours before
          pickup, {Number(partial.refund_percent)}% from {partial.notice_hours_at_least} to{' '}
          {full.notice_hours_at_least} hours before, {Number(late.refund_percent)}% later. A no-show keeps{' '}
          {Number(terms.no_show_retained_percent)}%. The deposit is always refunded in full.
        </li>
      ) : null}
    </ul>
  )
}
