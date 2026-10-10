import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Booking } from '@/features/booking/api'
import { confirmedBooking, heldBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, server, signedInAs } from '@/test/server'

const asListRow = ({ price: _price, transaction_id: _txn, ...row }: ReturnType<typeof heldBooking>): Booking => row

const page = (results: Booking[], extra = {}) => ({ count: results.length, next: null, previous: null, results, ...extra })

function customerWithBookings(respond: (url: URL) => Response) {
  const requests: URLSearchParams[] = []
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/bookings/`, ({ request }) => {
      const url = new URL(request.url)
      requests.push(url.searchParams)
      return respond(url)
    }),
  )
  renderAppAt('/app/bookings')
  return requests
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('booking history (History.View)', () => {
  it('lists the customer’s bookings with their status and amount', async () => {
    customerWithBookings(() => HttpResponse.json(page([asListRow(confirmedBooking()), { ...asListRow(heldBooking()), id: 71 }])))
    const list = await screen.findByRole('list', { name: 'Bookings' })
    const [confirmed, held] = within(list).getAllByRole('listitem')
    expect(within(confirmed).getByRole('link', { name: 'Maruti Suzuki Swift · VRMS-20261011-0001' })).toHaveAttribute(
      'href',
      '/app/bookings/70',
    )
    expect(within(confirmed).getByText('Confirmed')).toBeInTheDocument()
    expect(within(confirmed).getByText('₹4,248.00')).toBeInTheDocument()
    expect(within(held).getByText('Pending Payment')).toBeInTheDocument()
  })

  it('filters by status', async () => {
    const requests = customerWithBookings((url) =>
      HttpResponse.json(page(url.searchParams.get('status') ? [] : [asListRow(confirmedBooking())])),
    )
    const user = userEvent.setup()
    await screen.findByRole('list', { name: 'Bookings' })
    await user.selectOptions(screen.getByLabelText('Status'), 'Cancelled')
    expect(await screen.findByText('No Cancelled bookings')).toBeInTheDocument()
    expect(requests.at(-1)?.get('status')).toBe('Cancelled')
  })

  it('has an empty state and an error state', async () => {
    customerWithBookings(() => HttpResponse.json(page([])))
    expect(await screen.findByText('No bookings yet')).toBeInTheDocument()
  })

  it('explains when the list cannot load', async () => {
    customerWithBookings(() => HttpResponse.json({ detail: 'Down.' }, { status: 503 }))
    expect(await screen.findByText('We couldn’t load your bookings')).toBeInTheDocument()
  })

  it('pages through a long history', async () => {
    const requests = customerWithBookings((url) =>
      url.searchParams.get('page') === '2'
        ? HttpResponse.json(page([{ ...asListRow(heldBooking()), id: 99 }], { count: 21, previous: 'p1' }))
        : HttpResponse.json(page([asListRow(confirmedBooking())], { count: 21, next: 'p2' })),
    )
    const user = userEvent.setup()
    await screen.findByRole('list', { name: 'Bookings' })
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(await screen.findByRole('link', { name: 'Maruti Suzuki Swift' })).toHaveAttribute('href', '/app/bookings/99')
    expect(requests.at(-1)?.get('page')).toBe('2')
  })
})

describe('booking detail and invoice (History.Download)', () => {
  function customerOnBooking(booking = confirmedBooking()) {
    signedInAs('CUSTOMER')
    server.use(http.get(`${API}/bookings/:id/`, () => HttpResponse.json(booking)))
    renderAppAt(`/app/bookings/${booking.id}`)
  }

  it('shows the reference, pickup code, transaction, invoice and price', async () => {
    customerOnBooking()
    expect(await screen.findByRole('heading', { name: 'Booking VRMS-20261011-0001' })).toBeInTheDocument()
    expect(screen.getByText('042917')).toBeInTheDocument()
    expect(screen.getByText('INV-2026-000001')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Price' })).toBeInTheDocument()
    expect(screen.queryByText(/Your booking is confirmed/)).not.toBeInTheDocument() // only right after paying
  })

  it('downloads the invoice PDF with the access token', async () => {
    let authorization: string | null = null
    customerOnBooking()
    server.use(
      http.get(`${API}/bookings/:id/invoice/`, ({ request }) => {
        authorization = request.headers.get('Authorization')
        return new HttpResponse('%PDF-1.4', { headers: { 'Content-Type': 'application/pdf' } })
      }),
    )
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:invoice')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined)
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Download invoice INV-2026-000001' }))
    await vi.waitFor(() => expect(click).toHaveBeenCalledTimes(1))
    expect(authorization).toMatch(/^Bearer /)
    const link = click.mock.contexts[0] as HTMLAnchorElement
    expect(link.download).toBe('INV-2026-000001.pdf')
    expect(createUrl).toHaveBeenCalledTimes(1)
  })

  it('says so when the invoice cannot be downloaded', async () => {
    customerOnBooking()
    server.use(http.get(`${API}/bookings/:id/invoice/`, () => HttpResponse.json({ detail: 'x' }, { status: 500 })))
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Download invoice INV-2026-000001' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('We couldn’t download the invoice. Please try again.')
  })

  it('a held booking offers to continue to payment, and has no invoice yet', async () => {
    customerOnBooking(heldBooking())
    expect(await screen.findByRole('link', { name: 'Continue to payment' })).toHaveAttribute('href', '/app/bookings/70/pay')
    expect(screen.queryByRole('button', { name: /Download invoice/ })).not.toBeInTheDocument()
  })
})
