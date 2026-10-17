// Handover and return endpoints (SRS 3.3, Exp 2 use cases 7 and 8). Owner: Nidhi (N1, N2).
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

// ─── Return Vehicle (SRS 3.3 Return.*, Exp 2 use case 8; Module N2) ──────

export type ReturnDetail = Schemas['ReturnDetail']
export type ReturnQuote = Schemas['ReturnQuote']
export type ReturnCharge = Schemas['ReturnCharge']
export type SettlementRecord = Schemas['SettlementRecord']
export type PaidCharge = Schemas['PaidCharge']

export function listReturns({ q = '' }: { q?: string } = {}) {
  const params = new URLSearchParams(q ? { q } : {})
  return apiRequest<BranchBookingPage>(`${BASE}/returns/?${params.toString()}`)
}

export const getReturn = (id: number) => apiRequest<ReturnDetail>(`${BASE}/returns/${id}/`)

export interface MissingAccessory extends Accessory {
  cost: string
}

export interface DamageCharge {
  description: string
  amount: string
  justification: string
}

/** Return.Checklist readings and the charges the staff member enters. */
export interface ReturnReadings {
  odometer_reading: string
  fuel_level: string
  /** UTC ISO timestamp of the actual return time. */
  returned_at: string
  missing_accessories: MissingAccessory[]
  damage_charges: DamageCharge[]
}

/** UC 8 step 3: the itemised settlement for the customer to acknowledge; nothing is saved. */
export const quoteReturn = (id: number, readings: ReturnReadings) =>
  apiRequest<ReturnQuote>(`${BASE}/returns/${id}/quote/`, { method: 'POST', json: readings })

export interface ReturnInput extends ReturnReadings {
  damage_marks: DamageMark[]
  photos: Record<string, File>
  extra_photos: File[]
  /** The customer's acknowledgement of the settlement. */
  signature: Blob
  /** The total the customer acknowledged; the server refuses (409) if it changed. */
  expected_total: string
  flag: { problem: string; severity: string; unfit: boolean } | null
  override: { email: string; password: string; reason: string } | null
}

/** BranchStaff.return_vehicle(): record, settle and complete in one request. */
export function completeReturn(id: number, input: ReturnInput) {
  const form = new FormData()
  form.set('odometer_reading', input.odometer_reading)
  form.set('fuel_level', input.fuel_level)
  form.set('returned_at', input.returned_at)
  form.set('missing_accessories', JSON.stringify(input.missing_accessories))
  form.set('damage_charges', JSON.stringify(input.damage_charges))
  form.set('damage_marks', JSON.stringify(input.damage_marks))
  form.set('expected_total', input.expected_total)
  for (const [side, file] of Object.entries(input.photos)) form.set(`photo_${side.toLowerCase()}`, file)
  for (const file of input.extra_photos) form.append('extra_photos', file)
  form.set('signature', input.signature, 'signature.png')
  if (input.flag) {
    form.set('flag_problem', input.flag.problem)
    form.set('flag_severity', input.flag.severity)
    form.set('flag_unfit', String(input.flag.unfit))
  }
  if (input.override) {
    form.set('override_email', input.override.email)
    form.set('override_password', input.override.password)
    form.set('override_reason', input.override.reason)
  }
  return apiRequest<ReturnDetail>(`${BASE}/returns/${id}/complete/`, { method: 'POST', form })
}
