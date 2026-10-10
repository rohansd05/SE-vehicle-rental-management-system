import { createContext, useContext } from 'react'

import type { SessionUser } from '@/api/types'

export type AuthStatus = 'loading' | 'signed-in' | 'signed-out'

/** Why the last session ended; the sign-in page explains it. */
export type SignOutReason = 'signed-out' | 'inactivity' | 'session-expired' | 'password-changed'

export interface AuthContextValue {
  status: AuthStatus
  user: SessionUser | null
  signOutReason: SignOutReason | null
  signIn: (email: string, password: string) => Promise<SessionUser>
  signOut: (reason?: SignOutReason) => Promise<void>
  updateUser: (changes: Partial<Pick<SessionUser, 'name'>>) => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/** For screens that only render when signed in (inside RequireAuth). */
export function useSignedInUser(): SessionUser {
  const { user } = useAuth()
  if (!user) throw new Error('useSignedInUser needs a signed-in user')
  return user
}
