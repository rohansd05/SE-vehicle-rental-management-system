import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API, server, signedInAs } from '@/test/server'

import type { VehicleDetail } from './api'
import { renderAppAt } from './test-render'
import { CAR, CHILD_SEAT, heldBooking, PICKUP, QUOTE, QUOTE_WITH_SEAT_AND_CODE, RETURN, SCOOTER } from './fixtures'

const ROUTE = `/app/vehicles/11?${new URLSearchParams({ pickup_datetime: PICKUP, return_datetime: RETURN })}`

interface Captured {
  quotes: Record<string, unknown>[]
  bookings: Record<string, unknown>[]
}

/** A customer on the vehicle detail page of `vehicle`, booking for the fixture period. */
function customerOnVehicle(
  vehicle: VehicleDetail = CAR,
  createBooking: () => Response = () => HttpResponse.json(heldBooking(), { status: 201 }),
): Captured {
  const captured: Captured = { quotes: [], bookings: [] }
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(vehicle)),
    http.get(`${API}/pricing/add-ons/`, () => HttpResponse.json([CHILD_SEAT])),
    http.post(`${API}/pricing/quote/`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      captured.quotes.push(body)
      if (body.discount_code === 'NOPE') {
        return HttpResponse.json({ discount_code: ['This discount code does not exist.'] }, { status: 400 })
      }
      const addOns = body.add_ons as unknown[]
      return HttpResponse.json(addOns.length || body.discount_code ? QUOTE_WITH_SEAT_AND_CODE : QUOTE)
    }),
    http.post(`${API}/bookings/`, async ({ request }) => {
      captured.bookings.push((await request.json()) as Record<string, unknown>)
      return createBooking()
    }),
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(heldBooking())),
  )
  renderAppAt(ROUTE)
  return captured
}

const refusal = (code: string, detail: string, status = 400) => () =>
  HttpResponse.json({ code, detail }, { status })

