import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { BookingDetail } from '@/features/booking/api'
import { confirmedBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { makeRefund } from '@/features/payment/fixtures'
import { API, server, signedInAs } from '@/test/server'

function customerOpening(booking: BookingDetail) {
  signedInAs('CUSTOMER')
  server.use(http.get(`${API}/bookings/:id/`, () => HttpResponse.json(booking)))
  renderAppAt(`/app/bookings/${booking.id}`)
}

describe('refunds on a booking (Pay.Refund, BR-14, UC 13)', () => {
  it('shows each refund and where it stands', async () => {
    customerOpening({
      ...confirmedBooking(),
      refunds: [
        makeRefund({ id: 1, amount: '1000.00', reason: 'Goodwill', status: 'Pending Approval' }),
        makeRefund({
          id: 2,
          purpose: 'Security Deposit',
          amount: '4349.50',
          reason: 'Security deposit balance (BR-14)',
          status: 'Issued',
          refund_due_by: '2026-10-26',
          refund_transaction_id: 'TXN-REFUND000000000001',
        }),
        makeRefund({ id: 3, amount: '200.00', reason: 'Late fee', status: 'Rejected', rejection_reason: 'Returned 7 hours late.' }),
      ],
    })
    const list = (await screen.findByRole('heading', { name: 'Refunds' })).parentElement as HTMLElement
    const rows = within(list).getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('₹1,000.00 of the rental: Goodwill')
    expect(rows[0]).toHaveTextContent('Waiting for approval.')
    expect(rows[1]).toHaveTextContent('₹4,349.50 of the security deposit')
    expect(rows[1]).toHaveTextContent('Issued to your original payment method; it reaches you by 26 Oct 2026.')
    expect(rows[1]).toHaveTextContent('TXN-REFUND000000000001')
    expect(rows[2]).toHaveTextContent('Not approved: Returned 7 hours late.')
  })

  it('has no refunds section when there are none', async () => {
    customerOpening(confirmedBooking())
    await screen.findByRole('heading', { name: 'Booking VRMS-20261011-0001' })
    expect(screen.queryByRole('heading', { name: 'Refunds' })).not.toBeInTheDocument()
  })
})
