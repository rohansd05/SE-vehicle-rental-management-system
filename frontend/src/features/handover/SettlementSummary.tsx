// Return.Charges and Return.Settle: each charge as its own line, what was
// paid before the return (an extension included, never charged again), then
// what the deposit covers, its refund (BR-14) or the due left (Pay.Dues).
// Amounts arrive as decimal strings and are only formatted here (CO-6).

import { useAgency } from '@/hooks/page'
import { formatCurrency } from '@/lib/currency'

import type { PaidCharge, ReturnQuote, SettlementRecord } from './api'

const BODY =
  '[&_td]:py-2 [&_td:last-child]:num [&_td:last-child]:pl-4 [&_td:last-child]:text-right [&_td:last-child]:whitespace-nowrap [&_tr]:border-b [&_tr]:border-hairline'
const SUBHEAD = 'border-b-0! [&_th]:pt-5 [&_th]:pb-1 [&_th]:text-left [&_th]:text-label [&_th]:font-medium [&_th]:text-muted-foreground'

export function SettlementSummary({
  settlement,
  paid,
  rentalTotal,
}: {
  settlement: ReturnQuote | SettlementRecord
  paid: PaidCharge[]
  /** The booking's rental total, shown as paid when the ledger has no rental line. */
  rentalTotal: string
}) {
  const { currency } = useAgency()
  const money = (amount: string) => formatCurrency(amount, currency)
  const due = Number(settlement.due) > 0
  return (
    <table className="w-full text-sm">
      <caption className="heading mb-2 text-left text-section text-foreground">Settlement</caption>
      <tbody className={BODY}>
        <tr className={SUBHEAD}>
          <th colSpan={2} scope="colgroup">
            Already paid
          </th>
        </tr>
        {(paid.length ? paid : [{ description: 'Rental, paid at booking', amount: rentalTotal }]).map((line, index) => (
          <tr key={index}>
            <td>{line.description}</td>
            <td>{money(line.amount)}</td>
          </tr>
        ))}
        <tr className={SUBHEAD}>
          <th colSpan={2} scope="colgroup">
            Charges at return
          </th>
        </tr>
        {settlement.lines.length === 0 ? (
          <tr>
            <td>No charges</td>
            <td>{money('0')}</td>
          </tr>
        ) : (
          settlement.lines.map((line, index) => (
            <tr key={index}>
              <td>
                {line.description}
                {line.justification ? (
                  <span className="mt-0.5 block text-small text-muted-foreground">{line.justification}</span>
                ) : null}
              </td>
              <td>{money(line.amount)}</td>
            </tr>
          ))
        )}
        <tr className="font-semibold">
          <td>Total charges</td>
          <td>{money(settlement.total)}</td>
        </tr>
        <tr>
          <td>Security deposit</td>
          <td>{money(settlement.deposit)}</td>
        </tr>
        <tr>
          <td>Deducted from the deposit</td>
          <td>{money(settlement.deposit_used)}</td>
        </tr>
        <tr className="border-b-0! font-semibold [&_td]:pt-3 [&_td:last-child]:num-lg!">
          <td className="align-baseline">{due ? 'Due from the customer' : 'Deposit balance to refund'}</td>
          <td>{money(due ? settlement.due : settlement.refund)}</td>
        </tr>
      </tbody>
    </table>
  )
}
