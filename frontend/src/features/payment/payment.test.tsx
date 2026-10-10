import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { BookingDetail } from '@/features/booking/api'
import { confirmedBooking, heldBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, server, signedInAs } from '@/test/server'

type PayBody = { payment_token: string; idempotency_key: string; password: string }

/** A customer on the payment page of a booking; `respond` answers each payment attempt. */
function customerPaying(
  booking: BookingDetail,
  respond: (body: PayBody, attempt: number) => Response = () => HttpResponse.json(confirmedBooking()),
) {
  const attempts: PayBody[] = []
  let current = booking
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(current)),
    http.post(`${API}/bookings/:id/pay/`, async ({ request }) => {
      const body = (await request.json()) as PayBody
      attempts.push(body)
      const response = respond(body, attempts.length)
      if (response.status === 200) current = confirmedBooking()
      return response
    }),
    http.post(`${API}/bookings/:id/hold/`, () => {
      current = heldBooking()
      return HttpResponse.json(current)
    }),
  )
  renderAppAt(`/app/bookings/${booking.id}/pay`)
  return attempts
}

async function payWith(user: ReturnType<typeof userEvent.setup>, { card = 'Test card that is approved', password = 'Test@12345' } = {}) {
  await user.click(await screen.findByLabelText(card))
  const field = screen.getByLabelText('Your password')
  await user.clear(field)
  if (password) await user.type(field, password)
  await user.click(screen.getByRole('button', { name: /^Pay / }))
}

describe('payment (Pay.Authorize, Exp 4 sequence 1)', () => {
  it('shows the hold, the price and what will be authorised', async () => {
    customerPaying(heldBooking(12))
    expect(await screen.findByText(/The vehicle is held for you for/)).toHaveTextContent(/1[12]:\d\d more/)
    expect(screen.getByRole('table', { name: 'Price summary' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Pay ₹4,248.00 and hold ₹5,000.00 deposit' })).toBeInTheDocument()
    expect(screen.getByText(/no card details are entered here/)).toBeInTheDocument()
  })

  it('pays with a sandbox token and the password, then confirms the booking (Pay.Confirm.OK)', async () => {
    const attempts = customerPaying(heldBooking())
    const user = userEvent.setup()
    await payWith(user)

    expect(await screen.findByText(/Your booking is confirmed/)).toBeInTheDocument()
    expect(screen.getByText('VRMS-20261011-0001')).toBeInTheDocument()
    expect(screen.getByText('042917')).toBeInTheDocument()
    expect(screen.getByText('TXN-5F2A9C0B1D3E4F5A6B7C')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download invoice INV-2026-000001' })).toBeInTheDocument()
    expect(attempts).toHaveLength(1)
    expect(attempts[0].payment_token).toBe('tok_visa')
    expect(attempts[0].password).toBe('Test@12345')
    expect(attempts[0].idempotency_key).toMatch(/^[A-Za-z0-9_-]{8,40}$/)
  })

  it('a declined card keeps the hold; another card works with a new key', async () => {
    const attempts = customerPaying(heldBooking(), (body) =>
      body.payment_token === 'tok_decline'
        ? HttpResponse.json(
            {
              code: 'payment_declined',
              detail: 'Your payment was declined: Declined by mock gateway. The vehicle stays held.',
            },
            { status: 402 },
          )
        : HttpResponse.json(confirmedBooking()),
    )
    const user = userEvent.setup()
    await payWith(user, { card: 'Test card that is declined' })

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your payment was declined')
    expect(alert).toHaveTextContent('The vehicle stays held.')
    expect(alert).toHaveFocus()
    expect(screen.getByLabelText('Your password')).toHaveValue('') // never kept after an attempt

    await payWith(user)
    expect(await screen.findByText(/Your booking is confirmed/)).toBeInTheDocument()
    expect(attempts.map((attempt) => attempt.payment_token)).toEqual(['tok_decline', 'tok_visa'])
    expect(attempts[0].idempotency_key).not.toBe(attempts[1].idempotency_key)
  })

  it('a wrong password is shown on the password field (SE-9)', async () => {
    customerPaying(heldBooking(), () =>
      HttpResponse.json({ password: ['That password is not correct.'] }, { status: 400 }),
    )
    const user = userEvent.setup()
    await payWith(user, { password: 'wrong-one' })
    expect(await screen.findByText('That password is not correct.')).toBeInTheDocument()
    expect(screen.getByLabelText('Your password')).toHaveAttribute('aria-invalid', 'true')
  })

  it('asks for the password before sending anything', async () => {
    const attempts = customerPaying(heldBooking())
    const user = userEvent.setup()
    await payWith(user, { password: '' })
    expect(await screen.findByText('Enter your password to confirm the payment.')).toBeInTheDocument()
    expect(attempts).toHaveLength(0)
  })

  it('an expired hold offers to hold the vehicle again, then pays', async () => {
    customerPaying(heldBooking(), (_body, attempt) =>
      attempt === 1
        ? HttpResponse.json(
            { code: 'hold_expired', detail: 'The 15-minute hold on this vehicle has expired. Hold it again to pay.' },
            { status: 409 },
          )
        : HttpResponse.json(confirmedBooking()),
    )
    const user = userEvent.setup()
    await payWith(user)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your hold on this vehicle has expired')
    await user.click(within(alert).getByRole('button', { name: 'Hold the vehicle again' }))
    expect(await screen.findByText(/The vehicle is held for you for/)).toBeInTheDocument()
    await payWith(user)
    expect(await screen.findByText(/Your booking is confirmed/)).toBeInTheDocument()
  })

  it('a booking whose hold already lapsed (Draft) starts with the hold-again step', async () => {
    customerPaying({ ...heldBooking(), status: 'Draft', hold_expires_at: null })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Your hold on this vehicle has expired')
    expect(screen.queryByLabelText('Your password')).not.toBeInTheDocument()
    await userEvent.setup().click(within(alert).getByRole('button', { name: 'Hold the vehicle again' }))
    expect(await screen.findByLabelText('Your password')).toBeInTheDocument()
  })

  it('a price change asks to hold again for the new price', async () => {
    customerPaying(heldBooking(), () =>
      HttpResponse.json(
        { code: 'price_changed', detail: 'The price has changed. Hold the vehicle again to see the new price.' },
        { status: 409 },
      ),
    )
    const user = userEvent.setup()
    await payWith(user)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The price needs checking again')
    expect(within(alert).getByRole('button', { name: 'Hold the vehicle again' })).toBeInTheDocument()
  })

  it('a confirmed booking goes straight to its confirmation', async () => {
    customerPaying(confirmedBooking())
    expect(await screen.findByRole('heading', { name: 'Booking VRMS-20261011-0001' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Your password')).not.toBeInTheDocument()
  })
})
