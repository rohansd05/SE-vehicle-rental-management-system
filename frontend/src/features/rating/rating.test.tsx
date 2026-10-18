// Module R4: Exp 2 UC 6 Rate Vehicle on the booking detail page. Step 1 invites
// a rating while it can be given; steps 2-3 score vehicle and service 1 to 5
// with an optional comment; extension 2a edits the review within 24 hours.
// The server's refusals are shown as it words them.

import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { BookingDetail } from '@/features/booking/api'
import { confirmedBooking } from '@/features/booking/fixtures'
import { renderAppAt } from '@/features/booking/test-render'
import { API, server, signedInAs } from '@/test/server'

const hours = (n: number) => new Date(Date.now() + n * 3_600_000).toISOString()

const completed = (extra: Partial<BookingDetail> = {}): BookingDetail => ({
  ...confirmedBooking(),
  status: 'Completed',
  rating: null,
  rating_open_until: hours(24 * 10),
  ...extra,
})

const REVIEW = {
  vehicle_rating: 4,
  service_rating: 5,
  comment: 'Clean car.',
  created_at: hours(-1),
  editable_until: hours(23),
}

function customerOn(booking: BookingDetail, respond?: (body: Record<string, unknown>, method: string) => Response) {
  const sent: { method: string; body: Record<string, unknown> }[] = []
  signedInAs('CUSTOMER')
  server.use(
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json(booking)),
    http.all(`${API}/bookings/:id/rating/`, async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>
      sent.push({ method: request.method, body })
      return respond ? respond(body, request.method) : HttpResponse.json(booking)
    }),
  )
  renderAppAt(`/app/bookings/${booking.id}`)
  return sent
}

describe('Rate Vehicle (UC 6)', () => {
  it('invites a rating and sends both scores and the comment', async () => {
    const user = userEvent.setup()
    const rated = completed({ rating: REVIEW, rating_open_until: null })
    const sent = customerOn(completed(), () => HttpResponse.json(rated, { status: 201 }))
    expect(await screen.findByRole('heading', { name: 'Rate this rental' })).toBeInTheDocument()
    const vehicle = screen.getByRole('group', { name: 'The vehicle' })
    await user.click(vehicle.querySelector('input[value="4"]')!)
    const service = screen.getByRole('group', { name: 'Our service' })
    await user.click(service.querySelector('input[value="5"]')!)
    await user.type(screen.getByLabelText('Comment (optional)'), 'Clean car.')
    await user.click(screen.getByRole('button', { name: 'Submit rating' }))
    expect(await screen.findByText('Thank you. Your review is saved.')).toBeInTheDocument()
    expect(sent[0]).toEqual({
      method: 'POST',
      body: { vehicle_rating: 4, service_rating: 5, comment: 'Clean car.' },
    })
    expect(screen.getByRole('heading', { name: 'Your review' })).toBeInTheDocument()
  })

  it('asks for both scores before sending', async () => {
    const user = userEvent.setup()
    const sent = customerOn(completed())
    await user.click(await screen.findByRole('button', { name: 'Submit rating' }))
    expect(screen.getByText('Rate the vehicle from 1 to 5.')).toBeInTheDocument()
    expect(screen.getByText('Rate the service from 1 to 5.')).toBeInTheDocument()
    expect(sent).toHaveLength(0)
  })

  it('shows the server’s refusal in its words', async () => {
    const user = userEvent.setup()
    const detail = 'A rental can be rated only within 14 days of its return.'
    customerOn(completed(), () => HttpResponse.json({ detail, code: 'rating_refused' }, { status: 409 }))
    const vehicle = (await screen.findByRole('group', { name: 'The vehicle' })).querySelector('input[value="3"]')!
    await user.click(vehicle)
    await user.click(screen.getByRole('group', { name: 'Our service' }).querySelector('input[value="3"]')!)
    await user.click(screen.getByRole('button', { name: 'Submit rating' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
  })

  it('edits the review within 24 hours with PATCH', async () => {
    const user = userEvent.setup()
    const booking = completed({ rating: REVIEW, rating_open_until: null })
    const sent = customerOn(booking, () =>
      HttpResponse.json({ ...booking, rating: { ...REVIEW, vehicle_rating: 2 } }),
    )
    expect(await screen.findByRole('heading', { name: 'Your review' })).toBeInTheDocument()
    expect(screen.getByText('4 out of 5')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Edit review' }))
    await user.click(screen.getByRole('group', { name: 'The vehicle' }).querySelector('input[value="2"]')!)
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('2 out of 5')).toBeInTheDocument()
    expect(sent[0].method).toBe('PATCH')
    expect(sent[0].body).toMatchObject({ vehicle_rating: 2, service_rating: 5 })
  })

  it('no longer offers an edit after 24 hours', async () => {
    customerOn(completed({ rating: { ...REVIEW, editable_until: hours(-1) }, rating_open_until: null }))
    expect(await screen.findByRole('heading', { name: 'Your review' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit review' })).not.toBeInTheDocument()
  })

  it.each(['Confirmed', 'Cancelled', 'No-show'] as const)('says nothing about rating a %s booking', async (status) => {
    customerOn(completed({ status, rating_open_until: null }))
    expect(await screen.findByRole('heading', { name: /Booking VRMS/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Rate this rental' })).not.toBeInTheDocument()
  })
})
