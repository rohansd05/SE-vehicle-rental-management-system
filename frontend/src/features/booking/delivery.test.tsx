// Module R4: doorstep delivery on the booking form (Book.Addons, Book.Deliver.Location,
// BR-7). The address is asked for, sent with the booking, and the server's refusal
// is shown next to its field; nothing is refused up front any more.

import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API, server, signedInAs } from '@/test/server'

import type { AddOn } from './api'
import { CAR, heldBooking, PICKUP, QUOTE, RETURN } from './fixtures'
import { renderAppAt } from './test-render'

const DELIVERY: AddOn = { id: 9, name: 'Doorstep delivery', daily_rate: '300.00', vehicle_type: '' }
const ROUTE = `/app/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`

function customerBooking(respond: () => Response) {
  const bookings: Record<string, unknown>[] = []
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR)),
    http.get(`${API}/pricing/add-ons/`, () => HttpResponse.json([DELIVERY])),
    http.post(`${API}/pricing/quote/`, () => HttpResponse.json(QUOTE)),
    http.post(`${API}/bookings/`, async ({ request }) => {
      bookings.push((await request.json()) as Record<string, unknown>)
      return respond()
    }),
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(heldBooking())),
  )
  renderAppAt(ROUTE)
  return bookings
}

async function chooseDelivery(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByLabelText('Doorstep delivery (₹300.00 per day)'))
  await user.click(screen.getByLabelText('I accept the rental terms above.'))
}

describe('doorstep delivery (Book.Deliver.Location)', () => {
  it('asks for the address only once delivery is chosen', async () => {
    const user = userEvent.setup()
    customerBooking(() => HttpResponse.json(heldBooking(), { status: 201 }))
    await screen.findByLabelText('Doorstep delivery (₹300.00 per day)')
    expect(screen.queryByLabelText('Address')).not.toBeInTheDocument()
    await chooseDelivery(user)
    expect(screen.getByLabelText('Address')).toBeInTheDocument()
    expect(screen.getByLabelText('Pincode')).toBeInTheDocument()
  })

  it('needs an address and a six-digit pincode before holding', async () => {
    const user = userEvent.setup()
    const bookings = customerBooking(() => HttpResponse.json(heldBooking(), { status: 201 }))
    await chooseDelivery(user)
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByText('Enter the address we should deliver the vehicle to.')).toBeInTheDocument()
    expect(screen.getByText('Enter the six-digit pincode of the delivery address.')).toBeInTheDocument()
    expect(bookings).toHaveLength(0)
  })

  it('sends the address and shows the serviceable-area refusal next to the pincode', async () => {
    const user = userEvent.setup()
    const message = "We don't deliver to 400099 from this branch. Choose another address, or remove doorstep delivery and collect the vehicle at the branch."
    const bookings = customerBooking(() => HttpResponse.json({ delivery_pincode: [message] }, { status: 400 }))
    await chooseDelivery(user)
    await user.type(screen.getByLabelText('Address'), '12 Demo Lane, Andheri (W)')
    await user.type(screen.getByLabelText('Pincode'), '400099')
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(screen.getByLabelText('Pincode')).toHaveAttribute('aria-invalid', 'true')
    expect(bookings[0]).toMatchObject({
      add_ons: [{ add_on: 9, quantity: 1 }],
      delivery_address: '12 Demo Lane, Andheri (W)',
      delivery_pincode: '400099',
    })
  })

  it('holds the vehicle with a serviceable address', async () => {
    const user = userEvent.setup()
    customerBooking(() => HttpResponse.json(heldBooking(), { status: 201 }))
    await chooseDelivery(user)
    await user.type(screen.getByLabelText('Address'), '12 Demo Lane')
    await user.type(screen.getByLabelText('Pincode'), '400053')
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByRole('heading', { name: /Pay/ })).toBeInTheDocument()
  })
})
