// Exp 2 use case 8 (Return Vehicle) through the screens, against the API
// mocked by MSW: find the rental, record the checklist beside the handover
// photos, compute the settlement, the customer signs, and it is settled.

import { fireEvent, screen, within } from '@testing-library/react'
import userEvent, { type UserEvent } from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from '@/test/render'
import { API, server, signedInAs } from '@/test/server'

import type { ReturnDetail, ReturnQuote } from './api'
import { makeCollection, makeHandover, makeReturn, makeSettlement, page, QUOTE, REPORT, RETURN_REPORT, ZERO_QUOTE } from './fixtures'

const DETAIL = `${API}/rentals/returns/41/`
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

function serveReturn(initial: ReturnDetail) {
  const state = { detail: initial }
  server.use(http.get(DETAIL, () => HttpResponse.json(state.detail)))
  return state
}

function serveQuote(quote: ReturnQuote) {
  const bodies: Record<string, unknown>[] = []
  server.use(
    http.post(`${DETAIL}quote/`, async ({ request }) => {
      bodies.push((await request.json()) as Record<string, unknown>)
      return HttpResponse.json(quote)
    }),
  )
  return bodies
}

function sign() {
  const pad = screen.getByRole('img', { name: 'Customer signature' })
  fireEvent.pointerDown(pad, { clientX: 10, clientY: 10, pointerId: 1 })
  fireEvent.pointerMove(pad, { clientX: 60, clientY: 30, pointerId: 1 })
  fireEvent.pointerUp(pad, { pointerId: 1 })
}

async function fillReadings(user: UserEvent, { odometer = '8330', fuel = '100' } = {}) {
  const field = await screen.findByLabelText('Odometer (km)')
  await user.clear(field)
  await user.type(field, odometer)
  await user.type(screen.getByLabelText('Fuel or charge level (%)'), fuel)
}

async function addPhotos(user: UserEvent) {
  for (const side of ['Front', 'Rear', 'Left', 'Right']) {
    await user.upload(screen.getByLabelText(side), jpg(`${side}.jpg`))
  }
}

describe('the return desk (UC 8 step 1)', () => {
  it('lists the rentals due back today, each opening its return', async () => {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(`${API}/rentals/branch-bookings/`, () => HttpResponse.json(page([]))),
      http.get(`${API}/rentals/returns/`, () => HttpResponse.json(page([makeCollection({ status: 'Active' })]))),
    )
    renderApp({ route: '/app/handover' })
    const returns = await screen.findByRole('region', { name: 'Returns due today' })
    const row = await within(returns).findByRole('link', { name: /Tata Altroz · MH02DH3001/ })
    expect(row).toHaveAttribute('href', '/app/returns/41')
    expect(within(row).getByText(/Return due/)).toBeInTheDocument()
  })

  it('a search also finds a rental in progress', async () => {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(`${API}/rentals/branch-bookings/`, () => HttpResponse.json(page([]))),
      http.get(`${API}/rentals/returns/`, ({ request }) =>
        HttpResponse.json(new URL(request.url).searchParams.get('q') ? page([makeCollection({ status: 'Active' })]) : page([])),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/handover' })
    await user.type(await screen.findByLabelText('Booking reference, pickup code or mobile number'), 'VRMS-20261016-0007')
    await user.click(screen.getByRole('button', { name: 'Find booking' }))
    const found = await screen.findByRole('region', { name: 'Rentals in progress' })
    expect(within(found).getByRole('link', { name: /VRMS-20261016-0007/ })).toHaveAttribute('href', '/app/returns/41')
  })

  it('an Active handover links to its return', async () => {
    signedInAs('BRANCH_STAFF')
    server.use(
      http.get(`${API}/rentals/handovers/41/`, () =>
        HttpResponse.json(makeHandover({ status: 'Active', can_hand_over: false, report: REPORT })),
      ),
    )
    renderApp({ route: '/app/handover/41' })
    expect(await screen.findByRole('link', { name: 'Record the return' })).toHaveAttribute('href', '/app/returns/41')
  })
})

