// Administration endpoints (Module N3): fleet, tariffs, users and blacklist, audit log.
// SRS 3.7 (Fleet.*, Fleet.Tariff, Fleet.Users, Fleet.Audit), BR-4, BR-13; Exp 2 UC 11, 12.
// Owner: Nidhi. The server enforces every rule and permission (CO-3, SE-4).

import { apiRequest } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type AdminVehicle = Schemas['AdminVehicle']
export type AdminVehicleDetail = Schemas['AdminVehicleDetail']
export type AdminDocument = Schemas['AdminDocument']
export type AdminBranch = Schemas['AdminBranch']
export type VehicleUpdate = Schemas['PatchedVehicleUpdate']
export type DocumentType = Schemas['DocumentTypeEnum']
export type FuelType = Schemas['FuelTypeEnum']
export type VehicleCategory = Schemas['VehicleCategory']
export type AdminTariff = Schemas['AdminTariff']
export type TariffInput = Schemas['TariffInput']
export type AdminAddOn = Schemas['AdminAddOn']
export type AdminDiscountCode = Schemas['AdminDiscountCode']
export type DiscountType = Schemas['DiscountTypeEnum']
export type StaffAccount = Schemas['StaffAccount']
export type StaffCreate = Schemas['StaffCreate']
export type StaffUpdate = Schemas['PatchedStaffUpdate']
export type StaffRole = Schemas['StaffRoleEnum']
export type AdminCustomer = Schemas['AdminCustomer']
export type AdminCustomerDetail = Schemas['AdminCustomerDetail']
export type OpenBooking = Schemas['OpenBooking']
export type CancellationQuote = Schemas['CancellationQuote']
export type AuditEntry = Schemas['AuditEntry']
export type AuditFilterOptions = Schemas['AuditFilterOptions']
type Page<T> = { count: number; next?: string | null; previous?: string | null; results: T[] }

/** The four statutory documents (SA-3, Handover.Refuse), in the order the forms ask. */
export const DOCUMENT_TYPES = [
  'Insurance',
  'Pollution Certificate',
  'Fitness Certificate',
  'Road Tax',
] as const satisfies readonly DocumentType[]

export const FUEL_TYPES = ['Petrol', 'Diesel', 'CNG', 'Electric'] as const satisfies readonly FuelType[]

export const STAFF_ROLES = [
  'BRANCH_STAFF',
  'MAINTENANCE_TECHNICIAN',
  'BRANCH_MANAGER',
] as const satisfies readonly StaffRole[]

function query(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value)
  const text = search.toString()
  return text ? `?${text}` : ''
}

// ─── Fleet (Fleet.Add, Fleet.Status, Fleet.Retire; UC 11) ─────────────────

const FLEET = '/api/v1/fleet/admin'

export const listVehicles = (filters: { status?: string; q?: string } = {}) =>
  apiRequest<Page<AdminVehicle>>(`${FLEET}/vehicles/${query(filters)}`)

export const getVehicle = (id: number) => apiRequest<AdminVehicleDetail>(`${FLEET}/vehicles/${id}/`)

/** Fleet.Add: multipart, with `photos` repeated and `documents` as a JSON list. */
export const createVehicle = (form: FormData) =>
  apiRequest<AdminVehicleDetail>(`${FLEET}/vehicles/`, { method: 'POST', form })

export const updateVehicle = (id: number, data: VehicleUpdate) =>
  apiRequest<AdminVehicleDetail>(`${FLEET}/vehicles/${id}/`, { method: 'PATCH', json: data })

export const retireVehicle = (id: number, reason: string) =>
  apiRequest<AdminVehicleDetail>(`${FLEET}/vehicles/${id}/retire/`, { method: 'POST', json: { reason } })

export function addPhoto(id: number, image: File) {
  const form = new FormData()
  form.append('image', image)
  return apiRequest(`${FLEET}/vehicles/${id}/photos/`, { method: 'POST', form })
}

export const removePhoto = (id: number, photoId: number) =>
  apiRequest<void>(`${FLEET}/vehicles/${id}/photos/${photoId}/`, { method: 'DELETE' })

export const addDocument = (id: number, form: FormData) =>
  apiRequest<AdminDocument>(`${FLEET}/vehicles/${id}/documents/`, { method: 'POST', form })

export const removeDocument = (id: number, documentId: number) =>
  apiRequest<void>(`${FLEET}/vehicles/${id}/documents/${documentId}/`, { method: 'DELETE' })

export const listCategories = () => apiRequest<VehicleCategory[]>('/api/v1/fleet/categories/', { auth: false })

export const listBranches = () => apiRequest<AdminBranch[]>(`${FLEET}/branches/`)

export const createBranch = (data: { branch_name: string; address: string }) =>
  apiRequest<AdminBranch>(`${FLEET}/branches/`, { method: 'POST', json: data })

export const updateBranch = (id: number, data: { branch_name?: string; address?: string }) =>
  apiRequest<AdminBranch>(`${FLEET}/branches/${id}/`, { method: 'PATCH', json: data })

