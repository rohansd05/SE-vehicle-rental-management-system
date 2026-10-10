import { act, fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server } from '@/test/server'

import { OTP_MESSAGES } from './messages'

const EMAIL = 'asha@example.com'
const generic = () =>
  HttpResponse.json({ detail: ['The code is invalid or has expired.'] }, { status: 400 })

function renderVerify(sentAt = Date.now()) {
  renderApp({ route: '/verify', state: { email: EMAIL, mobile: '+919812345678', sentAt } })
}

describe('Verify OTP', () => {
  it('says the code is valid for 10 minutes', async () => {
    renderVerify()
    expect(await screen.findByText('The code is valid for 10 minutes.')).toBeInTheDocument()
  })

  it('verifies and sends the user to sign in', async () => {
    let body: unknown
    server.use(
      http.post(`${API}/auth/verify-otp/`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json({ detail: 'Your account is verified.' })
      }),
    )
    const user = userEvent.setup()
    renderVerify()
    await user.type(await screen.findByLabelText('Verification code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByText('Your account is verified. Sign in to continue.')).toBeInTheDocument()
    expect(screen.getByLabelText('E-mail')).toHaveValue(EMAIL)
    expect(body).toEqual({ email: EMAIL, code: '123456' })
  })

  it('explains a wrong code and how many tries are left', async () => {
    server.use(http.post(`${API}/auth/verify-otp/`, generic))
    const user = userEvent.setup()
    renderVerify()
    await user.type(await screen.findByLabelText('Verification code'), '000000')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(OTP_MESSAGES.wrong(4))
  })

  it('stops after five wrong tries', async () => {
    server.use(http.post(`${API}/auth/verify-otp/`, generic))
    const user = userEvent.setup()
    renderVerify()
    const input = await screen.findByLabelText('Verification code')
    for (let attempt = 0; attempt < 5; attempt++) {
      await user.clear(input)
      await user.type(input, '000000')
      await user.click(screen.getByRole('button', { name: 'Verify' }))
      await screen.findByRole('alert')
    }
    expect(screen.getByRole('alert')).toHaveTextContent(OTP_MESSAGES.tooMany)
    expect(screen.getByRole('button', { name: 'Verify' })).toBeDisabled()
  })

  it('explains an expired code without asking the server', async () => {
    const posted = vi.fn()
    server.use(http.post(`${API}/auth/verify-otp/`, posted))
    const user = userEvent.setup()
    renderVerify(Date.now() - 11 * 60 * 1000)
    await user.type(await screen.findByLabelText('Verification code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(OTP_MESSAGES.expired)
    expect(posted).not.toHaveBeenCalled()
  })

  it('counts down 60 seconds before a new code can be requested', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date'] })
    const resend = vi.fn(() => HttpResponse.json({ detail: 'sent' }))
    server.use(http.post(`${API}/auth/resend-otp/`, resend))
    renderVerify()
    const button = screen.getByRole('button', { name: 'Send a new code in 60 s' })
    expect(button).toBeDisabled()

    for (let second = 0; second < 59; second++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000)
      })
    }
    expect(screen.getByRole('button', { name: 'Send a new code in 1 s' })).toBeDisabled()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    const ready = screen.getByRole('button', { name: 'Send a new code' })
    expect(ready).toBeEnabled()

    vi.useRealTimers()
    fireEvent.click(ready)
    expect(await screen.findByText(/A new code is on its way/)).toBeInTheDocument()
    expect(resend).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Send a new code in \d+ s/ })).toBeDisabled()
  })
})
