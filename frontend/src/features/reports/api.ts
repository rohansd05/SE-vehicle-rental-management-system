// Reports (SRS 3.8 Report.*; UC 14 View Reports). The server computes every figure for the
// caller's scope (Report.Access: an Administrator every branch, a Branch Manager their own)
// and refuses everyone else (SE-4); this screen only shows its answers (CO-3).

import { apiRequest } from '@/api/client'
import type { components } from '@/api/schema'

type Schemas = components['schemas']

export type Dashboard = Schemas['Dashboard']
export type UtilisationReport = Schemas['UtilisationReport']
export type RevenueReport = Schemas['RevenueReport']
export type MaintenanceReport = Schemas['MaintenanceCostReport']
export type CustomerReport = Schemas['CustomerReport']

export interface Reports {
  utilisation: UtilisationReport
  revenue: RevenueReport
  maintenance: MaintenanceReport
  customers: CustomerReport
}
export type ReportType = keyof Reports

/** UC 14 step 1: the period, as local dates (YYYY-MM-DD), both included. */
export interface ReportPeriod {
  date_from: string
  date_to: string
}

export const REPORTS_KEY = ['reports'] as const
export const DASHBOARD_KEY = ['reports', 'summary'] as const

/** Report.Dashboard for the home page. */
export const getDashboard = () => apiRequest<Dashboard>('/api/v1/reports/summary/')

/** UC 14 step 2: the report the actor selected, for the period. */
export function getReport<T extends ReportType>(type: T, period: ReportPeriod): Promise<Reports[T]> {
  return apiRequest<Reports[T]>(`/api/v1/reports/${type}/?${new URLSearchParams({ ...period })}`)
}
