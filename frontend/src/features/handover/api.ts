// Handover endpoints (SRS 3.3, Exp 2 use case 7). Owner: Nidhi (Module N1).
// The server enforces every rule and the branch scope (CO-3, SE-4, SE-5).

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type BranchBooking = Schemas['BranchBooking']
export type BranchBookingPage = Schemas['PaginatedBranchBookingList']
export type HandoverDetail = Schemas['HandoverDetail']
export type ConditionReport = Schemas['ConditionReport']
export type Refusal = Schemas['Refusal']
export type Accessory = Schemas['Accessory']
export type DamageMark = Schemas['DamageMark']
export type HandoverRefused = Schemas['HandoverRefused']

const BASE = '/api/v1/rentals'

export function listCollections({ when = 'today', q = '' }: { when?: 'today' | 'upcoming'; q?: string }) {
  const params = new URLSearchParams(q ? { q } : { when })
  return apiRequest<BranchBookingPage>(`${BASE}/branch-bookings/?${params.toString()}`)
}

export const getHandover = (id: number) => apiRequest<HandoverDetail>(`${BASE}/handovers/${id}/`)

export interface HandoverInput {
  odometer_reading: string
  fuel_level: string
  accessories: Accessory[]
  damage_marks: DamageMark[]
  /** One photo per side, keyed by the side's name ("Front", "Rear", ...). */
  photos: Record<string, File>
  extra_photos: File[]
  signature: Blob
}

/** BranchStaff.handover_vehicle(): checklist, signature and activation in one request. */
export function completeHandover(id: number, input: HandoverInput) {
  const form = new FormData()
  form.set('odometer_reading', input.odometer_reading)
  form.set('fuel_level', input.fuel_level)
  form.set('accessories', JSON.stringify(input.accessories))
  form.set('damage_marks', JSON.stringify(input.damage_marks))
  for (const [side, file] of Object.entries(input.photos)) form.set(`photo_${side.toLowerCase()}`, file)
  for (const file of input.extra_photos) form.append('extra_photos', file)
  form.set('signature', input.signature, 'signature.png')
  return apiRequest<HandoverDetail>(`${BASE}/handovers/${id}/complete/`, { method: 'POST', form })
}
