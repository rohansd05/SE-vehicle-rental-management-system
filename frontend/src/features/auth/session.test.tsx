// The session in the running app (SE-9, D19, D21).

import { act, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, makeAccessToken, server, signedInAs, USERS } from '@/test/server'

import { SIGN_OUT_MESSAGES } from './messages'

describe('session', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('restores the session from the refresh cookie on page load', async () => {
    signedInAs('CUSTOMER')
    renderApp({ route: '/app' })
    expect(await screen.findByRole('heading', { name: 'Welcome, Asha Rao' })).toBeInTheDocument()
  })

  it('sends signed-out visitors to sign in', async () => {
    renderApp({ route: '/app/profile' })
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('signs the user out when a refresh fails', async () => {
    let refreshes = 0
    server.use(
      http.post(`${API}/auth/refresh/`, () => {
        refreshes += 1
        return refreshes === 1
          ? HttpResponse.json({ access: makeAccessToken(), user: USERS.CUSTOMER })
          : HttpResponse.json({ detail: 'ended', code: 'session_ended' }, { status: 401 })
      }),
      http.get(`${API}/me/`, () => HttpResponse.json({ detail: 'expired' }, { status: 401 })),
    )
    renderApp({ route: '/app/profile' })
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText(SIGN_OUT_MESSAGES['session-expired'])).toBeInTheDocument()
    expect(refreshes).toBe(2) // page load, then the one retry attempt
  })

  it('signs an inactive user out after 30 minutes, without refreshing', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let refreshes = 0
    server.use(
      http.post(`${API}/auth/refresh/`, () => {
        refreshes += 1
        return HttpResponse.json({ access: makeAccessToken(5 * 60), user: USERS.CUSTOMER })
      }),
    )
    renderApp({ route: '/app' })
    expect(await screen.findByRole('heading', { name: 'Welcome, Asha Rao' })).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30 * 60 * 1000)
    })
    expect(await screen.findByText(SIGN_OUT_MESSAGES.inactivity)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(refreshes).toBe(1) // only the page-load restore: no blind refresh
  })

  it('never puts a token in localStorage or sessionStorage', async () => {
    const access = makeAccessToken()
    server.use(
      http.post(`${API}/auth/login/`, () => HttpResponse.json({ access, user: USERS.CUSTOMER })),
    )
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const user = userEvent.setup()
    renderApp({ route: '/login' })
    await user.type(await screen.findByLabelText('E-mail'), 'customer@vrms.test')
    await user.type(screen.getByLabelText('Password'), 'Demo@1234')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('heading', { name: 'Welcome, Asha Rao' })

    expect(setItem).not.toHaveBeenCalled()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
    expect(document.cookie).not.toContain(access)
  })

  it('sign-out ends the session and returns to sign in', async () => {
    signedInAs('CUSTOMER')
    const logout = vi.fn(() => new HttpResponse(null, { status: 204 }))
    server.use(http.post(`${API}/auth/logout/`, logout))
    const user = userEvent.setup()
    renderApp({ route: '/app' })
    await user.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(logout).toHaveBeenCalledTimes(1)
  })
})
