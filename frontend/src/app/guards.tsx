import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import type { Role } from '@/api/types'
import { LoadingState } from '@/components/states'
import { useAuth } from '@/features/auth/auth-context'
import { ForbiddenPage } from '@/pages/ForbiddenPage'

/** Signed-in users only; others go to sign-in and come back afterwards (SE-3). */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return (
      <div className="flex min-h-svh items-center justify-center px-4">
        <LoadingState label="Restoring your session…" />
      </div>
    )
  }
  if (status === 'signed-out') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return children
}

/**
 * Role guard (UI-1, SE-4). This only decides what the screen shows: the API
 * checks the role again on every request, so hiding a page is never the
 * only control.
 */
export function RequireRole({ roles, children }: { roles: readonly Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <ForbiddenPage />
  return children
}

/** Sign-in and registration make no sense once signed in. */
export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'signed-in') return <Navigate to="/app" replace />
  return children
}
