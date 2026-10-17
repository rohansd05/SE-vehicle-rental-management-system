import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { BookingDetail } from '@/features/booking/api'
import { confirmedBooking, heldBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, server, signedInAs } from '@/test/server'

type PayBody = { method: string; payment_token: string; channel: string; upi_id: string; idempotency_key: string; password: string }

/** A customer on the payment page; `respond` answers each payment attempt. */
function customerPaying(respond: (body: PayBody) => BookingDetail | Response, initial: BookingDetail = heldBooking()) {
  const attempts: PayBody[] = []
  let current = initial
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(current)),
    http.post(`${API}/bookings/:id/pay/`, async ({ request }) => {
      const body = (await request.json()) as PayBody
      attempts.push(body)
      const answer = respond(body)
      if (answer instanceof Response) return answer
      current = answer
      return HttpResponse.json(answer)
    }),
  )
  renderAppAt(`/app/bookings/${current.id}/pay`)
  return attempts
}

// The API's answer once cash is chosen: still Pending Payment, held until 2 hours after pickup.
const cashHeld = (): BookingDetail => ({ ...heldBooking(), cash_on_collection: true, hold_expires_at: '2027-01-10T06:30:00.000Z' })

describe('payment methods (Pay.Method, D6, BR-9)', () => {
  it('pays by UPI with the UPI ID and an on-line sandbox token, then confirms', async () => {
    const attempts = customerPaying(() => confirmedBooking())
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('UPI, net banking or wallet'))
    await user.type(screen.getByLabelText('UPI ID (optional)'), 'asha@okbank')
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: /^Pay / }))

    expect(await screen.findByText(/Your booking is confirmed/)).toBeInTheDocument()
    expect(attempts).toHaveLength(1)
    expect(attempts[0]).toMatchObject({ method: 'online', channel: 'UPI', upi_id: 'asha@okbank', payment_token: 'tok_online' })
  })

  it('pays by net banking or wallet without a UPI ID', async () => {
    const attempts = customerPaying(() => confirmedBooking())
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('UPI, net banking or wallet'))
    await user.click(screen.getByLabelText('Wallet'))
    expect(screen.queryByLabelText('UPI ID (optional)')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: /^Pay / }))
    await screen.findByText(/Your booking is confirmed/)
    expect(attempts[0]).toMatchObject({ method: 'online', channel: 'Wallet', upi_id: '' })
  })

  it('cash at collection keeps the booking held and says what to bring (BR-9)', async () => {
    const attempts = customerPaying(() => cashHeld())
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Cash when I collect the vehicle'))
    expect(screen.getByText(/Bring ₹4,248.00 for the rental and ₹5,000.00 for the refundable deposit to Andheri/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: 'Pay in cash when I collect' }))

    expect(await screen.findByText(/You chose to pay in cash when you collect the vehicle/)).toBeInTheDocument()
    expect(attempts[0]).toMatchObject({ method: 'cash', payment_token: '' })
    expect(screen.getByRole('link', { name: 'Continue to payment' })).toBeInTheDocument() // still payable online
  })

  it('a booking already set for cash opens with cash chosen and its collection hold', async () => {
    customerPaying(() => cashHeld(), cashHeld())
    expect(await screen.findByText(/The vehicle is held for your collection until/)).toBeInTheDocument()
    expect(screen.getByLabelText('Cash when I collect the vehicle')).toBeChecked()
  })

  it('shows a refusal of cash from the server', async () => {
    customerPaying(() =>
      HttpResponse.json({ method: ['Cash is accepted only for a booking collected at the branch (BR-9).'] }, { status: 400 }),
    )
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Cash when I collect the vehicle'))
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: 'Pay in cash when I collect' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cash is accepted only for a booking collected at the branch')
  })
})
