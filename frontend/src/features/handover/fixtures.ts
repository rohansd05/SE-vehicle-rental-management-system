// Test data for the handover screens, shaped exactly like the API's answers.

import type { BranchBooking, ConditionReport, HandoverDetail, ReturnDetail, ReturnQuote, SettlementRecord } from './api'

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
    delivery_address: '',
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

// ─── Return Vehicle (Module N2) ───────────────────────────────────────────

export function makeReturn(overrides: Partial<ReturnDetail> = {}): ReturnDetail {
  const { vehicle, ...booking } = makeCollection({ status: 'Active' })
  return {
    ...booking,
    vehicle: { ...vehicle, status: 'On Rent', odometer: 8210, fuel_type: 'Petrol', fuel_capacity: '37.00' },
    handed_over_at: '2026-10-16T01:40:00Z',
    returned_at: null,
    distance_travelled: null,
    total_amount: '2124.00',
    security_deposit: '5000.00',
    refusals: [],
    can_return: true,
    photo_sides: ['Front', 'Rear', 'Left', 'Right'],
    terms: TERMS,
    handover_report: REPORT,
    return_report: null,
    rental_paid: [
      { description: 'Rental charge (Book.Done)', amount: '2124.00' },
      { description: 'Rental extended to 24 Oct 2026 07:00 (Book.Extend)', amount: '2124.00' },
    ],
    deposit_method: 'Card',
    settlement: null,
    ...overrides,
  }
}

export const QUOTE: ReturnQuote = {
  lines: [
    { kind: 'late_return', description: 'Late return, 3 h after the return time: 3 hours at 150.00 (BR-10)', amount: '450.00', justification: '' },
    { kind: 'excess_km', description: 'Excess kilometres, 150 km over the 250 km allowance at 10.00 per km (BR-11)', amount: '1500.00', justification: '' },
    { kind: 'fuel_shortfall', description: 'Fuel or charge shortfall, 25% of 37 L (9.25 L) at 104.21 plus 20% (BR-12)', amount: '1156.73', justification: '' },
    { kind: 'accessory', description: 'Accessory not returned: Child seat × 1', amount: '1200.00', justification: '' },
    { kind: 'damage', description: 'Damage: Dent on the rear door', amount: '800.00', justification: 'Not on the handover report' },
    { kind: 'tax', description: 'Tax at 18% on the return charges (BR-6)', amount: '919.21', justification: '' },
  ],
  total: '6025.94',
  deposit: '5000.00',
  deposit_used: '5000.00',
  refund: '0.00',
  due: '1025.94',
  distance: 400,
  free_km: 250,
  accessories_returned: [],
  override_required: false,
  plausibility_limit_km: 1000,
}

/** A settlement with nothing to charge: the whole deposit comes back. */
export const ZERO_QUOTE: ReturnQuote = {
  ...QUOTE,
  lines: [],
  total: '0.00',
  deposit_used: '0.00',
  refund: '5000.00',
  due: '0.00',
  distance: 120,
  accessories_returned: [{ name: 'Child seat', quantity: 1 }],
}

export function makeSettlement(overrides: Partial<SettlementRecord> = {}): SettlementRecord {
  const { lines, total, deposit, deposit_used, refund, due } = ZERO_QUOTE
  return {
    lines,
    total,
    deposit,
    deposit_used,
    refund,
    due,
    refund_status: 'Issued',
    refund_paid_out_by: '',
    maintenance_job: null,
    ...overrides,
  }
}

export const RETURN_REPORT: ConditionReport = {
  ...REPORT,
  report_type: 'Return',
  odometer_reading: 8330,
  fuel_level: '100.00',
  damage_marks: [],
  photos: ['Front', 'Rear', 'Left', 'Right'].map((caption) => ({ caption, url: `/api/v1/files/return-${caption}/` })),
  signature_url: '/api/v1/files/return-signature/',
}
