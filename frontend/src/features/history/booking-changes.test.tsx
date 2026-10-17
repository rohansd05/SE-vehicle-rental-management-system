import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import type {
  Booking,
  BookingDetail,
  CancellationQuote,
  ExtensionQuote,
  ModificationQuote,
} from '@/features/booking/api'
import { CAR, CHILD_SEAT, QUOTE, confirmedBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, server, signedInAs } from '@/test/server'

type Body = Record<string, unknown>

const SWIFT = { id: 11, brand: 'Maruti Suzuki', model: 'Swift', registration_no: 'MH01AB1234', vehicle_type: 'Car', category: 'Hatchback' }

const CANCEL_QUOTE: CancellationQuote = {
  notice_hours: 30,
  refund_percent: '75.00',
  rental_amount: '4248.00',
  rental_refund: '3186.00',
  deposit_refund: '5000.00',
  total_refund: '8186.00',
  awaits_approval: false,
}

const MODIFY_QUOTE: ModificationQuote = {
  price: { ...QUOTE, billing_count: 3, base_charge: '5400.00', total_payable: '6372.00' },
  vehicle: SWIFT,
  vehicle_free: true,
  alternatives: [],
  previous_total: '4248.00',
  new_total: '6372.00',
  extra_charge: '2124.00',
  refund_percent: '100.00',
  refund_amount: '0.00',
}

/** A customer on a booking's detail page; every request to the change endpoints is recorded. */
function customerOn(booking: BookingDetail, handlers: Parameters<typeof server.use> = []) {
  const posted: { path: string; body: Body }[] = []
  let current = booking
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(current)),
    http.get(`${API}/fleet/branches/`, () =>
      HttpResponse.json([
        { branch_id: 1, branch_name: 'Andheri', address: '', serviceable_areas: [] },
        { branch_id: 2, branch_name: 'Bandra', address: '', serviceable_areas: [] },
      ]),
    ),
    http.get(`${API}/pricing/add-ons/`, () => HttpResponse.json([CHILD_SEAT])),
    ...handlers,
    http.post(`${API}/bookings/:id/:action/`, async ({ request, params }) => {
      posted.push({ path: String(params.action), body: (await request.json()) as Body })
      current = { ...current, status: params.action === 'cancel' ? 'Cancelled' : current.status }
      return HttpResponse.json(current)
    }),
  )
  renderAppAt(`/app/bookings/${booking.id}`)
  return posted
}

async function confirmWithPassword(user: ReturnType<typeof userEvent.setup>, button: string | RegExp) {
  await user.type(screen.getByLabelText('Your password'), 'Test@12345')
  await user.click(screen.getByRole('button', { name: button }))
}

