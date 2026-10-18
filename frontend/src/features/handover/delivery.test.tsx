// Module R4: the handover screen shows a doorstep delivery's address (display
// only, Book.Deliver.Location), read from the booking.

import { screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { makeCollection, makeHandover, page } from './fixtures'

function staffOnHandover(delivery: { delivery_address: string; delivery_pincode: string }) {
  signedInAs('BRANCH_STAFF')
  server.use(
    http.get(`${API}/rentals/handovers/41/`, () => HttpResponse.json(makeHandover())),
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(delivery)),
  )
  renderApp({ route: '/app/handover/41' })
}

describe('handover of a delivered booking', () => {
  it('shows the delivery address', async () => {
    staffOnHandover({ delivery_address: '12 Demo Lane, Andheri (W)', delivery_pincode: '400053' })
    expect(await screen.findByText('Doorstep delivery')).toBeInTheDocument()
    expect(screen.getByText(/12 Demo Lane, Andheri \(W\)/)).toBeInTheDocument()
    expect(screen.getByText('400053')).toBeInTheDocument()
  })

  it('shows no delivery row for a branch collection', async () => {
    staffOnHandover({ delivery_address: '', delivery_pincode: '' })
    expect(await screen.findByRole('heading', { name: 'Handover checklist' })).toBeInTheDocument()
    expect(screen.queryByText('Doorstep delivery')).not.toBeInTheDocument()
  })
})

// Module N4 (R4 follow-up): the branch bookings list names the address too.
describe('branch bookings with a delivered booking', () => {
  function serveList(rows: ReturnType<typeof makeCollection>[]) {
    server.use(
      http.get(`${API}/rentals/branch-bookings/`, ({ request }) =>
        HttpResponse.json(page(new URL(request.url).searchParams.get('when') === 'today' ? rows : [])),
      ),
      http.get(`${API}/rentals/returns/`, () => HttpResponse.json(page([]))),
    )
  }

  it('shows the delivery address on the delivered booking only', async () => {
    signedInAs('BRANCH_MANAGER')
    serveList([
      makeCollection({ delivery_address: '12 Demo Lane, Andheri (W)' }),
      makeCollection({ id: 42, booking_reference: 'VRMS-20261018-0002' }),
    ])
    renderApp({ route: '/app/branch-bookings' })
    const today = await screen.findByRole('region', { name: 'Today’s collections' })
    const [delivered, collected] = await within(today).findAllByRole('link')
    expect(within(delivered).getByText('12 Demo Lane, Andheri (W)')).toBeInTheDocument()
    expect(delivered).toHaveTextContent('Doorstep delivery: 12 Demo Lane, Andheri (W)')
    expect(collected).not.toHaveTextContent('Doorstep delivery')
  })
})
