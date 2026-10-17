// Test data for the handover screens, shaped exactly like the API's answers.

import type { BranchBooking, ConditionReport, HandoverDetail } from './api'

export function makeCollection(overrides: Partial<BranchBooking> = {}): BranchBooking {
  return {
    id: 41,
    booking_reference: 'VRMS-20261016-0007',
    status: 'Confirmed',
    pickup_datetime: '2026-10-16T01:30:00Z',
    return_datetime: '2026-10-23T01:30:00Z',
    pickup_branch: 'Andheri',
    customer_name: 'Asha Rao',
    customer_mobile: '+919800000001',
    vehicle: {
      id: 9,
      brand: 'Tata',
      model: 'Altroz',
      registration_no: 'MH02DH3001',
      vehicle_type: 'Car',
      category: 'Hatchback',
    },
    ...overrides,
  }
}

export const TERMS: HandoverDetail['terms'] = {
  free_km_allowance_per_day: 250,
  excess_km_rate: '10.00',
  late_return_grace_minutes: 15,
  late_return_hourly_rate: '150.00',
  late_return_daily_cap: '1800.00',
  late_return_full_day_after_hours: 6,
  fuel_shortfall_service_charge_percent: '20.00',
  cancellation_refunds: [
    { notice_hours_at_least: 48, refund_percent: '100.00' },
    { notice_hours_at_least: 12, refund_percent: '75.00' },
    { notice_hours_at_least: 0, refund_percent: '50.00' },
  ],
  no_show_retained_percent: '50.00',
}

export function makeHandover(overrides: Partial<HandoverDetail> = {}): HandoverDetail {
  const { vehicle, ...booking } = makeCollection()
  return {
    ...booking,
    vehicle: { ...vehicle, status: 'Available', odometer: 8200 },
    handed_over_at: null,
    licence: {
      licence_number: 'MH02 20150012345',
      status: 'Verified',
      expiry_date: '2035-05-19',
      categories: ['Car', 'Two-Wheeler'],
    },
    refusals: [],
    can_hand_over: true,
    accessories: [{ name: 'Child seat', quantity: 1 }],
    photo_sides: ['Front', 'Rear', 'Left', 'Right'],
    terms: TERMS,
    report: null,
    ...overrides,
  }
}

export const REPORT: ConditionReport = {
  report_type: 'Handover',
  odometer_reading: 8210,
  fuel_level: '75.00',
  accessories: [{ name: 'Child seat', quantity: 1 }],
  damage_marks: [{ x: 50, y: 85, note: 'Rear: scratch on the bumper' }],
  photos: ['Front', 'Rear', 'Left', 'Right'].map((caption) => ({ caption, url: `/api/v1/files/${caption}/` })),
  signature_url: '/api/v1/files/signature/',
  signed_at: '2026-10-16T04:35:00Z',
  recorded_by: 'Ravi Staff',
  recorded_at: '2026-10-16T04:35:00Z',
}

export const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })
