// Report payloads for the MSW tests, shaped as the API sends them (decimal strings).

import type { CustomerReport, Dashboard, MaintenanceReport, RevenueReport, UtilisationReport } from './api'

const HEADER = { date_from: '2026-10-01', date_to: '2026-10-15', scope: 'All branches' }

export function makeDashboard(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    scope: 'All branches',
    vehicles_by_status: [
      { status: 'Available', count: 0 },
      { status: 'On Rent', count: 0 },
      { status: 'Under Maintenance', count: 0 },
      { status: 'Unsafe', count: 0 },
      { status: 'Retired', count: 0 },
    ],
    collections_today: 0,
    returns_today: 0,
    overdue_returns: 0,
    open_maintenance_jobs: 0,
    periods: [
      { period: 'today', bookings: 0, revenue: '0.00' },
      { period: 'week', bookings: 0, revenue: '0.00' },
      { period: 'month', bookings: 0, revenue: '0.00' },
    ],
    ...overrides,
  }
}

const vehicle = {
  vehicle_id: 7,
  registration_no: 'MH02DB2001',
  vehicle: 'Maruti Suzuki Baleno',
  category: 'Hatchback',
  branch: 'Andheri',
  rented_hours: '46.0',
  available_hours: '336.0',
  maintenance_days: '1.0',
  utilisation_percent: '13.7',
}

export function makeUtilisation(overrides: Partial<UtilisationReport> = {}): UtilisationReport {
  const group = { vehicles: 1, rented_hours: '46.0', available_hours: '336.0', utilisation_percent: '13.7' }
  return {
    ...HEADER,
    totals: { name: 'All vehicles', ...group },
    by_vehicle: [vehicle],
    by_category: [{ name: 'Hatchback', ...group }],
    by_branch: [{ name: 'Andheri', ...group }],
    least_utilised: [vehicle],
    ...overrides,
  }
}

export function makeRevenue(overrides: Partial<RevenueReport> = {}): RevenueReport {
  return {
    ...HEADER,
    totals: {
      invoices: 2,
      rental: '3000.00',
      add_ons: '200.00',
      discounts: '-100.00',
      tax: '558.00',
      invoiced: '3658.00',
      debit_notes: '236.00',
      credit_notes: '118.00',
      net_revenue: '3776.00',
      refunds_awaiting_approval: '500.00',
      outstanding_dues: '850.00',
    },
    by_branch: [
      {
        name: 'Andheri',
        rental: '1000.00',
        add_ons: '200.00',
        discounts: '-100.00',
        tax: '198.00',
        debit_notes: '236.00',
        credit_notes: '118.00',
        net_revenue: '1416.00',
      },
    ],
    by_category: [],
    by_method: [{ method: 'Card', charges: '1534.00', refunds: '118.00', net: '1416.00' }],
    ...overrides,
  }
}

export function makeMaintenance(overrides: Partial<MaintenanceReport> = {}): MaintenanceReport {
  const zero = { jobs: 0, automatic: 0, labour: '0.00', parts: '0.00', total: '0.00' }
  return {
    ...HEADER,
    totals: { jobs: 2, labour: '1300.00', parts: '2000.00', total: '3300.00', invoices_attached: 1 },
    by_vehicle: [
      {
        vehicle_id: 7,
        registration_no: 'MH02DB2001',
        vehicle: 'Maruti Suzuki Baleno',
        branch: 'Andheri',
        jobs: 1,
        labour: '800.00',
        parts: '1700.00',
        total: '2500.00',
      },
    ],
    by_job_type: [
      { job_type: 'Preventive', jobs: 1, automatic: 1, labour: '500.00', parts: '300.00', total: '800.00' },
      { job_type: 'Corrective', jobs: 1, automatic: 0, labour: '800.00', parts: '1700.00', total: '2500.00' },
      { job_type: 'Inspection', ...zero },
      { job_type: 'Cleaning', ...zero },
      { job_type: 'Documentation', ...zero },
    ],
    ...overrides,
  }
}

export function makeCustomers(overrides: Partial<CustomerReport> = {}): CustomerReport {
  return {
    ...HEADER,
    totals: { new: 2, active: 2, no_shows: 1, with_dues: 1, dues_total: '850.00' },
    top: [
      { customer_id: 3, name: 'Asha Rao', email: 'asha@example.com', bookings: 2, no_shows: 1, net_revenue: '2360.00' },
    ],
    with_dues: [{ customer_id: 4, name: '=Ravi Kumar', email: 'ravi@example.com', outstanding_due: '850.00' }],
    ...overrides,
  }
}

export const EMPTY_REPORTS = {
  utilisation: makeUtilisation({ by_vehicle: [], by_category: [], by_branch: [], least_utilised: [] }),
  revenue: makeRevenue({ by_branch: [], by_method: [] }),
  maintenance: makeMaintenance({ by_vehicle: [] }),
  customers: makeCustomers({ top: [], with_dues: [] }),
}