describe('booking actions by status (Appendix B)', () => {
  it('a confirmed booking can be modified or cancelled', async () => {
    customerOn(confirmedBooking())
    const actions = await screen.findByRole('group', { name: 'Booking actions' })
    expect(within(actions).getByRole('button', { name: 'Modify booking' })).toBeInTheDocument()
    expect(within(actions).getByRole('button', { name: 'Cancel booking' })).toBeInTheDocument()
    expect(within(actions).queryByRole('button', { name: 'Extend rental' })).not.toBeInTheDocument()
  })

  it('an active rental can only be extended', async () => {
    customerOn({ ...confirmedBooking(), status: 'Active' })
    const actions = await screen.findByRole('group', { name: 'Booking actions' })
    expect(within(actions).getAllByRole('button').map((b) => b.textContent)).toEqual(['Extend rental'])
  })

  it('an unpaid cash booking can be cancelled', async () => {
    customerOn({ ...confirmedBooking(), status: 'Pending Payment', cash_on_collection: true, booking_reference: '' })
    const actions = await screen.findByRole('group', { name: 'Booking actions' })
    expect(within(actions).getAllByRole('button').map((b) => b.textContent)).toEqual(['Cancel booking'])
  })

  it('a card hold being paid has no change actions', async () => {
    customerOn({ ...confirmedBooking(), status: 'Pending Payment', booking_reference: '' })
    expect(await screen.findByRole('link', { name: 'Continue to payment' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Booking actions' })).not.toBeInTheDocument()
  })
})

describe('cancel (Book.Cancel: the refund is shown and confirmed)', () => {
  it('shows the BR-8 refund, asks for the password and cancels', async () => {
    const posted = customerOn(confirmedBooking(), [
      http.get(`${API}/bookings/:id/cancel/`, () => HttpResponse.json(CANCEL_QUOTE)),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }))
    const dialog = await screen.findByRole('dialog', { name: 'Cancel this booking?' })
    expect(await within(dialog).findByText('Rental refund, 75% of the rental')).toBeInTheDocument()
    expect(within(dialog).getByText('₹3,186.00')).toBeInTheDocument()
    expect(within(dialog).getByText('Security deposit, refunded in full')).toBeInTheDocument()
    expect(within(dialog).getByText('₹8,186.00')).toBeInTheDocument()
    await confirmWithPassword(user, 'Cancel booking')
    expect(await screen.findByText('Cancelled')).toBeInTheDocument()
    expect(posted).toEqual([{ path: 'cancel', body: { expected_refund: '8186.00', password: 'Test@12345' } }])
  })

  it('says when part of the refund waits for an administrator', async () => {
    customerOn(confirmedBooking(), [
      http.get(`${API}/bookings/:id/cancel/`, () => HttpResponse.json({ ...CANCEL_QUOTE, awaits_approval: true })),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }))
    expect(await screen.findByText(/issued once an administrator approves it/)).toBeInTheDocument()
  })

  it('an unpaid cash booking has nothing to refund', async () => {
    customerOn({ ...confirmedBooking(), status: 'Pending Payment', cash_on_collection: true }, [
      http.get(`${API}/bookings/:id/cancel/`, () =>
        HttpResponse.json({ ...CANCEL_QUOTE, rental_refund: '0.00', deposit_refund: '0.00', total_refund: '0.00' }),
      ),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }))
    expect(await screen.findByText(/nothing to refund/)).toBeInTheDocument()
  })

  it('shows the new refund when it changed before confirming', async () => {
    let quote = CANCEL_QUOTE
    customerOn(confirmedBooking(), [
      http.get(`${API}/bookings/:id/cancel/`, () => HttpResponse.json(quote)),
      http.post(`${API}/bookings/:id/cancel/`, () => {
        quote = { ...CANCEL_QUOTE, refund_percent: '50.00', rental_refund: '2124.00', total_refund: '7124.00' }
        return HttpResponse.json(
          { detail: 'The refund is now INR 7,124.00. Check it and confirm again.', code: 'refund_changed' },
          { status: 409 },
        )
      }),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }))
    await screen.findByText('₹8,186.00')
    await confirmWithPassword(user, 'Cancel booking')
    expect(await screen.findByRole('alert')).toHaveTextContent('The refund is now INR 7,124.00.')
    expect(await screen.findByText('₹7,124.00')).toBeInTheDocument()
  })
})

