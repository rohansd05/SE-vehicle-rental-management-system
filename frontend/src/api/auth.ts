// Authentication, OTP and profile endpoints (SE-7 to SE-9, D19, D21).

import { setAccessToken } from '@/lib/session'

import { ApiError, apiRequest } from './client'
import {
  toSessionUser,
  type AccessTokenResponse,
  type Detail,
  type PasswordChangeRequest,
  type Profile,
  type ProfileUpdate,
  type ProfileUpdateResponse,
  type RegisterRequest,
  type RegisterResponse,
  type SessionUser,
} from './types'

const AUTH = '/api/v1/auth'

export async function login(email: string, password: string): Promise<SessionUser> {
  const response = await apiRequest<AccessTokenResponse>(`${AUTH}/login/`, {
    method: 'POST',
    json: { email, password },
    auth: false,
  })
  setAccessToken(response.access)
  return toSessionUser(response.user)
}

let inflightRefresh: Promise<SessionUser | null> | null = null

/**
 * Trade the httpOnly refresh cookie for a new access token (D21).
 * Single-flight: concurrent callers share one request, because the cookie
 * rotates and a second, parallel use of the old one would be refused.
 * Resolves null when there is no session to restore or renew.
 */
export function refreshSession(): Promise<SessionUser | null> {
  if (!inflightRefresh) {
    inflightRefresh = (async () => {
      try {
        const response = await apiRequest<AccessTokenResponse>(`${AUTH}/refresh/`, {
          method: 'POST',
          auth: false,
        })
        setAccessToken(response.access)
        return toSessionUser(response.user)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          setAccessToken(null)
          return null
        }
        throw error
      }
    })().finally(() => {
      inflightRefresh = null
    })
  }
  return inflightRefresh
}

/** Revoke the refresh cookie on the server. Never throws: signing out always works. */
export async function logout(): Promise<void> {
  try {
    await apiRequest<void>(`${AUTH}/logout/`, { method: 'POST', auth: false })
  } catch {
    // Offline or already signed out; the local session ends regardless.
  } finally {
    setAccessToken(null)
  }
}

export const register = (data: RegisterRequest) =>
  apiRequest<RegisterResponse>(`${AUTH}/register/`, { method: 'POST', json: data, auth: false })

export const verifyOtp = (email: string, code: string) =>
  apiRequest<Detail>(`${AUTH}/verify-otp/`, { method: 'POST', json: { email, code }, auth: false })

export const resendOtp = (email: string) =>
  apiRequest<Detail>(`${AUTH}/resend-otp/`, { method: 'POST', json: { email }, auth: false })

export const getProfile = () => apiRequest<Profile>('/api/v1/me/')

export const updateProfile = (data: ProfileUpdate) =>
  apiRequest<ProfileUpdateResponse>('/api/v1/me/', { method: 'PATCH', json: data })

export const confirmMobile = (code: string) =>
  apiRequest<Profile>('/api/v1/me/verify-mobile/', { method: 'POST', json: { code } })

export const changePassword = (data: PasswordChangeRequest) =>
  apiRequest<Detail>(`${AUTH}/password/change/`, { method: 'POST', json: data })
