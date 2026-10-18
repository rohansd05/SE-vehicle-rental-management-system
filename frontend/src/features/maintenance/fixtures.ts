// Test data for the maintenance screens, shaped exactly like the API's answers.

import type { MaintenanceJob, MaintenanceVehicle } from '@/api/maintenance'

export const VEHICLE: MaintenanceVehicle = {
  id: 12,
  registration_no: 'MH01AB1234',
  brand: 'Maruti Suzuki',
  model: 'Swift',
  status: 'Under Maintenance',
  vehicle_type: 'Car',
  category: 'Hatchback',
  home_branch: 'Andheri',
  home_branch_id: 1,
  odometer: 15000,
  last_service_date: null,
  last_service_odometer: null,
  next_service_due: { odometer: null, date: null },
  service_overdue: false,
}

export function makeJob(overrides: Partial<MaintenanceJob> = {}): MaintenanceJob {
  return {
    job_id: 7,
    job_type: 'Corrective',
    severity: 'High',
    status: 'Scheduled',
    vehicle: VEHICLE,
    technician: { technician_id: 3, name: 'Tara Tech', workshop: 'Agency workshop', authorised_to_clear_unsafe: false },
    reported_problem: 'Brake pedal feels soft.',
    reported_by: 'Ravi Staff',
    due_odometer: null,
    due_date: null,
    scheduled_from: '2026-10-14T04:30:00Z',
    scheduled_to: '2026-10-14T12:30:00Z',
    started_at: null,
    service_date: null,
    odometer_at_service: null,
    work_description: '',
    labour_cost: '0.00',
    downtime_hours: null,
    total_cost: '0.00',
    parts: [],
    missing_work: [],
    awaiting_clearance: false,
    clearance_requested_at: null,
    closed_by: null,
    closed_at: null,
    cancelled_by: null,
    cancelled_at: null,
    cancel_reason: '',
    workshop_invoice_url: null,
    can_clear_unsafe: false,
    created_at: '2026-10-12T09:00:00Z',
    ...overrides,
  }
}

/** An In Progress job with its work recorded (Maint.Record). */
export const RECORDED = {
  status: 'In Progress',
  started_at: '2026-10-14T05:00:00Z',
  service_date: '2026-10-14',
  odometer_at_service: 15100,
  work_description: 'Replaced front brake pads.',
  labour_cost: '800.00',
  downtime_hours: '6.50',
  total_cost: '2250.00',
  parts: [
    { id: 1, part_name: 'Brake pads', quantity: '1.00', unit_cost: '1450.00', total_cost: '1450.00' },
  ],
} satisfies Partial<MaintenanceJob>

export const page = (results: MaintenanceJob[]) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
})
