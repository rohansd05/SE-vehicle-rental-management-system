import { useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { login, logout, refreshSession } from '@/api/auth'
import { installSessionHooks } from '@/api/client'
import type { SessionUser } from '@/api/types'
import { SessionActivity, setAccessToken } from '@/lib/session'

import {
  AuthContext,
  type AuthContextValue,
  type AuthStatus,
  type SignOutReason,
} from './auth-context'

interface State {
  status: AuthStatus
  user: SessionUser | null
  signOutReason: SignOutReason | null
}

/**
 * Holds the signed-in user and enforces the session rules (SE-9, D19, D21):
 * restores the session from the refresh cookie on page load, refreshes only
 * after user activity, and ends the session after 30 idle minutes.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [state, setState] = useState<State>({
    status: 'loading',
    user: null,
    signOutReason: null,
  })
  const activity = useRef<SessionActivity | null>(null)

  const endSession = useCallback(
    (reason: SignOutReason) => {
      setAccessToken(null)
      activity.current?.stop()
      queryClient.clear() // nothing of this user's data stays in memory
      setState({ status: 'signed-out', user: null, signOutReason: reason })
    },
    [queryClient],
  )

  const signOut = useCallback(
    async (reason: SignOutReason = 'signed-out') => {
      await logout() // revokes and clears the refresh cookie; never throws
      endSession(reason)
    },
    [endSession],
  )

  const refresh = useCallback(async () => {
    try {
      const user = await refreshSession()
      if (!user) return false
      setState((current) => ({ ...current, user }))
      activity.current?.markRefreshed()
      return true
    } catch {
      return false
    }
  }, [])

  // The API client asks for one refresh on a 401, and ends the session if
  // that fails.
  useEffect(() => {
    installSessionHooks({
      refresh,
      onSessionLost: () => {
        void logout()
        endSession('session-expired')
      },
    })
    return () => installSessionHooks(null)
  }, [refresh, endSession])

  // Restore the session from the httpOnly cookie when the page loads.
  useEffect(() => {
    let cancelled = false
    refreshSession()
      .then((user) => {
        if (cancelled) return
        setState(
          user
            ? { status: 'signed-in', user, signOutReason: null }
            : { status: 'signed-out', user: null, signOutReason: null },
        )
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'signed-out', user: null, signOutReason: null })
      })
    return () => {
      cancelled = true
    }
  }, [])

  // While signed in, watch activity: refresh only when active, sign out when idle.
  useEffect(() => {
    if (state.status !== 'signed-in') return
    const watcher = new SessionActivity({
      refresh,
      onIdle: () => void signOut('inactivity'),
    })
    activity.current = watcher
    watcher.start()
    return () => {
      watcher.stop()
      if (activity.current === watcher) activity.current = null
    }
  }, [state.status, refresh, signOut])

  const signIn = useCallback(async (email: string, password: string) => {
    const user = await login(email, password)
    setState({ status: 'signed-in', user, signOutReason: null })
    return user
  }, [])

  const updateUser = useCallback((changes: Partial<Pick<SessionUser, 'name'>>) => {
    setState((current) =>
      current.user ? { ...current, user: { ...current.user, ...changes } } : current,
    )
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, signIn, signOut, updateUser }),
    [state, signIn, signOut, updateUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