export const addArea = (branchId: number, data: { pincode: string; locality: string }) =>
  apiRequest(`${FLEET}/branches/${branchId}/areas/`, { method: 'POST', json: data })

export const removeArea = (branchId: number, areaId: number) =>
  apiRequest<void>(`${FLEET}/branches/${branchId}/areas/${areaId}/`, { method: 'DELETE' })

// ─── Tariffs, add-ons, discount codes (Fleet.Tariff, BR-13, D17) ──────────

const PRICING = '/api/v1/pricing/admin'

export const listTariffs = () => apiRequest<AdminTariff[]>(`${PRICING}/tariffs/`)

export const defineTariff = (data: TariffInput) =>
  apiRequest<AdminTariff>(`${PRICING}/tariffs/`, { method: 'POST', json: data })

export const withdrawTariff = (id: number) =>
  apiRequest<void>(`${PRICING}/tariffs/${id}/`, { method: 'DELETE' })

export const listAddOns = () => apiRequest<AdminAddOn[]>(`${PRICING}/add-ons/`)

export const saveAddOn = (data: Partial<AdminAddOn>, id?: number) =>
  id
    ? apiRequest<AdminAddOn>(`${PRICING}/add-ons/${id}/`, { method: 'PATCH', json: data })
    : apiRequest<AdminAddOn>(`${PRICING}/add-ons/`, { method: 'POST', json: data })

export const listDiscountCodes = () => apiRequest<AdminDiscountCode[]>(`${PRICING}/discount-codes/`)

export const saveDiscountCode = (data: Partial<AdminDiscountCode>, id?: number) =>
  id
    ? apiRequest<AdminDiscountCode>(`${PRICING}/discount-codes/${id}/`, { method: 'PATCH', json: data })
    : apiRequest<AdminDiscountCode>(`${PRICING}/discount-codes/`, { method: 'POST', json: data })

// ─── Staff accounts and the blacklist (Fleet.Users, BR-4; UC 12) ──────────

const ADMIN = '/api/v1/admin'

export const listStaff = (filters: { role?: string; is_active?: string; q?: string } = {}) =>
  apiRequest<Page<StaffAccount>>(`${ADMIN}/users/${query(filters)}`)

export const getStaff = (id: number) => apiRequest<StaffAccount>(`${ADMIN}/users/${id}/`)

export const createStaff = (data: StaffCreate) =>
  apiRequest<StaffAccount>(`${ADMIN}/users/`, { method: 'POST', json: data })

export const updateStaff = (id: number, data: StaffUpdate) =>
  apiRequest<StaffAccount>(`${ADMIN}/users/${id}/`, { method: 'PATCH', json: data })

export const setStaffActive = (id: number, active: boolean, reason: string) =>
  apiRequest<StaffAccount>(`${ADMIN}/users/${id}/${active ? 'enable' : 'disable'}/`, {
    method: 'POST',
    json: { reason },
  })

/** BR-16: authorise a technician to clear an Unsafe flag, or revoke it. */
export const setUnsafeAuthorisation = (technicianId: number, authorised: boolean) =>
  apiRequest(`/api/v1/maintenance/technicians/${technicianId}/authorisation/`, {
    method: authorised ? 'PUT' : 'DELETE',
  })

export const listCustomers = (filters: { q?: string; blacklisted?: string } = {}) =>
  apiRequest<Page<AdminCustomer>>(`${ADMIN}/customers/${query(filters)}`)

export const getCustomer = (id: number) => apiRequest<AdminCustomerDetail>(`${ADMIN}/customers/${id}/`)

export const setBlacklisted = (id: number, blacklisted: boolean, reason: string) =>
  apiRequest<AdminCustomerDetail>(
    `${ADMIN}/customers/${id}/${blacklisted ? 'blacklist' : 'lift-blacklist'}/`,
    { method: 'POST', json: { reason } },
  )

/** UC 12 extension 2a, through R2's cancellation (BR-8). */
export const cancellationQuote = (customerId: number, bookingId: number) =>
  apiRequest<CancellationQuote>(`${ADMIN}/customers/${customerId}/bookings/${bookingId}/cancel/`)

export const cancelCustomerBooking = (
  customerId: number,
  bookingId: number,
  data: { expected_refund: string; password: string },
) =>
  apiRequest<OpenBooking>(`${ADMIN}/customers/${customerId}/bookings/${bookingId}/cancel/`, {
    method: 'POST',
    json: data,
  })

// ─── Audit log (Fleet.Audit, SE-10) ───────────────────────────────────────

export interface AuditFilters {
  actor?: string
  action?: string
  entity_type?: string
  entity_id?: string
  date_from?: string
  date_to?: string
  page?: string
}

export const listAudit = (filters: AuditFilters = {}) =>
  apiRequest<Page<AuditEntry>>(`/api/v1/audit/${query({ ...filters })}`)

export const auditFilterOptions = () => apiRequest<AuditFilterOptions>('/api/v1/audit/filters/')