describe('modify (Book.Modify, Book.Modify.Price)', () => {
  it('checks the new price, takes the extra charge by card and confirms', async () => {
    const quotes: Body[] = []
    const posted = customerOn(confirmedBooking(), [
      http.post(`${API}/bookings/:id/modify/quote/`, async ({ request }) => {
        quotes.push((await request.json()) as Body)
        return HttpResponse.json(MODIFY_QUOTE)
      }),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Modify booking' }))
    const dialog = await screen.findByRole('dialog', { name: 'Modify this booking' })
    await user.click(within(dialog).getByLabelText(/Child seat/))
    await user.click(within(dialog).getByRole('button', { name: 'Check the new price' }))
    expect(await within(dialog).findByText('To pay now')).toBeInTheDocument()
    expect(within(dialog).getByText('₹2,124.00')).toBeInTheDocument()
    expect(quotes[0]).toMatchObject({ pickup_branch: 1, add_ons: [{ add_on: 5, quantity: 1 }], vehicle: null })
    await user.click(within(dialog).getByLabelText('Test card that is approved'))
    await confirmWithPassword(user, 'Confirm the change')
    await screen.findByRole('button', { name: 'Modify booking' }) // the dialog closed
    expect(posted).toHaveLength(1)
    expect(posted[0].path).toBe('modify')
    expect(posted[0].body).toMatchObject({
      expected_charge: '2124.00',
      expected_refund: '0.00',
      method: 'card',
      payment_token: 'tok_visa',
      password: 'Test@12345',
      vehicle: null,
    })
  })

  it('shows the BR-8 refund for a cheaper change and sends no payment', async () => {
    const posted = customerOn(confirmedBooking(), [
      http.post(`${API}/bookings/:id/modify/quote/`, () =>
        HttpResponse.json({
          ...MODIFY_QUOTE,
          new_total: '2124.00',
          extra_charge: '0.00',
          refund_percent: '75.00',
          refund_amount: '1593.00',
        }),
      ),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Modify booking' }))
    await user.click(await screen.findByRole('button', { name: 'Check the new price' }))
    expect(await screen.findByText('Refund, 75% of the difference')).toBeInTheDocument()
    expect(screen.queryByText('How would you like to pay?')).not.toBeInTheDocument()
    await confirmWithPassword(user, 'Confirm the change')
    await screen.findByRole('button', { name: 'Modify booking' })
    expect(posted[0].body).toMatchObject({ expected_refund: '1593.00', payment_token: '' })
  })

  it('offers a vehicle of the same category when this one is not free (UC 4 3a)', async () => {
    const quotes: Body[] = []
    const posted = customerOn(confirmedBooking(), [
      http.post(`${API}/bookings/:id/modify/quote/`, async ({ request }) => {
        const body = (await request.json()) as Body
        quotes.push(body)
        return HttpResponse.json(
          body.vehicle
            ? { ...MODIFY_QUOTE, extra_charge: '0.00', vehicle: { ...SWIFT, id: 12, registration_no: 'MH01AB9999' } }
            : { ...MODIFY_QUOTE, vehicle_free: false, alternatives: [{ ...SWIFT, id: 12, registration_no: 'MH01AB9999' }] },
        )
      }),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Modify booking' }))
    await user.click(await screen.findByRole('button', { name: 'Check the new price' }))
    expect(await screen.findByText(/is not free for these dates/)).toBeInTheDocument()
    await confirmWithPassword(user, 'Confirm the change')
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose a vehicle that is free, or other dates.')
    const list = screen.getByRole('list', { name: 'Other vehicles at the same price' })
    await user.click(within(list).getByRole('button', { name: 'Take this Hatchback' }))
    expect(await screen.findByText('The price does not change.')).toBeInTheDocument()
    expect(quotes.at(-1)?.vehicle).toBe(12)
    await user.click(screen.getByRole('button', { name: 'Confirm the change' }))
    await screen.findByRole('button', { name: 'Modify booking' })
    expect(posted[0].body.vehicle).toBe(12)
  })

  it('states the 12-hour cut-off (UC 4 2a)', async () => {
    customerOn(confirmedBooking(), [
      http.post(`${API}/bookings/:id/modify/quote/`, () =>
        HttpResponse.json(
          {
            detail: 'A booking can be changed until 12 hours before the pickup time (12 Jan 2027 10:00). You can still cancel it.',
            code: 'modification_cutoff',
          },
          { status: 409 },
        ),
      ),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Modify booking' }))
    await user.click(await screen.findByRole('button', { name: 'Check the new price' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('until 12 hours before the pickup time')
  })

  it('asks for the price to be checked before confirming', async () => {
    const posted = customerOn(confirmedBooking())
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Modify booking' }))
    await confirmWithPassword(user, 'Confirm the change')
    expect(await screen.findByRole('alert')).toHaveTextContent('Check the new price first.')
    expect(posted).toEqual([])
  })
})

describe('extend (Book.Extend)', () => {
  it('quotes the extra charge and collects it before extending', async () => {
    const extension: ExtensionQuote = {
      price: { ...QUOTE, total_payable: '6372.00' },
      return_datetime: '2027-01-13T04:30:00Z',
      previous_total: '4248.00',
      extra_charge: '2124.00',
    }
    const posted = customerOn({ ...confirmedBooking(), status: 'Active' }, [
      http.post(`${API}/bookings/:id/extend/quote/`, () => HttpResponse.json(extension)),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Extend rental' }))
    const field = await screen.findByLabelText('New return time')
    await user.clear(field)
    await user.type(field, '2027-01-13T10:00')
    await user.click(screen.getByRole('button', { name: 'Check the extra charge' }))
    expect(await screen.findByText('To pay now')).toBeInTheDocument()
    await confirmWithPassword(user, 'Pay and extend')
    await screen.findByRole('button', { name: 'Extend rental' })
    expect(posted[0]).toMatchObject({
      path: 'extend',
      body: { return_datetime: '2027-01-13T04:30:00Z', expected_charge: '2124.00', payment_token: 'tok_visa' },
    })
  })

  it('shows why an extension is refused', async () => {
    customerOn({ ...confirmedBooking(), status: 'Active' }, [
      http.post(`${API}/bookings/:id/extend/quote/`, () =>
        HttpResponse.json(
          { detail: 'Another booking of this vehicle starts before the new return time.', code: 'vehicle_unavailable' },
          { status: 409 },
        ),
      ),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Extend rental' }))
    await user.click(await screen.findByRole('button', { name: 'Check the extra charge' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Another booking of this vehicle starts')
  })
})

describe('rebook (UC 5 extension 5a)', () => {
  it('opens the vehicle again with a period of the same length', async () => {
    let quoted: Body | null = null
    customerOn({ ...confirmedBooking(), status: 'Completed' }, [
      http.get(`${API}/fleet/vehicles/:id/`, () => HttpResponse.json(CAR)),
      http.post(`${API}/pricing/quote/`, async ({ request }) => {
        quoted = (await request.json()) as Body
        return HttpResponse.json(QUOTE)
      }),
    ])
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Book this vehicle again' }))
    expect(await screen.findByRole('heading', { name: 'Maruti Suzuki Swift (2023)' })).toBeInTheDocument()
    await vi.waitFor(() => expect(quoted).not.toBeNull())
    const { pickup_datetime, return_datetime } = quoted as unknown as Record<string, string>
    expect(new Date(return_datetime).getTime() - new Date(pickup_datetime).getTime()).toBe(2 * 86_400_000)
    expect(new Date(pickup_datetime).getTime()).toBeGreaterThan(Date.now())
  })
})

describe('history filters (History.View)', () => {
  it('filters by vehicle type, pickup dates and reference', async () => {
    const requests: URLSearchParams[] = []
    signedInAs('CUSTOMER')
    const row: Booking = (({ price: _p, transaction_id: _t, refunds: _r, ...rest }) => rest)(confirmedBooking())
    server.use(
      http.get(`${API}/bookings/`, ({ request }) => {
        const params = new URL(request.url).searchParams
        requests.push(params)
        const narrowed = params.get('reference') === 'nothing'
        return HttpResponse.json({ count: narrowed ? 0 : 1, next: null, previous: null, results: narrowed ? [] : [row] })
      }),
    )
    renderAppAt('/app/bookings')
    const user = userEvent.setup()
    await screen.findByRole('list', { name: 'Bookings' })
    await user.selectOptions(screen.getByLabelText('Vehicle type'), 'Two-Wheeler')
    await user.type(screen.getByLabelText('Pickup from'), '2026-11-01')
    await user.type(screen.getByLabelText('Pickup to'), '2026-11-30')
    await user.type(screen.getByLabelText('Reference'), 'nothing')
    expect(await screen.findByText('No bookings match these filters')).toBeInTheDocument()
    const last = requests.at(-1)
    expect(Object.fromEntries(last ?? [])).toEqual({
      vehicle_type: 'Two-Wheeler',
      pickup_from: '2026-11-01',
      pickup_to: '2026-11-30',
      reference: 'nothing',
    })
  })
})
