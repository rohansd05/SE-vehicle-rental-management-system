// Payments completion (SRS 3.4 Pay.*; UC 13 Approve Refund; BR-4, BR-9). The
// server checks every rule and asks for the password before money moves
// (SE-9); these screens only show its answers (CO-3). No card detail ever
// passes through here (CO-2): the sandbox tokens stand in for the gateway's
// hosted fields and pages.

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'
import type { BookingDetail } from '@/features/booking/api'

type Schemas = components['schemas']

export type Due = Schemas['Due']
export type Channel = Schemas['ChannelEnum']
export type Refund = Schemas['Refund']
export type RefundStatus = Schemas['RefundStatusEnum']
export type RefundPage = Schemas['PaginatedRefundList']
export type CashDueBooking = Schemas['CashDueBooking']
export type CashDuePage = Schemas['PaginatedCashDueBookingList']

/** Pay.Method as sent to the API: a card or on-line token, or cash (bookings only). */
export interface MethodRequest {
  method: 'card' | 'online' | 'cash'
  payment_token: string
  channel: Channel | ''
  upi_id: string
}

/** Pay.Dues: what the signed-in customer owes (BR-4 blocks booking above zero). */
export const getDue = () => apiRequest<Due>('/api/v1/payments/due/')

/** Pay.Dues: clear the whole due on-line; the restriction lifts at once. */
export const payDue = (data: MethodRequest & { idempotency_key: string; password: string }) =>
  apiRequest<Due>('/api/v1/payments/due/', { method: 'POST', json: data })

/** UC 13 and Pay.Refund: refunds in the caller's scope, oldest request first. */
export const listRefunds = (status: RefundStatus) =>
  apiRequest<RefundPage>(`/api/v1/payments/refunds/?${new URLSearchParams({ status })}`)

/** UC 13 step 3: approve; the refund goes back to the original payment method. */
export const approveRefund = (id: number, password: string) =>
  apiRequest<Refund>(`/api/v1/payments/refunds/${id}/approve/`, { method: 'POST', json: { password } })

/** UC 13 extension 2a: reject with a reason; the customer is told by e-mail. */
export const rejectRefund = (id: number, reason: string, password: string) =>
  apiRequest<Refund>(`/api/v1/payments/refunds/${id}/reject/`, {
    method: 'POST',
    json: { reason, password },
  })

/** Pay.Refund: a named staff member pays an approved cash refund out. */
export const payOutCashRefund = (id: number, password: string) =>
  apiRequest<Refund>(`/api/v1/payments/refunds/${id}/pay-out/`, {
    method: 'POST',
    json: { customer_acknowledged: true, password },
  })

/** BR-9: the branch's bookings whose customers pay cash at collection. */
export const listAwaitingCash = () => apiRequest<CashDuePage>('/api/v1/bookings/awaiting-cash/')

/** BR-9, Book.Done: record the cash received; the booking is confirmed. */
export const recordCash = (id: number, data: { amount_received: string; idempotency_key: string; password: string }) =>
  apiRequest<BookingDetail>(`/api/v1/bookings/${id}/cash/`, { method: 'POST', json: data })
