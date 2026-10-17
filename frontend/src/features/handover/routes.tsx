// Handover routes, mounted under /app by one line in AppRoutes. Returned as a
// fragment of <Route>s (not a component) so <Routes> can read them.
// RequireRole only shapes the screen; the API checks every request (SE-4).

import type { ReactNode } from 'react'
import { Route } from 'react-router-dom'

import type { Role } from '@/api/types'
import { RequireRole } from '@/app/guards'

import { BranchBookingsPage, HandoverDeskPage } from './CollectionsPage'
import { HandoverPage } from './HandoverPage'
import { ReturnPage } from './ReturnPage'

/** Exp 2 UC 7 and UC 8: Branch Staff hand vehicles over and take them back. */
const STAFF: readonly Role[] = ['BRANCH_STAFF']
/** Branch Managers follow their branch's bookings, read only. */
const BRANCH_TEAM: readonly Role[] = ['BRANCH_STAFF', 'BRANCH_MANAGER']

const guard = (roles: readonly Role[], page: ReactNode) => <RequireRole roles={roles}>{page}</RequireRole>

export function handoverRoutes() {
  return (
    <>
      <Route path="handover" element={guard(STAFF, <HandoverDeskPage />)} />
      <Route path="handover/:id" element={guard(BRANCH_TEAM, <HandoverPage />)} />
      <Route path="branch-bookings" element={guard(BRANCH_TEAM, <BranchBookingsPage />)} />
      <Route path="returns/:id" element={guard(BRANCH_TEAM, <ReturnPage />)} />
    </>
  )
}