describe('vehicle detail (Search.Detail)', () => {
  it('shows the photographs, specification, tariff, deposit, rating, last service and policies', async () => {
    customerOnVehicle()
    expect(await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Photographs' })).getAllByRole('img')).toHaveLength(4)
    expect(screen.getByRole('img', { name: 'Maruti Suzuki Swift, photo 1 of 4' })).toBeInTheDocument()
    expect(screen.getByText('Petrol · White · Manual · 5 seats')).toBeInTheDocument()
    expect(screen.getByText('₹150.00 per hour, ₹1,800.00 per day')).toBeInTheDocument()
    expect(screen.getByText('₹5,000.00, refundable')).toBeInTheDocument()
    expect(screen.getByText('4.5 out of 5')).toBeInTheDocument()
    const policies = screen.getByRole('heading', { name: 'Policies' }).parentElement!
    expect(within(policies).getByText(/250 km free per rental day/)).toBeInTheDocument()
    expect(within(policies).getByText(/75% from 12 to 48 hours before/)).toBeInTheDocument()
  })

  it('leads with the representative model photo and keeps the own photos as a gallery below it', async () => {
    customerOnVehicle()
    const main = await screen.findByRole('img', { name: 'Representative image of a Maruti Suzuki Swift' })
    expect(screen.getByText('Representative image')).toBeInTheDocument()
    const gallery = within(screen.getByRole('region', { name: 'Vehicle photos' })).getByRole('list', { name: 'Photographs' })
    const own = within(gallery).getAllByRole('img')
    expect(own).toHaveLength(4)
    expect(main.compareDocumentPosition(own[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows the representative photo when the vehicle has no photos of its own', async () => {
    customerOnVehicle({ ...CAR, photos: [] })
    expect(await screen.findByRole('img', { name: 'Representative image of a Maruti Suzuki Swift' })).toBeInTheDocument()
    expect(screen.getByText('No photographs have been added yet.')).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Photographs' })).not.toBeInTheDocument()
  })

  it('leads with the own photos when neither the model nor the category has a representative photo', async () => {
    customerOnVehicle({ ...CAR, brand: 'Acme', model: 'Zip', category: 'Van' })
    expect(await screen.findByRole('img', { name: 'Acme Zip, photo 1 of 4' })).toHaveClass('aspect-[3/2]')
    expect(within(screen.getByRole('list', { name: 'Photographs' })).getAllByRole('img')).toHaveLength(4)
    expect(screen.queryByText('Representative image')).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Vehicle photos' })).not.toBeInTheDocument()
  })

  it('asks for dates when it was opened without a search', async () => {
    signedInAs('CUSTOMER')
    server.use(http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR)))
    renderAppAt('/app/vehicles/11')
    expect(await screen.findByText('Choose your dates first')).toBeInTheDocument()
    expect(screen.queryByRole('form', { name: 'Book this vehicle' })).not.toBeInTheDocument()
  })

  it('says so when no tariff is published', async () => {
    customerOnVehicle({ ...CAR, tariff: null, terms: null })
    expect(await screen.findByText('Not bookable yet')).toBeInTheDocument()
  })
})

describe('booking form and price summary (Book.Quote.Display)', () => {
  it('itemises the price with the deposit apart', async () => {
    customerOnVehicle()
    const summary = await screen.findByRole('table', { name: 'Price summary' })
    expect(within(summary).getByText('Rental, 2 days at ₹1,800.00')).toBeInTheDocument()
    expect(within(summary).getByText('Tax at 18%')).toBeInTheDocument()
    expect(within(summary).getByRole('row', { name: /Total payable ₹4,248.00/ })).toBeInTheDocument()
    expect(screen.getByText(/Refundable security deposit/)).toHaveTextContent(
      'Refundable security deposit ₹5,000.00, held separately and not part of the total.',
    )
  })

  it('re-prices when an add-on and a discount code are chosen', async () => {
    const captured = customerOnVehicle()
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText(/Child seat/))
    await user.type(screen.getByLabelText('Discount code'), 'WELCOME10')
    await user.click(screen.getByRole('button', { name: 'Apply' }))

    const summary = await screen.findByRole('table', { name: 'Price summary' })
    expect(await within(summary).findByText('Discount WELCOME10')).toBeInTheDocument()
    expect(within(summary).getByText('Child seat × 1, 2 days at ₹100.00')).toBeInTheDocument()
    expect(within(summary).getByRole('row', { name: /Total payable ₹4,035.60/ })).toBeInTheDocument()
    expect(captured.quotes.at(-1)).toEqual({
      vehicle: 11,
      pickup_datetime: PICKUP,
      return_datetime: RETURN,
      add_ons: [{ add_on: 5, quantity: 1 }],
      discount_code: 'WELCOME10',
    })
  })

  it('shows a rejected discount code next to its field', async () => {
    customerOnVehicle()
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Discount code'), 'NOPE')
    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(await screen.findByText('This discount code does not exist.')).toBeInTheDocument()
    expect(screen.getByLabelText('Discount code')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: 'Hold this vehicle and pay' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Remove' }))
    expect(await screen.findByRole('table', { name: 'Price summary' })).toBeInTheDocument()
  })

  it('requires the rental terms before holding (Book.Quote.Terms)', async () => {
    const captured = customerOnVehicle()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Price summary' })
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByText('Accept the rental terms to continue.')).toBeInTheDocument()
    expect(screen.getByLabelText('I accept the rental terms above.')).toHaveAttribute('aria-invalid', 'true')
    expect(captured.bookings).toHaveLength(0)
  })

  it('holds the vehicle and goes on to payment', async () => {
    const captured = customerOnVehicle()
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Price summary' })
    await user.click(screen.getByLabelText('I accept the rental terms above.'))
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByRole('heading', { name: 'Pay for your booking' })).toBeInTheDocument()
    expect(captured.bookings[0]).toEqual({
      vehicle: 11,
      pickup_datetime: PICKUP,
      return_datetime: RETURN,
      add_ons: [],
      discount_code: '',
      terms_accepted: true,
      safety_notice_acknowledged: false,
      delivery_address: '', // collected at the branch (Book.Deliver.Location)
      delivery_pincode: '',
    })
  })

  it('asks for the safety notice on a two-wheeler (SA-1)', async () => {
    const captured = customerOnVehicle(SCOOTER)
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Price summary' })
    expect(screen.getByText(/One helmet per rider is included with this two-wheeler/)).toBeInTheDocument()
    await user.click(screen.getByLabelText('I accept the rental terms above.'))
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    expect(await screen.findByText('Read and acknowledge the safety notice.')).toBeInTheDocument()
    expect(captured.bookings).toHaveLength(0)
    await user.click(screen.getByLabelText('I have read the safety notice.'))
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    await screen.findByRole('heading', { name: 'Pay for your booking' })
    expect(captured.bookings[0]).toMatchObject({ safety_notice_acknowledged: true })
  })
})

