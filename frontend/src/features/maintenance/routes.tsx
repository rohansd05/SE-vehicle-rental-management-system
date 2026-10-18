// Maintenance routes, mounted under /app by one line in AppRoutes. Returned as
// a fragment of <Route>s (not a component) so <Routes> can read them.
// RequireRole only shapes the screen; the API checks every request (SE-4).

import type { ReactNode } from 'react'
import { Route } from 'react-router-dom'

import type { Role } from '@/api/types'
import { RequireRole } from '@/app/guards'

import { BranchJobsPage, ClearanceQueuePage, JobDetailPage, MyJobsPage, ReportFaultPage, VehicleHistoryPage } from './lazy'

const TECHNICIAN: readonly Role[] = ['MAINTENANCE_TECHNICIAN']
/** Maint.Create, Maint.Schedule (Proposed M11 includes the Branch Manager). */
export const JOB_MANAGERS: readonly Role[] = ['BRANCH_STAFF', 'BRANCH_MANAGER', 'ADMINISTRATOR']
const ADMINISTRATOR: readonly Role[] = ['ADMINISTRATOR']

const guard = (roles: readonly Role[], page: ReactNode) => (
  <RequireRole roles={roles}>{page}</RequireRole>
)

export function maintenanceRoutes() {
  return (
    <>
      <Route path="jobs" element={guard(TECHNICIAN, <MyJobsPage />)} />
      <Route path="jobs/:id" element={guard(TECHNICIAN, <JobDetailPage />)} />
      <Route
        path="jobs/vehicles/:id/history"
        element={guard(TECHNICIAN, <VehicleHistoryPage basePath="/app/jobs" />)}
      />
      <Route path="maintenance" element={guard(JOB_MANAGERS, <BranchJobsPage />)} />
      <Route path="maintenance/report" element={guard(JOB_MANAGERS, <ReportFaultPage />)} />
      <Route path="maintenance/:id" element={guard(JOB_MANAGERS, <JobDetailPage />)} />
      <Route
        path="maintenance/vehicles/:id/history"
        element={guard(JOB_MANAGERS, <VehicleHistoryPage basePath="/app/maintenance" />)}
      />
      <Route path="clearances" element={guard(ADMINISTRATOR, <ClearanceQueuePage />)} />
    </>
  )
}
