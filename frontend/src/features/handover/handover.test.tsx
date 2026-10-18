// Exp 2 use case 7 (Handover Vehicle) through the screens, against the API
// mocked by MSW: find the booking, see why a handover is refused, record the
// checklist, the customer signs, and the booking becomes Active.

import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import type { HandoverDetail } from './api'
import { makeCollection, makeHandover, page, REPORT } from './fixtures'

const LIST = `${API}/rentals/branch-bookings/`
const RETURNS = `${API}/rentals/returns/`
const DETAIL = `${API}/rentals/handovers/41/`

const jpg = (name: string) => new File(['jpeg'], name, { type: 'image/jpeg' })

beforeEach(() => {
  // jsdom has no canvas: the pad draws nothing, and the PNG is a stand-in.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (callback) {
    callback(new Blob(['png'], { type: 'image/png' }))
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

function serveCollections(respond: (url: URL) => object) {
  const seen: URLSearchParams[] = []
  server.use(
    http.get(LIST, ({ request }) => {
      const url = new URL(request.url)
      seen.push(url.searchParams)
      return HttpResponse.json(respond(url))
    }),
    http.get(RETURNS, () => HttpResponse.json(page([]))), // the desk lists returns too (N2)
  )
  return seen
}

function serveHandover(initial: HandoverDetail) {
  const state = { handover: initial }
  server.use(
    http.get(DETAIL, () => HttpResponse.json(state.handover)),
    // Module R4: the delivery address comes from the booking; none here.
    http.get(`${API}/bookings/:id/`, () => HttpResponse.json({ delivery_address: '', delivery_pincode: '' })),
  )
  return state
}

/** Draw a stroke on the signature pad. */
function sign() {
  const pad = screen.getByRole('img', { name: 'Customer signature' })
  fireEvent.pointerDown(pad, { clientX: 10, clientY: 10, pointerId: 1 })
  fireEvent.pointerMove(pad, { clientX: 60, clientY: 30, pointerId: 1 })
  fireEvent.pointerUp(pad, { pointerId: 1 })
}

describe('branch bookings (UC 7 step 1)', () => {
  it('shows today’s and upcoming collections at the branch, each opening its handover', async () => {
    signedInAs('BRANCH_MANAGER')
    const seen = serveCollections((url) =>
      url.searchParams.get('when') === 'upcoming'
        ? page([makeCollection({ id: 42, booking_reference: 'VRMS-20261018-0002' })])
        : page([makeCollection()]),
    )
    renderApp({ route: '/app/branch-bookings' })

    expect(await screen.findByRole('heading', { level: 1, name: 'Branch bookings' })).toBeInTheDocument()
    const today = await screen.findByRole('region', { name: 'Today’s collections' })
    const row = await within(today).findByRole('link', { name: /Tata Altroz · MH02DH3001/ })
    expect(row).toHaveAttribute('href', '/app/handover/41')
    expect(within(row).getByText('Asha Rao')).toBeInTheDocument()
    const upcoming = screen.getByRole('region', { name: 'Upcoming collections' })
    expect(await within(upcoming).findByText('VRMS-20261018-0002')).toBeInTheDocument()
    expect(seen.map((params) => params.get('when')).sort()).toEqual(['today', 'upcoming'])
  })

  it('is in the menu, no longer marked Soon', async () => {
    signedInAs('BRANCH_STAFF')
    serveCollections(() => page([]))
    renderApp({ route: '/app/branch-bookings' })
    expect(await screen.findAllByText('No collections today')).not.toHaveLength(0)
    for (const label of [/Branch bookings/, /Handover and return/]) {
      expect(screen.getAllByRole('link', { name: label })[0]).not.toHaveTextContent('Soon')
    }
  })

  it('shows an error state with a retry', async () => {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(LIST, () => HttpResponse.json({ detail: 'Server unavailable.' }, { status: 500 })),
      http.get(RETURNS, () => HttpResponse.json(page([]))),
    )
    renderApp({ route: '/app/handover' })
    expect(await screen.findByRole('alert')).toHaveTextContent('Server unavailable.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})

describe('handover desk: find a booking', () => {
  it('finds a booking by its pickup code, and clears the search', async () => {
    signedInAs('BRANCH_STAFF')
    const seen = serveCollections((url) => (url.searchParams.get('q') === '246810' ? page([makeCollection()]) : page([])))
    const user = userEvent.setup()
    renderApp({ route: '/app/handover' })

    expect(await screen.findByText('No collections today')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Booking reference, pickup code or mobile number'), '246810')
    await user.click(screen.getByRole('button', { name: 'Find booking' }))
    const results = await screen.findByRole('region', { name: 'Search results' })
    expect(await within(results).findByRole('link', { name: /VRMS-20261016-0007/ })).toBeInTheDocument()
    expect(seen.at(-1)?.get('q')).toBe('246810')

    await user.click(screen.getByRole('button', { name: 'Clear search' }))
    expect(screen.queryByRole('region', { name: 'Search results' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Booking reference, pickup code or mobile number')).toHaveValue('')
  })

  it('says when no booking matches', async () => {
    signedInAs('BRANCH_STAFF')
    serveCollections(() => page([]))
    const user = userEvent.setup()
    renderApp({ route: '/app/handover' })
    await user.type(await screen.findByLabelText('Booking reference, pickup code or mobile number'), 'VRMS-0')
    await user.click(screen.getByRole('button', { name: 'Find booking' }))
    expect(await screen.findByText('No booking found')).toBeInTheDocument()
  })
})

describe('Handover.Refuse', () => {
  it('states every condition that was not met and offers no checklist', async () => {
    signedInAs('BRANCH_STAFF')
    serveHandover(
      makeHandover({
        can_hand_over: false,
        refusals: [
          { code: 'licence_expired', message: 'The customer’s driving licence has expired.' },
          { code: 'document_insurance', message: 'The vehicle’s insurance expires on 20 Oct 2026, before the return date (SA-3).' },
        ],
      }),
    )
    renderApp({ route: '/app/handover/41' })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('This vehicle cannot be handed over')
    expect(within(alert).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'The customer’s driving licence has expired.',
      'The vehicle’s insurance expires on 20 Oct 2026, before the return date (SA-3).',
    ])
    expect(screen.queryByRole('button', { name: 'Complete handover' })).not.toBeInTheDocument()
  })
})

describe('Handover.Checklist, Handover.Sign and Handover.Activate', () => {
  it('records the checklist, the customer signs, and the booking becomes Active', { timeout: 20_000 }, async () => {
    signedInAs('BRANCH_STAFF')
    const state = serveHandover(makeHandover())
    let received: FormData | undefined
    server.use(
      http.post(`${DETAIL}complete/`, async ({ request }) => {
        received = await request.formData()
        state.handover = makeHandover({
          status: 'Active',
          handed_over_at: '2026-10-16T04:35:00Z',
          vehicle: { ...makeHandover().vehicle, status: 'On Rent' },
          can_hand_over: false,
          refusals: [{ code: 'already_handed_over', message: 'This booking has already been handed over.' }],
          report: REPORT,
        })
        return HttpResponse.json(state.handover, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/handover/41' })

    expect(await screen.findByRole('heading', { name: 'Handover checklist' })).toBeInTheDocument()
    expect(screen.getByText('MH02 20150012345')).toBeInTheDocument() // the re-verified licence
    expect(screen.getByLabelText('Odometer (km)')).toHaveValue('8200') // the vehicle's last reading

    const odometer = screen.getByLabelText('Odometer (km)')
    await user.clear(odometer)
    await user.type(odometer, '8210')
    await user.type(screen.getByLabelText('Fuel or charge level (%)'), '75')
    await user.click(screen.getByLabelText(/Child seat ×/))
    for (const side of ['Front', 'Rear', 'Left', 'Right']) {
      await user.upload(screen.getByLabelText(side), jpg(`${side}.jpg`))
    }
    await user.click(screen.getByRole('button', { name: 'Mark damage: Rear' }))
    const note = screen.getByLabelText('Mark 1')
    await user.clear(note)
    await user.type(note, 'Rear: scratch on the bumper')
    expect(screen.getByText(/A no-show keeps 50%/)).toBeInTheDocument() // the rental agreement
    sign()
    expect(screen.getByText('Signed.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Complete handover' }))

    expect(await screen.findByText(/Handover complete\. The booking is Active/)).toBeInTheDocument()
    expect(received?.get('odometer_reading')).toBe('8210')
    expect(received?.get('fuel_level')).toBe('75')
    expect(JSON.parse(String(received?.get('accessories')))).toEqual([{ name: 'Child seat', quantity: 1 }])
    expect(JSON.parse(String(received?.get('damage_marks')))).toEqual([{ x: 50, y: 85, note: 'Rear: scratch on the bumper' }])
    // jsdom's FormData drops file names on the way to MSW; a browser keeps them.
    for (const field of ['photo_front', 'photo_rear', 'photo_left', 'photo_right']) {
      expect(received?.get(field)).toMatchObject({ type: 'image/jpeg' })
    }
    expect(received?.get('signature')).toMatchObject({ type: 'image/png' })

    // The signed report replaces the form; nothing can be changed.
    expect(await screen.findByRole('heading', { name: 'Signed condition report' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete handover' })).not.toBeInTheDocument()
    expect(screen.getAllByText('Active')[0]).toBeInTheDocument()
    expect(screen.getAllByText('On Rent')[0]).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Customer signature' })).toHaveAttribute('src', '/api/v1/files/signature/')
    expect(within(screen.getByRole('list', { name: 'Condition photos' })).getAllByRole('img')).toHaveLength(4)
  })

  it('asks for every side and the signature before sending anything', async () => {
    signedInAs('BRANCH_STAFF')
    serveHandover(makeHandover())
    const post = vi.fn()
    server.use(http.post(`${DETAIL}complete/`, () => post()))
    const user = userEvent.setup()
    renderApp({ route: '/app/handover/41' })

    await user.click(await screen.findByRole('button', { name: 'Complete handover' }))
    expect(await screen.findByText('Complete the checklist and the signature before you finish the handover.')).toBeInTheDocument()
    expect(screen.getByText('Enter the fuel or charge level, from 0 to 100%.')).toBeInTheDocument()
    expect(screen.getByText('Add a photo of the left of the vehicle.')).toBeInTheDocument()
    expect(screen.getByText('The customer must sign the condition report.')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('refuses a photo that is not a JPG or PNG', async () => {
    signedInAs('BRANCH_STAFF')
    serveHandover(makeHandover())
    const user = userEvent.setup({ applyAccept: false })
    renderApp({ route: '/app/handover/41' })
    await user.upload(await screen.findByLabelText('Front'), new File(['GIF89a'], 'front.gif', { type: 'image/gif' }))
    expect(await screen.findByText('Choose a JPG or PNG image.')).toBeInTheDocument()
  })

  it('shows the server’s refusal when a condition fails while the form is open', { timeout: 20_000 }, async () => {
    signedInAs('BRANCH_STAFF')
    serveHandover(makeHandover())
    server.use(
      http.post(`${DETAIL}complete/`, () =>
        HttpResponse.json(
          {
            detail: 'The vehicle is flagged Unsafe.',
            code: 'handover_refused',
            refusals: [{ code: 'vehicle_unsafe', message: 'The vehicle is flagged Unsafe. Only an Administrator can clear the flag (SA-2).' }],
          },
          { status: 409 },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/handover/41' })
    await user.type(await screen.findByLabelText('Fuel or charge level (%)'), '60')
    for (const side of ['Front', 'Rear', 'Left', 'Right']) {
      await user.upload(screen.getByLabelText(side), jpg(`${side}.jpg`))
    }
    sign()
    await user.click(screen.getByRole('button', { name: 'Complete handover' }))
    expect(await screen.findByText('This vehicle cannot be handed over')).toBeInTheDocument()
    expect(screen.getByText(/flagged Unsafe\. Only an Administrator/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete handover' })).not.toBeInTheDocument()
  })

  it('a Branch Manager sees the booking read only', async () => {
    signedInAs('BRANCH_MANAGER')
    serveHandover(makeHandover())
    renderApp({ route: '/app/handover/41' })
    expect(await screen.findByRole('heading', { name: 'Driving licence' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Handover checklist' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to branch bookings' })).toHaveAttribute('href', '/app/branch-bookings')
  })
})
