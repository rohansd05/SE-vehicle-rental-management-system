import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

type DueBody = { method: string; payment_token: string; channel: string; idempotency_key: string; password: string }

function customerOwing(amount: string, respond?: (body: DueBody) => Response) {
  const attempts: DueBody[] = []
  let due = amount
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/payments/due/`, () => HttpResponse.json({ outstanding_due: due })),
    http.post(`${API}/payments/due/`, async ({ request }) => {
      const body = (await request.json()) as DueBody
      attempts.push(body)
      if (respond) return respond(body)
      due = '0.00'
      return HttpResponse.json({ outstanding_due: '0.00', transaction_id: 'TXN-DUE0000000000000001' })
    }),
  )
  return attempts
}

describe('outstanding due (Pay.Dues, BR-4)', () => {
  it('the customer home screen shows the due and leads to paying it', async () => {
    customerOwing('850.00')
    renderApp({ route: '/app' })
    expect(await screen.findByText(/You have an outstanding due of/)).toHaveTextContent('₹850.00')
    await userEvent.setup().click(screen.getByRole('link', { name: 'Pay your due' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Pay your due' })).toBeInTheDocument()
  })

  it('the due banner links to /app/due with a readable primary button', async () => {
    customerOwing('850.00')
    renderApp({ route: '/app' })
    const link = await screen.findByRole('link', { name: 'Pay your due' })
    expect(link).toHaveAttribute('href', '/app/due')
    // The shared Button, primary variant, keeping its own text colour (not the banner's).
    expect(link).toHaveAttribute('data-slot', 'button')
    expect(link).toHaveAttribute('data-variant', 'default')
    expect(link).toHaveClass('bg-primary', 'text-primary-foreground', 'hover:bg-primary-hover')
  })

  it('the home screen says nothing when nothing is owed', async () => {
    customerOwing('0.00')
    renderApp({ route: '/app' })
    await screen.findByRole('heading', { name: /Welcome/ })
    expect(screen.queryByText(/outstanding due/)).not.toBeInTheDocument()
  })

  it('pays the whole due on-line with the password; booking is allowed again at once', async () => {
    const attempts = customerOwing('850.00')
    renderApp({ route: '/app/due' })
    const user = userEvent.setup()
    expect(await screen.findByText('₹850.00')).toBeInTheDocument()
    await user.click(screen.getByLabelText('UPI, net banking or wallet'))
    await user.click(screen.getByLabelText('Net banking'))
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: 'Pay ₹850.00' }))

    expect(await screen.findByText('Your due is cleared. You can book vehicles again.')).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Find a vehicle' })).toHaveAttribute('href', '/app/search')
    expect(attempts).toHaveLength(1)
    expect(attempts[0]).toMatchObject({ method: 'online', channel: 'Net Banking', password: 'Test@12345' })
    expect(attempts[0].idempotency_key).toMatch(/^[A-Za-z0-9_-]{8,40}$/)
  })

  it('cash is not offered for a due', async () => {
    customerOwing('850.00')
    renderApp({ route: '/app/due' })
    await screen.findByText('₹850.00')
    expect(screen.queryByLabelText('Cash when I collect the vehicle')).not.toBeInTheDocument()
  })

  it('asks for the password first, and shows a wrong one on its field (SE-9)', async () => {
    const attempts = customerOwing('850.00', () =>
      HttpResponse.json({ password: ['That password is not correct.'] }, { status: 400 }),
    )
    renderApp({ route: '/app/due' })
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Pay ₹850.00' }))
    expect(await screen.findByText('Enter your password to confirm the payment.')).toBeInTheDocument()
    expect(attempts).toHaveLength(0)
    await user.type(screen.getByLabelText('Your password'), 'wrong-one')
    await user.click(screen.getByRole('button', { name: 'Pay ₹850.00' }))
    expect(await screen.findByText('That password is not correct.')).toBeInTheDocument()
  })

  it('a declined payment keeps the due and says so', async () => {
    customerOwing('850.00', () =>
      HttpResponse.json({ code: 'payment_declined', detail: 'Your payment was declined: Declined by mock gateway.' }, { status: 402 }),
    )
    renderApp({ route: '/app/due' })
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Test card that is declined'))
    await user.type(screen.getByLabelText('Your password'), 'Test@12345')
    await user.click(screen.getByRole('button', { name: 'Pay ₹850.00' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Your payment was declined')
    expect(screen.getByRole('button', { name: 'Pay ₹850.00' })).toBeInTheDocument()
  })

  it('with no due there is nothing to pay', async () => {
    customerOwing('0.00')
    renderApp({ route: '/app/due' })
    expect(await screen.findByText('You have no outstanding due')).toBeInTheDocument()
    expect(screen.queryByLabelText('Your password')).not.toBeInTheDocument()
  })
})
