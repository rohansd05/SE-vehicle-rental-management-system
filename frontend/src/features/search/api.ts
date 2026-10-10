// Catalogue and availability search (SRS 3.2). Public endpoints: any visitor
// may browse and search (Search.Browse); the server applies every rule (CO-3).

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type Branch = Schemas['Branch']
export type VehicleCategory = Schemas['VehicleCategory']
export type AvailableVehicle = Schemas['AvailableVehicle']
export type SearchResults = Schemas['PaginatedAvailableVehicleList']

/** A search as sent to the server: date-times are UTC ISO strings (CO-6). */
export interface SearchQuery {
  branch: string
  pickup_datetime: string
  return_datetime: string
  category?: string
  page?: number
}

const BASE = '/api/v1/fleet'

export const listBranches = () => apiRequest<Branch[]>(`${BASE}/branches/`, { auth: false })

export const listCategories = () =>
  apiRequest<VehicleCategory[]>(`${BASE}/categories/`, { auth: false })

/** Search.Available: vehicles bookable for the whole period. */
export function searchVehicles(query: SearchQuery) {
  const params = new URLSearchParams({
    branch: query.branch,
    pickup_datetime: query.pickup_datetime,
    return_datetime: query.return_datetime,
  })
  if (query.category) params.set('category', query.category)
  if (query.page && query.page > 1) params.set('page', String(query.page))
  return apiRequest<SearchResults>(`${BASE}/search/?${params.toString()}`, { auth: false })
}
