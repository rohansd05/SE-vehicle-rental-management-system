// Test data for the Book Vehicle screens, shaped like the generated API types.

import type { AddOn, BookingDetail, Quote, QuoteTerms, VehicleDetail } from './api'

export const PICKUP = '2027-01-10T04:30:00.000Z'
export const RETURN = '2027-01-12T04:30:00.000Z'

export const TERMS: QuoteTerms = {
  free_km_allowance_per_day: 250,
  excess_km_rate: '12.00',
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

export const CAR: VehicleDetail = {
  id: 11,
  brand: 'Maruti Suzuki',
  model: 'Swift',
  year: 2023,
  colour: 'White',
  fuel_type: 'Petrol',
  vehicle_type: 'Car',
  category: 'Hatchback',
  category_id: 3,
  home_branch: 'Andheri',
  home_branch_id: 1,
  transmission: 'Manual',
  seating_capacity: 5,
  engine_cc: null,
  average_rating: '4.50',
  last_service_date: '2026-09-20',
  status: 'Available',
  photos: ['/api/v1/files/p1/', '/api/v1/files/p2/', '/api/v1/files/p3/', '/api/v1/files/p4/'],
  tariff: { hourly_rate: '150.00', daily_rate: '1800.00', free_km_allowance_per_day: 250, excess_km_rate: '12.00' },
  security_deposit: '5000.00',
  terms: TERMS,
}

export const SCOOTER: VehicleDetail = {
  ...CAR,
  id: 12,
  brand: 'Honda',
  model: 'Activa 6G',
  vehicle_type: 'Two-Wheeler',
  category: 'Scooter',
  transmission: null,
  seating_capacity: null,
  engine_cc: 110,
  security_deposit: '2000.00',
}

export const CHILD_SEAT: AddOn = { id: 5, name: 'Child seat', daily_rate: '100.00', vehicle_type: 'Car' }

export const QUOTE: Quote = {
  tariff_id: 9,
  billing_unit: 'day',
  billing_count: 2,
  unit_rate: '1800.00',
  base_charge: '3600.00',
  add_ons: [],
  add_ons_total: '0.00',
  rental_charge: '3600.00',
  discount_code: '',
  discount_amount: '0.00',
  taxable_amount: '3600.00',
  tax_rate_percent: '18.00',
  tax_amount: '648.00',
  total_payable: '4248.00',
  security_deposit: '5000.00',
  free_helmets_per_rider: 0,
  terms: TERMS,
}

export const QUOTE_WITH_SEAT_AND_CODE: Quote = {
  ...QUOTE,
  add_ons: [{ add_on_id: 5, name: 'Child seat', quantity: 1, daily_rate: '100.00', days: 2, amount: '200.00' }],
  add_ons_total: '200.00',
  rental_charge: '3800.00',
  discount_code: 'WELCOME10',
  discount_amount: '380.00',
  taxable_amount: '3420.00',
  tax_amount: '615.60',
  total_payable: '4035.60',
}

/** A hold that expires `minutes` from now. */
export const heldBooking = (minutes = 15): BookingDetail => ({
  id: 70,
  booking_reference: '',
  status: 'Pending Payment',
  vehicle: { id: 11, brand: 'Maruti Suzuki', model: 'Swift', registration_no: 'MH01AB1234', vehicle_type: 'Car', category: 'Hatchback' },
  pickup_branch: 'Andheri',
  pickup_branch_id: 1,
  pickup_datetime: PICKUP,
  return_datetime: RETURN,
  hold_expires_at: new Date(Date.now() + minutes * 60_000).toISOString(),
  confirmed_at: null,
  pickup_code: '',
  add_ons: [],
  total_amount: '4248.00',
  security_deposit: '5000.00',
  discount_code: '',
  discount_amount: '0.00',
  terms_accepted_at: '2026-10-11T10:00:00Z',
  safety_notice_acknowledged_at: null,
  invoice_number: null,
  created_at: '2026-10-11T10:00:00Z',
  price: QUOTE,
  transaction_id: null,
})

export const confirmedBooking = (): BookingDetail => ({
  ...heldBooking(),
  status: 'Confirmed',
  booking_reference: 'VRMS-20261011-0001',
  pickup_code: '042917',
  hold_expires_at: null,
  confirmed_at: '2026-10-11T10:05:00Z',
  invoice_number: 'INV-2026-000001',
  transaction_id: 'TXN-5F2A9C0B1D3E4F5A6B7C',
})
