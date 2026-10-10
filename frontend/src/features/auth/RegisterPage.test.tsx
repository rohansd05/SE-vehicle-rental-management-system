import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server } from '@/test/server'

async function fillValid(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText('Full name'), 'Asha Rao')
  await user.type(screen.getByLabelText('E-mail'), 'asha@example.com')
  const [mobile, emergencyMobile] = screen.getAllByLabelText('Mobile number')
  await user.type(mobile, '+919812345678')
  await user.type(screen.getByLabelText('Address'), '14 Hill Road, Mumbai')
  await user.type(screen.getByLabelText('Date of birth'), '1996-04-12')
  await user.type(screen.getByLabelText('Name'), 'Ravi Rao')
  await user.type(emergencyMobile, '+919812300000')
  await user.type(screen.getByLabelText('Password'), 'Str0ng!Passw0rd')
  await user.type(screen.getByLabelText('Confirm password'), 'Str0ng!Passw0rd')
}

describe('Register', () => {
  it('shows the password rules before anything is typed', async () => {
    renderApp({ route: '/register' })
    expect(await screen.findByText('At least 8 characters.')).toBeInTheDocument()
    expect(screen.getByText('Not only numbers.')).toBeInTheDocument()
  })

  it('validates on the client and sends nothing while invalid', async () => {
    const posted = vi.fn()
    server.use(http.post(`${API}/auth/register/`, posted))
    const user = userEvent.setup()
    renderApp({ route: '/register' })
    await user.click(await screen.findByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Enter your full name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid e-mail address.')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Full name')).toHaveFocus()

    await user.type(screen.getByLabelText('Password'), '12345678')
    await user.type(screen.getByLabelText('Confirm password'), '87654321')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText('Use more than just numbers.')).toBeInTheDocument()
    expect(screen.getByText('The passwords do not match.')).toBeInTheDocument()
    expect(posted).not.toHaveBeenCalled()
  })

  it('puts server field errors next to the right fields', async () => {
    server.use(
      http.post(`${API}/auth/register/`, () =>
        HttpResponse.json(
          {
            email: ['An account with this e-mail address already exists.'],
            password: ['This password is too common.'],
          },
          { status: 400 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/register' })
    await fillValid(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    const email = screen.getByLabelText('E-mail')
    const emailError = await screen.findByText('An account with this e-mail address already exists.')
    expect(email).toHaveAttribute('aria-invalid', 'true')
    expect(email.getAttribute('aria-describedby')).toContain(emailError.closest('p')!.id)
    const passwordError = screen.getByText('This password is too common.')
    expect(screen.getByLabelText('Password').getAttribute('aria-describedby')).toContain(
      passwordError.closest('p')!.id,
    )
    await waitFor(() => expect(email).toHaveFocus())
  })

  it('goes on to verification after a successful registration', async () => {
    let body: unknown
    server.use(
      http.post(`${API}/auth/register/`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          { email: 'asha@example.com', detail: 'Account created.' },
          { status: 201 },
        )
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/register' })
    await fillValid(user)
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('heading', { name: 'Verify your mobile number' })).toBeInTheDocument()
    expect(screen.getByText(/sent by SMS to \+919812345678/)).toBeInTheDocument()
    expect(body).toEqual({
      name: 'Asha Rao',
      email: 'asha@example.com',
      mobile_no: '+919812345678',
      address: '14 Hill Road, Mumbai',
      date_of_birth: '1996-04-12',
      emergency_contact_name: 'Ravi Rao',
      emergency_contact_mobile: '+919812300000',
      password: 'Str0ng!Passw0rd',
    })
  })
})
