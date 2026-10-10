import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, makeAccessToken, server, USERS } from '@/test/server'

import { LOCKED_MESSAGE } from './messages'

async function signIn(password = 'Demo@1234') {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('E-mail'), 'customer@vrms.test')
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('Sign in', () => {
  it('signs in and lands on the home page', async () => {
    server.use(
      http.post(`${API}/auth/login/`, () =>
        HttpResponse.json({ access: makeAccessToken(), user: USERS.CUSTOMER }),
      ),
    )
    renderApp({ route: '/login' })
    await signIn()
    expect(await screen.findByRole('heading', { name: 'Welcome, Asha Rao' })).toBeInTheDocument()
  })

  it('shows the server’s generic message for a wrong password', async () => {
    server.use(
      http.post(`${API}/auth/login/`, () =>
        HttpResponse.json(
          { detail: 'Unable to sign in with the details provided.', code: 'authentication_failed' },
          { status: 401 },
        ),
      ),
    )
    renderApp({ route: '/login' })
    await signIn('wrong')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to sign in with the details provided.',
    )
  })

  it('explains a locked account (SE-8)', async () => {
    server.use(
      http.post(`${API}/auth/login/`, () =>
        HttpResponse.json(
          { detail: 'Too many failed sign-in attempts.', code: 'account_locked' },
          { status: 403 },
        ),
      ),
    )
    renderApp({ route: '/login' })
    await signIn('wrong')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(LOCKED_MESSAGE)
    expect(alert).toHaveTextContent('15 minutes')
    expect(alert).toHaveTextContent('Check your e-mail')
  })

  it('validates the form before sending', async () => {
    const user = userEvent.setup()
    renderApp({ route: '/login' })
    await user.click(await screen.findByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid e-mail address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
  })
})
