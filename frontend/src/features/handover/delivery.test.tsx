// Module R4: the handover screen shows a doorstep delivery's address (display
// only, Book.Deliver.Location), read from the booking.

import { screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import { makeHandover } from './fixtures'

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
