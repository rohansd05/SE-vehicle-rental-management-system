import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { getAccessToken, setAccessToken } from '@/lib/session'
import { API, makeAccessToken, server, USERS } from '@/test/server'

import { refreshSession } from './auth'
import { ApiError, apiRequest, installSessionHooks, parseApiError } from './client'

const PROFILE = { id: 1, email: 'a@b.c', name: 'A', mobile_no: '1', address: '', role: 'CUSTOMER' }

describe('a 401 triggers one refresh and one retry', () => {
  it('retries once with the new token', async () => {
    const seen: (string | null)[] = []
    server.use(
      http.get(`${API}/me/`, ({ request }) => {
        seen.push(request.headers.get('Authorization'))
        return request.headers.get('Authorization') === 'Bearer new'
          ? HttpResponse.json(PROFILE)
          : HttpResponse.json({ detail: 'Token expired' }, { status: 401 })
      }),
    )
    setAccessToken('old')
    const refresh = vi.fn(async () => {
      setAccessToken('new')
      return true
    })
    const onSessionLost = vi.fn()
    installSessionHooks({ refresh, onSessionLost })

    await expect(apiRequest('/api/v1/me/')).resolves.toEqual(PROFILE)
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(seen).toEqual(['Bearer old', 'Bearer new'])
    expect(onSessionLost).not.toHaveBeenCalled()
  })

  it('never retries more than once', async () => {
    const me = vi.fn(() => HttpResponse.json({ detail: 'no' }, { status: 401 }))
    server.use(http.get(`${API}/me/`, me))
    const refresh = vi.fn(async () => true)
    installSessionHooks({ refresh, onSessionLost: vi.fn() })
    await expect(apiRequest('/api/v1/me/')).rejects.toMatchObject({ status: 401 })
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(me).toHaveBeenCalledTimes(2)
  })

  it('ends the session when the refresh fails', async () => {
    server.use(http.get(`${API}/me/`, () => HttpResponse.json({ detail: 'no' }, { status: 401 })))
    const onSessionLost = vi.fn()
    installSessionHooks({ refresh: async () => false, onSessionLost })
    await expect(apiRequest('/api/v1/me/')).rejects.toBeInstanceOf(ApiError)
    expect(onSessionLost).toHaveBeenCalledTimes(1)
  })

  it('does not refresh for requests made without the session (auth: false)', async () => {
    server.use(
      http.post(`${API}/auth/login/`, () => HttpResponse.json({ detail: 'no' }, { status: 401 })),
    )
    const refresh = vi.fn(async () => true)
    installSessionHooks({ refresh, onSessionLost: vi.fn() })
    await expect(
      apiRequest('/api/v1/auth/login/', { method: 'POST', json: {}, auth: false }),
    ).rejects.toMatchObject({ status: 401 })
    expect(refresh).not.toHaveBeenCalled()
  })
})

describe('refreshSession', () => {
  it('shares one request between concurrent callers (the cookie rotates)', async () => {
    const refresh = vi.fn(() =>
      HttpResponse.json({ access: makeAccessToken(), user: USERS.CUSTOMER }),
    )
    server.use(http.post(`${API}/auth/refresh/`, refresh))
    const [first, second] = await Promise.all([refreshSession(), refreshSession()])
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(first).toEqual(USERS.CUSTOMER)
    expect(second).toEqual(USERS.CUSTOMER)
    expect(getAccessToken()).not.toBeNull()
  })

  it('resolves null and forgets the token when there is no session', async () => {
    setAccessToken('stale')
    await expect(refreshSession()).resolves.toBeNull()
    expect(getAccessToken()).toBeNull()
  })
})

describe('parseApiError', () => {
  it('separates field errors, non-field errors and detail', () => {
    const error = parseApiError(400, {
      email: ['Taken.'],
      non_field_errors: ['Try again.'],
    })
    expect(error.fieldErrors).toEqual({ email: ['Taken.'] })
    expect(error.nonFieldErrors).toEqual(['Try again.'])
    expect(error.message).toBe('Try again.')
  })

  it('reads detail as a string or a list, the code, and Retry-After', () => {
    expect(parseApiError(400, { detail: ['A', 'B'] }).message).toBe('A B')
    const locked = parseApiError(403, { detail: 'Locked.', code: 'account_locked' }, '42')
    expect(locked.code).toBe('account_locked')
    expect(locked.retryAfterSeconds).toBe(42)
  })

  it('never shows an HTML error page to the user', () => {
    expect(parseApiError(500, '<html>Server Error</html>').message).toBe(
      'Something went wrong (error 500).',
    )
  })
})