describe('alternative flows when holding', () => {
  async function holdAndExpectRefusal() {
    const user = userEvent.setup()
    await screen.findByRole('table', { name: 'Price summary' })
    await user.click(screen.getByLabelText('I accept the rental terms above.'))
    await user.click(screen.getByRole('button', { name: 'Hold this vehicle and pay' }))
    return screen.findByRole('alert')
  }

  it.each([
    ['licence_not_verified', 'Your driving licence has not been verified yet.'],
    ['licence_expired', 'Your driving licence has expired. Submit your renewed licence.'],
    ['licence_expires_before_return', 'Your driving licence expires before the return date (BR-2).'],
  ])('licence refused (%s): offers to submit a licence, keep browsing or exit (Book.Eligible.No)', async (code, detail) => {
    customerOnVehicle(CAR, refusal(code, detail))
    const alert = await holdAndExpectRefusal()
    expect(alert).toHaveTextContent('Your driving licence doesn’t allow this booking yet')
    expect(alert).toHaveTextContent(detail)
    expect(within(alert).getByRole('link', { name: 'Submit your licence' })).toHaveAttribute('href', '/app/licence')
    expect(within(alert).getByRole('link', { name: 'Keep browsing' })).toHaveAttribute('href', '/app/search')
    expect(within(alert).getByRole('link', { name: 'Exit' })).toHaveAttribute('href', '/app')
    expect(alert).toHaveFocus()
  })

  it('vehicle just taken: says so and offers another vehicle', async () => {
    customerOnVehicle(
      CAR,
      refusal('vehicle_unavailable', 'Sorry, this vehicle has just been taken for these dates.', 409),
    )
    const alert = await holdAndExpectRefusal()
    expect(alert).toHaveTextContent('This vehicle has just been taken')
    expect(within(alert).getByRole('link', { name: 'Choose another vehicle' })).toHaveAttribute('href', '/app/search')
  })

  it('an outstanding due: explains and offers to keep browsing', async () => {
    customerOnVehicle(CAR, refusal('outstanding_due', 'You have an outstanding due of INR 200.00.'))
    const alert = await holdAndExpectRefusal()
    expect(alert).toHaveTextContent('You can’t make this booking')
    expect(within(alert).queryByRole('link', { name: 'Submit your licence' })).not.toBeInTheDocument()
  })

  it('a server field error lands on its field', async () => {
    customerOnVehicle(CAR, () =>
      HttpResponse.json({ terms_accepted: ['Accept the rental terms to continue.'] }, { status: 400 }),
    )
    await holdAndExpectRefusal().catch(() => undefined)
    expect(await screen.findByText('Accept the rental terms to continue.')).toBeInTheDocument()
  })
})

describe('from the search results', () => {
  it('each result links to its detail page for the searched period', async () => {
    signedInAs('CUSTOMER')
    server.use(
      http.get(`${API}/fleet/branches/`, () =>
        HttpResponse.json([{ branch_id: 1, branch_name: 'Andheri', address: '' }]),
      ),
      http.get(`${API}/fleet/categories/`, () => HttpResponse.json([])),
      http.get(`${API}/fleet/search/`, () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [{ ...CAR, estimate: null }] }),
      ),
    )
    renderAppAt(`/app/search?${new URLSearchParams({ branch: '1', pickup_datetime: PICKUP, return_datetime: RETURN })}`)
    const link = await screen.findByRole('link', { name: 'View and book the Maruti Suzuki Swift' })
    expect(link).toHaveAttribute('href', ROUTE)
  })
})

describe('menu', () => {
  it('“My bookings” is available, no longer marked Soon', async () => {
    customerOnVehicle()
    await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })
    expect(screen.getAllByRole('link', { name: /My bookings/ })[0]).not.toHaveTextContent('Soon')
  })
})
