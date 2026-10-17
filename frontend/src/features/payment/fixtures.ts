// Test data shaped like the API (generated types), for the payments screens.

import { heldBooking } from '@/features/booking/fixtures'

import type { CashDueBooking, Refund } from './api'

export const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

export const makeRefund = (overrides: Partial<Refund> = {}): Refund => ({
  id: 31,
  booking_id: 70,
  booking_reference: 'VRMS-20261011-0001',
  customer_name: 'Asha Rao',
  purpose: 'Rental',
  method: 'Card',
  original_transaction_id: 'TXN-5F2A9C0B1D3E4F5A6B7C',
  amount: '6372.00',
  reason: 'Cancelled by the branch',
  status: 'Pending Approval',
  requested_by_name: 'Ravi Staff',
  requested_at: '2026-10-16T05:30:00Z',
  decided_by_name: '',
  decided_at: null,
  rejection_reason: '',
  failure_reason: '',
  refund_due_by: null,
  refund_transaction_id: null,
  ...overrides,
})

export const cashBooking = (): CashDueBooking => {
  const { price: _price, transaction_id: _transaction, refunds: _refunds, ...booking } = heldBooking()
  return {
    ...booking,
    cash_on_collection: true,
    hold_expires_at: '2027-01-10T06:30:00.000Z',
    customer_name: 'Asha Rao',
    customer_mobile: '+919812345678',
    amount_due: '9248.00',
  }
}
