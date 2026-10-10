// Maintenance endpoints (SRS 3.6, Exp 4 sequence 3, BR-15, BR-16).
// Owner: Nidhi. The server enforces every rule and scope (CO-3, SE-4, SE-5).

import { apiRequest } from './client'
import type { components } from './schema'

type Schemas = components['schemas']

export type MaintenanceJob = Schemas['MaintenanceJob']
export type JobStatus = Schemas['MaintenanceJobStatusEnum']
export type JobType = Schemas['JobTypeEnum']
export type Severity = Schemas['SeverityEnum']
export type MaintenanceVehicle = Schemas['MaintenanceVehicle']
export type VehicleStatus = Schemas['MaintenanceVehicleStatusEnum']
export type Technician = Schemas['Technician']
export type PaginatedJobs = Schemas['PaginatedMaintenanceJobList']
export type ReportJobRequest = Schemas['ReportJob']
export type ScheduleJobRequest = Schemas['ScheduleJob']
export type RecordWorkRequest = Schemas['RecordWork']
export type ScheduleConflict = Schemas['ScheduleConflict']
export type WorkIncomplete = Schemas['WorkIncomplete']

export const JOB_STATUSES = [
  'Reported',
  'Scheduled',
  'In Progress',
  'Completed',
  'Cancelled',
] as const satisfies readonly JobStatus[]

export const JOB_TYPES = [
  'Preventive',
  'Corrective',
  'Inspection',
  'Cleaning',
  'Documentation',
] as const satisfies readonly JobType[]

export const SEVERITIES = ['Low', 'Medium', 'High', 'Critical'] as const satisfies readonly Severity[]

const BASE = '/api/v1/maintenance'

export function listJobs(filters: { status?: JobStatus | '' } = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  const query = params.toString()
  return apiRequest<PaginatedJobs>(`${BASE}/jobs/${query ? `?${query}` : ''}`)
}

export const getJob = (id: number) => apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/`)

export const reportJob = (data: ReportJobRequest) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/`, { method: 'POST', json: data })

export const scheduleJob = (id: number, data: ScheduleJobRequest) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/schedule/`, { method: 'POST', json: data })

export const cancelJob = (id: number, reason: string) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/cancel/`, { method: 'POST', json: { reason } })

export const startJob = (id: number) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/start/`, { method: 'POST' })

export const recordWork = (id: number, data: RecordWorkRequest) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/record/`, { method: 'PUT', json: data })

/** Exp 4 sequence 3: MaintenanceJob.complete_job(). */
export const completeJob = (id: number) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/complete/`, { method: 'POST' })

export const listClearances = () => apiRequest<PaginatedJobs>(`${BASE}/clearances/`)

/** BR-16: an Administrator clears the Unsafe flag and the job completes. */
export const approveClearance = (id: number) =>
  apiRequest<MaintenanceJob>(`${BASE}/jobs/${id}/approve-clearance/`, { method: 'POST' })

export const listTechnicians = () => apiRequest<Technician[]>(`${BASE}/technicians/`)

export const listMaintenanceVehicles = () =>
  apiRequest<MaintenanceVehicle[]>(`${BASE}/vehicles/`)
