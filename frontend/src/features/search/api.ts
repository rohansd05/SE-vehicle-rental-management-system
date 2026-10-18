// Catalogue and availability search (SRS 3.2). Public endpoints: any visitor
// may browse and search (Search.Browse); the server applies every rule (CO-3).

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type Branch = Schemas['Branch']
export type VehicleCategory = Schemas['VehicleCategory']
export type AvailableVehicle = Schemas['AvailableVehicle']
export type SearchResults = Schemas['PaginatedAvailableVehicleList']
export type SearchAlternative = Schemas['SearchAlternative']

/** Search.Filter criteria, as sent to the server; an empty value does not filter. */
export const FILTER_KEYS = [
  'category',
  'vehicle_type',
  'brand',
  'model',
  'fuel_type',
  'transmission',
  'min_seats',
  'min_price',
  'max_price',
  'min_rating',
  'sort',
] as const
export type FilterKey = (typeof FILTER_KEYS)[number]

/** A search as sent to the server: date-times are UTC ISO strings (CO-6). */
export interface SearchQuery extends Partial<Record<FilterKey, string>> {
  branch: string
  pickup_datetime: string
  return_datetime: string
  page?: number
}

const BASE = '/api/v1/fleet'

export const listBranches = () => apiRequest<Branch[]>(`${BASE}/branches/`, { auth: false })

export const listCategories = () =>
  apiRequest<VehicleCategory[]>(`${BASE}/categories/`, { auth: false })

/** The query string of a search: the period, then every filter that is set. */
export function searchParams(query: SearchQuery): URLSearchParams {
  const params = new URLSearchParams({
    branch: query.branch,
    pickup_datetime: query.pickup_datetime,
    return_datetime: query.return_datetime,
  })
  for (const key of FILTER_KEYS) {
    const value = query[key]?.trim()
    if (value) params.set(key, value)
  }
  return params
}

/** Search.Available narrowed by Search.Filter, sorted by price or rating. */
export function searchVehicles(query: SearchQuery) {
  const params = searchParams(query)
  if (query.page && query.page > 1) params.set('page', String(query.page))
  return apiRequest<SearchResults>(`${BASE}/search/?${params.toString()}`, { auth: false })
}

/** Exp 2 UC 2 extension 3a: other branches, then nearby dates, with matching vehicles. */
export const searchAlternatives = (query: SearchQuery) =>
  apiRequest<SearchAlternative[]>(`${BASE}/search/alternatives/?${searchParams(query).toString()}`, {
    auth: false,
  })
