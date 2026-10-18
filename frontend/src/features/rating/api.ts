// Rate Vehicle (Exp 2 UC 6, D13). The server checks every rule: own Completed
// booking, within 14 days of its return, once, edits within 24 hours (CO-3).

import { apiRequest } from '@/api/client'
import type { BookingDetail } from '@/features/booking/api'

export interface RatingInput {
  vehicle_rating: number
  service_rating: number
  comment: string
}

/** UC 6 steps 2-3 (POST), or extension 2a, editing the review (PATCH). */
export const rateBooking = (bookingId: number, data: RatingInput, edit: boolean) =>
  apiRequest<BookingDetail>(`/api/v1/bookings/${bookingId}/rating/`, {
    method: edit ? 'PATCH' : 'POST',
    json: data,
  })
