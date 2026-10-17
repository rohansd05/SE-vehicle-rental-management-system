import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { confirmedBooking } from '@/features/booking/fixtures'
import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { cashBooking, makeRefund, page } from './fixtures'

type CashBody = { amount_received: string; idempotency_key: string; password: string }

function staffAtTheDesk({ collections = [cashBooking()], payouts = [makeRefund({ status: 'Approved', amount: '2000.00' })] } = {}) {
  const recorded: CashBody[] = []
  const paidOut: unknown[] = []
  let waiting = collections
  let approved = payouts
  signedInAs('BRANCH_STAFF')
  server.use(
    http.get(`${API}/bookings/awaiting-cash/`, () => HttpResponse.json(page(waiting))),
    http.get(`${API}/payments/refunds/`, ({ request }) => {
      expect(new URL(request.url).searchParams.get('status')).toBe('Approved')
      return HttpResponse.json(page(approved))
    }),
    http.post(`${API}/bookings/:id/cash/`, async ({ request }) => {
      const body = (await request.json()) as CashBody
      recorded.push(body)
      if (body.password !== 'Test@12345') {
        return HttpResponse.json({ password: ['That password is not correct.'] }, { status: 400 })
      }
      waiting = []
      return HttpResponse.json(confirmedBooking())
    }),
    http.post(`${API}/payments/refunds/:id/pay-out/`, async ({ request }) => {
      paidOut.push(await request.json())
      approved = []
      return HttpResponse.json(makeRefund({ status: 'Issued' }))
    }),
  )
  renderApp({ route: '/app/cash' })
  return { recorded, paidOut }
}

describe('cash desk (BR-9, Pay.Refund)', () => {
  it('lists the customers who pay cash at collection, with what they owe', async () => {
    staffAtTheDesk()
    const collections = await screen.findByRole('region', { name: 'Waiting for cash' })
    const row = (await within(collections).findByText('Asha Rao')).closest('li') as HTMLElement
    expect(row).toHaveTextContent('+919812345678')
    expect(row).toHaveTextContent('MH01AB1234')
    expect(row).toHaveTextContent('₹4,248.00 rental')
    expect(row).toHaveTextContent('₹5,000.00 deposit')
  })

  it('records the cash with the staff password and a fresh key; the booking is confirmed', async () => {
    const { recorded } = staffAtTheDesk()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Record cash' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Record cash and confirm' }))
    expect(await within(dialog).findByText('Enter the cash you received.')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Cash received'), '9248.00')
    await user.type(within(dialog).getByLabelText('Your password'), 'wrong')
    await user.click(within(dialog).getByRole('button', { name: 'Record cash and confirm' }))
    expect(await within(dialog).findByText('That password is not correct.')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('Your password'), 'Test@12345')
    await user.click(within(dialog).getByRole('button', { name: 'Record cash and confirm' }))
    expect(await screen.findByText('Cash recorded. Booking VRMS-20261011-0001 is confirmed.')).toBeInTheDocument()
    expect(await screen.findByText('No cash to collect')).toBeInTheDocument()
    expect(recorded.map((body) => body.amount_received)).toEqual(['9248.00', '9248.00'])
    expect(recorded[0].idempotency_key).not.toBe(recorded[1].idempotency_key)
  })

  it('pays out an approved cash refund only once the customer has acknowledged it', async () => {
    const { paidOut } = staffAtTheDesk()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Pay out' }))
    const dialog = await screen.findByRole('dialog')
    await user.type(within(dialog).getByLabelText('Your password'), 'Test@12345')
    await user.click(within(dialog).getByRole('button', { name: 'Record the payout' }))
    expect(await within(dialog).findByText('The customer must acknowledge the cash first.')).toBeInTheDocument()
    expect(paidOut).toHaveLength(0)

    await user.click(within(dialog).getByRole('checkbox', { name: /acknowledged it/ }))
    await user.click(within(dialog).getByRole('button', { name: 'Record the payout' }))
    expect(await screen.findByText('Cash refund of ₹2,000.00 paid out.')).toBeInTheDocument()
    expect(paidOut).toEqual([{ customer_acknowledged: true, password: 'Test@12345' }])
  })

  it('says when there is nothing to do', async () => {
    staffAtTheDesk({ collections: [], payouts: [] })
    expect(await screen.findByText('No cash to collect')).toBeInTheDocument()
    expect(await screen.findByText('No cash refunds to pay')).toBeInTheDocument()
  })

  it('appears in the menu for branch staff only', async () => {
    staffAtTheDesk()
    const menu = (await screen.findAllByRole('navigation', { name: 'Main' }))[0]
    expect(within(menu).getByRole('link', { name: /Cash desk/ })).toBeInTheDocument()
    expect(within(menu).queryByRole('link', { name: /Refunds/ })).not.toBeInTheDocument()
  })
})
