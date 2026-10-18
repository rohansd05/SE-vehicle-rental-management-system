// Book Vehicle (SRS 3.1, 3.4; Exp 4 sequence 1). The server checks every
// rule (eligibility, availability, price, payment); the screens only show
// its answers (CO-3). No card detail ever passes through here (CO-2).

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'
import { getAccessToken } from '@/lib/session'

type Schemas = components['schemas']

export type VehicleDetail = Schemas['VehicleDetail']
export type AddOn = Schemas['AddOn']
export type Quote = Schemas['Quote']
export type QuoteTerms = Schemas['QuoteTerms']
export type Booking = Schemas['Booking']
export type BookingDetail = Schemas['BookingDetail']
export type BookingStatus = Schemas['BookingStatusEnum']
export type BookingPage = Schemas['PaginatedBookingList']
export type BookingVehicle = Schemas['BookingVehicle']
export type CancellationQuote = Schemas['CancellationQuote']
export type ModificationQuote = Schemas['ModificationQuote']
export type ExtensionQuote = Schemas['ExtensionQuote']

export interface AddOnChoice {
  add_on: number
  quantity: number
}

/** The period a booking is for, as UTC ISO strings (CO-6). */
export interface Period {
  pickup_datetime: string
  return_datetime: string
}

export const BOOKING_STATUSES = [
  'Pending Payment',
  'Confirmed',
  'Active',
  'Completed',
  'Cancelled',
  'No-show',
  'Draft',
] as const satisfies readonly BookingStatus[]

export const getVehicle = (id: number) =>
  apiRequest<VehicleDetail>(`/api/v1/fleet/vehicles/${id}/`, { auth: false })

export const listAddOns = (vehicleType: string) =>
  apiRequest<AddOn[]>(`/api/v1/pricing/add-ons/?${new URLSearchParams({ vehicle_type: vehicleType })}`, {
    auth: false,
  })

/** Book.Quote.Display: nothing is saved. */
export const getQuote = (vehicle: number, period: Period, addOns: AddOnChoice[], discountCode: string) =>
  apiRequest<Quote>('/api/v1/pricing/quote/', {
    method: 'POST',
    json: { vehicle, ...period, add_ons: addOns, discount_code: discountCode },
  })

export interface CreateBookingRequest extends Period {
  vehicle: number
  add_ons: AddOnChoice[]
  discount_code: string
  terms_accepted: boolean
  safety_notice_acknowledged: boolean
  /** Book.Deliver.Location: with the doorstep delivery add-on only. */
  delivery_address: string
  delivery_pincode: string
}

/** Booking.create_booking(): eligibility, availability, price, then a 15-minute hold. */
export const createBooking = (data: CreateBookingRequest) =>
  apiRequest<BookingDetail>('/api/v1/bookings/', { method: 'POST', json: data })

export const getBooking = (id: number) => apiRequest<BookingDetail>(`/api/v1/bookings/${id}/`)

/** Book.Hold.Expire: hold a Draft booking again with its details. */
export const holdAgain = (id: number) =>
  apiRequest<BookingDetail>(`/api/v1/bookings/${id}/hold/`, { method: 'POST' })

export interface PayRequest {
  payment_token: string
  idempotency_key: string
  password: string
}

/** Payment.authorize() and Book.Done. */
export const payBooking = (id: number, data: PayRequest) =>
  apiRequest<BookingDetail>(`/api/v1/bookings/${id}/pay/`, { method: 'POST', json: data })

/** History.View filters: pickup date range (YYYY-MM-DD), status, vehicle type, reference. */
export interface HistoryFilters {
  status?: BookingStatus | ''
  vehicle_type?: string
  pickup_from?: string
  pickup_to?: string
  reference?: string
  page?: number
}

/** History.View: the customer's own bookings, newest pickup first. */
export function listBookings(filters: HistoryFilters = {}) {
  const params = new URLSearchParams()
  for (const name of ['status', 'vehicle_type', 'pickup_from', 'pickup_to'] as const) {
    if (filters[name]) params.set(name, filters[name])
  }
  if (filters.reference?.trim()) params.set('reference', filters.reference.trim())
  if (filters.page && filters.page > 1) params.set('page', String(filters.page))
  const query = params.toString()
  return apiRequest<BookingPage>(`/api/v1/bookings/${query ? `?${query}` : ''}`)
}

// ─── Modify / Cancel Booking (UC 4) and Book.Extend ──────────────────────
// Each action is priced first (nothing saved), then confirmed with the
// password (SE-9) and the amounts shown; the server refuses (409) if they
// changed meanwhile.

/** An extra charge is paid by card or on-line (Pay.Method, D6), never cash. */
export interface ExtraPayment {
  method: 'card' | 'online'
  payment_token: string
  channel: string
  upi_id: string
  idempotency_key: string
  password: string
}

/** Book.Cancel: the refund under BR-8, shown before the customer confirms. */
export const getCancellationQuote = (id: number) =>
  apiRequest<CancellationQuote>(`/api/v1/bookings/${id}/cancel/`)

/** Booking.cancel_booking(): release, Cancelled, refund, notify (Book.Cancel.Release). */
export const cancelBooking = (id: number, data: { expected_refund: string; password: string }) =>
  apiRequest<BookingDetail>(`/api/v1/bookings/${id}/cancel/`, { method: 'POST', json: data })

/** Book.Modify: the new period, branch and add-ons; `vehicle` takes a UC 4 3a alternative. */
export interface ModificationRequest extends Period {
  pickup_branch: number
  add_ons: AddOnChoice[]
  vehicle: number | null
}

/** Book.Modify.Price: availability, the new price, the extra charge or the BR-8 refund. */
export const quoteModification = (id: number, data: ModificationRequest) =>
  apiRequest<ModificationQuote>(`/api/v1/bookings/${id}/modify/quote/`, { method: 'POST', json: data })

/** Booking.modify_booking(). */
export const modifyBooking = (
  id: number,
  data: ModificationRequest & ExtraPayment & { expected_charge: string; expected_refund: string },
) => apiRequest<BookingDetail>(`/api/v1/bookings/${id}/modify/`, { method: 'POST', json: data })

/** Book.Extend: the extra charge for a later return (BR-5: 30 days in all). */
export const quoteExtension = (id: number, returnDatetime: string) =>
  apiRequest<ExtensionQuote>(`/api/v1/bookings/${id}/extend/quote/`, {
    method: 'POST',
    json: { return_datetime: returnDatetime },
  })

/** Booking.extend_booking(): collected before the extension takes effect. */
export const extendBooking = (
  id: number,
  data: ExtraPayment & { return_datetime: string; expected_charge: string },
) => apiRequest<BookingDetail>(`/api/v1/bookings/${id}/extend/`, { method: 'POST', json: data })

/** Pay.Idempotent: one fresh key per payment attempt, so a repeat never charges twice. */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `pay-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

/**
 * History.Download: fetch the invoice PDF with the in-memory access token
 * (D21) and hand it to the browser as a download.
 */
export async function downloadInvoice(bookingId: number, invoiceNumber: string): Promise<void> {
  // DRF negotiates against its JSON renderers before the view runs, so Accept: application/pdf is a 406.
  const headers = new Headers({ Accept: '*/*' })
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(new URL(`/api/v1/bookings/${bookingId}/invoice/`, window.location.origin), {
    headers,
    credentials: 'same-origin',
  })
  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? 'Your session has ended. Sign in again to download the invoice.'
        : 'We couldn’t download the invoice. Please try again.',
    )
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = `${invoiceNumber}.pdf`
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
