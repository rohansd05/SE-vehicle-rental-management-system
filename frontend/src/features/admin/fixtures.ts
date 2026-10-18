// Test data for the administration screens, shaped exactly like the API's answers.

import type {
  AdminBranch,
  AdminCustomerDetail,
  AdminTariff,
  AdminVehicle,
  AdminVehicleDetail,
  AuditEntry,
  StaffAccount,
} from '@/api/admin'

export const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results })

export const CATEGORIES = [
  { id: 1, name: 'Hatchback', vehicle_type: 'Car' },
  { id: 2, name: 'Scooter', vehicle_type: 'Two-Wheeler' },
]

export const BRANCHES: AdminBranch[] = [
  {
    branch_id: 1,
    branch_name: 'Andheri',
    address: 'Link Road, Andheri (W)',
    serviceable_areas: [{ id: 5, pincode: '400053', locality: 'Andheri West' }],
    vehicle_count: 12,
  },
]

export const VEHICLE: AdminVehicle = {
  id: 12,
  registration_no: 'MH02DM1001',
  vehicle_type: 'Car',
  category: 1,
  category_name: 'Hatchback',
  brand: 'Maruti Suzuki',
  model: 'Swift',
  year: 2024,
  colour: 'Red',
  fuel_type: 'Petrol',
  transmission: 'Manual',
  seating_capacity: 5,
  engine_cc: null,
  chassis_number: 'DEMOCHASSIS000001',
  home_branch: 1,
  home_branch_name: 'Andheri',
  odometer: 12000,
  fuel_capacity: '37.00',
  available_from: '2026-01-01',
  status: 'Available',
  photo_count: 4,
  document_alerts: [{ document_type: 'Road Tax', state: 'Missing', expiry_date: null }],
}

export const VEHICLE_DETAIL: AdminVehicleDetail = {
  ...VEHICLE,
  last_service_date: '2026-09-01',
  last_service_odometer: 11000,
  photos: [1, 2, 3, 4].map((n) => ({ id: n, position: n - 1, url: `/api/v1/files/photo-${n}/` })),
  documents: [
    {
      id: 30,
      document_type: 'Insurance',
      document_number: 'POL-1',
      valid_from: '2026-01-01',
      expiry_date: '2026-12-31',
      state: 'Valid',
      current: true,
      file_url: null,
    },
  ],
}

export const TARIFFS: AdminTariff[] = [
  {
    id: 2,
    vehicle_category: 1,
    category_name: 'Hatchback',
    vehicle_type: 'Car',
    hourly_rate: '175.00',
    daily_rate: '2000.00',
    weekly_rate: '12000.00',
    security_deposit: '5000.00',
    free_km_allowance: 250,
    excess_km_rate: '11.00',
    effective_from: '2026-12-01T04:30:00Z',
    defined_by: 'Anil Admin',
    state: 'Scheduled',
    booking_count: 0,
  },
  {
    id: 1,
    vehicle_category: 1,
    category_name: 'Hatchback',
    vehicle_type: 'Car',
    hourly_rate: '150.00',
    daily_rate: '1800.00',
    weekly_rate: '11000.00',
    security_deposit: '5000.00',
    free_km_allowance: 250,
    excess_km_rate: '10.00',
    effective_from: '2026-01-01T00:00:00Z',
    defined_by: 'Anil Admin',
    state: 'In force',
    booking_count: 3,
  },
]

export function staffAccount(overrides: Partial<StaffAccount> = {}): StaffAccount {
  return {
    id: 40,
    email: 'neha@vrms.test',
    name: 'Neha Kulkarni',
    mobile_no: '+919811122233',
    address: '7 Station Road, Thane',
    role: 'BRANCH_STAFF',
    is_active: true,
    date_joined: '2026-10-18T05:00:00Z',
    last_login: null,
    branch: 1,
    branch_name: 'Andheri',
    workshop: null,
    technician_id: null,
    authorised_to_clear_unsafe: false,
    ...overrides,
  }
}

export function customer(overrides: Partial<AdminCustomerDetail> = {}): AdminCustomerDetail {
  return {
    customer_id: 9,
    name: 'Kiran Desai',
    email: 'kiran@example.com',
    mobile_no: '+919812300011',
    is_blacklisted: false,
    outstanding_due: '0.00',
    blacklist_reason: null,
    blacklisted_at: null,
    blacklisted_by: null,
    open_bookings: [
      {
        id: 70,
        booking_reference: 'VRMS-20261018-0007',
        status: 'Confirmed',
        registration_no: 'MH02DB8001',
        vehicle: 'Honda Amaze',
        pickup_branch: 'Andheri',
        pickup_datetime: '2026-10-21T04:30:00Z',
        return_datetime: '2026-10-23T04:30:00Z',
        return_pending: false,
      },
      {
        id: 71,
        booking_reference: 'VRMS-20261018-0008',
        status: 'Active',
        registration_no: 'MH02DB8002',
        vehicle: 'Honda Jazz',
        pickup_branch: 'Andheri',
        pickup_datetime: '2026-10-17T04:30:00Z',
        return_datetime: '2026-10-20T04:30:00Z',
        return_pending: true,
      },
    ],
    ...overrides,
  }
}

export const AUDIT_ENTRY: AuditEntry = {
  id: 501,
  timestamp: '2026-10-18T05:30:00Z',
  actor: { id: 5, name: 'Meera Manager', email: 'manager@vrms.test', role: 'BRANCH_MANAGER' },
  action: 'Odometer Override Approved',
  entity_type: 'rentals.ConditionReport',
  entity_id: '44',
  before: null,
  after: { distance: 1500, reason: 'Outstation trip' },
  ip_address: null,
}