describe('only an Active booking can be returned', () => {
  it('states why and offers no checklist', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(
      makeReturn({
        status: 'Cancelled',
        can_return: false,
        refusals: [{ code: 'booking_cancelled', message: 'This booking was cancelled, so there is nothing to return.' }],
      }),
    )
    renderApp({ route: '/app/returns/41' })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('This vehicle cannot be returned')
    expect(alert).toHaveTextContent('This booking was cancelled')
    expect(screen.queryByRole('heading', { name: 'Return checklist' })).not.toBeInTheDocument()
  })

  it('a Branch Manager sees the rental read only', async () => {
    signedInAs('BRANCH_MANAGER')
    serveReturn(makeReturn())
    renderApp({ route: '/app/returns/41' })
    expect(await screen.findByRole('heading', { name: 'Rental terms' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Return checklist' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to branch bookings' })).toBeInTheDocument()
  })
})

describe('Return.Checklist, Return.Charges, Return.Settle', () => {
  it('records the return beside the handover photos, itemises it, and settles once signed', { timeout: 30_000 }, async () => {
    signedInAs('BRANCH_STAFF')
    const state = serveReturn(makeReturn())
    const quotes = serveQuote(QUOTE)
    let received: FormData | undefined
    server.use(
      http.post(`${DETAIL}complete/`, async ({ request }) => {
        received = await request.formData()
        state.detail = makeReturn({
          status: 'Completed',
          vehicle: { ...makeReturn().vehicle, status: 'Available', odometer: 8610 },
          can_return: false,
          refusals: [{ code: 'already_returned', message: 'This vehicle has already been returned and the booking settled.' }],
          returned_at: '2026-10-17T05:00:00Z',
          distance_travelled: 400,
          return_report: RETURN_REPORT,
          settlement: makeSettlement({ ...QUOTE, refund_status: '' }),
        })
        return HttpResponse.json(state.detail, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })

    expect(await screen.findByRole('heading', { name: 'Return checklist' })).toBeInTheDocument()
    expect(screen.getByLabelText('Odometer (km)')).toHaveValue('8210') // the handover reading
    // Return.Checklist: the handover photo of each side beside the one to take now.
    expect(screen.getByRole('img', { name: 'Rear of the vehicle at handover' })).toHaveAttribute('src', '/api/v1/files/Rear/')

    await fillReadings(user, { odometer: '8610', fuel: '75' })
    await user.click(screen.getByLabelText(/Child seat ×/)) // not returned
    await user.type(screen.getByLabelText('Cost of the missing child seat'), '1200')
    await user.click(screen.getByRole('button', { name: 'Add a damage charge' }))
    await user.type(screen.getByLabelText('Damage 1'), 'Dent on the rear door')
    await user.type(screen.getByLabelText('Amount'), '800')
    await user.type(screen.getByLabelText('Justification'), 'Not on the handover report')
    await addPhotos(user)

    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    const table = await screen.findByRole('table', { name: 'Settlement' })
    expect(quotes[0]).toMatchObject({
      odometer_reading: '8610',
      fuel_level: '75',
      missing_accessories: [{ name: 'Child seat', quantity: 1, cost: '1200' }],
      damage_charges: [{ description: 'Dent on the rear door', amount: '800', justification: 'Not on the handover report' }],
    })
    expect(String(quotes[0]?.returned_at)).toMatch(/Z$/) // sent in UTC (CO-6)
    // Each charge on its own line; the extension shown as already paid, not charged again.
    expect(within(table).getByText(/Late return, 3 h/)).toBeInTheDocument()
    expect(within(table).getByText(/Excess kilometres/)).toBeInTheDocument()
    expect(within(table).getByText(/Fuel or charge shortfall/)).toBeInTheDocument()
    expect(within(table).getByText('Not on the handover report')).toBeInTheDocument()
    expect(within(table).getByText(/Rental extended to .* \(Book\.Extend\)/)).toBeInTheDocument()
    expect(within(table).getByText('Due from the customer')).toBeInTheDocument()

    sign()
    await user.click(screen.getByRole('button', { name: 'Settle and complete return' }))

    expect(await screen.findByText(/Return complete\. The booking is Completed and the vehicle is Available/)).toBeInTheDocument()
    expect(received?.get('expected_total')).toBe('6025.94')
    expect(received?.get('odometer_reading')).toBe('8610')
    expect(JSON.parse(String(received?.get('missing_accessories')))).toEqual([{ name: 'Child seat', quantity: 1, cost: '1200' }])
    for (const field of ['photo_front', 'photo_rear', 'photo_left', 'photo_right']) {
      expect(received?.get(field)).toMatchObject({ type: 'image/jpeg' })
    }
    expect(received?.get('signature')).toMatchObject({ type: 'image/png' })
    expect(received?.get('flag_problem')).toBeNull()
    expect(received?.get('override_email')).toBeNull()

    // The signed settlement replaces the form; the photos side by side.
    expect(await screen.findByRole('heading', { name: 'Signed settlement' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Return checklist' })).not.toBeInTheDocument()
    expect(screen.getByText(/recorded against the customer/)).toBeInTheDocument()
    const photos = screen.getByRole('list', { name: 'Handover and return photos' })
    expect(within(photos).getByRole('img', { name: 'Front of the vehicle at return' })).toHaveAttribute('src', '/api/v1/files/return-Front/')
  })

  it('asks for the readings before computing anything, and for the settlement before settling', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn())
    const quotes = serveQuote(QUOTE)
    const post = vi.fn()
    server.use(http.post(`${DETAIL}complete/`, () => post()))
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })

    await user.click(await screen.findByRole('button', { name: 'Calculate settlement' }))
    expect(await screen.findByText('Enter the fuel or charge level, from 0 to 100%.')).toBeInTheDocument()
    expect(quotes).toHaveLength(0)

    await user.click(screen.getByRole('button', { name: 'Settle and complete return' }))
    expect(await screen.findByText('Calculate the settlement and show it to the customer first.')).toBeInTheDocument()
    expect(screen.getByText('Add a photo of the left of the vehicle.')).toBeInTheDocument()
    expect(post).not.toHaveBeenCalled()
  })

  it('shows the server’s reason when the odometer is below the handover reading', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn())
    const message = 'The odometer reading cannot be lower than the 8210 km recorded at handover (Return.Odometer).'
    server.use(
      http.post(`${DETAIL}quote/`, () =>
        HttpResponse.json({ detail: message, code: 'odometer_lower', odometer_reading: [message] }, { status: 400 }),
      ),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })
    await fillReadings(user, { odometer: '8000' })
    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    expect(await screen.findAllByText(message)).toHaveLength(2) // the form alert and the field
    expect(screen.getByLabelText('Odometer (km)')).toHaveAttribute('aria-invalid', 'true')
  })

  it('a changed reading makes the customer see the settlement again', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn())
    serveQuote(ZERO_QUOTE)
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })
    await fillReadings(user)
    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    expect(await screen.findByRole('table', { name: 'Settlement' })).toBeInTheDocument()
    expect(screen.getByText('Deposit balance to refund')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Fuel or charge level (%)'), '0')
    expect(screen.queryByRole('table', { name: 'Settlement' })).not.toBeInTheDocument()
  })

  it('a cash deposit is refunded in cash by the staff member, who is named', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn({ deposit_method: 'Cash' }))
    serveQuote(ZERO_QUOTE)
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })
    await fillReadings(user)
    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    expect(await screen.findByText(/The deposit was paid in cash\. Pay the customer/)).toHaveTextContent(
      'you, Ravi Staff, are recorded as the staff member who paid it',
    )
  })

  it('an implausible distance needs a supervisor’s approval and a reason', { timeout: 30_000 }, async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn())
    serveQuote({ ...ZERO_QUOTE, distance: 1800, override_required: true })
    let received: FormData | undefined
    server.use(
      http.post(`${DETAIL}complete/`, async ({ request }) => {
        received = await request.formData()
        return HttpResponse.json(makeReturn({ status: 'Completed', settlement: makeSettlement(), return_report: RETURN_REPORT }), {
          status: 201,
        })
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })
    await fillReadings(user, { odometer: '10010' })
    await addPhotos(user)
    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    expect(await screen.findByText(/1800 km is more than the 1000 km plausible/)).toBeInTheDocument()
    sign()
    await user.click(screen.getByRole('button', { name: 'Settle and complete return' }))
    expect(
      await screen.findByText('A Branch Manager or an Administrator must approve the reading and give the reason.'),
    ).toBeInTheDocument()

    await user.type(screen.getByLabelText('Supervisor e-mail'), 'manager@vrms.test')
    await user.type(screen.getByLabelText('Supervisor password'), 'Demo@1234')
    await user.type(screen.getByLabelText('Reason'), 'Trip to Goa, agreed at booking')
    await user.click(screen.getByRole('button', { name: 'Settle and complete return' }))
    expect(await screen.findByRole('heading', { name: 'Signed settlement' })).toBeInTheDocument()
    expect(received?.get('override_email')).toBe('manager@vrms.test')
    expect(received?.get('override_reason')).toBe('Trip to Goa, agreed at booking')
  })

  it('flags the vehicle for maintenance with the problem and severity', { timeout: 30_000 }, async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(makeReturn())
    serveQuote(ZERO_QUOTE)
    let received: FormData | undefined
    server.use(
      http.post(`${DETAIL}complete/`, async ({ request }) => {
        received = await request.formData()
        return HttpResponse.json(
          makeReturn({
            status: 'Completed',
            vehicle: { ...makeReturn().vehicle, status: 'Under Maintenance' },
            settlement: makeSettlement({ maintenance_job: 7 }),
            return_report: RETURN_REPORT,
          }),
          { status: 201 },
        )
      }),
    )
    const user = userEvent.setup()
    renderApp({ route: '/app/returns/41' })
    await fillReadings(user)
    await addPhotos(user)
    await user.click(screen.getByLabelText('Flag the vehicle for maintenance'))
    await user.type(screen.getByLabelText('Problem'), 'Brakes squeal')
    await user.selectOptions(screen.getByLabelText('Severity'), 'High')
    await user.click(screen.getByRole('button', { name: 'Calculate settlement' }))
    await screen.findByRole('table', { name: 'Settlement' })
    sign()
    await user.click(screen.getByRole('button', { name: 'Settle and complete return' }))
    expect(await screen.findByText(/the vehicle is Under Maintenance/)).toBeInTheDocument()
    expect(received?.get('flag_problem')).toBe('Brakes squeal')
    expect(received?.get('flag_severity')).toBe('High')
    expect(received?.get('flag_unfit')).toBe('true')
    expect(screen.getByText(/raised for the problem found at return/)).toHaveTextContent('#7')
  })
})

describe('the completed return', () => {
  it('says the refund is awaiting approval, not refunded', async () => {
    signedInAs('BRANCH_STAFF')
    serveReturn(
      makeReturn({
        status: 'Completed',
        settlement: makeSettlement({ refund_status: 'Pending Approval' }),
        return_report: RETURN_REPORT,
      }),
    )
    renderApp({ route: '/app/returns/41' })
    expect(await screen.findByText('Refund awaiting approval')).toBeInTheDocument()
    expect(screen.queryByText('Refunded')).not.toBeInTheDocument()
  })

  it('names who paid a cash refund out', async () => {
    signedInAs('BRANCH_MANAGER')
    serveReturn(
      makeReturn({
        status: 'Completed',
        deposit_method: 'Cash',
        settlement: makeSettlement({ refund_paid_out_by: 'Ravi Staff' }),
        return_report: RETURN_REPORT,
      }),
    )
    renderApp({ route: '/app/returns/41' })
    expect(await screen.findByText('Refunded in cash by Ravi Staff')).toBeInTheDocument()
  })
})
