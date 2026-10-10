import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { SIGN_OUT_MESSAGES } from '@/features/auth/messages'

const PROFILE = {
  id: 1,
  email: 'customer@vrms.test',
  name: 'Asha Rao',
  mobile_no: '+919800000001',
  address: '12 Demo Lane',
  role: 'CUSTOMER',
}

beforeEach(() => {
  signedInAs('CUSTOMER')
  server.use(http.get(`${API}/me/`, () => HttpResponse.json(PROFILE)))
})

describe('Profile', () => {
  it('shows the details', async () => {
    renderApp({ route: '/app/profile' })
    expect(await screen.findByText('12 Demo Lane')).toBeInTheDocument()
    expect(screen.getByText('+919800000001')).toBeInTheDocument()
  })

  it('changes the mobile number only after the OTP sent to it (A10)', async () => {
    const patch = vi.fn()
    let verified = false
    server.use(
      http.patch(`${API}/me/`, async ({ request }) => {
        patch(await request.json())
        return HttpResponse.json({ ...PROFILE, mobile_change_pending: true })
      }),
      http.post(`${API}/me/verify-mobile/`, () => {
        verified = true
        return HttpResponse.json({ ...PROFILE, mobile_no: '+919898989898' })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/profile' })
    await user.type(await screen.findByLabelText('New mobile number'), '+919898989898')
    await user.click(screen.getByRole('button', { name: 'Send code' }))
    expect(patch).toHaveBeenCalledWith({ mobile_no: '+919898989898' })
    await user.type(await screen.findByLabelText('Code sent to +919898989898'), '123456')
    await user.click(screen.getByRole('button', { name: 'Confirm new number' }))
    expect(await screen.findByText('Your mobile number has been changed.')).toBeInTheDocument()
    expect(verified).toBe(true)
  })

  it('a password change signs the user out everywhere and says so (A11)', async () => {
    server.use(
      http.post(`${API}/auth/password/change/`, () =>
        HttpResponse.json({ detail: 'Password changed. Please sign in again.' }),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/profile' })
    await user.type(await screen.findByLabelText('Current password'), 'Demo@1234')
    await user.type(screen.getByLabelText('New password'), 'N3w!Passw0rd-2026')
    await user.type(screen.getByLabelText('Confirm new password'), 'N3w!Passw0rd-2026')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText(SIGN_OUT_MESSAGES['password-changed'])).toBeInTheDocument()
  })

  it('shows a wrong current password next to its field', async () => {
    server.use(
      http.post(`${API}/auth/password/change/`, () =>
        HttpResponse.json({ current_password: ['The current password is incorrect.'] }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/profile' })
    await user.type(await screen.findByLabelText('Current password'), 'wrong')
    await user.type(screen.getByLabelText('New password'), 'N3w!Passw0rd-2026')
    await user.type(screen.getByLabelText('Confirm new password'), 'N3w!Passw0rd-2026')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('The current password is incorrect.')).toBeInTheDocument()
    expect(screen.getByLabelText('Current password')).toHaveAttribute('aria-invalid', 'true')
  })
})
