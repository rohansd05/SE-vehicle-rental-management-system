// Reports (Module R3, UC 14), mounted under /app by one line in AppRoutes. Returned as a
// fragment of <Route>s (not a component) so <Routes> can read them. RequireRole only shapes
// the screen; the API refuses every other role (Report.Access, SE-4).

import { Suspense } from 'react'
import { Route } from 'react-router-dom'

import type { Role } from '@/api/types'
import { RequireRole } from '@/app/guards'
import { LoadingState } from '@/components/states'

import { ReportsPage } from './lazy'

/** Report.Access: Administrators, and Branch Managers for their own branch (UC 14 1a). */
const REPORT_READERS: readonly Role[] = ['ADMINISTRATOR', 'BRANCH_MANAGER']

export function reportRoutes() {
  return (
    <Route
      path="reports"
      element={
        <RequireRole roles={REPORT_READERS}>
          <Suspense fallback={<LoadingState label="Loading the reports…" />}>
            <ReportsPage />
          </Suspense>
        </RequireRole>
      }
    />
  )
}
