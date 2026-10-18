// Administration routes (Module N3), mounted under /app by one line in AppRoutes. Returned
// as a fragment of <Route>s (not a component) so <Routes> can read them. RequireRole only
// shapes the screen; the API checks every request (SE-4).

import type { ReactNode } from 'react'
import { Route } from 'react-router-dom'

import type { Role } from '@/api/types'
import { RequireRole } from '@/app/guards'

import { AuditPage } from './AuditPage'
import { BranchesPage } from './BranchesPage'
import { CustomerPage } from './CustomerPage'
import { FleetPage } from './FleetPage'
import { StaffFormPage, StaffPage } from './StaffPages'
import { TariffsPage } from './TariffsPage'
import { UsersPage } from './UsersPage'
import { VehicleFormPage } from './VehicleFormPage'
import { VehiclePage } from './VehiclePage'

const ADMINISTRATOR: readonly Role[] = ['ADMINISTRATOR']
/** Fleet.Audit: Administrators; a Branch Manager reads their own branch's entries. */
const AUDIT_READERS: readonly Role[] = ['ADMINISTRATOR', 'BRANCH_MANAGER']

const guard = (roles: readonly Role[], page: ReactNode) => <RequireRole roles={roles}>{page}</RequireRole>

export function adminRoutes() {
  return (
    <>
      <Route path="fleet" element={guard(ADMINISTRATOR, <FleetPage />)} />
      <Route path="fleet/new" element={guard(ADMINISTRATOR, <VehicleFormPage />)} />
      <Route path="fleet/branches" element={guard(ADMINISTRATOR, <BranchesPage />)} />
      <Route path="fleet/:id" element={guard(ADMINISTRATOR, <VehiclePage />)} />
      <Route path="tariffs" element={guard(ADMINISTRATOR, <TariffsPage />)} />
      <Route path="users" element={guard(ADMINISTRATOR, <UsersPage />)} />
      <Route path="users/new" element={guard(ADMINISTRATOR, <StaffFormPage />)} />
      <Route path="users/customers/:id" element={guard(ADMINISTRATOR, <CustomerPage />)} />
      <Route path="users/:id" element={guard(ADMINISTRATOR, <StaffPage />)} />
      <Route path="audit" element={guard(AUDIT_READERS, <AuditPage />)} />
    </>
  )
}
