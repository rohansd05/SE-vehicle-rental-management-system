// Refund approval (UC 13) and the payments screens, mounted under /app by one
// line in AppRoutes. Returned as a fragment of <Route>s (not a component) so
// <Routes> can read them. RequireRole only shapes the screen; the API checks
// every request (SE-4) and asks for the password before money moves (SE-9).

import type { ReactNode } from 'react'
import { Route } from 'react-router-dom'

import type { Role } from '@/api/types'
import { RequireRole } from '@/app/guards'
import { CashDeskPage } from '@/features/payment/CashDeskPage'
import { DuePage } from '@/features/payment/DuePage'

import { RefundQueuePage } from './RefundQueuePage'

const guard = (roles: readonly Role[], page: ReactNode) => <RequireRole roles={roles}>{page}</RequireRole>

export function paymentRoutes() {
  return (
    <>
      <Route path="refunds" element={guard(['ADMINISTRATOR'], <RefundQueuePage />)} />
      <Route path="cash" element={guard(['BRANCH_STAFF'], <CashDeskPage />)} />
      <Route path="due" element={guard(['CUSTOMER'], <DuePage />)} />
    </>
  )
}
